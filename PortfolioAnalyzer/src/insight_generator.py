import json
import sys
from pathlib import Path
from google import genai
from google.genai import types

import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import settings
from src.utils import setup_logger, load_yaml_config, ensure_directories

logger = setup_logger("InsightGen")

def main():
    ensure_directories()
    
    logger.info("Loading data files...")
    try:
        with open(settings.FEATURE_DATA_JSON, "r") as f: feature_data = json.load(f)
        with open(settings.MARKET_DATA_JSON, "r") as f: market_data = json.load(f)
        with open(settings.NEWS_DATA_JSON, "r") as f: news_data = json.load(f)
    except FileNotFoundError as e:
        logger.error(f"Missing input file: {e}")
        sys.exit(1)

    prompt_config = load_yaml_config(settings.PROMPT_SYSTEM_ANALYZER)
    system_instruction = prompt_config["system_prompt"]

    user_payload = f"""
    PORTFOLIO FEATURES:
    {json.dumps(feature_data, indent=2)}

    MARKET DATA:
    {json.dumps(market_data, indent=2)}

    NEWS DATA:
    {json.dumps(news_data, indent=2)}

    Generate structured portfolio insights according to the defined schema.
    Ensure all claims are traceable to either market_data or news_data.
    """

    logger.info("Sending request to LLM...")
    client = genai.Client(
        http_options=types.HttpOptions(base_url=settings.NEXUS_BASE_URL),
        api_key=settings.NEXUS_API_KEY,
    )

    response = client.models.generate_content(
        model=settings.TEXT_MODEL,
        contents=[user_payload],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0,
            response_mime_type="application/json"
        )
    )

    with open(settings.INSIGHTS_JSON, "w", encoding="utf-8") as f:
        f.write(response.text)

    logger.info(f"Insights saved to {settings.INSIGHTS_JSON}")

if __name__ == "__main__":
    main()