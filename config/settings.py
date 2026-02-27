import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database - DuckDB (file-based, no server needed)
    DUCKDB_PATH: str = "data/job_engine.duckdb"
    
    # Browser
    CHROME_USER_DATA_DIR: str = "./chrome_profile"
    HEADLESS: bool = False

    # Resume
    RESUME_FILE_PATH: Optional[str] = "resume/candidate_resume.pdf"
    RESUME_PATH: Optional[str] = None # Backwards compatibility

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
    PLATFORM_FILTER: Optional[str] = None  # Filter by platform: "LanceSoft", "InsightGlobal", etc.

    # Capgemini credentials (SuccessFactors login required)
    CAPGEMINI_EMAIL: Optional[str] = None
    CAPGEMINI_PASSWORD: Optional[str] = None
    CAPGEMINI_KEYWORDS: str = "AI,Python,Machine Learning"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def chrome_profile_path(self) -> str:
        return str(Path(self.CHROME_USER_DATA_DIR).resolve())

settings = Settings()
