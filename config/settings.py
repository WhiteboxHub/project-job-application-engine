from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to the project root (config/ -> ..)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Database - DuckDB (file-based, no server needed)
    DUCKDB_PATH: str = str(_PROJECT_ROOT / "data" / "job_engine.duckdb")
    MOTHERDUCK_TOKEN: Optional[str] = None

    # Backend API
    BACKEND_URL: str = "http://localhost:8001"
    TRIGGER_ENDPOINT: str = "/weekly-workflow/trigger-run"
    INTERNAL_SECRET_KEY: Optional[str] = None

    # Browser
    CHROME_USER_DATA_DIR: str = "./chrome_profile"
    HEADLESS: bool = False

    # Resume
    RESUME_FILE_PATH: Optional[str] = "resume/candidate_resume.pdf"
    RESUME_PATH: Optional[str] = None  # Backwards compatibility
    DOWNLOADED_RESUME_DIR: str = "resume/downloads/"

    # Proxy
    PROXY_URL: Optional[str] = None

    # Safety
    MAX_APPLICATIONS_PER_RUN: int = 200  # Effectively unlimited
    SUBMISSION_COOLDOWN_SECONDS: int = 60
    DRY_RUN: bool = False
    # Keep browser open after run (useful for debugging)
    KEEP_BROWSER_OPEN: bool = False
    # How long to wait after clicking submit for navigation (seconds)
    SUBMIT_POST_CLICK_WAIT: int = 15

    # Multi-platform support (backward compatible)
    PLATFORM_FILTER: Optional[str] = (
        None  # Filter by platform: "LanceSoft", "InsightGlobal", etc.
    )

    # Capgemini credentials (SuccessFactors login required)
    CAPGEMINI_EMAIL: Optional[str] = None
    CAPGEMINI_PASSWORD: Optional[str] = None

# Email Reporting Setup
    SMTP_SERVER: Optional[str] = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    REPORT_RECEIVER_EMAIL: str = ""
    SENDER_EMAIL: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def chrome_profile_path(self) -> str:
        return str(Path(self.CHROME_USER_DATA_DIR).resolve())


settings = Settings()
