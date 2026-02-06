from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler
import time
import os
import json
import random
import re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from models.history_models import Application
from config.settings import settings


class InfosysStrategy(BaseStrategy):
    """
    Refactored Infosys strategy aligned with Insight Global template.
    1. Loads config from JSON (or falls back to settings)
    2. Searches for AI/Engineering jobs
    3. Applies using guest/standard flows with HumanBehavior and CaptchaHandler
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None):
        super().__init__(driver, job_site, selectors)
        self.db_session = db_session
        self.job_site = job_site
        self.config_data = self._load_config()
        # Initialize human behavior and CAPTCHA handler
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
        
        # Ensure default selectors exist
        self._ensure_default_selectors()
        
        if self.db_session:
            logger.info("✅ Database session available - will save to DuckDB")
        else:
            logger.warning("⚠️ No database session - will only use CSV tracking")

    def _load_config(self):
        """Load configuration from JSON file (or mock if needed)"""
        try:
            # First try loading the same guest_form_data.json as Insight Global
            # This provides a consistent "applicant" profile
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data',
                'guest_form_data.json'
            )
            data = {}
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
            else:
                logger.warning(f"Config file not found at {config_path}")
            
            # Map settings.py values to this structure if missing
            # This ensures backward compatibility with Infosys-specific settings
            if 'applicant' not in data:
                data['applicant'] = {}
            
            app = data['applicant']
            if not app.get('first_name'): app['first_name'] = getattr(settings, 'FIRST_NAME', '')
            if not app.get('last_name'): app['last_name'] = getattr(settings, 'LAST_NAME', '')
            if not app.get('email'): app['email'] = getattr(settings, 'EMAIL', '')
            if not app.get('phone'): app['phone'] = getattr(settings, 'PHONE_NUMBER', '')
            # Add other fields as needed
            
            # Search config
            if 'search' not in data:
                data['search'] = {
                    "keyword": "AI Engineer",
                    "location": "Remote",
                    "distance": "50"
                }

            return data
        except Exception as e:
            logger.error(f"Failed to load config JSON: {e}")
            return {}

    def _ensure_default_selectors(self):
        if not self.selectors:
            self.selectors = {}
        
        # Migration of selectors from the old Infosys file
        defaults = {
            "search": {
                "input_box": [["css selector", "input.js_search_cp_jobs"], ["css selector", "input[placeholder='Search job']"]],
                "job_links": [["css selector", "a.job[href*='/description/reqid/']"]]
            },
            "apply": {
                "apply_button": [["css selector", "a.infosys-apply-link"], ["css selector", ".apply-button-container a"]],
                "form_signals": [["css selector", "input[name='firstName']"], ["css selector", "#firstname"]]
            }
        }
        
        # Merge logic
        for key, val in defaults.items():
            if key not in self.selectors:
                self.selectors[key] = val

    def login(self):
        """No login required usually, or handled during apply."""
        logger.info("Infosys: No login required (or not implemented).")
        return True

    def _search_jobs(self, keyword, location, distance):
        """
        Perform a single search with given parameters
        Returns list of job URLs found
        """
        # Infosys specific URL construction or navigation
        base_search_url = getattr(self.job_site, "search_url_template", None) or \
            "https://digitalcareers.infosys.com/infosys/global-careers?location=USA"
            
        logger.info(f"Opening Infosys Search: {base_search_url}")
        self.driver.get(base_search_url)
        self.human.random_delay(2, 4)
        
        # Close popups
        self._close_common_popups()
        
        # 1. Reveal search box if hidden (Infosys specific)
        try:
            reveal_btn = self.driver.find_element(By.CSS_SELECTOR, ".search-toggle, button.search")
            if reveal_btn.is_displayed():
                self.human.human_click(reveal_btn)
                time.sleep(1)
        except:
            pass

        # 2. Enter Keyword
        try:
            search_box = self.driver.find_element(By.CSS_SELECTOR, "input.js_search_cp_jobs, input[placeholder*='Search']")
            self.human.fill_text_field(search_box, keyword)
            search_box.send_keys(Keys.ENTER)
            logger.info(f"Entered keyword: {keyword}")
            time.sleep(5) # Wait for results
        except Exception as e:
            logger.error(f"Failed to enter keyword: {e}")
            return []

        # 3. Extract Results
        job_urls = []
        seen = set()
        
        try:
            # Wait for results
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a.job, div.job-title a"))
            )
            
            # Simple pagination loop (limit to 5 pages for safety)
            max_pages = 5
            for page in range(1, max_pages + 1):
                logger.info(f"Processing Page {page}")
                
                links = self.driver.find_elements(By.CSS_SELECTOR, "a.job[href*='/description/reqid/'], a[href*='reqid']")
                
                found_on_page = 0
                for link in links:
                    try:
                        href = link.get_attribute('href')
                        title = link.text.strip() or link.get_attribute("aria-label") or "Infosys Job"
                        
                        if href and href not in seen:
                            # Filter logic (AI/Engineer only)
                            if self._is_target_job(title):
                                seen.add(href)
                                job_urls.append(href)
                                logger.info(f"  ✓ Found target job: {title}")
                                found_on_page += 1
                                
                                # Track discovered
                                simple_id = href.split('/')[-1] if '/' in href else href
                                csv_tracker.add_discovered_jobs('infosys', [{'external_id': simple_id, 'job_title': title, 'job_url': href}])
                                
                                # Save to DB logic (copied from Insight Global)
                                if self.db_session and self.job_site:
                                    self._save_job_to_db(simple_id, title, href)
                    except:
                        continue
                        
                if found_on_page == 0:
                    logger.info("No more relevant jobs found on this page.")
                
                # Pagination click
                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, "a.next, li.next a, a[title='Next']")
                    if "disabled" in next_btn.get_attribute("class"):
                        break
                    self.human.scroll_to_element(next_btn)
                    self.human.human_click(next_btn)
                    time.sleep(3)
                except:
                    logger.info("Pagination complete (no next button).")
                    break
                    
        except Exception as e:
            logger.warning(f"Search interruption: {e}")
            
        return job_urls

    def _save_job_to_db(self, job_id, title, href):
        try:
            existing = self.db_session.query(JobListing).filter(
                JobListing.job_site_id == self.job_site.id,
                JobListing.job_url == href
            ).first()
            if not existing:
                job_listing = JobListing(
                    job_site_id=self.job_site.id,
                    external_job_id=job_id,
                    job_title=title,
                    job_url=href,
                    status='discovered'
                )
                self.db_session.add(job_listing)
                self.db_session.commit()
        except:
            self.db_session.rollback()

    def _is_target_job(self, title):
        """Filter for AI/ML roles"""
        if not title: return False
        t = title.lower()
        allow = ["ai ", "artificial intelligence", "machine learning", "ml", "data scientist", "engineer", "developer", "technology"]
        block = ["nurse", "sales", "hr", "marketing", "finance", "legal"]
        
        if any(b in t for b in block): return False
        if any(a in t for a in allow): return True
        return False

    def _apply_to_job(self, job_url):
        from engine.guards import guards
        
        if not guards.can_apply():
            logger.info("Application limit reached - stopping")
            return False
            
        # Check tracker
        status = csv_tracker.get_job_status('infosys', job_url)
        if status and status.get('status') == 'applied':
            logger.info(f"Already applied: {job_url}")
            return False

        logger.info(f"{'='*60}")
        logger.info(f"Applying to: {job_url}")
        logger.info(f"{'='*60}")
        
        try:
            self.driver.get(job_url)
            time.sleep(3)
            self._close_common_popups()
            
            # Click Apply
            apply_selectors = [
                "a.infosys-apply-link", 
                ".apply-button-container a", 
                "a[contains(text(), 'Apply')]",
                "button[contains(text(), 'Apply')]"
            ]
            
            if not self._click_any(apply_selectors):
                logger.error("Could not find Apply button")
                csv_tracker.update_job_status('infosys', job_url, 'failed', last_error='No Apply button')
                return False
                
            self._maybe_switch_new_tab()
            
            # Handle privacy/first-time flow
            self._handle_infosys_privacy_modal()
            
            # Form Filling Flow
            # 1. Personal Details
            applicant = self.config_data.get('applicant', {})
            
            # Using HumanBehavior for form filling
            logger.info("Filling form fields...")
            
            # Map standard fields to possible Infosys selectors
            field_map = {
                'first_name': ["#firstname", "input[name='firstName']"],
                'last_name': ["#lastname", "input[name='lastName']"],
                'email': ["#email", "input[name='email']"],
                'phone': ["#phone", "input[name='mobileNumber']", "input[name='phone']"]
            }
            
            for key, selectors in field_map.items():
                val = applicant.get(key, '')
                if not val: continue
                
                for sel in selectors:
                    try:
                        elem = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if elem.is_displayed():
                            self.human.fill_text_field(elem, val)
                            break
                    except:
                        continue
            
            # Upload Resume
            resume_path = self.config_data.get('resume_path', getattr(settings, 'RESUME_PATH', ''))
            if resume_path:
                self._upload_resume_focused(resume_path)
            
            # Handle additional Infosys sections (simplified logic)
            self._handle_dynamic_sections()
            
            # Submit
            return self._submit_application(job_url)
            
        except Exception as e:
            logger.error(f"Application error: {e}")
            csv_tracker.update_job_status('infosys', job_url, 'failed', last_error=str(e))
            return False

    def _click_any(self, selectors):
        for sel in selectors:
            try:
                # Handle xpath if needed
                by = By.XPATH if "//" in sel else By.CSS_SELECTOR
                elem = self.driver.find_element(by, sel)
                if elem.is_displayed():
                    self.human.human_click(elem)
                    return True
            except:
                continue
        return False

    def _close_common_popups(self):
        """Close typical cookie/alert popups"""
        popups = [
            "button#onetrust-accept-btn-handler",
            "button.close",
            "//button[contains(text(), 'Accept')]",
            "//button[contains(text(), 'Close')]"
        ]
        self._click_any(popups)

    def _maybe_switch_new_tab(self):
        if len(self.driver.window_handles) > 1:
            self.driver.switch_to.window(self.driver.window_handles[-1])

    def _handle_infosys_privacy_modal(self):
        # Look for privacy/consent modal and click Proceed/Agree
        if "privacy" in self.driver.page_source.lower():
            logger.info("Handling Privacy Modal...")
            # Often requires scrolling a text box
            try:
                box = self.driver.find_element(By.CSS_SELECTOR, ".consent-text-box, .modal-body")
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", box)
                time.sleep(1)
            except: pass
            
            self._click_any(["button.agree", "button.proceed", "//button[contains(text(), 'Proceed')]"])

    def _upload_resume_focused(self, resume_path):
        # Logic adapted from Insight Global / previous Infosys
        if not os.path.exists(resume_path):
            logger.warning(f"Resume not found: {resume_path}")
            return

        try:
            logger.info(f"Uploading resume: {resume_path}")
            # Try to find file input
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if inputs:
                # Unhide if necessary (Infosys often hides it)
                self.driver.execute_script("arguments[0].style.display = 'block';", inputs[0])
                inputs[0].send_keys(os.path.abspath(resume_path))
                logger.info("Sent resume to file input")
            else:
                # Dropzone click fallback
                self._click_any([".dropzone", "#pnlResumeDrop"])
                time.sleep(1)
                # Try finding input again
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if inputs:
                    inputs[0].send_keys(os.path.abspath(resume_path))
        except Exception as e:
            logger.error(f"Upload failed: {e}")

    def _handle_dynamic_sections(self):
        """Attempts to navigate Next through sections like Education, Experience"""
        # A simple loop to click 'Next' a few times if visible
        for _ in range(5):
            if self._click_any(["#forward-navigation", "button.next", "//button[contains(text(), 'Next')]"]):
                time.sleep(3)
                # handle any section-specific logic here if needed generically
            else:
                break

    def _submit_application(self, job_url):
        if getattr(settings, "DRY_RUN", True) and not getattr(settings, "INFY_SUBMIT", False):
            logger.info("DRY RUN: Skipping final submit click.")
            csv_tracker.update_job_status('infosys', job_url, 'dry_run')
            return True

        # Click Submit
        logger.info("Attempting Submit...")
        success = self._click_any([
            ".form-submit-button", 
            "input[type='submit']", 
            "//button[contains(text(), 'Submit')]"
        ])
        
        if success:
            logger.info("Clicked Submit!")
            time.sleep(5)
            # Verify?
            csv_tracker.update_job_status('infosys', job_url, 'applied')
            return True
        return False

    def apply(self, listing):
        """Public API matching BaseStrategy"""
        job_url = listing.get('job_url') if isinstance(listing, dict) else getattr(listing, 'job_url', None)
        if hasattr(listing, 'job_url'): job_url = listing.job_url # Object fallback
        
        return self._apply_to_job(job_url)
        
    def find_jobs(self):
        """Public API matching BaseStrategy"""
        search_cfg = self.config_data.get('search', {})
        keyword = search_cfg.get('keyword', 'AI Engineer')
        location = search_cfg.get('location', '')
        distance = search_cfg.get('distance', '')
        
        urls = self._search_jobs(keyword, location, distance)
        # Convert to list of dicts/listings as expected
        return [{"job_url": url, "job_title": "Infosys Job"} for url in urls]

# Execution block
if __name__ == "__main__":
    import sys
    # Add project root
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

    from core.browser import browser_service
    
    try:
        logger.info("Starting Infosys Strategy Test...")
        driver = browser_service.start_browser()
        
        # Mock site
        class MockSite:
            id = 1
            name = "Infosys"
            search_url_template = "https://digitalcareers.infosys.com/infosys/global-careers"
            
        strategy = InfosysStrategy(driver, MockSite(), {})
        
        # Test Search
        jobs = strategy.find_jobs()
        logger.info(f"Found {len(jobs)} jobs")
        
        # Test Apply (limit 1)
        if jobs:
            strategy.apply(jobs[0])
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        browser_service.stop_browser()
