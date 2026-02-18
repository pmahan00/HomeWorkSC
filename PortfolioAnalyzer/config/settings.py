import os
from pathlib import Path

# Base Directory (sc/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Directory Paths
ENV_DIR = BASE_DIR / "env"
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
PROMPTS_DIR = BASE_DIR / "prompts"

# File Paths
ENV_FILE = ENV_DIR / "secrets.env"

# --- TYPO HANDLING LOGIC ---
# We check if the correct file exists; if not, we check for the known typo.
_default_csv = INPUT_DIR / "portfolio.csv"
_typo_csv = INPUT_DIR / "portoflio.csv"

if _typo_csv.exists() and not _default_csv.exists():
    print(f"[CONFIG] Note: Using '{_typo_csv.name}' (detected typo). Recommended: Rename to 'portfolio.csv'.")
    PORTFOLIO_CSV = _typo_csv
else:
    PORTFOLIO_CSV = _default_csv
# ---------------------------

MARKET_DATA_JSON = OUTPUT_DIR / "market_data.json"
FEATURE_DATA_JSON = OUTPUT_DIR / "feature_data.json"
NEWS_DATA_JSON = OUTPUT_DIR / "news_data.json"
INSIGHTS_JSON = OUTPUT_DIR / "insights.json"
PORTFOLIO_ANALYSIS_JSON = OUTPUT_DIR / "portfolio_analysis.json"

# Prompt Paths
PROMPT_SYSTEM_ANALYZER = PROMPTS_DIR / "system_analyzer.yaml"
PROMPT_NEWS_ANALYST = PROMPTS_DIR / "news_analyst.yaml"
PROMPT_MARKET_DISCOVERY = PROMPTS_DIR / "market_discovery.yaml"


# Defaults
HISTORY_PERIOD = "90d"
HISTORY_INTERVAL = "1wk"
BENCHMARK_SYMBOL = "URTH"

def load_env_vars():
    """Simple .env loader to avoid external dependencies like python-dotenv"""
    if not ENV_FILE.exists():
        # It's okay if secrets.env doesn't exist for data_fetch, 
        # but we warn if it's missing for scripts that need keys.
        return

    with open(ENV_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                key, value = line.split("=", 1)
                os.environ[key] = value
            except ValueError:
                pass # Skip malformed lines

# Load env vars immediately upon import
load_env_vars()

# API Configs (fetched from env)
NEXUS_BASE_URL = os.getenv("NEXUS_BASE_URL")
NEXUS_API_KEY = os.getenv("NEXUS_API_KEY")
TEXT_MODEL = os.getenv("TEXT_MODEL", "gemini-3-pro-preview")
