
import sys
import os
import time

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_mysql import db_mysql
from models.config_models import JobSite, JobListing, SiteSelector
from core.browser import browser_service
from core.logger import logger
from strategies.custom.infosys import InfosysStrategy
from sqlalchemy import text

def scrape_infosys():
    session = db_mysql.SessionLocal()
    driver = None
    try:
        logger.info("Starting Infosys Scraper...")
        
        # 1. Fetch site and selectors
        site = session.query(JobSite).filter(JobSite.company_name == 'Infosys').first()
        if not site:
            logger.error("Infosys site not found in database. Please run register_infosys.py first.")
            return

        selectors_raw = session.query(SiteSelector).filter(
            (SiteSelector.job_site_id == site.id) | 
            (SiteSelector.ats_platform_id == site.ats_platform_id)
        ).all()
        selectors = {}
        for s in selectors_raw:
            selectors.update(s.config_json)

        # 2. Start browser
        driver = browser_service.start_browser()
        
        # 3. Instantiate strategy and find jobs
        strategy = InfosysStrategy(driver, site, selectors)
        jobs = strategy.find_jobs()
        logger.info(f"Scraper found {len(jobs)} jobs on Infosys.")

        # 4. Persist to database
        new_count = 0
        update_count = 0
        
        for j in jobs:
            ext_id = j.get("external_job_id")
            if not ext_id:
                continue

            # Check if exists
            existing = session.query(JobListing).filter(
                JobListing.job_site_id == site.id,
                JobListing.external_job_id == ext_id
            ).first()

            if existing:
                # Update basic info if changed
                existing.job_title = j["job_title"]
                existing.job_url = j["job_url"]
                # Keep status as is (unless we want to re-scrape?)
                update_count += 1
            else:
                # Insert new
                new_job = JobListing(
                    job_site_id = site.id,
                    external_job_id = ext_id,
                    job_title = j["job_title"],
                    job_url = j["job_url"],
                    status = 'discovered'
                )
                session.add(new_job)
                new_count += 1
        
        session.commit()
        logger.info(f"Infosys Scrape complete. New: {new_count}, Updated: {update_count}")

    except Exception as e:
        logger.error(f"Scraper failed: {e}", exc_info=True)
        session.rollback()
    finally:
        if driver:
            browser_service.stop_browser()
        session.close()

if __name__ == "__main__":
    scrape_infosys()
