import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from core.logger import logger
from strategies.base import BaseStrategy
from core.human_behavior import HumanBehavior

class AETalentsStrategy(BaseStrategy):
    """AE Talents job application automation strategy."""

    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.portal_url = getattr(job_site, "search_url_template", "https://aetalentsgroup.com/careers.php")
        # runner._load_selectors returns {"listing": {...}, "application": {...}}
        # Merge both dicts into a flat config so .get("key") works for all phases
        self.selectors_config = {
            **((selectors or {}).get("listing", {})),
            **((selectors or {}).get("application", {})),
        }
        self.human = HumanBehavior(driver)

    def login(self):
        """No login required for AE Talents."""
        logger.info("AETalents: Checking login requirements... (No login required)")
        return True

    def find_jobs(self):
        """Search for jobs."""
        if not self.candidate_data:
            logger.error("No candidate data provided")
            return []

        search_config = self.candidate_data.get("search", {})
        keyword = search_config.get("keyword", "")
        if not keyword and search_config.get("keywords"):
             keyword = search_config.get("keywords")[0]
        location = search_config.get("location", "")

        logger.info(f"Navigating to {self.portal_url}")
        self.driver.get(self.portal_url)
        time.sleep(3)

        search_input_sel = self.selectors_config.get("search_input", "")
        # Fill search keyword
        if keyword:
            try:
                search_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, search_input_sel))
                )
                self.human.fill_text_field(search_input, keyword)
                logger.info(f"Entered search keyword: {keyword}")
            except Exception as e:
                logger.warning(f"Could not find search input: {e}")

        # Fill location (Temporarily commented out due to site issues)
        # location_input_sel = self.selectors_config.get("location_input", "")
        # if location:
        #     try:
        #         loc_input = WebDriverWait(self.driver, 5).until(
        #             EC.presence_of_element_located((By.CSS_SELECTOR, location_input_sel))
        #         )
        #         self.human.fill_text_field(loc_input, location)
        #         logger.info(f"Entered location: {location}")
        #     except Exception as e:
        #         logger.warning(f"Could not find location input: {e}")

        search_btn_sel = self.selectors_config.get("search_button", "")
        # Click search
        try:
            search_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, search_btn_sel))
            )
            self.human.human_click(search_btn)
            logger.info("Clicked search button")
            time.sleep(3) # Wait for page reload
        except Exception as e:
            logger.warning(f"Could not click search button: {e}")

        job_card_sel = self.selectors_config.get("job_card_link", "")
        # Extract job cards
        jobs = []
        try:
            # Check for "No positions found" message first
            no_results_elements = self.driver.find_elements(By.XPATH, "//h3[contains(text(), 'No positions found')]")
            if no_results_elements:
                logger.info("No positions found for this search. Returning empty list.")
                return []

            # Look for <a> tags linking to the detail page
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, job_card_sel))
            )
            job_links = self.driver.find_elements(By.CSS_SELECTOR, job_card_sel)
            
            seen = set()
            for link in job_links:
                url = link.get_attribute("href")
                title = link.text.strip()
                
                # Strict AI/ML check
                title_lower = title.lower()
                ai_keywords = ['ai', 'ml', 'artificial intelligence', 'machine learning', 'data scientist', 'llm', 'genai']
                is_ai_ml = any(kw in title_lower for kw in ai_keywords)
                
                # Ignore empty titles or generic "View Details" text
                if url not in seen and title and "View Details" not in title and is_ai_ml:
                    seen.add(url)
                    jobs.append({
                        "job_title": title,
                        "job_url": url,
                        "external_id": url.split("id=")[-1] if "id=" in url else ""
                    })
            logger.info(f"Found {len(jobs)} jobs matching criteria")
        except Exception as e:
            logger.warning(f"No job cards found or error parsing them: {e}")

        return jobs

    def apply(self, listing):
        """Phase 2: Apply to the job"""
        url = listing.get("job_url", "")
        title = listing.get("job_title", "Unknown")

        logger.info(f"\n[APPLY] Applying to: {title}")
        logger.info(f"URL: {url}")

        try:
            self.driver.get(url)
            time.sleep(3)

            # Step 1: Click "Apply Now" button to load the application form
            apply_now_sel = self.selectors_config.get("apply_now_button", "a.btn-secondary")
            try:
                apply_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, apply_now_sel))
                )
                self.human.human_click(apply_btn)
                logger.info("Clicked 'Apply Now' button on job detail page")
                time.sleep(3)
            except Exception as e:
                logger.error(f"Could not find or click 'Apply Now' button: {e}")
                return False

            # Application form logic
            logger.info("Application form loaded. Filling in candidate details...")

            applicant = self.candidate_data.get("applicant", {})

            first_name_sel = self.selectors_config.get("first_name", "")
            first_name_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, first_name_sel))
            )
            self.human.fill_text_field(first_name_input, applicant.get("first_name", ""))

            last_name_sel = self.selectors_config.get("last_name", "")
            last_name_input = self.driver.find_element(By.CSS_SELECTOR, last_name_sel)
            self.human.fill_text_field(last_name_input, applicant.get("last_name", ""))

            email_sel = self.selectors_config.get("email", "")
            email_input = self.driver.find_element(By.CSS_SELECTOR, email_sel)
            self.human.fill_text_field(email_input, applicant.get("email", ""))

            visa_status = (
                applicant.get("workstatus")
                or applicant.get("work_authorization", {}).get("visa_status", "")
                or "Other"
            )
            if visa_status:
                visa_sel = self.selectors_config.get("visa_status", "")
                try:
                    from selenium.webdriver.support.ui import Select
                    visa_element = self.driver.find_element(By.CSS_SELECTOR, visa_sel)
                    select = Select(visa_element)
                    matched = False
                    for option in select.options:
                        if visa_status.lower() in option.text.lower():
                            select.select_by_visible_text(option.text)
                            matched = True
                            break
                    if not matched:
                        select.select_by_value("Other")
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Could not set visa status: {e}")

            resume_path = self.get_resume_path()
            if resume_path:
                try:
                    resume_sel = self.selectors_config.get("resume", "")
                    resume_input = self.driver.find_element(By.CSS_SELECTOR, resume_sel)
                    resume_input.send_keys(resume_path)
                    logger.info("Uploaded resume")
                    time.sleep(2)
                except Exception as e:
                    logger.warning(f"Failed to upload resume: {e}")

            submit_sel = self.selectors_config.get("submit_button", "")
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, submit_sel)
            
            from config.settings import settings
            if getattr(settings, "DRY_RUN", False):
                logger.info("[DRY RUN] Skipping actual submission click.")
                logger.info("Dry run successful!")
                return True

            self.human.human_click(submit_btn)
            logger.info("Clicked submit application button, waiting for confirmation...")
            time.sleep(4)

            # Validate success
            try:
                success_sel = self.selectors_config.get("success_message", "")
                if success_sel:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, success_sel))
                    )
                    logger.info("Explicit success element detected!")
                else:
                    # Fallback generic validation
                    WebDriverWait(self.driver, 10).until(
                        lambda d: any(
                            phrase in d.page_source.lower() 
                            for phrase in ["success", "thank you", "application submitted", "received"]
                        )
                    )
                    logger.info("Generic success text detected on the page!")
                return True
            except Exception as e:
                logger.error(f"Could not verify application success confirmation: {e}")
                return False

        except Exception as e:
            logger.error(f"Error during application for {title}: {e}")
            return False
