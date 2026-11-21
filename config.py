import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List

ENV_FILE = Path(__file__).resolve().parent / ".env"

def load_env(filepath: Path):
    """Simple, pure-stdlib .env file loader."""
    if not filepath.exists():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass

load_env(ENV_FILE)

@dataclass
class Settings:
    SLACK_BOT_TOKEN: str = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN", ""))
    SLACK_APP_TOKEN: str = field(default_factory=lambda: os.getenv("SLACK_APP_TOKEN", ""))
    SLACK_USER_TOKEN: Optional[str] = field(default_factory=lambda: os.getenv("SLACK_USER_TOKEN") or None)
    SLACK_APPROVER_USER_ID: str = field(default_factory=lambda: os.getenv("SLACK_APPROVER_USER_ID", ""))
    
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MODEL: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
    
    AI_PERSONA_PROMPT: str = field(default_factory=lambda: os.getenv(
        "AI_PERSONA_PROMPT",
        "You are an intelligent executive assistant drafting replies on behalf of the user. "
        "Keep responses professional, clear, and context-appropriate. "
        "Be concise and natural. Never mention you are an AI assistant unless explicitly asked."
    ))
    
    DATABASE_PATH: str = field(default_factory=lambda: os.getenv(
        "DATABASE_PATH",
        str(Path(__file__).resolve().parent / "drafts.db")
    ))

settings = Settings()

def validate_config() -> List[str]:
    """Returns a list of missing configuration warnings or errors."""
    missing = []
    if not settings.SLACK_BOT_TOKEN or settings.SLACK_BOT_TOKEN.startswith("xoxb-your"):
        missing.append("SLACK_BOT_TOKEN is missing or not configured.")
    if not settings.SLACK_APP_TOKEN or settings.SLACK_APP_TOKEN.startswith("xapp-your"):
        missing.append("SLACK_APP_TOKEN (for Socket Mode) is missing or not configured.")
    if not settings.SLACK_APPROVER_USER_ID or settings.SLACK_APPROVER_USER_ID == "U0123456789":
        missing.append("SLACK_APPROVER_USER_ID is missing or still set to the placeholder.")
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "your-gemini-api-key-here":
        missing.append("GEMINI_API_KEY is missing or not configured.")
    return missing
