import csv
import json
import time
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import yfinance as yf

# Import from local config/utils
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent)) # Add sc/ to path
from config import settings
from src.utils import setup_logger, ensure_directories

logger = setup_logger("DataFetch")

# Known alias overrides
TICKER_ALIAS: Dict[str, str] = {
    "INRG.DE": "INRG.L",
    "IIND.DE": "IIND.L",
    "ISAC.DE": "ISAC.L",
    "SPXD.DE": "SPXD.L",
}

SUFFIX_CANDIDATES = [".L", ".DE", ".F", ".MI", ".PA", ".SW", ".AS"]
_RESOLVE_CACHE: Dict[str, str] = {}

def _sleep_backoff(attempt: int):
    time.sleep(min(2 ** attempt, 8))

def load_portfolio(csv_path: Path) -> List[Dict[str, Any]]:
    logger.info(f"Loading portfolio from {csv_path}")
    portfolio = []
    if not csv_path.exists():
        raise FileNotFoundError(f"Input CSV not found at {csv_path}")

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                quantity = float(row.get("quantity", ""))
            except ValueError:
                quantity = None

            portfolio.append({
                "ticker": row.get("ticker", "").strip(),
                "name": row.get("name", "").strip(),
                "sector": row.get("sector", "").strip(),
                "country": row.get("country", "").strip(),
                "asset_type": row.get("asset_type", "").strip(),
                "quantity": quantity,
                "purchase_price": None,
            })
    return portfolio

def _has_history(y_ticker: str, period: str = "30d") -> bool:
    try:
        df = yf.Ticker(y_ticker).history(period=period, interval="1d", auto_adjust=False)
        return (df is not None) and (not df.empty)
    except Exception:
        return False

def resolve_ticker(original: str, asset_type: Optional[str] = None) -> str:
    if original in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[original]

    alias = TICKER_ALIAS.get(original)
    if alias and _has_history(alias):
        logger.debug(f"Resolved alias: {original} -> {alias}")
        _RESOLVE_CACHE[original] = alias
        return alias

    if _has_history(original):
        _RESOLVE_CACHE[original] = original
        return original

    base, suffix = (original, "")
    if "." in original:
        parts = original.split(".", 1)
        base, suffix = parts[0], "." + parts[1]

    candidates = SUFFIX_CANDIDATES
    if asset_type and asset_type.upper() == "ETF":
        candidates = [".L"] + [s for s in SUFFIX_CANDIDATES if s != ".L"]

    for sfx in candidates:
        if sfx == suffix: continue
        probe = f"{base}{sfx}"
        if _has_history(probe):
            logger.info(f"Resolved market: {original} -> {probe}")
            _RESOLVE_CACHE[original] = probe
            return probe

    logger.warning(f"Could not resolve {original}. Keeping original.")
    _RESOLVE_CACHE[original] = original
    return original

def fetch_ticker_snapshot(ticker: str, resolved: Optional[str] = None) -> Dict[str, Any]:
    y_symbol = resolved or ticker
    tk = yf.Ticker(y_symbol)
    current_price = None
    currency = None
    beta = None

    try:
        fi = getattr(tk, "fast_info", None)
        if fi:
            current_price = fi.get("last_price") or fi.get("last_price_extended")
            currency = fi.get("currency")
    except Exception:
        pass

    if current_price is None:
        try:
            hist = tk.history(period="5d", interval="1d", auto_adjust=False)
            if not hist.empty:
                current_price = float(hist["Close"].dropna().iloc[-1])
        except Exception:
            pass

    for attempt in range(3):
        try:
            info = tk.info
            beta = info.get("beta3Year") or info.get("beta") or info.get("beta_3y")
            if beta is not None: beta = float(beta)
            break
        except Exception:
            _sleep_backoff(attempt)

    return {
        "ticker": ticker,
        "resolved_symbol": y_symbol,
        "market": {
            "current_price": current_price,
            "currency": currency,
            "beta": beta,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        },
    }

def fetch_ticker_history(ticker: str, resolved: Optional[str] = None) -> List[Dict[str, Any]]:
    y_symbol = resolved or ticker
    tk = yf.Ticker(y_symbol)
    history_points = []
    for attempt in range(3):
        try:
            df = tk.history(period=settings.HISTORY_PERIOD, interval=settings.HISTORY_INTERVAL, auto_adjust=False)
            if df is None or df.empty: return history_points
            closes = df["Close"].dropna()
            for idx, val in closes.items():
                history_points.append({
                    "date": idx.to_pydatetime().replace(tzinfo=timezone.utc).isoformat(),
                    "close": float(val),
                })
            break
        except Exception:
            _sleep_backoff(attempt)
    return history_points

def build_market_data(portfolio_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {"as_of": datetime.now(timezone.utc).isoformat(), "items": {}}
    total = len(portfolio_rows)
    
    for i, row in enumerate(portfolio_rows, 1):
        original_ticker = row["ticker"]
        if not original_ticker: continue
        
        logger.info(f"[{i}/{total}] Fetching data for {original_ticker}...")
        resolved_symbol = resolve_ticker(original_ticker, asset_type=row.get("asset_type"))
        snapshot = fetch_ticker_snapshot(original_ticker, resolved=resolved_symbol)
        history = fetch_ticker_history(original_ticker, resolved=resolved_symbol)

        result["items"][original_ticker] = {
            "static": row,
            "market": snapshot.get("market"),
            "history": {
                "period": settings.HISTORY_PERIOD,
                "interval": settings.HISTORY_INTERVAL,
                "closes": history,
            }
        }
    return result

def main():
    ensure_directories()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(settings.PORTFOLIO_CSV))
    parser.add_argument("--output", default=str(settings.MARKET_DATA_JSON))
    args = parser.parse_args()

    portfolio = load_portfolio(Path(args.input))
    market_data = build_market_data(portfolio)
    
    out_path = Path(args.output)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(market_data, f, indent=2)
    
    logger.info(f"Wrote {out_path} with {len(market_data['items'])} tickers.")

if __name__ == "__main__":
    main()