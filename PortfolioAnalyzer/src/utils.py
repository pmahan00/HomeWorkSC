import logging
import yaml
import sys
from pathlib import Path

def setup_logger(name: str):
    """Configures a logger with timestamp and level."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def load_yaml_config(path: Path):
    """Safely loads a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"YAML config not found at: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def ensure_directories():
    """Ensures output directories exist."""
    from config import settings
    settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)