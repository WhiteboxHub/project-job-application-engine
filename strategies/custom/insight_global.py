from strategies.base import BaseStrategy
from core.logger import logger
import time
import os
from selenium.webdriver.common.by import By

class InsightGlobalStrategy(BaseStrategy):
    def login(self):
        # No login required for Insight Global public board
        logger.info("InsightGlobal: No login required.")
        return True

    def find_jobs(self):
        """
        Scrapes jobs by interactively filling the search form for each keyword.
        """
        listing_config = self.selectors.get('listing')
        if not listing_config:
            logger.error("No listing selectors found for Insight Global")
            return []

        # Use candidate profile
        keywords = self.candidate_profile.get('keywords', ['python'])
        if isinstance(keywords, str):
            keywords = [keywords]
            
        location = self.candidate_profile.get('location', 'Remote')
        distance = self.candidate_profile.get('distance', '25 miles')

        all_found_jobs = []
        seen_job_ids = set()

        for keyword in keywords:
            logger.info(f"--- Searching for keyword: {keyword} ---")
            logger.info(f"Navigating to Insight Global Jobs page")
            self.driver.get("https://www.insightglobal.com/jobs")
            time.sleep(5)

            try:
                # 1. Fill Keyword
                logger.info(f"Filling keyword: {keyword}")
                # Clear field first if possible
                kw_input = self.driver.find_element(By.CSS_SELECTOR, "#textinput")
                kw_input.clear()
                self.actions.safe_type("#textinput", keyword)

                # 2. Fill Location
                if location.lower() != 'remote':
                    logger.info(f"Filling location: {location}")
                    loc_input = self.driver.find_element(By.CSS_SELECTOR, "#locationinput")
                    loc_input.clear()
                    self.actions.safe_type("#locationinput", location)
                else:
                    logger.info("Setting Remote Jobs checkbox")
                    remote_chk = self.driver.find_element(By.CSS_SELECTOR, "#ContentPlaceHolder1_ctl00_chkRemote")
                    if not remote_chk.is_selected():
                        self.actions.safe_click("#ContentPlaceHolder1_ctl00_chkRemote")

                # 3. Handle Distance Dropdown
                if location.lower() != 'remote':
                    dist_val = "".join(filter(str.isdigit, distance))
                    if dist_val:
                        logger.info(f"Setting distance radius: {dist_val}")
                        self.actions.safe_click("#dropdownMenu1")
                        time.sleep(1)
                        distance_selector = f".dropdown-menu li[data-value='{dist_val}']"
                        if not self.actions.check_exists(distance_selector):
                            distance_selector = ".dropdown-menu li[data-value='30']"
                        self.actions.safe_click(distance_selector)

                # 4. Click Search
                logger.info("Clicking Search button")
                self.actions.safe_click("#homesearch")
                time.sleep(8) 

                # 5. Extract results for this keyword
                container_selector = listing_config.get('container', 'div.result')
                containers = self.driver.find_elements(By.CSS_SELECTOR, container_selector)
                
                if not containers:
                    logger.warning(f"No job containers found for keyword: {keyword}")
                    self.driver.save_screenshot(f"debug_no_jobs_{keyword}.png")
                    continue
                
                for container in containers:
                    try:
                        fields = listing_config.get('fields', {})
                        
                        # Extract Job ID
                        id_conf = fields.get('job_id', {})
                        if id_conf.get('attr'):
                            job_id_elem = container.find_element(By.CSS_SELECTOR, id_conf['selector'])
                            external_id = job_id_elem.get_attribute(id_conf['attr'])
                        else:
                            external_id = container.find_element(By.CSS_SELECTOR, id_conf['selector']).text
                            
                        # Extract Title
                        title_conf = fields.get('title', {})
                        title = container.find_element(By.CSS_SELECTOR, title_conf['selector']).text
                        
                        # Extract URL
                        url_conf = fields.get('url', {})
                        if url_conf.get('attr'):
                            url = container.find_element(By.CSS_SELECTOR, url_conf['selector']).get_attribute(url_conf['attr'])
                        else:
                            url = container.find_element(By.CSS_SELECTOR, url_conf['selector']).text
                            
                        if external_id and external_id not in seen_job_ids:
                            all_found_jobs.append({
                                'external_id': external_id,
                                'title': title,
                                'url': url
                            })
                            seen_job_ids.add(external_id)
                            logger.info(f"Discovered Job: {title} (ID: {external_id})")
                            
                    except Exception as e:
                        logger.warning(f"Failed to parse a job container for {keyword}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error during search for keyword '{keyword}': {e}")
                self.driver.save_screenshot(f"debug_error_{keyword}.png")
            
        return all_found_jobs
    def apply(self, listing):
        logger.info(f"Applying to {listing.job_title} at {listing.job_url}")
        app_config = self.selectors.get('application')
        if not app_config:
            logger.error("No application selectors found for Insight Global")
            return False

        self.driver.get(listing.job_url)
        time.sleep(3)
        
        try:
            # For simplicity, we process only the first step in this template
            step = app_config.get('steps', [{}])[0]
            
            # Wait for form
            if step.get('wait_for'):
                if not self.actions.check_exists(step['wait_for']):
                   logger.error("Application form not found on page")
                   return False
            
            inputs = step.get('inputs', {})
            
            # Use candidate data if available, otherwise defaults
            first_name = self.candidate_profile.get('first_name', 'Test')
            last_name = self.candidate_profile.get('last_name', 'User')
            email = self.candidate_profile.get('email', 'test@example.com')
            phone = self.candidate_profile.get('phone', '1234567890')

            self.actions.safe_type(inputs['first_name'], first_name)
            self.actions.safe_type(inputs['last_name'], last_name)
            self.actions.safe_type(inputs['email'], email)
            self.actions.safe_type(inputs['phone'], phone)
            
            # Resume upload
            if inputs.get('resume_upload'):
                resume_path = os.path.abspath(settings.RESUME_PATH)
                if os.path.exists(resume_path):
                    logger.info(f"Uploading resume from: {resume_path}")
                    upload_elem = self.driver.find_element(By.CSS_SELECTOR, inputs['resume_upload'])
                    upload_elem.send_keys(resume_path)
                else:
                    logger.error(f"Resume not found at: {resume_path}")

            # Submit (Safety Guarded)
            from config.settings import settings
            if not settings.DRY_RUN:
                logger.info(f"SUBMITTING application for {listing.job_title}")
                # self.actions.safe_click(inputs['submit_btn'])
                # return True
            else:
                logger.info(f"[DRY-RUN] Would click submit for {listing.job_title}")
                return True
                
        except Exception as e:
            logger.error(f"Error during application process: {e}")
            return False
            
        return False
