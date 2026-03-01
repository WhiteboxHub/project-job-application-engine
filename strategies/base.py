from abc import ABC, abstractmethod
from core.logger import logger
from models.config_models import JobListing
from selenium.webdriver.common.by import By
import os
from config.settings import settings
class BaseStrategy(ABC):
    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        self.driver = driver
        self.job_site = job_site
        self.selectors = selectors # JSON config from DB
        self.db_session = db_session
        self.candidate_data = candidate_data  # Candidate parameters from database
        self.use_single_phase = False
        
    @abstractmethod
    def login(self):
        """
        Handles authentication if required.
        """
        pass

    @abstractmethod
    def find_jobs(self):
        """
        Navigates to the search URL and scrapes job listings.
        Returns a list of dictionaries with job details (external_id, title, url).
        """
        pass

    @abstractmethod
    def apply(self, listing: JobListing):
        """
        Navigates to listing.job_url and attempts to apply.
        Returns True if successful, False otherwise.
        """
        pass

    def validate_content(self, required_selectors):
        """
        Checks if critical elements exist on the page.
        """
        for selector in required_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if not elements:
                    logger.error(f"Validation failed: Essential element '{selector}' missing.")
                    return False
            except Exception:
                logger.error(f"Validation failed: Error checking '{selector}'.")
                return False
        return True

    def get_resume_path(self):
        """
        Resolves the absolute path to the resume file.
        Priority:
        1. settings.RESUME_FILE_PATH (new)
        2. settings.RESUME_PATH (backwards compatible)
        3. self.config_data['resume_path'] (if exists)
        """
        # 1. Try settings (environment variables)
        resume_path = getattr(settings, 'RESUME_FILE_PATH', None)
        if not resume_path:
            resume_path = getattr(settings, 'RESUME_PATH', None)
        
        # 2. Try config_data (guest_form_data.json)
        if not resume_path and hasattr(self, 'config_data') and self.config_data:
            resume_path = self.config_data.get('resume_path')
            
        if not resume_path:
            logger.warning("No resume path configured in settings or data JSON.")
            return None
            
        # Ensure absolute path
        if not os.path.isabs(resume_path):
            # BaseStrategy is in strategies/, project root is one level up
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            resume_path = os.path.abspath(os.path.join(project_root, resume_path))
            
        if not os.path.exists(resume_path):
            logger.error(f"Resume file not found at: {resume_path}")
            return None
            
    def _record_application_db(self, status, job_url, job_title=None, listing_id=None, error=None):
        """
        Robust application recording using raw SQL to avoid SQLAlchemy/DuckDB transaction issues.
        """
        if not self.db_session:
            return
            
        try:
            # 1. Update listing status if exists
            if listing_id:
                try:
                    self.db_session.execute(
                        "UPDATE job_listings SET status = ?, attempts = attempts + 1, last_error = ? WHERE id = ?",
                        ['applied' if status == 'success' else 'failed', error, listing_id]
                    )
                except Exception as e:
                    logger.debug(f"Failed to update listing {listing_id}: {e}")
            elif job_url:
                try:
                    self.db_session.execute(
                        "UPDATE job_listings SET status = ?, attempts = attempts + 1, last_error = ? WHERE job_url = ?",
                        ['applied' if status == 'success' else 'failed', error, job_url]
                    )
                except Exception as e:
                    logger.debug(f"Failed to update listing by URL {job_url}: {e}")

            # 2. Insert application record
            from datetime import datetime
            now = datetime.now().isoformat()
            
            self.db_session.execute(
                """
                INSERT INTO applications 
                (job_site_id, job_listing_id, job_title, job_url, status, applied_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [self.job_site.id, listing_id, job_title, job_url, status, now, error]
            )
            logger.info(f"  [DB] Recorded {status} for {job_title or job_url}")
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to record application in DB: {e}")
