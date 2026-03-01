from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler
from core.safe_actions import SafeActions
import time
import os
import json
import random
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from config.settings import settings

class KForceStrategy(BaseStrategy):
    """
    KForce automation strategy - Fully Database-Driven with List Support.
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
        self.safe_actions = SafeActions(driver)
        
        # Identity data
        self.config_data = self._load_config()
        
        # Configuration from MotherDuck
        self.full_config = self.selectors.get('full_config', {})
        self.listing_cfg = self.full_config.get('listing', {})
        self.application_cfg = self.full_config.get('application', {})

    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'data',
                'guest_form_data.json'
            )
            with open(config_path, 'r') as f:
                data = json.load(f)
            return data
        except Exception:
            return {}

    def _get_resume(self):
        """
        Resolve resume path with fallback chain:
        1. config_data['resume_path'] (guest_form_data.json)
        2. settings.RESUME_FILE_PATH
        3. settings.RESUME_PATH
        """
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 1. Try guest_form_data.json resume_path (most reliable)
        raw_path = self.config_data.get('resume_path')
        if raw_path:
            full = raw_path if os.path.isabs(raw_path) else os.path.join(project_root, raw_path)
            if os.path.exists(full):
                logger.info(f"Resume: {full}")
                return full
        
        # 2. Try settings
        for attr in ('RESUME_FILE_PATH', 'RESUME_PATH'):
            p = getattr(settings, attr, None)
            if p and os.path.exists(p):
                logger.info(f"Resume (settings): {p}")
                return p
        
        logger.warning("Resume not found — skipping upload")
        return None


    def _find_element_safe(self, selectors, timeout=5, clickable=False):
        """Try a list of selectors (CSS or XPath) until one is found."""
        if not selectors:
            return None
        if isinstance(selectors, str):
            selectors = [selectors]
            
        for sel in selectors:
            try:
                by = By.XPATH if sel.startswith("//") or sel.startswith("(") else By.CSS_SELECTOR
                condition = EC.element_to_be_clickable((by, sel)) if clickable else EC.presence_of_element_located((by, sel))
                return WebDriverWait(self.driver, timeout).until(condition)
            except:
                continue
        return None

    def login(self):
        return True

    def find_and_apply_jobs(self):
        logger.info("[SEARCH] KForce: Starting DB-driven workflow")
        
        keywords = self.listing_cfg.get('search_keywords', ["AI Engineer"])
        total_applied = 0
        seen_urls = set()
        
        for keyword in keywords:
            logger.info(f"\n{'='*60}\n[SEARCH] Keyword: {keyword}\n{'='*60}")
            listings = self._perform_search(keyword)
            
            for listing in listings:
                url = listing.get('job_url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    if self.apply(listing):
                        total_applied += 1
                        time.sleep(random.uniform(3, 6))
                
        return total_applied

    def find_jobs(self):
        return self._perform_search("AI Engineer")

    def _perform_search(self, keyword):
        self.driver.get(self.job_site.search_url_template)
        time.sleep(3)
        
        try:
            # Handle cookie banner
            cb = self._find_element_safe(["button#onetrust-accept-btn-handler", "button:contains('Accept')", "#cookie-accept"], timeout=2)
            if cb: cb.click()
        except: pass

        search_box = self._find_element_safe(self.listing_cfg.get('search_input'), timeout=10)
        if not search_box:
            logger.error("KForce: Search input not found")
            return []

        self.human.human_type(search_box, keyword)
        time.sleep(1)
        
        search_btn = self._find_element_safe(self.listing_cfg.get('search_button'), timeout=3, clickable=True)
        if search_btn:
            self.human.human_click(search_btn)
        else:
            search_box.send_keys(Keys.ENTER)
                
        time.sleep(5)
        
        job_cards_sel = self.listing_cfg.get('job_cards')
        if not job_cards_sel: return []
        
        by = By.XPATH if job_cards_sel[0].startswith("//") else By.CSS_SELECTOR
        job_elements = self.driver.find_elements(by, job_cards_sel[0]) # Use first as base
        
        listings = []
        for el in job_elements:
            try:
                title = el.text.strip()
                url = el.get_attribute('href')
                if title and url:
                    listings.append({'job_title': title, 'job_url': url})
            except: continue
                
        logger.info(f"KForce: Found {len(listings)} job(s)")
        return listings

    def apply(self, listing):
        job_url = listing.get('job_url')
        job_title = listing.get('job_title')
        
        logger.info(f"Applying to {job_title}...")
        self.driver.get(job_url)
        time.sleep(4)
        
        try:
            # 1. Initiator
            initiator = self._find_element_safe(self.application_cfg.get('apply_button_main'), timeout=10, clickable=True)
            if not initiator:
                raise RuntimeError("Apply initiator not found")
            self.human.human_click(initiator)
            time.sleep(3)
            
            # 2. Dropdown option
            option = self._find_element_safe(self.application_cfg.get('dropdown_option'), timeout=5, clickable=True)
            if option:
                self.human.human_click(option)
                time.sleep(5)

            # 2b. Select local resume radio (if present)
            local_radio_sel = self.application_cfg.get('local_resume_radio')
            if local_radio_sel:
                r = self._find_element_safe(local_radio_sel, timeout=3)
                if r:
                    self.driver.execute_script("arguments[0].click();", r)
                    time.sleep(0.5)

            # 3. Form fields
            fields = self.application_cfg.get('form_fields') or {}
            raw = self.config_data
            # guest_form_data.json stores identity under 'applicant' key
            data = raw.get('applicant', raw)
            
            mapping = {
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "email": data.get("email"),
                "email_verify": data.get("email"),
                "phone": data.get("phone"),
                "zip_code": data.get("zip_code") or data.get("zipcode")
            }
            logger.info(f"  [DATA] Loaded applicant: {data.get('first_name')} {data.get('last_name')} <{data.get('email')}>")

            
            for key, selectors in fields.items():
                try:
                    if not selectors:
                        continue
                    if key == "eligibility":
                        # Click work authorization radio via JS
                        el = self._find_element_safe(selectors, timeout=2)
                        if el:
                            self.driver.execute_script("arguments[0].click();", el)
                            logger.info(f"  [OK] Clicked eligibility radio")
                    elif key in mapping:
                        value = mapping[key]
                        if value is None:
                            logger.warning(f"  [SKIP] '{key}' has no value in guest_form_data.json")
                            continue
                        el = self._find_element_safe(selectors, timeout=2)
                        if el:
                            # Try normal type first, fall back to JS setValue
                            try:
                                self.human.human_type(el, str(value))
                            except Exception:
                                self.driver.execute_script("arguments[0].value = arguments[1];", el, str(value))
                            logger.info(f"  [OK] Filled '{key}'")
                        else:
                            logger.warning(f"  [SKIP] Element not found for '{key}'")
                    elif key == "state_dropdown":
                        el = self._find_element_safe(selectors, timeout=2)
                        if el:
                            from selenium.webdriver.support.ui import Select
                            try:
                                Select(el).select_by_visible_text(data.get("state", "California"))
                                logger.info(f"  [OK] Selected state")
                            except: pass
                    elif key == "resume_upload":
                        el = self._find_element_safe(selectors, timeout=3)
                        path = self._get_resume()
                        if el and path:
                            # Make input visible then upload
                            self.driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible';", el)
                            el.send_keys(path)
                            logger.info(f"  [OK] Resume attached: {path}")
                            
                            logger.info("  Waiting strictly for 15 seconds for resume upload to process...")
                            time.sleep(15)
                        else:
                            logger.warning(f"  [SKIP] Resume upload failed - el:{bool(el)} path:{path}")

                    elif key == "submit_btn":
                        pass  # Handled separately
                    else:
                        logger.debug(f"  [SKIP] Unknown field key: '{key}'")
                except Exception as field_err:
                    logger.warning(f"  [WARN] Error filling field '{key}': {field_err}")


            # 4. Questionnaire
            quest = self.application_cfg.get('questionnaire') or {}
            for q_key, q_selectors in quest.items():
                if q_selectors:
                    el = self._find_element_safe(q_selectors, timeout=2)
                    if el: self.driver.execute_script("arguments[0].click();", el)

            # 5. Submit
            submit_btn = self._find_element_safe(fields.get('submit_btn'), timeout=5, clickable=True)
            if not submit_btn:
                raise RuntimeError("Submit button not found")

            if settings.DRY_RUN:
                logger.info("DRY RUN: Simulation success.")
                self._record_application_db("success", job_url, job_title)
                return True
                
            self.human.human_click(submit_btn)
            logger.info("Application submitted")
            time.sleep(10)
            
            self._record_application_db("success", job_url, job_title)
            return True
            
        except Exception as e:
            import traceback
            logger.error(f"Application failed: {e}")
            logger.error(traceback.format_exc())
            self._record_application_db("failed", job_url, job_title, error=str(e))
            return False
