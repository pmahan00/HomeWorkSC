import json
import sys
import time
import yfinance as yf
from pathlib import Path
from typing import List, Dict, Any

# Import Config & Utils
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings
from src.utils import setup_logger, load_yaml_config, ensure_directories

# Import GenAI
try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: 'google-genai' library required.")
    sys.exit(1)

logger = setup_logger("PortAnalysis")

# ==========================================
# 1. Analysis Logic (Same as before)
# ==========================================

def analyze_sector_distribution(feature_data: dict) -> dict:
    sector_dist = feature_data.get("sector_distribution", {}) or {}
    if sector_dist:
        top_sector = max(sector_dist, key=lambda k: float(sector_dist[k]))
    else:
        top_sector = "Technology" # Default
    return {"top_sector": top_sector}

def get_portfolio_metadata(feature_data: dict):
    items = feature_data.get("items", {})
    existing_tickers = set(items.keys())
    
    countries = {}
    for i in items.values():
        c = i.get("country", "Unknown")
        countries[c] = countries.get(c, 0) + 1
    
    top_country = max(countries, key=countries.get) if countries else "USA"
    return existing_tickers, top_country

# ==========================================
# 2. Discovery Logic with Google Search
# ==========================================

def generate_candidates_with_grounding(existing_tickers: set, target_sector: str, target_country: str) -> Dict[str, Any]:
    """
    Asks LLM to Google Search for competitors/peers.
    """
    if not settings.NEXUS_API_KEY:
        logger.warning("No API Key found. Skipping discovery.")
        return {}

    logger.info(f"🔍 Google Searching for candidates in '{target_sector}' and '{target_country}'...")

    client = genai.Client(
        http_options=types.HttpOptions(base_url=settings.NEXUS_BASE_URL),
        api_key=settings.NEXUS_API_KEY,
    )

    prompt_config = load_yaml_config(settings.PROMPT_MARKET_DISCOVERY)
    system_prompt = prompt_config["system_prompt"]

    # We explicitly ask it to search for "competitors" or "top stocks"
    user_content = f"""
    Exclude List (Do not recommend): {", ".join(list(existing_tickers))}
    
    Task 1: Search for "top {target_sector} stocks competitors to {list(existing_tickers)[:3]}" and suggest 3 new ones.
    Task 2: Search for "best performing stocks in {target_country} 2025" and suggest 3 new ones.
    """

    try:
        # --- THE KEY CHANGE: Enable Google Search Tool ---
        response = client.models.generate_content(
            model=settings.TEXT_MODEL,
            contents=user_content,
            config=types.GenerateContentConfig(
                tools=[
                    types.Tool(google_search=types.GoogleSearch()) 
                    # Note: Use GoogleSearch() for public stocks, not EnterpriseWebSearch
                ],
                system_instruction=system_prompt,
                temperature=0.1, # Keep it factual
                response_mime_type="application/json"
            )
        )
        
        # Optional: Print sources found by Google
        if response.candidates[0].grounding_metadata:
            chunks = response.candidates[0].grounding_metadata.grounding_chunks
            if chunks:
                logger.info(f"   -> Found {len(chunks)} search sources.")

        return json.loads(response.text)

    except Exception as e:
        logger.error(f"LLM Search failed: {e}")
        return {}

def validate_candidates(candidates: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Validates tickers with Yahoo Finance."""
    validated = []
    for item in candidates:
        ticker = item.get("ticker")
        if not ticker: continue
        
        # Clean ticker (sometimes LLM returns 'Ticker: AAPL')
        ticker = ticker.split(":")[-1].strip()

        try:
            tk = yf.Ticker(ticker)
            price = tk.fast_info.last_price
            
            if price:
                item["current_price"] = round(price, 2)
                item["currency"] = tk.fast_info.currency
                validated.append(item)
                logger.info(f"  [OK] {ticker}: {price:.2f} {item['currency']}")
            else:
                logger.warning(f"  [FAIL] {ticker}: No price data.")
        except Exception:
            logger.warning(f"  [FAIL] {ticker}: Validation error.")
            
    return validated

# ==========================================
# 3. Main Execution
# ==========================================

def main():
    ensure_directories()
    
    if not settings.FEATURE_DATA_JSON.exists():
        logger.error("Feature data not found.")
        sys.exit(1)

    with open(settings.FEATURE_DATA_JSON, "r") as f:
        feature_data = json.load(f)

    # Analyze
    sector_analysis = analyze_sector_distribution(feature_data)
    existing_tickers, top_country = get_portfolio_metadata(feature_data)
    top_sector = sector_analysis["top_sector"]

    # Discover
    discovery_results = {}
    if settings.NEXUS_API_KEY:
        raw_candidates = generate_candidates_with_grounding(existing_tickers, top_sector, top_country)
        
        if raw_candidates:
            logger.info("Validating Sector Candidates...")
            sector_picks = validate_candidates(raw_candidates.get("sector_candidates", []))
            
            logger.info("Validating Country Candidates...")
            country_picks = validate_candidates(raw_candidates.get("country_candidates", []))
            
            discovery_results = {
                "sector_peers": sector_picks,
                "country_peers": country_picks
            }

    # Save
    output = {
        "internal_analysis": {"top_sector": top_sector, "top_country": top_country},
        "external_discovery": discovery_results
    }

    with open(settings.PORTFOLIO_ANALYSIS_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
        
    logger.info(f"Analysis saved to {settings.PORTFOLIO_ANALYSIS_JSON}")

if __name__ == "__main__":
    main()