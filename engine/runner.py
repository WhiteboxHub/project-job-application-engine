import time
from sqlalchemy.orm import Session
from data.db_mysql import db_mysql
from models.config_models import JobSite, SiteSelector
from engine.factory import strategy_factory
from core.browser import browser_service
from core.logger import logger
from engine.guards import guards
from data.db_duckdb import db_duckdb
from models.config_models import JobSite, SiteSelector, JobListing

class EngineRunner:
    def __init__(self):
        self.browser = None

    def run(self, company_name: str = None):

        """
        Main execution workflow.
        1. Initialize Browser
        2. Fetch Active Sites from DB
        3. For each site:
           a. Instantiate Strategy
           b. Run Discovery (Find Jobs)
           c. Filter/Validate Jobs
           d. Run Application Loop
        """
        logger.info("Starting Job Engine Runner...")
        
        try:
            # 1. Start Browser
            self.browser = browser_service.start_browser()
            
            # 2. Sync DuckDB from MySQL
            mysql_session = db_mysql.SessionLocal()
            try:
                db_duckdb.sync_from_mysql(mysql_session)
            finally:
                mysql_session.close()

            # 3. Get Sites
            session = db_mysql.SessionLocal()
            try:
                query = session.query(JobSite).filter(JobSite.is_active == True)
                if company_name:
                    logger.info(f"Filtering for company: {company_name}")
                    query = query.filter(JobSite.company_name == company_name)
                
                active_sites = query.all()
                if not active_sites:
                    if company_name:
                        logger.warning(f"No active job site found with company name: {company_name}")
                    else:
                        logger.warning("No active job sites found in database.")
                    return

                
                for site in active_sites:
                    if not guards.can_apply():
                        break
                        
                    self._process_site(session, site)
                    
            finally:
                session.close()

        except Exception as e:
            logger.critical(f"Engine crashed: {e}")
        finally:
            if self.browser:
                logger.info("Stopping browser...")
                browser_service.stop_browser()

    def _process_site(self, session: Session, site: JobSite):
        logger.info(f"Processing Site: {site.company_name} ({site.domain})")
        
        # Load Strategy from DuckDB
        selectors = db_duckdb.get_selectors(job_site_id=site.id, ats_platform_id=site.ats_platform_id)

        strategy_path = site.platform.class_handler
        try:
            strategy = strategy_factory.get_strategy(strategy_path, self.browser, site, selectors)
        except Exception as e:
            logger.error(f"Skipping site {site.company_name}: {e}")
            return
            
        # Login (if needed)
        if not strategy.login():
            logger.error(f"Login failed for {site.company_name}")
            return

        # Discovery
        jobs = strategy.find_jobs() 
        logger.info(f"Found {len(jobs)} jobs for {site.company_name}")
        
        # Application loop
        for job in jobs:
            if not guards.can_apply():
                logger.info("Application limit reached for this run.")
                break
            
            # Check if already applied in DB
            job_url = job.get("job_url")
            existing_listing = session.query(JobListing).filter(JobListing.job_url == job_url).first()
            
            if existing_listing and existing_listing.status == 'applied':
                logger.info(f"Skipping already applied job: {job.get('job_title')}")
                continue

            success = strategy.apply(job)
            
            # Update/Create listing in DB
            if not existing_listing:
                existing_listing = JobListing(
                    job_site_id=site.id,
                    external_job_id=job.get("external_id", str(hash(job_url))[:10]),
                    job_title=job.get("job_title", "Unknown"),
                    job_url=job_url
                )
                session.add(existing_listing)
            
            if success:
                guards.increment_counter()
                existing_listing.status = 'applied'
                logger.info(f"Successfully applied to {job.get('job_title', 'Unknown Job')}")
            else:
                existing_listing.status = 'failed'
                existing_listing.last_error = "Strategy returned False"
                logger.error(f"Failed to apply to {job.get('job_title', 'Unknown Job')}")
            
            session.commit()

        
