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
from selenium.common.exceptions import TimeoutException
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from models.history_models import Application
from config.settings import settings

class CapgeminiStrategy(BaseStrategy):
    """
    Capgemini automation strategy using SAP SuccessFactors.
    
    Features:
    - Login-based application flow
    - Multi-step navigation (Capgemini → SuccessFactors)
    - Human-like form filling
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
        self.safe_actions = SafeActions(driver)
        
        # Load applicant data from guest_form_data.json
        self.config_data = self._load_config()
        
        # Initialize selectors from database
        self.selectors_config = self._load_selectors()
        
        # Load delays from database
        self.delays = self.selectors_config.get('application', {}).get('delays', {
            "between_steps_min": 1.0,
            "between_steps_max": 2.5,
            "after_login_click": 10.0,
            "form_fill_min": 0.5,
            "form_fill_max": 1.2,
            "dropdown_select_min": 0.5,
            "dropdown_select_max": 1.0
        })
        
        # Get credentials from settings
        self.email = settings.CAPGEMINI_EMAIL
        self.password = settings.CAPGEMINI_PASSWORD
        
        if not self.email or not self.password:
            logger.warning("⚠️ Capgemini: No credentials found in .env file!")
            logger.warning("   Please set CAPGEMINI_EMAIL and CAPGEMINI_PASSWORD")
        
        # Initial log
        if self.db_session:
            logger.info("✅ Capgemini: Database session available")
        else:
            logger.warning("⚠️ Capgemini: No database session")

    def _load_selectors(self):
        """Load selectors from database configuration."""
        listing = self.selectors.get('listing', {})
        application = self.selectors.get('application', {})
        
        if not listing or not application:
            logger.error("❌ Capgemini: Missing critical selectors in database!")
        
        return {
            'listing': listing,
            'application': application
        }

    def get_sel(self, category, key, subkey=None, required=True):
        """
        Helper to safely fetch selectors from the database-loaded config.
        Raises RuntimeError if a critical selector is missing.
        """
        cat_dict = self.selectors_config.get(category, {})
        if subkey:
            val = cat_dict.get(key, {}).get(subkey)
        else:
            val = cat_dict.get(key)
            
        if not val:
            if required:
                msg = f"❌ Capgemini: Critical selector '{key}'" + (f"['{subkey}']" if subkey else "") + f" missing in database '{category}' config!"
                logger.error(msg)
                raise RuntimeError(msg)
            return None
            
        return val

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
            logger.info(f"Loaded configuration from {config_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load config JSON: {e}")
            return None

    def login(self):
        """Capgemini requires SuccessFactors login during application."""
        logger.info("Capgemini: Login handled during application flow")
        return True

    def find_and_apply_jobs(self):
        """
        Combined workflow: Find and apply to jobs immediately.
        """
        logger.info("🔍 Capgemini: Starting combined find-and-apply workflow")
        
        # Strictly database-driven keywords
        keywords = self.selectors.get('listing', {}).get('search_keywords')
        if not keywords:
            logger.error("❌ Capgemini: Critically missing 'search_keywords' in database configuration!")
            return 0
            
        logger.info(f"  📊 Using {len(keywords)} keywords from database")
        
        total_applied = 0
        seen_urls = set()
        
        for keyword in keywords:
            keyword = keyword.strip()
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Search: {keyword}")
            logger.info(f"{'='*60}")
            
            # 1. Search for jobs
            listings = self._perform_search(keyword)
            
            # 2. Apply immediately to new jobs
            for listing in listings:
                url = listing.get('job_url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    
                    logger.info(f"\n🚀 Applying to: {listing.get('job_title')}")
                    if self.apply(listing):
                        total_applied += 1
                        # Pause after submission
                        logger.info("  ✓ Human Behavior: Pausing for 3 seconds...")
                        time.sleep(3)
                else:
                    logger.debug(f"Capgemini: Skipping duplicate job: {listing.get('job_title')}")
            
            # Delay between searches
            if len(keywords) > 1:
                time.sleep(random.uniform(3, 6))
                
        logger.info(f"\n✅ Capgemini: Combined workflow finished. Total applications: {total_applied}")
        return total_applied

    def find_jobs(self):
        """Legacy discovery-only method."""
        logger.info("Capgemini: Starting job discovery phase...")
        
        keywords = settings.CAPGEMINI_KEYWORDS.split(',')
        
        all_listings = []
        seen_urls = set()
        
        for keyword in keywords:
            keyword = keyword.strip()
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Capgemini Search: {keyword}")
            logger.info(f"{'='*60}")
            
            listings = self._perform_search(keyword)
            
            # De-duplicate results
            new_jobs = 0
            for listing in listings:
                url = listing.get('job_url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_listings.append(listing)
                    new_jobs += 1
            
            logger.info(f"Capgemini: Added {new_jobs} unique jobs from this search")

            # Delay between searches
            if len(keywords) > 1:
                time.sleep(random.uniform(2, 4))
                
        logger.info(f"Capgemini: Finished discovery. Total unique jobs: {len(all_listings)}")
        return all_listings

    def _perform_search(self, keyword):
        """Internal method for a single search iteration."""
        sel_input = self.get_sel('listing', 'search_input')
        sel_cards = self.get_sel('listing', 'job_cards')
        
        try:
            # Navigate to search page
            base_url = "https://www.capgemini.com/us-en/careers/join-capgemini/job-search/?country_code=us-en&country_name=United%20States&size=15"
            self.driver.get(base_url)
            time.sleep(3)
            
            # Wait for search input
            search_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel_input))
            )
            
            # Type keyword
            logger.info(f"Capgemini [Keyword]: Entering '{keyword}'")
            self.human.human_click(search_input)
            time.sleep(1)
            
            search_input.clear()
            self.human.fill_text_field(search_input, keyword)
            time.sleep(2)
            
            # Press Enter to search
            from selenium.webdriver.common.keys import Keys
            search_input.send_keys(Keys.RETURN)
            
            # Wait for results to load
            time.sleep(5)
            
            # Scroll to load more jobs
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Extract job listings
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, sel_cards)
            listings = []
            
            for card in job_cards:
                try:
                    title = card.text.strip().split('\n')[0] if card.text else "Unknown"
                    url = card.get_attribute('href')
                    
                    if not url or not title:
                        continue
                    
                    # Extract ID from URL - handle trailing slashes
                    clean_url = url.rstrip('/')
                    external_id = clean_url.split('/')[-1] if '/' in clean_url else 'unknown'
                    
                    job_data = {
                        'job_title': title,
                        'job_url': url,
                        'external_id': external_id,
                        'card_element': card
                    }
                    
                    # Save to database
                    if self.db_session and self.job_site:
                        try:
                            existing = self.db_session.query(JobListing).filter(
                                JobListing.job_site_id == self.job_site.id,
                                JobListing.job_url == url
                            ).first()
                            
                            if existing:
                                if existing.status in ['applied', 'success']:
                                    logger.info(f"  ⏭️ Found job already applied: {title} ({external_id})")
                                    # Note: We still append to listings so the run loop sees it for dry-run context
                            else:
                                job_listing = JobListing(
                                    job_site_id=self.job_site.id,
                                    external_job_id=external_id,
                                    job_title=title,
                                    job_url=url,
                                    status='discovered'
                                )
                                self.db_session.add(job_listing)
                                self.db_session.commit()
                                logger.info(f"  💾 Saved to DB: {title} ({external_id})")
                        except Exception as db_err:
                            logger.warning(f"  ⚠️ DB save failed for {title}: {db_err}")
                            self.db_session.rollback()
                    
                    listings.append(job_data)
                    
                    # Track in CSV
                    csv_tracker.add_discovered_jobs('capgemini', [job_data])

                except Exception as e:
                    logger.warning(f"Error parsing job card: {e}")
            
            logger.info(f"Capgemini: Found {len(listings)} jobs for this search")
            return listings
            
        except Exception as e:
            logger.error(f"Capgemini: Error during search for {keyword}: {e}")
            if self.db_session:
                self.db_session.rollback()
            return []

    def apply(self, listing):
        """
        Apply to a specific job listing.
        Handles multi-step flow: Capgemini → SuccessFactors → Login → Application
        """
        # Support both dictionary and object inputs
        if isinstance(listing, dict):
            job_title = listing.get('job_title', 'Unknown Title')
            job_url = listing.get('job_url')
            external_id = listing.get('external_id', 'unknown')
        else:
            job_title = getattr(listing, 'job_title', 'Unknown Title')
            job_url = getattr(listing, 'job_url', None)
            external_id = getattr(listing, 'external_job_id', 'unknown')

        logger.info(f"Capgemini: Applying to {job_title} ({external_id})...")
        
        if not job_url:
            logger.error("Capgemini: No job URL provided")
            return False

        applicant = self.config_data.get('applicant', {})
        
        try:
            # 1. Click job card from search results
            logger.info(f"Capgemini [Step 1]: Clicking job card for {job_title}")
            card_element = listing.get('card_element') if isinstance(listing, dict) else None
            if card_element:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card_element)
                    time.sleep(1)
                    self.human.human_click(card_element)
                    logger.info("  ✓ Clicked job card")
                    time.sleep(3)
                except Exception as e:
                    logger.warning(f"Could not click card: {e}, navigating directly")
                    self.driver.get(job_url)
                    time.sleep(3)
            else:
                logger.info(f"  → Navigating to {job_url}")
                self.driver.get(job_url)
                time.sleep(3)
            
            # Check credentials after clicking (so we at least navigate to job page)
            if not self.email or not self.password:
                logger.error("Capgemini: Missing credentials! Set CAPGEMINI_EMAIL and CAPGEMINI_PASSWORD in .env")
                return False
            
            # 2. Click first "Apply now" button
            logger.info("Capgemini [Step 2]: Clicking 'Apply now' on job page")
            apply_btn_sel = self.get_sel('application', 'apply_button_main')
            apply_btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, apply_btn_sel))
            )
            self.human.human_click(apply_btn)
            time.sleep(self.delays.get('page_load_min', 3))
            
            # 3. Click second "Apply now" button (on careers subdomain)
            logger.info("Capgemini [Step 3]: Clicking 'Apply now' on careers page")
            try:
                apply_btn2 = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, apply_btn_sel))
                )
                self.human.human_click(apply_btn2)
                time.sleep(self.delays.get('page_load_min', 3))
            except:
                logger.debug("Second apply button not found, continuing...")
            
            # 4. Wait for SuccessFactors page to load (and handle new windows)
            logger.info("Capgemini [Step 4]: Waiting for SuccessFactors page")
            
            # More robust window switching: find the window that is SuccessFactors and not devtools
            start_time = time.time()
            sf_window_found = False
            while time.time() - start_time < 30:
                for handle in self.driver.window_handles:
                    self.driver.switch_to.window(handle)
                    curr_url = self.driver.current_url.lower()
                    if ("successfactors" in curr_url or "sfcareer" in curr_url) and "devtools" not in curr_url:
                        logger.info(f"  → Switched to SuccessFactors window: {curr_url}")
                        sf_window_found = True
                        break
                if sf_window_found:
                    break
                time.sleep(self.delays.get('short_delay_min', 1))
            
            if not sf_window_found:
                logger.warning(f"  ⚠️ Could not identify SuccessFactors window. Current URL: {self.driver.current_url}")
            
            time.sleep(self.delays.get('page_load_min', 3))
            
            # 5. Click "Sign In" button
            logger.info("Capgemini [Step 5]: Clicking 'Sign In' button")
            sign_in_sel = self.get_sel('application', 'sign_in_button', required=False)
            if sign_in_sel:
                try:
                    # Check if it's an XPath selector
                    if sign_in_sel.startswith('//') or sign_in_sel.startswith('('):
                        sign_in_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, sign_in_sel))
                        )
                    else:
                        sign_in_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, sign_in_sel))
                        )
                    self.human.human_click(sign_in_btn)
                    time.sleep(self.delays.get('click_min', 2))
                except Exception as e:
                    logger.debug(f"Sign in button not found or already on login page: {e}")
            
            # 6. Login to SuccessFactors
            logger.info("Capgemini [Step 6]: Logging in to SuccessFactors")
            self._login_to_successfactors()
            
            # 7. Fill application form
            logger.info("Capgemini [Step 7]: Filling application form")
            self._fill_application_form(applicant)
            
            # 8. Handle work authorization dropdown
            logger.info("Capgemini [Step 8]: Handling work authorization")
            self._handle_work_authorization()
            
            # 9. Upload resume
            logger.info("Capgemini [Step 9]: Uploading resume")
            self._upload_resume()
            
            # 10. Submit application
            logger.info("Capgemini [Step 10]: Submitting application")
            success = self._submit_application(listing, job_url, job_title)
            
            return success
                
        except Exception as e:
            logger.error(f"Capgemini: Error applying to {job_title}: {e}")
            self._record_application(listing, job_url, job_title, "failed", str(e))
            return False

    def _select_sf_dropdown(self, field_name, option_text):
        """Helper to handle SuccessFactors custom dropdowns with iframe support."""
        selector = self.get_sel('application', 'form_fields', field_name, required=False)
        if not selector:
            logger.debug(f"  ⏭️ No selector for {field_name}")
            return False
            
        logger.info(f"  📝 Selecting '{option_text}' for {field_name} (Sel: {selector})")
        
        # Helper to find and click trigger in current context
        def find_and_click_trigger(ctx):
            clean_id = selector.lstrip('#').replace('\\\\', ':').replace('\\', ':').replace('::', ':')
            trigger_strategies = [
                (By.ID, clean_id),
                (By.XPATH, f"//*[@id='{clean_id}']"),
                (By.XPATH, f"//*[contains(@id, '{clean_id.split(':')[-1]}')]"),
                (By.CSS_SELECTOR, selector),
                (By.XPATH, f"//input[@aria-label[contains(., '{field_name.replace('_', ' ')}')]]")
            ]
            
            for by, val in trigger_strategies:
                try:
                    trigger = WebDriverWait(ctx, 3).until(EC.element_to_be_clickable((by, val)))
                    ctx.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
                    time.sleep(self.delays.get('scroll_min', 1))
                    try:
                        trigger.click()
                    except:
                        ctx.execute_script("arguments[0].click();", trigger)
                    return True
                except:
                    continue
            return False

        try:
            # 1. Try finding in main document
            if not find_and_click_trigger(self.driver):
                # 2. Scan iframes
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                found_in_iframe = False
                for iframe in iframes:
                    try:
                        self.driver.switch_to.frame(iframe)
                        if find_and_click_trigger(self.driver):
                            found_in_iframe = True
                            break
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                
                if not found_in_iframe:
                    logger.warning(f"  ⚠️ Could not find trigger for {field_name}")
                    return False

            time.sleep(self.delays.get('dropdown_open_min', 1.5))
            
            # 3. Find and click the option (options often appear at bottom of main body)
            # Switch back to default content as SuccessFactors often puts listbox at top level
            self.driver.switch_to.default_content()
            
            option_strategies = [
                f"//li[normalize-space()='{option_text}']",
                f"//li[contains(text(), '{option_text}')]",
                f"//div[contains(@class, 'option') and normalize-space()='{option_text}']",
                f"//span[contains(text(), '{option_text}')]",
                f"//*[text()='{option_text}']"
            ]
            
            option_found = False
            # 1. Try exact matches first
            for xpath in option_strategies:
                try:
                    option = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    self.human.human_click(option)
                    time.sleep(random.uniform(
                        self.delays.get('dropdown_select_min', 0.5), 
                        self.delays.get('dropdown_select_max', 1.0)
                    ))
                    logger.info(f"  ✓ Set {field_name} to '{option_text}'")
                    option_found = True
                    break
                except:
                    continue
            
            # 2. Try case-insensitive and partial matches if exact failed
            if not option_found:
                logger.info(f"  🔍 Attempting case-insensitive match for '{option_text}'")
                try:
                    # SuccessFactors often uses <li> for dropdown options
                    options = self.driver.find_elements(By.TAG_NAME, "li")
                    for opt in options:
                        if opt.is_displayed() and option_text.lower() in opt.text.lower():
                            logger.info(f"  ✓ Found case-insensitive match: '{opt.text}'")
                            self.human.human_click(opt)
                            time.sleep(random.uniform(
                                self.delays.get('dropdown_select_min', 0.5), 
                                self.delays.get('dropdown_select_max', 1.0)
                            ))
                            option_found = True
                            break
                except:
                    pass
            
            if not option_found:
                logger.warning(f"  ⚠️ Could not find option '{option_text}' for {field_name}")
                self.driver.save_screenshot(f"/Users/bavishsaireddy/project-job-application-engine/logs/error_option_{field_name}.png")
                return False
                
            time.sleep(self.delays.get('short_delay_min', 1))
            return True
            
        except Exception as e:
            logger.warning(f"  ⚠️ Failed to handle dropdown {field_name}: {e}")
            self.driver.save_screenshot(f"/Users/bavishsaireddy/project-job-application-engine/logs/error_dropdown_{field_name}.png")
            return False
        finally:
            self.driver.switch_to.default_content()

    def _login_to_successfactors(self):
        """Handle SuccessFactors login."""
        email_sel = self.get_sel('application', 'login_email')
        password_sel = self.get_sel('application', 'login_password')
        submit_sel = self.get_sel('application', 'login_submit')
        phone_sel = self.get_sel('application', 'form_fields', 'phone', required=False)

        try:
            # Check if we are already logged in/on the application page
            # We must be very careful not to skip if the fields are visible but disabled (behind a login modal)
            apply_btn_sel = self.selectors_config.get('application', {}).get('submit_btn')
            if phone_sel:
                try:
                    # Check for phone field AND if it's actually visible and enabled
                    already_on_form = self.driver.find_elements(By.CSS_SELECTOR, phone_sel)
                    if already_on_form and already_on_form[0].is_displayed() and already_on_form[0].is_enabled():
                        # Also check if an apply/submit button is visible
                        if apply_btn_sel:
                            submit_btn = self.driver.find_elements(By.CSS_SELECTOR, apply_btn_sel)
                            if submit_btn and submit_btn[0].is_displayed():
                                logger.info("  ✓ Already logged in and on application form (Submit button visible)")
                                return True
                        else:
                            # Fallback if no specific submit_btn configured but phone is ready
                            logger.info("  ✓ Already on application form (Phone field ready)")
                            return True
                except:
                    pass

            # 0. Handle Cookie Banner if present
            try:
                cookie_btn_sel = "#cookiemanageracceptall"
                # Try finding it multiple ways
                cookie_btns = self.driver.find_elements(By.CSS_SELECTOR, cookie_btn_sel)
                if cookie_btns:
                    logger.info("  🍪 Dismissing cookie banner using JS")
                    self.driver.execute_script("arguments[0].click();", cookie_btns[0])
                    # Wait for it to disappear
                    WebDriverWait(self.driver, 5).until(
                        EC.invisibility_of_element_located((By.ID, "cookieManagerModal"))
                    )
                    time.sleep(self.delays.get('dropdown_select_min', 1))
            except Exception as ce:
                logger.debug(f"  Cookie banner interaction issue: {ce}")

            # Check for email field presence first
            try:
                email_input = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, email_sel))
                )
            except:
                # If email field not found, maybe we are ALREADY logged in (multi-job flow)
                logger.info("  ℹ️ Login field not found, checking if already logged in...")
                if self._check_if_logged_in_on_form(phone_sel):
                    return True
                raise Exception("Login fields not found and not detected as logged in")

            # 1. Fill Email
            logger.info(f"  ⌨️ Entering email: {self.email}")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", email_input)
            time.sleep(self.delays.get('scroll_min', 1))
            
            # Clear thoroughly
            self.driver.execute_script("arguments[0].value = '';", email_input)
            email_input.clear()
            try:
                email_input.send_keys(Keys.CONTROL, "a")
                email_input.send_keys(Keys.BACKSPACE)
            except:
                pass
            time.sleep(self.delays.get('short_delay_min', 0.5))
            
            # Use JS to set the value, then send a key to trigger events
            self.driver.execute_script("arguments[0].value = arguments[1];", email_input, self.email)
            time.sleep(self.delays.get('short_delay_min', 0.5))
            try:
                email_input.send_keys(Keys.END)
                email_input.send_keys(" ")
                email_input.send_keys(Keys.BACKSPACE)
            except:
                pass
            time.sleep(self.delays.get('form_fill_min', 1))
            
            # 2. Enter password
            password_input = self.driver.find_element(By.CSS_SELECTOR, password_sel)
            self.driver.execute_script("arguments[0].value = '';", password_input)
            password_input.clear()
            self.driver.execute_script("arguments[0].value = arguments[1];", password_input, self.password)
            time.sleep(self.delays.get('short_delay_min', 0.5))
            try:
                # Trigger input events then send ENTER as a primary submission attempt
                password_input.send_keys(Keys.END)
                password_input.send_keys(Keys.ENTER)
                logger.info("  ⌨️ Sent ENTER to password field")
            except Exception as pe:
                logger.debug(f"  Password ENTER failed: {pe}")
            time.sleep(self.delays.get('form_fill_min', 2))
            
            # Debug: take screenshot before sign-in click
            self.driver.save_screenshot("/Users/bavishsaireddy/project-job-application-engine/logs/before_login_click.png")
            
            # 3. Click submit button
            time.sleep(self.delays.get('form_fill_min', 2))
            sign_in_clicked = False
            
            # Strategy 1: Find by ID or CSS from database
            try:
                submit_sel = self.get_sel('application', 'login_submit', required=False)
                if submit_sel:
                    logger.info(f"  🚀 Attempting login submission with selector: {submit_sel}")
                    # Handle comma-separated selectors
                    selectors = [s.strip() for s in submit_sel.split(',')]
                    for sel in selectors:
                        elements = []
                        if sel.startswith('#'):
                            elements = self.driver.find_elements(By.ID, sel[1:])
                        if not elements:
                            elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        
                        for btn in elements:
                            if btn.is_displayed():
                                logger.info(f"  ✓ Found visible submit button: {sel}")
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                                time.sleep(self.delays.get('scroll_min', 1))
                                try:
                                    btn.click()
                                except:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                sign_in_clicked = True
                                break
                        if sign_in_clicked: break
            except Exception as e1:
                logger.debug(f"  Selector-based lookup failed: {e1}")
            
            if not sign_in_clicked:
                # Fallback to legacy hardcoded ID if needed
                try:
                    buttons = self.driver.find_elements(By.ID, "fbqa_signin")
                    for btn in buttons:
                        if btn.is_displayed():
                            logger.info("  🚀 Found visible Sign In button by legacy ID")
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                            time.sleep(self.delays.get('scroll_min', 1))
                            self.driver.execute_script("arguments[0].click();", btn)
                            sign_in_clicked = True
                            break
                except:
                    pass
            
            # Strategy 2: Find all buttons with CSS and click the visible one
            if not sign_in_clicked:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, "#fbqa_signin")
                    for btn in buttons:
                        if btn.is_displayed():
                            logger.info("  🚀 Found visible Sign In button by CSS selector")
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                            try:
                                btn.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", btn)
                            sign_in_clicked = True
                            break
                except Exception as e2:
                    logger.debug(f"  Visible CSS lookup failed: {e2}")
            
            # Strategy 3: By.NAME
            if not sign_in_clicked:
                try:
                    submit_btn = self.driver.find_element(By.NAME, "fbqa_signin")
                    logger.info("  🚀 Found Sign In button by NAME")
                    self.driver.execute_script("arguments[0].click();", submit_btn)
                    sign_in_clicked = True
                except Exception as e3:
                    logger.debug(f"  NAME lookup failed: {e3}")
            
            # Strategy 4: Pure JavaScript
            if not sign_in_clicked:
                try:
                    result = self.driver.execute_script("""
                        var btn = document.getElementById('fbqa_signin');
                        if (btn) { btn.click(); return 'clicked'; }
                        btn = document.querySelector('[name="fbqa_signin"]');
                        if (btn) { btn.click(); return 'clicked_by_name'; }
                        btn = document.querySelector('button[value="signin"]');
                        if (btn) { btn.click(); return 'clicked_by_value'; }
                        return 'not_found';
                    """)
                    if result and 'clicked' in result:
                        logger.info(f"  🚀 Clicked Sign In via JS ({result})")
                        sign_in_clicked = True
                    else:
                        logger.warning(f"  ⚠️ JS result: {result}")
                except Exception as e4:
                    logger.debug(f"  JS lookup failed: {e4}")
            
            # Strategy 5: XPath by button text
            if not sign_in_clicked:
                try:
                    submit_btn = self.driver.find_element(By.XPATH, "//button[contains(text(),'Sign In')]")
                    logger.info("  🚀 Found Sign In button by XPath text")
                    self.driver.execute_script("arguments[0].click();", submit_btn)
                    sign_in_clicked = True
                except Exception as e5:
                    logger.debug(f"  XPath lookup failed: {e5}")
            
            # Strategy 6: Check iframes
            if not sign_in_clicked:
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                logger.info(f"  🔍 Checking {len(iframes)} iframe(s) for Sign In button")
                for i, iframe in enumerate(iframes):
                    try:
                        self.driver.switch_to.frame(iframe)
                        btn = self.driver.find_element(By.ID, "fbqa_signin")
                        logger.info(f"  🚀 Found Sign In in iframe {i}")
                        self.driver.execute_script("arguments[0].click();", btn)
                        sign_in_clicked = True
                        self.driver.switch_to.default_content()
                        break
                    except:
                        self.driver.switch_to.default_content()
            
            else:
                # Debug: take screenshot after click
                time.sleep(self.delays.get('click_min', 2))
                self.driver.save_screenshot("/Users/bavishsaireddy/project-job-application-engine/logs/after_login_click.png")

            # Wait for login to complete and verify redirect
            time.sleep(self.delays.get('page_load_max', 15))
            
            # Check for error message on page
            try:
                error_msg = self.driver.find_elements(By.CSS_SELECTOR, ".error-message, .alert-danger, #loginError")
                if error_msg and any(e.is_displayed() for e in error_msg):
                    active_error = next(e.text for e in error_msg if e.is_displayed())
                    logger.warning(f"  ⚠️ Login error detected: {active_error}")
                    self.driver.save_screenshot("/Users/bavishsaireddy/project-job-application-engine/logs/login_error_visible.png")
            except:
                pass
                
            logger.info("  ✓ Login attempt finished")
            
        except Exception as e:
            self.driver.save_screenshot("/Users/bavishsaireddy/project-job-application-engine/logs/login_exception.png")
            logger.error(f"Login failed: {e}")
            raise

    def _fill_application_form(self, applicant):
        """
        Fill personal information in the application form.
        Note: First name, last name, and email are pre-populated from SuccessFactors profile.
        We only need to fill additional fields like phone number.
        """
        # Only fill fields that are NOT pre-populated
        fields_map = {
            'phone': applicant.get('phone')
        }
        
        logger.info("  ℹ️ First name, last name, and email are pre-filled from profile")
        
        for field, value in fields_map.items():
            if not value:
                logger.debug(f"  ⏭️ Skipping {field}: no value provided")
                continue
                
            try:
                selector = self.get_sel('application', 'form_fields', field, required=False)
                if selector:
                    elem = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    # Check if field is already filled
                    current_value = elem.get_attribute('value')
                    if current_value:
                        logger.info(f"  ℹ️ {field} already filled with: {current_value}")
                        continue
                    
                    self.human.fill_text_field(elem, value)
                    time.sleep(random.uniform(0.7, 1.2))
                    logger.info(f"  ✓ Filled {field}")
                else:
                    logger.debug(f"  ⏭️ No selector found for {field}")
            except Exception as e:
                logger.warning(f"  ⚠️ Could not fill {field}: {e}")

    def _handle_work_authorization(self):
        """
        Handle all questionnaire and dropdown fields using database-driven answers.
        """
        try:
            # Load answers from database configuration
            answers = self.selectors.get('application', {}).get('questionnaire_answers', {})
            
            if not answers:
                logger.warning("  ⚠️ No questionnaire_answers found in database configuration")
                return
                
            for field, answer in answers.items():
                self._select_sf_dropdown(field, answer)
                # Small delay between selections for stability
                time.sleep(random.uniform(0.5, 1.0))
            
            logger.info("  ✓ All questionnaire fields handled from database config")
        except Exception as e:
            logger.warning(f"  ⚠️ Error in handle_work_authorization loop: {e}")

    def _upload_resume(self):
        """
        Upload resume file.
        Checks if resume is already uploaded first - only uploads if:
        1. No resume is currently attached, OR
        2. User wants to change/update the resume
        """
        resume_selector = self.get_sel('application', 'form_fields', 'resume_upload', required=False)
        
        if not resume_selector:
            logger.warning("  ⚠️ No resume upload selector found")
            return
        
        try:
            # Check if resume is already uploaded
            # SuccessFactors typically shows uploaded file name or a confirmation element
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            # Common indicators that a resume is already uploaded
            resume_indicators = [
                '.pdf', '.doc', '.docx',  # File extensions
                'resume uploaded', 'file uploaded', 'attached',
                'current resume', 'existing resume'
            ]
            
            has_existing_resume = any(indicator in page_text for indicator in resume_indicators)
            
            if has_existing_resume:
                logger.info("  ℹ️ Resume appears to be already uploaded")
                logger.info("  ℹ️ Skipping resume upload (using existing resume)")
                # If you want to force upload a new resume, you can add logic here
                # For now, we'll use the existing resume
                return
            
            # No existing resume found, proceed with upload
            resume_path = self.get_resume_path()
            if not resume_path:
                logger.warning("  ⚠️ No resume path configured")
                return
                
            file_input = self.driver.find_element(By.CSS_SELECTOR, resume_selector)
            # Unhide if necessary
            self.driver.execute_script(
                "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                file_input
            )
            file_input.send_keys(resume_path)
            logger.info(f"  ✓ Resume uploaded: {os.path.basename(resume_path)}")
            time.sleep(2)
            
        except Exception as e:
            logger.warning(f"  ⚠️ Resume upload check/upload failed: {e}")
            logger.info("  ℹ️ Continuing with application (may use existing resume)")

    def _submit_application(self, listing, job_url, job_title):
        """Submit the application form."""
        submit_sel = self.get_sel('application', 'form_fields', 'submit_btn', required=False)
        
        if not submit_sel:
            logger.warning("No submit button selector found")
            return False
        
        try:
            submit_btn = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, submit_sel))
            )
            
            # Scroll to button
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                submit_btn
            )
            time.sleep(2)
            
            from engine.guards import guards
            if guards.is_dry_run():
                # Highlight button in dry run
                self.driver.execute_script("arguments[0].style.border = '5px solid orange';", submit_btn)
                logger.info("\n" + "!" * 60)
                logger.info("! DRY RUN SIMULATION: FOUND SUBMIT BUTTON")
                logger.info("! NO REAL SUBMISSION WILL BE PERFORMED IN THIS MODE")
                logger.info("!" * 60 + "\n")
                self._record_application(listing, job_url, job_title, "success", "Dry run simulation")
                return True
            else:
                submit_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, submit_sel))
                )
                self.human.human_click(submit_btn)
                logger.info("Capgemini: Application submitted, waiting for verification...")
                
                # Verify submission
                success = self._verify_submission()
                if success:
                    self._record_application(listing, job_url, job_title, "success")
                    return True
                else:
                    raise Exception("Submission verification failed")
                    
        except Exception as e:
            logger.error(f"Submit interaction failed: {e}")
            self._record_application(listing, job_url, job_title, "failed", str(e))
            return False

    def _verify_submission(self):
        """Verify if the application was successfully submitted."""
        success_indicators = self.get_sel('application', 'success_indicators')
        
        try:
            time.sleep(5)
            
            # Check URL change
            if "success" in self.driver.current_url.lower() or "confirmation" in self.driver.current_url.lower():
                logger.info("  ✓ Verified via URL redirection")
                return True
            
            # Check page content
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            for indicator in success_indicators:
                if indicator.lower() in page_text.lower():
                    logger.info(f"  ✓ Verified via confirmation text: '{indicator}'")
                    return True
            
            logger.warning("  ⚠️ Submission verification could not find success indicators")
            return False
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False

    def _record_application(self, listing, job_url, job_title, status, error=None):
        """Record application in DB and CSV"""
        # CSV Update
        csv_tracker.update_job_status('capgemini', job_url, 
                                    'applied' if status == 'success' else 'failed',
                                    attempts_inc=1,
                                    last_error=error)
        
        # Database Update
        if self.db_session:
            try:
                db_listing = self.db_session.query(JobListing).filter(
                    JobListing.job_url == job_url
                ).first()
                
                listing_id = None
                if db_listing:
                    listing_id = db_listing.id
                    # Update listing status - use flush to catch FK constraint errors
                    try:
                        db_listing.status = 'applied' if status == 'success' else 'failed'
                        db_listing.attempts += 1
                        db_listing.last_error = str(error) if error else None
                        db_listing.updated_at = datetime.now()
                        self.db_session.flush()
                    except Exception as db_err:
                        logger.warning(f"  ⚠️ Could not update job_listing status (DB quirk?): {db_err}")
                        self.db_session.rollback()
                        # Get ID again
                        db_listing = self.db_session.query(JobListing).filter(
                            JobListing.job_url == job_url
                        ).first()
                        listing_id = db_listing.id if db_listing else None
                        self.db_session.flush()
                    except Exception as db_err:
                        logger.warning(f"  ⚠️ Could not update job_listing status (DB quirk?): {db_err}")
                        self.db_session.rollback()
                        # Refetch to ensure session is clean
                        db_listing = self.db_session.query(JobListing).filter(JobListing.job_url == job_url).first()
                        listing_id = db_listing.id if db_listing else None
                        self.db_session.flush()
                    except Exception as db_err:
                        logger.warning(f"  ⚠️ Could not update job_listing status (DB quirk?): {db_err}")
                        self.db_session.rollback()
                        # Refetch to ensure session is clean
                        db_listing = self.db_session.query(JobListing).filter(JobListing.job_url == job_url).first()
                        listing_id = db_listing.id if db_listing else None
                    
                # Create or update application record
                from models.history_models import Application
                from sqlalchemy import select
                
                # Check for existing application for this listing
                stmt = select(Application).where(Application.job_listing_id == listing_id)
                app = self.db_session.execute(stmt).scalars().first() if listing_id else None
                
                if app:
                    app.status = status
                    app.error_message = str(error) if error else None
                    app.updated_at = datetime.now()
                else:
                    app = Application(
                        job_site_id=self.job_site.id,
                        job_listing_id=listing_id,
                        job_title=job_title,
                        job_url=job_url,
                        status=status,
                        error_message=str(error) if error else None
                    )
                    self.db_session.add(app)
                
                self.db_session.commit()
                logger.info(f"  📊 Application record updated in database ({status})")
            except Exception as e:
                logger.error(f"Failed to record application in DB: {e}")
                self.db_session.rollback()

    def _check_if_logged_in_on_form(self, phone_sel=None):
        """Helper to verify if we are already authenticated and on the application questionnaire."""
        if not phone_sel:
            return False
            
        try:
            # Check for phone field AND if it's actually visible and enabled
            already_on_form = self.driver.find_elements(By.CSS_SELECTOR, phone_sel)
            if already_on_form and already_on_form[0].is_displayed() and already_on_form[0].is_enabled():
                return True
        except:
            pass
        return False
