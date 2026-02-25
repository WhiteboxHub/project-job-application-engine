from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
import time
import json
import os
from selenium.webdriver.common.by import By

from config.settings import settings

class HiringCafeStrategy(BaseStrategy):
    """
    HiringCafe.com Automation Strategy
    Reads pre-scraped jobs from data/hiring_cafe_jobs.json and applies
    to all jobs listed under the 'ashby' ATS platform.
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None):
        super().__init__(driver, job_site, selectors)
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.safe_actions = SafeActions(driver)
        self._load_applicant_data()

    def _load_applicant_data(self):
        """Loads applicant info from guest_form_data.json"""
        try:
            path = os.path.join("data", "guest_form_data.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    self.applicant_data = json.load(f)
                    logger.info(f"HIRINGCAFE: Loaded applicant data for {self.applicant_data.get('applicant', {}).get('first_name')}")
            else:
                self.applicant_data = {}
        except Exception as e:
            logger.error(f"HIRINGCAFE: Error loading applicant data: {e}")
            self.applicant_data = {}

    def login(self):
        """HiringCafe does not require login — jobs are read from local JSON."""
        logger.info("HIRINGCAFE: No login required. Jobs loaded from JSON file.")
        return True

    def find_jobs(self):
        """
        Reads Ashby jobs from data/hiring_cafe_jobs.json.
        Returns a list of job dicts with title, job_url (Ashby ATS URL), and site.
        """
        logger.info("HIRINGCAFE: Loading Ashby jobs from data/hiring_cafe_jobs.json...")

        try:
            json_path = os.path.join("data", "hiring_cafe_jobs.json")
            if not os.path.exists(json_path):
                logger.error(f"HIRINGCAFE: JSON file not found at '{json_path}'. Please place it in the data/ folder.")
                return []

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            ashby_jobs = data.get("by_ats", {}).get("ashby", [])
            logger.info(f"HIRINGCAFE: Found {len(ashby_jobs)} Ashby job(s) in JSON.")

            jobs = []
            for entry in ashby_jobs:
                ats_url = entry.get("ats_url")
                if not ats_url:
                    logger.warning(f"HIRINGCAFE: Skipping entry with no ats_url: {entry.get('job_id')}")
                    continue

                # Parse a clean title from the raw multi-line title string
                raw_title = entry.get("title", "")
                lines = [line.strip() for line in raw_title.split("\n") if line.strip()]
                # Skip the leading time token (e.g. "1d", "22h")
                if lines and (lines[0].endswith("h") or lines[0].endswith("d")):
                    lines = lines[1:]
                title = lines[0] if lines else "Ashby Job"

                jobs.append({
                    "title": title,
                    "job_url": ats_url,
                    "hiring_cafe_url": entry.get("hiring_cafe_url"),
                    "site": "ASHBY"
                })
                logger.info(f"HIRINGCAFE:   Queued -> {title} ({ats_url})")

            logger.info(f"HIRINGCAFE: Total Ashby jobs queued for application: {len(jobs)}")
            return jobs

        except Exception as e:
            logger.error(f"HIRINGCAFE: Failed to load jobs from JSON: {e}")
            return []

    def apply(self, listing):
        """
        Applies to an Ashby job by delegating directly to AshbyStrategy.
        The job_url is already the direct jobs.ashbyhq.com URL.
        """
        title = listing.get('title', 'Unknown')
        job_url = listing.get('job_url')
        logger.info(f"HIRINGCAFE: Applying to '{title}' via Ashby ATS...")
        logger.info(f"HIRINGCAFE: URL -> {job_url}")

        try:
            from strategies.custom.ashby import AshbyStrategy
            ashby_strat = AshbyStrategy(
                self.driver,
                self.job_site,
                self.selectors,
                getattr(self, 'db_session', None)
            )
            # Pass the listing with the direct Ashby URL
            result = ashby_strat.apply(listing)
            return result

        except Exception as e:
            logger.error(f"HIRINGCAFE: Error applying to '{title}': {e}")
            return False
