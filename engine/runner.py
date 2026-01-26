import time
from sqlalchemy.orm import Session
from data.db_mysql import db_mysql
from models.config_models import JobSite, SiteSelector
from engine.factory import strategy_factory
from core.browser import browser_service
from core.logger import logger
from engine.guards import guards

class EngineRunner:
    def __init__(self):
        self.browser = None

    def run(self):
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
            
            # 2. Get Sites
            session = db_mysql.SessionLocal()
            try:
                active_sites = session.query(JobSite).filter(JobSite.is_active == True).all()
                if not active_sites:
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
        
        # Load Strategy
        # Note: In a real app we'd need to resolve selectors properly, potentially merging platform + site
        # For this MVP, we grab the first listing-type selector for the site or platform
        selectors = {} # Placeholder for complex selector resolution logic
        
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
        # jobs = strategy.find_jobs() 
        # For MVP we might skip straight to applying if jobs are pre-seeded or just log discovery
        logger.info(f"Running strategy for {site.company_name}")
        
        # Placeholder for job loop
        # for job in jobs:
        #   if not guards.can_apply(): break
        #   success = strategy.apply(job)
        #   if success: guards.increment_counter()
        
