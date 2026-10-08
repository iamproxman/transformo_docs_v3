import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file from current or root directory
load_dotenv(".env")
load_dotenv("../.env")

# Ensure user-installed scoop and local binary tools are in PATH
user_profile = os.environ.get("USERPROFILE", "")
if user_profile:
    scoop_shims = os.path.join(user_profile, "scoop", "shims")
    if os.path.isdir(scoop_shims) and scoop_shims not in os.environ.get("PATH", ""):
        os.environ["PATH"] = scoop_shims + os.pathsep + os.environ.get("PATH", "")

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=True,
        env_file=[".env", "../.env"]
    )

    PROJECT_NAME: str = "TransformoDocs"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    API_BASE_URL: str = "http://localhost:8000/api/v1"
    
    # Storage & DB
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./transformo_docs.db")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./storage")
    
    # API Keys & Bot Secrets
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    INTERNAL_SECRET_KEY: str = os.getenv("INTERNAL_SECRET_KEY", "transformo-docs-secret-key-2026")
    
    # CORS
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings()
