import json
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
    GENDER: str = "Female"
    ETHNICITY: str = "No, I am not Hispanic or Latino"
    RACE: str = "White (Not Hispanic or Latino)"

    # Education
    SCHOOL: str = ""
    GRADUATION_YEAR: str = ""
    AREA_OF_STUDY: str = "Computer Science"
    GPA: str = ""
    DEGREE: str = "Master's"

    # Work Experience (First Job)
    WORK_COMPANY_1: str = ""
    WORK_JOB_TITLE_1: str = ""
    WORK_START_YEAR_1: str = ""
    WORK_IS_CURRENT_1: bool = True
    
    # Work Experience (Second Job)
    WORK_COMPANY_2: str = ""
    WORK_JOB_TITLE_2: str = ""
    WORK_START_YEAR_2: str = ""
    WORK_END_YEAR_2: str = ""

    # Work Experience (Third Job)
    WORK_COMPANY_3: str = ""
    WORK_JOB_TITLE_3: str = ""
    WORK_START_YEAR_3: str = ""
    WORK_END_YEAR_3: str = ""

    # Work Experience (Fourth Job)
    WORK_COMPANY_4: str = ""
    WORK_JOB_TITLE_4: str = ""
    WORK_START_YEAR_4: str = ""
    WORK_END_YEAR_4: str = ""

    # Eligibility
    AUTHORIZED_US: bool = True
    VISA_SPONSORSHIP: bool = False

    # Infosys Specific
    INFY_USERNAME: str = ""
    INFY_PASSWORD: str = ""
    INFY_SUBMIT: bool = False
    INFY_PAUSE_BEFORE_SUBMIT: bool = True

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

# Post-initialization: Override with JSON data if it exists
profile_json = Path("resume_data/profile.json")
if profile_json.exists():
    try:
        with open(profile_json, "r") as f:
            data = json.load(f)
            
            # Personal
            p = data.get("personal", {})
            settings.FIRST_NAME = p.get("first_name", settings.FIRST_NAME)
            settings.LAST_NAME = p.get("last_name", settings.LAST_NAME)
            settings.EMAIL = p.get("email", settings.EMAIL)
            settings.PHONE_NUMBER = p.get("phone", settings.PHONE_NUMBER)
            settings.STREET_ADDRESS = p.get("address", settings.STREET_ADDRESS)
            settings.CITY = p.get("city", settings.CITY)
            settings.STATE = p.get("state", settings.STATE)
            settings.ZIP_CODE = p.get("zip_code", settings.ZIP_CODE)
            settings.CURRENT_TITLE = p.get("current_title", settings.CURRENT_TITLE)
            settings.GENDER = p.get("gender", settings.GENDER)

            # EEO / Other
            o = data.get("other", {})
            settings.RACE = o.get("race", settings.RACE)
            settings.ETHNICITY = o.get("ethnicity", settings.ETHNICITY)
            settings.VETERAN_STATUS = o.get("veteran_status", settings.VETERAN_STATUS)
            settings.DISABILITY_STATUS = o.get("disability_status", settings.DISABILITY_STATUS)

            # Education
            e = data.get("education", {})
            settings.SCHOOL = e.get("school", settings.SCHOOL)
            settings.DEGREE = e.get("degree", settings.DEGREE)
            settings.AREA_OF_STUDY = e.get("area_of_study", settings.AREA_OF_STUDY)
            settings.GRADUATION_YEAR = e.get("graduation_year", settings.GRADUATION_YEAR)
            settings.GPA = e.get("gpa", settings.GPA)

            # Work Experience
            w = data.get("work_experience", [])
            for i, exp in enumerate(w[:4], 1):
                setattr(settings, f"WORK_COMPANY_{i}", exp.get("company", ""))
                setattr(settings, f"WORK_JOB_TITLE_{i}", exp.get("title", ""))
                setattr(settings, f"WORK_START_YEAR_{i}", exp.get("start_year", ""))
                end_val = exp.get("end_year", "")
                if hasattr(settings, f"WORK_END_YEAR_{i}"):
                    setattr(settings, f"WORK_END_YEAR_{i}", end_val)
                if i == 1:
                    settings.WORK_IS_CURRENT_1 = exp.get("is_current", True)

            # Eligibility
            el = data.get("eligibility", {})
            settings.AUTHORIZED_US = el.get("authorized_us", settings.AUTHORIZED_US)
            settings.VISA_SPONSORSHIP = el.get("visa_sponsorship", settings.VISA_SPONSORSHIP)

    except Exception as exc:
        print(f"Warning: Failed to load profile.json: {exc}")
