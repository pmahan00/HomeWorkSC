import argparse
import json
import numpy as np
import pandas as pd
import yfinance as yf
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings
from src.utils import setup_logger, ensure_directories

logger = setup_logger("FeatureEng")

def load_data(input_csv: Path, market_json: Path):
    logger.info("Loading portfolio and market data...")
    if not input_csv.exists():
        raise FileNotFoundError(f"CSV not found: {input_csv}")
    if not market_json.exists():
        raise FileNotFoundError(f"Market JSON not found: {market_json}")
        
    df = pd.read_csv(input_csv)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    
    with market_json.open("r", encoding="utf-8") as f:
        market = json.load(f)
        
    return df, market

def compute_weights_and_values(port_df: pd.DataFrame, market: Dict[str, Any]):
    def price_for(t):
        return market["items"].get(t, {}).get("market", {}).get("current_price")
    
    port_df["current_price"] = port_df["ticker"].map(price_for)
    port_df["market_value"] = port_df["current_price"] * port_df["quantity"]
    total_value = float(pd.to_numeric(port_df["market_value"], errors="coerce").sum())
    
    port_df["weight_pct"] = np.where(
        total_value > 0, (port_df["market_value"] / total_value) * 100.0, 0.0
    )
    return port_df, total_value

def closes_series_for_ticker(ticker: str, market: Dict[str, Any]) -> pd.Series:
    hist = market["items"].get(ticker, {}).get("history", {}).get("closes", [])
    if not hist: return pd.Series(dtype=float)
    return pd.Series({pd.to_datetime(h["date"]): h["close"] for h in hist}, dtype=float).sort_index()

def compute_daily_returns(closes: pd.Series) -> pd.Series:
    return closes.pct_change().dropna()

def infer_return_window(rets: pd.Series) -> int:
    if rets.empty or len(rets) < 2: return 0
    gaps = np.diff(pd.to_datetime(rets.index).values).astype("timedelta64[D]").astype(int)
    median_gap = int(np.median(gaps))
    if median_gap >= 25: return 6
    if median_gap >= 5: return 12
    return 30

def compute_volatility(closes: pd.Series) -> float | None:
    if closes.empty: return None
    rets = compute_daily_returns(closes)
    window = infer_return_window(rets)
    if window == 0 or len(rets) < window: return None
    return float(rets.iloc[-window:].std())

def compute_portfolio_returns(port_df: pd.DataFrame, market: Dict[str, Any]) -> pd.Series:
    returns_map, weights_map = {}, {}
    for _, row in port_df.iterrows():
        t, w = row["ticker"], float(row["weight_pct"])
        rets = compute_daily_returns(closes_series_for_ticker(t, market))
        if not rets.empty and w > 0:
            returns_map[t] = rets
            weights_map[t] = w / 100.0
            
    if not returns_map: return pd.Series(dtype=float)
    aligned = pd.concat(returns_map.values(), axis=1, join="inner")
    aligned.columns = list(returns_map.keys())
    weights_vec = pd.Series(weights_map).reindex(aligned.columns).fillna(0.0)
    return aligned.dot(weights_vec)

def fetch_benchmark_returns(symbol: str) -> pd.Series:
    logger.info(f"Fetching benchmark history for {symbol}...")
    tk = yf.Ticker(symbol)
    df = tk.history(period="730d", interval="1d", auto_adjust=False)
    if df is None or df.empty: return pd.Series(dtype=float)
    return df["Close"].dropna().pct_change().dropna()

def compute_correlation_matrix(port_df: pd.DataFrame, market: Dict[str, Any]) -> Dict:
    series_list, cols = [], []
    for _, row in port_df.iterrows():
        t = row["ticker"]
        rets = compute_daily_returns(closes_series_for_ticker(t, market))
        if len(rets) >= 6:
            series_list.append(rets)
            cols.append(t)
    if len(series_list) < 2: return {}
    aligned = pd.concat(series_list, axis=1, join="inner")
    aligned.columns = cols
    corr = aligned.corr().round(4)
    return {c: {r: float(corr.loc[c, r]) for r in corr.columns} for c in corr.columns}

def main():
    ensure_directories()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(settings.PORTFOLIO_CSV))
    parser.add_argument("--market", default=str(settings.MARKET_DATA_JSON))
    parser.add_argument("--output", default=str(settings.FEATURE_DATA_JSON))
    parser.add_argument("--benchmark", default=settings.BENCHMARK_SYMBOL)
    parser.add_argument("--compute-corr", action="store_true")
    args = parser.parse_args()

    port_df, market = load_data(Path(args.input), Path(args.market))
    port_df, total_value = compute_weights_and_values(port_df, market)

    logger.info("Computing volatilities...")
    vol_map = {t: compute_volatility(closes_series_for_ticker(t, market)) for t in port_df["ticker"]}

    # Sector Distribution
    grp = port_df.groupby("sector", dropna=False)["weight_pct"].sum().sort_values(ascending=False)
    sector_dist = {str(k): float(v) for k, v in grp.items()}

    # Top Exposures
    top3 = [
        {
            "ticker": row["ticker"], "name": row["name"], 
            "weight_pct": float(row["weight_pct"]),
            "market_value": float(row["market_value"]) if pd.notna(row["market_value"]) else None
        }
        for _, row in port_df.sort_values("weight_pct", ascending=False).head(3).iterrows()
    ]

    # Portfolio & Benchmark Risk
    port_rets = compute_portfolio_returns(port_df, market)
    w_port = infer_return_window(port_rets)
    port_vol = float(port_rets.iloc[-w_port:].std()) if len(port_rets) >= w_port and w_port > 0 else None

    bench_rets = fetch_benchmark_returns(args.benchmark)
    w_bench = infer_return_window(bench_rets)
    bench_vol = float(bench_rets.iloc[-w_bench:].std()) if len(bench_rets) >= w_bench and w_bench > 0 else None

    corr_matrix = compute_correlation_matrix(port_df, market) if args.compute_corr else {}

    # Build Output
    items = {}
    for _, row in port_df.iterrows():
        t = row["ticker"]
        mkt_entry = market.get("items", {}).get(t, {})
        items[t] = {
            "name": row["name"],
            "sector": row["sector"],
            "country": row["country"],
            "asset_type": row["asset_type"],
            "quantity": float(row["quantity"]) if pd.notna(row["quantity"]) else None,
            "current_price": float(row["current_price"]) if pd.notna(row["current_price"]) else None,
            "market_value": float(row["market_value"]) if pd.notna(row["market_value"]) else None,
            "weight_pct": float(row["weight_pct"]),
            "volatility_recent_window": vol_map.get(t),
            "beta": mkt_entry.get("market", {}).get("beta"),
            "resolved_symbol": mkt_entry.get("static", {}).get("resolved_symbol")
        }

    output_data = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "portfolio_summary": {"total_market_value": total_value, "top_exposures": top3},
        "sector_distribution": sector_dist,
        "risk_metrics": {
            "per_ticker_volatility": vol_map,
            "portfolio_volatility": port_vol,
            "benchmark": {"symbol": args.benchmark, "volatility": bench_vol},
            "correlation_matrix": corr_matrix,
        },
        "items": items
    }

    with Path(args.output).open("w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Feature engineering complete. Saved to {args.output}")

if __name__ == "__main__":
    main()