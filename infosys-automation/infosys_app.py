import os
import sys
import logging
import time

# Add current directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from core.logger import logger
from core.browser import browser_service
from infosys_strategy import InfosysStrategy
from config.settings import settings

def run_standalone():
    try:
        logger.info("Starting STANDALONE Infosys Automation...")
        driver = browser_service.start_browser()

        # Mock job site config for Infosys
        class StandaloneJobSite:
            def __init__(self):
                self.name = "Infosys"
                self.base_url = "https://digitalcareers.infosys.com/infosys/global-careers"
                self.search_url_template = "https://digitalcareers.infosys.com/infosys/global-careers?location=USA"
                self.keyword = getattr(settings, "INFY_KEYWORD", "AI Engineer")
                self.location = getattr(settings, "INFY_LOCATION", "USA")

        # In standalone mode, we might want to fetch selectors from a local file or DB
        # For now, we'll try to use the DB connection if available, or a fallback
        selectors = {}
        try:
            from data.db_mysql import db_mysql
            from models.config_models import SiteSelector
            
            logger.info("Attempting to fetch selectors from database...")
            # You might need to adjust this depending on your local DB setup
            # This is a placeholder for the fetch logic
            # selectors = db_mysql.get_selectors_for_site("digitalcareers.infosys.com")
        except Exception as e:
            logger.warning(f"Could not load selectors from DB: {e}. Automation may fail if selectors are missing.")

        strategy = InfosysStrategy(driver, StandaloneJobSite(), selectors)

        logger.info("Step 1: Finding jobs...")
        jobs = strategy.find_jobs()
        logger.info(f"Found {len(jobs)} target jobs.")

        if jobs:
            for job in jobs[:3]: # Limit to 3 for initial test
                logger.info(f"Processing job: {job['job_title']} ({job['job_url']})")
                success = strategy.apply(job)
                if success:
                    logger.info(f"Successfully processed {job['job_title']}")
                else:
                    logger.error(f"Failed to apply to {job['job_title']}")
                time.sleep(5)
        else:
            logger.warning("No jobs found to process.")

    except Exception as e:
        logger.critical(f"Standalone run failed: {e}", exc_info=True)
    finally:
        try:
            # Keep browser open if needed for debug, otherwise stop
            # browser_service.stop_browser()
            pass
        except:
            pass

if __name__ == "__main__":
    run_standalone()
