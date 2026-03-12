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
            
        logger.info(f"Resolved resume path: {resume_path}")
        return resume_path
