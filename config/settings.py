from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Absolute path to the project root (config/ -> ..)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Database - DuckDB (file-based, no server needed)
    DUCKDB_PATH: str = str(_PROJECT_ROOT / "data" / "job_engine.duckdb")
    MOTHERDUCK_TOKEN: Optional[str] = None

    # Backend API (include /api — routers are mounted under /api)
    BACKEND_URL: str = "http://localhost:8001/api"
    TRIGGER_ENDPOINT: str = "/weekly-workflow/trigger-run"
    INTERNAL_SECRET_KEY: Optional[str] = None
    # Auth for protected routes (e.g. /api/automation-workflow-log). Use one of:
    # - API_ACCESS_TOKEN (JWT), or
    # - AUTH_URL + AUTH_USERNAME + AUTH_PASSWORD (login form, same as hiring-cafe-engine), or
    # - SCHEDULER_INTERNAL_SECRET as X-Internal-Secret (must match server env)
    AUTH_URL: Optional[str] = None
    AUTH_USERNAME: Optional[str] = None
    AUTH_PASSWORD: Optional[str] = None
    API_ACCESS_TOKEN: Optional[str] = None
    SCHEDULER_INTERNAL_SECRET: Optional[str] = None
    # When trigger-run payload omits workflow/schedule IDs, fill from env (Avatar workflow id = 7)
    DEFAULT_AUTOMATION_WORKFLOW_ID: Optional[int] = None
    DEFAULT_AUTOMATION_SCHEDULE_ID: Optional[int] = None

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

    # After each run, append the full output.json payload to this file (UTF-8). Empty = disabled.
    EXECUTION_LOG_FILE: str = str(_PROJECT_ROOT / "data" / "execution.log")

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
    SMTP_USERNAME: Optional[str] = "[EMAIL_ADDRESS]"
    SMTP_PASSWORD: Optional[str] = "nzon sigv nxms isqy"
    REPORT_RECEIVER_EMAIL: str = "[EMAIL_ADDRESS]"
    SENDER_EMAIL: Optional[str] = "[EMAIL_ADDRESS]"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def chrome_profile_path(self) -> str:
        return str(Path(self.CHROME_USER_DATA_DIR).resolve())


settings = Settings()
