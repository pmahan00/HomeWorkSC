import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("Error: 'google-genai' library required.")
    sys.exit(1)

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings
from src.utils import setup_logger, load_yaml_config, ensure_directories

logger = setup_logger("NewsPipeline")

def init_client():
    if not settings.NEXUS_BASE_URL or not settings.NEXUS_API_KEY:
        logger.error("NEXUS_BASE_URL and NEXUS_API_KEY must be set in sc/env/secrets.env")
        sys.exit(1)
        
    return genai.Client(
        http_options=types.HttpOptions(base_url=settings.NEXUS_BASE_URL),
        api_key=settings.NEXUS_API_KEY,
    )

def fetch_news(client, model_id: str, ticker: str, name: str, prompt_template: str) -> Dict[str, Any]:
    # Inject variables into the YAML prompt
    prompt = prompt_template.format(name=name, ticker=ticker)

    try:
        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_mime_type="application/json"
            )
        )
        
        try:
            text_content = response.candidates[0].content.parts[0].text
            data = json.loads(text_content)
            stories = data.get("stories", [])
        except Exception:
            logger.warning(f"Failed to parse JSON for {ticker}")
            return {"stories": [], "aggregate_sentiment": {"score": 0, "label": "neutral"}}

        score_map = {"positive": 1, "negative": -1, "neutral": 0}
        total_score = sum(score_map.get(s.get("sentiment_label", "neutral").lower(), 0) for s in stories)
        agg_label = "positive" if total_score > 0 else "negative" if total_score < 0 else "neutral"

        return {
            "ticker": ticker,
            "name": name,
            "stories": stories,
            "aggregate_sentiment": {"score": total_score, "label": agg_label}
        }

    except Exception as e:
        logger.error(f"API Error for {ticker}: {e}")
        return {"stories": [], "aggregate_sentiment": {"score": 0, "label": "neutral"}}

def main():
    ensure_directories()
    parser = argparse.ArgumentParser()
    parser.add_argument("--market", default=str(settings.MARKET_DATA_JSON))
    parser.add_argument("--output", default=str(settings.NEWS_DATA_JSON))
    parser.add_argument("--model", default=settings.TEXT_MODEL)
    args = parser.parse_args()

    logger.info(f"Starting News Pipeline using model: {args.model}")
    
    # Load Prompt
    prompt_config = load_yaml_config(settings.PROMPT_NEWS_ANALYST)
    system_prompt = prompt_config.get("system_prompt", "")

    with Path(args.market).open("r", encoding="utf-8") as f:
        market_data = json.load(f)

    client = init_client()
    result = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "items": {},
        "notes": ["Source: Google Search Grounding"]
    }

    items = market_data.get("items", {})
    total = len(items)

    for i, (ticker, data) in enumerate(items.items(), 1):
        name = data.get("static", {}).get("name", ticker)
        logger.info(f"[{i}/{total}] Processing: {ticker} ({name})")
        
        entry = fetch_news(client, args.model, ticker, name, system_prompt)
        result["items"][ticker] = entry
        
        count = len(entry['stories'])
        logger.info(f"   -> Found {count} stories. Sentiment: {entry['aggregate_sentiment']['label']}")
        time.sleep(1.0)

    with Path(args.output).open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    logger.info(f"News data saved to {args.output}")

if __name__ == "__main__":
    main()