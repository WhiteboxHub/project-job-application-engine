import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database (MySQL)
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str
    DB_NAME: str = "job_engine"

    # Persistence (DuckDB)
    DUCKDB_PATH: str = "data/history.duckdb"

    # Browser
    CHROME_USER_DATA_DIR: str = "./chrome_profile"
    HEADLESS: bool = False
    
    # Proxy
    PROXY_URL: Optional[str] = None

    # Safety
    MAX_APPLICATIONS_PER_RUN: int = 10
    SUBMISSION_COOLDOWN_SECONDS: int = 30
    DRY_RUN: bool = False
    # Career Profile
    RESUME_PATH: str = "./data/resume.pdf"
    FIRST_NAME: str = ""
    LAST_NAME: str = ""
    PHONE_NUMBER: str = ""
    EMAIL: str = ""
    STREET_ADDRESS: str = ""
    CITY: str = ""
    ZIP_CODE: str = ""
    COUNTRY: str = "United States"
    STATE: str = ""
    CURRENT_TITLE: str = ""

    # Eligibility
    AUTHORIZED_US: bool = True
    VISA_SPONSORSHIP: bool = False

    # TekSystems Specific
    TEK_SUBMIT: bool = False
    TEK_PAUSE_ON_LOCK: bool = True
    TEK_PAUSE_BEFORE_SUBMIT: bool = False
    TEK_YEARS_OPTION: str = "6-10 years"
    DESIRED_SALARY: str = "100000"
    WORK_HYBRID: bool = True
    WORK_REMOTE: bool = True
    WORK_ONSITE: bool = False
    SMS_OPT_IN: bool = False
    VETERAN_STATUS: str = "I am not a protected veteran"
    DISABILITY_STATUS: str = "I don't have a disability"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def mysql_url(self) -> str:
        return f"mysql+mysqlconnector://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def chrome_profile_path(self) -> str:
        return str(Path(self.CHROME_USER_DATA_DIR).resolve())

settings = Settings()
