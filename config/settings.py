import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DUCKDB_PATH: str = "data/job_engine.duckdb"
    
    # Browser
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
    PLATFORM_FILTER: Optional[str] = None  # Filter by platform: "KForce", "InsightGlobal", etc.
    
    # KForce Defaults (Template support)
    KFORCE_LOCATIONS: str = ""
    KFORCE_DISTANCE_DEFAULT: str = ""
    
    # Capgemini Defaults
    CAPGEMINI_EMAIL: Optional[str] = None
    CAPGEMINI_PASSWORD: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def chrome_profile_path(self) -> str:
        return str(Path(self.CHROME_USER_DATA_DIR).resolve())

settings = Settings()
