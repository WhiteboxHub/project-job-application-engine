import time
from sqlalchemy.orm import Session
from data.db_mysql import db_mysql
from models.config_models import JobSite, SiteSelector
from engine.factory import strategy_factory
from core.browser import browser_service
from core.logger import logger
from config.settings import settings
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
        
        # Load candidate profile
        candidate_profile = {}
        import json
        import os
        if os.path.exists(settings.CANDIDATE_PATH):
            try:
                with open(settings.CANDIDATE_PATH, 'r') as f:
                    candidate_profile = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load candidate profile: {e}")

        # Resolve selectors: merge platform + site selectors
        # For this implementation, we combine them into a dictionary
        selectors = {
            'listing': None,
            'application': None
        }
        
        for s in site.platform.selectors:
            selectors[s.type] = s.config_json
            
        for s in site.selectors:
            # Site-specific selectors override platform defaults
            selectors[s.type] = s.config_json
            
        strategy_path = site.platform.class_handler
        try:
            strategy = strategy_factory.get_strategy(strategy_path, self.browser, site, selectors, candidate_profile)
        except Exception as e:
            logger.error(f"Skipping site {site.company_name}: {e}")
            return
            
        # Login (if needed)
        if not strategy.login():
            logger.error(f"Login failed for {site.company_name}")
            return

        # Discovery
        logger.info(f"Finding jobs for {site.company_name}...")
        jobs_data = strategy.find_jobs() 
        
        if not jobs_data:
            logger.info(f"No new jobs found for {site.company_name}")
            return
            
        logger.info(f"Found {len(jobs_data)} potential jobs at {site.company_name}")
        
        # 1. First, persist ALL discovered jobs to DB
        from models.config_models import JobListing
        ready_listings = []
        
        for job_data in jobs_data:
            job = session.query(JobListing).filter(
                JobListing.job_site_id == site.id,
                JobListing.external_job_id == job_data['external_id']
            ).first()
            
            if not job:
                job = JobListing(
                    job_site_id=site.id,
                    external_job_id=job_data['external_id'],
                    job_title=job_data.get('title', 'Unknown Title'),
                    job_url=job_data['url'],
                    status='discovered'
                )
                session.add(job)
                logger.debug(f"Saved new job: {job.job_title} ({job.external_job_id})")
            
            # Re-collect all jobs that need application
            if job and job.status != 'applied':
                ready_listings.append(job)

        session.commit()
        logger.info(f"Successfully synchronized {len(jobs_data)} jobs with database.")

        # 2. Then, run Application Loop on the listings we have in DB
        for job in ready_listings:
            if not guards.can_apply():
                break
            
            # Refresh from session to be safe
            session.refresh(job)
            if job.status == 'applied':
                continue

            # Apply
            success = strategy.apply(job)
            if success:
                job.status = 'applied'
                guards.increment_counter()
                
                # Record in persistence DB
                from data.db_duck import db_duck
                from models.persistence_models import Application
                from datetime import datetime
                
                try:
                    p_session = db_duck.SessionLocal()
                    new_app = Application(
                        run_id=f"run_{int(time.time())}",
                        job_id=job.external_job_id,
                        status='success' if not guards.is_dry_run() else 'dry_run',
                        timestamp=datetime.utcnow()
                    )
                    p_session.add(new_app)
                    p_session.commit()
                    p_session.close()
                except Exception as e:
                    logger.error(f"Failed to log application to persistence DB: {e}")
            else:
                job.status = 'failed'
                job.attempts += 1
                
            session.commit()
            
            # Cooldown
            if success and not guards.is_dry_run():
                time.sleep(settings.SUBMISSION_COOLDOWN_SECONDS)
