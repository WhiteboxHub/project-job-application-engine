import sys
import os
import random
import time

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import logger
from core.browser import browser_service
from engine.factory import strategy_factory
from models.config_models import JobListing

def test_run():
    """
    Directly verify the Collabera strategy iframe fix by forcing a run on a job URL.
    This script mocks the candidate data and bypasses the backend API.
    """
    logger.info("Initializing Verification Run for Collabera Iframe Fix...")
    
    # 1. Mock Candidate Data
    mock_candidate = {
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "phone": "1234567890",
        "resume_path": os.path.abspath("resume/downloads/candidate_resume_downloaded.pdf"),
        "search": {"keywords": ["Python"]},
        "applicant": {
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "phone": "1234567890"
        }
    }

    # 2. Mock Site Configuration
    class MockSite:
        def __init__(self):
            self.company_name = "Collabera"
            self.domain = "collabera.com"

    site = MockSite()
    selectors = {
        "listing": {"job_link": "//a[contains(@href, 'job-description')]"},
        "application": {"form_fields": {}} # No specific iframe selector to force the fallback fix
    }

    # 3. Start Browser
    browser = browser_service.start_browser()
    
    try:
        # 4. Initialize Strategy
        strategy = strategy_factory.get_strategy(
            "strategies.custom.CollaberaStrategy",
            browser,
            site,
            selectors,
            None,
            mock_candidate
        )
        
        # 5. Run Apply on a known Collabera job (or generic page to test iframes)
        # Note: We use a real job URL to see if it detects the iframe
        test_job_url = "https://collabera.com/job-description/?post=367614"
        
        listing = {
            "job_url": test_job_url,
            "job_title": "TEST - Collabera Verification",
            "external_id": "test_id_001"
        }
        
        logger.info(f"Targeting TEST URL: {test_job_url}")
        
        # Use dry-run logic so it doesn't submit
        import engine.guards as guards
        from config.settings import settings
        settings.DRY_RUN = True
        
        success = strategy.apply(listing)
        
        if success:
            logger.info("[SUCCESS] Verification completed. The strategy navigated to the page and handled the form/iframe.")
        else:
            logger.error("[FAIL] Strategy failed to complete the application flow.")

    finally:
        logger.info("Test finished. Closing browser...")
        time.sleep(5)
        browser_service.stop_browser()

if __name__ == "__main__":
    test_run()
