from abc import ABC, abstractmethod
from core.logger import logger
from models.config_models import JobListing
from selenium.webdriver.common.by import By

class BaseStrategy(ABC):
    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        self.driver = driver
        self.job_site = job_site
        self.selectors = selectors # JSON config from DB
        self.db_session = db_session
        self.candidate_data = candidate_data  # Candidate parameters from database
        
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
