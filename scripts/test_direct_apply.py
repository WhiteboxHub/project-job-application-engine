#!/usr/bin/env python3
"""
Test script to apply directly to a TekSystems job using the application portal URL.
This bypasses the search/scraping and goes straight to the application form.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.browser import browser_service
from strategies.custom.tek_systems import TekSystemsStrategy
from config.settings import settings
from core.logger import logger

def test_direct_application():
    """Test applying directly to a specific job via its application portal URL."""
    
    # Job details
    job_listing = {
        "job_title": "Ai Engineer",
        "job_url": "https://careers.teksystems.com/us/en/job/JP-005791646/Ai-Engineer",
        "application_url": "https://careers.teksystems.com/us/en/apply?jobSeqNo=TESYUSJP005791646ENUS&step=1&stepname=personalInformation"
    }
    
    try:
        # Start browser
        driver = browser_service.start_browser()
        logger.info("Browser started for direct application test")
        
        # Create strategy instance
        # We need a minimal job_site object
        class MockJobSite:
            def __init__(self):
                self.name = "TekSystems"
                self.base_url = "https://careers.teksystems.com"
                self.search_url_template = "https://careers.teksystems.com/us/en/search-results?keywords={keyword}"
                self.keyword = "AI Engineer"
                self.location = ""
        
        # Minimal selectors (not used in TekSystems strategy but required by base class)
        selectors = {}
        
        strategy = TekSystemsStrategy(driver, MockJobSite(), selectors)
        
        # Navigate directly to application portal
        logger.info(f"Navigating to application portal: {job_listing['application_url']}")
        driver.get(job_listing['application_url'])
        
        # Now test the form filling logic
        # We'll simulate being at the form already
        result = strategy.apply(job_listing)
        
        if result:
            logger.info("✅ Application completed successfully!")
        else:
            logger.warning("⚠️ Application did not complete")
        
        # Keep browser open for inspection
        input("Press Enter to close browser and exit...")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
    finally:
        browser_service.stop_browser()

if __name__ == "__main__":
    test_direct_application()
