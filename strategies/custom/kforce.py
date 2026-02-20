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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from models.history_models import Application

class KForceStrategy(BaseStrategy):
    """
    KForce automation strategy.
    
    Features:
    - Custom job search parsing
    - Human-like form filling
    - Guest application support
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
        self.safe_actions = SafeActions(driver)
        
        # Load applicant data from guest_form_data.json
        self.config_data = self._load_config()
        
        # Initialize selectors from database only
        self.selectors_config = self._load_selectors()
        
        # Initial log
        if self.db_session:
            logger.info("✅ KForce: Database session available")
        else:
            logger.warning("⚠️ KForce: No database session - strategy may fail if selectors not pre-loaded")

    def _load_selectors(self):
        """
        Loads selectors directly from the database configuration.
        No hardcoded fallbacks allowed here anymore.
        """
        listing = self.selectors.get('listing', {})
        application = self.selectors.get('application', {})
        
        if not listing or not application:
            logger.error("❌ KForce: Missing critical selectors in database!")
            # We still return the dict, but major methods should check for keys
        
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
                msg = f"❌ KForce: Critical selector '{key}'" + (f"['{subkey}']" if subkey else "") + f" missing in database '{category}' config!"
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
        """KForce typically allows guest browsing/applications."""
        logger.info("KForce: Checking login requirements...")
        return True

    def find_and_apply_jobs(self):
        """
        Combined workflow: Find and apply to jobs immediately.
        Iterates through search configurations, performs search, and applies to each unique job.
        Returns the number of successful applications.
        """
        logger.info("🔍 KForce: Starting combined find-and-apply workflow")
        
        # Strictly database-driven keywords
        keywords = self.selectors.get('listing', {}).get('search_keywords')
        if not keywords:
            logger.error("❌ KForce: Critically missing 'search_keywords' in database configuration!")
            return 0
            
        logger.info(f"  📊 Using {len(keywords)} keywords from database")
        location = None # Removed location search as per user request
        
        total_applied = 0
        seen_urls = set()
        
        for keyword in keywords:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Search: {keyword} (Location: {location})")
            logger.info(f"{'='*60}")
            
            # 1. Search for jobs
            listings = self._perform_search(keyword, location)
            
            # 2. Apply immediately to new jobs
            for listing in listings:
                url = listing.get('job_url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    
                    # We have a listing, now apply
                    logger.info(f"\n🚀 Applying to: {listing.get('job_title')}")
                    if self.apply(listing):
                        total_applied += 1
                        # Human Behavior: Pause after submission before next job
                        logger.info("  ✓ Human Behavior: Pausing for 3 seconds...")
                        time.sleep(3)
                else:
                    logger.debug(f"KForce: Skipping duplicate job: {listing.get('job_title')}")
            
            # Delay between searches
            if len(keywords) > 1:
                time.sleep(random.uniform(3, 6))
                
        logger.info(f"\n✅ KForce: Combined workflow finished. Total applications: {total_applied}")
        return total_applied

    def find_jobs(self):
        """
        Legacy discovery-only method. 
        Maintained for backward compatibility, though Runner now prefers find_and_apply_jobs.
        """
        logger.info("KForce: Starting job discovery phase...")
        
        keywords = self.config_data.get('keywords', ['AI Engineer'])
        location = None
        
        all_listings = []
        seen_urls = set()
        
        for keyword in keywords:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 KForce Search: {keyword} (Location: {location})")
            logger.info(f"{'='*60}")
            
            listings = self._perform_search(keyword, location)
            
            # De-duplicate results across different search iterations
            new_jobs = 0
            for listing in listings:
                url = listing.get('job_url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_listings.append(listing)
                    new_jobs += 1
                else:
                    logger.debug(f"KForce: Skipping duplicate job: {listing.get('job_title')}")
            
            logger.info(f"KForce: Added {new_jobs} unique jobs from this search")

            # Delay between searches
            if len(keywords) > 1:
                time.sleep(random.uniform(2, 4))
                
        logger.info(f"KForce: Finished discovery. Total unique jobs to process: {len(all_listings)}")
        return all_listings

    def _perform_search(self, keyword, location=None):
        """Internal method for a single search iteration."""
        sel_input = self.get_sel('listing', 'search_input')
        sel_button = self.get_sel('listing', 'search_button')
        sel_link = self.get_sel('listing', 'container')
        
        try:
            # Navigate to search page
            self.driver.get("https://www.kforce.com/find-work/search-jobs/")
            time.sleep(3)
            
            # Wait for search input
            search_input = WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel_input))
            )
            
            # Type keyword
            logger.info(f"KForce [Keyword]: Entering '{keyword}'")
            # Explicitly click to focus
            self.human.human_click(search_input)
            time.sleep(1)
            
            success = self.human.fill_text_field(search_input, keyword)
            
            if success:
                # Double-check the value via JS to be sure React caught it
                current_val = self.driver.execute_script("return arguments[0].value;", search_input)
                if current_val != keyword:
                    logger.warning(f"  ⚠️ React value mismatch (JS: '{current_val}'). Forcing value via JS.")
                    self.driver.execute_script(f"arguments[0].value = '{keyword}';", search_input)
                    # Trigger input event for React
                    self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", search_input)
                
                logger.info("  ✓ Keyword verified")
                time.sleep(2)
            else:
                logger.warning("  ⚠️ Failed to fill keyword via human behavior")
            
            # Click search button
            search_btn = self.driver.find_element(By.CSS_SELECTOR, sel_button)
            self.human.human_click(search_btn)
            
            # Wait for results to load
            time.sleep(5)
            
            # Extract job listings
            job_links = self.driver.find_elements(By.CSS_SELECTOR, sel_link)
            listings = []
            
            for link in job_links:
                try:
                    title = link.text.strip()
                    url = link.get_attribute('href')
                    
                    if not url or not title:
                        continue
                        
                    # KForce URLs usually have the ID in them
                    external_id = url.split('/')[-2] if '/' in url else 'unknown'
                    
                    job_data = {
                        'job_title': title,
                        'job_url': url,
                        'external_id': external_id
                    }
                    
                    # Save to database and check for previous applications
                    if self.db_session and self.job_site:
                        existing = self.db_session.query(JobListing).filter(
                            JobListing.job_site_id == self.job_site.id,
                            JobListing.job_url == url
                        ).first()
                        
                        if existing:
                            if existing.status in ['applied', 'success']:
                                logger.info(f"  ⏭️ Skipping job already applied: {title}")
                                continue
                            logger.debug(f"  Found existing listing: {title} (status: {existing.status})")
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
                            logger.info(f"  💾 Saved to DB: {title}")
                            
                    listings.append(job_data)
                    
                    # Track in CSV
                    csv_tracker.add_discovered_jobs('kforce', [job_data])

                except Exception as e:
                    logger.warning(f"Error parsing job link: {e}")
            
            logger.info(f"KForce: Found {len(listings)} jobs for this search")
            return listings
            
        except Exception as e:
            logger.error(f"KForce: Error during search for {keyword}: {e}")
            if self.db_session:
                self.db_session.rollback()
            return []

    def apply(self, listing):
        """
        Apply to a specific job listing.
        """
        # Support both dictionary and object (JobListing) inputs
        if isinstance(listing, dict):
            job_title = listing.get('job_title', 'Unknown Title')
            job_url = listing.get('job_url')
            external_id = listing.get('external_id', 'unknown')
        else:
            job_title = getattr(listing, 'job_title', 'Unknown Title')
            job_url = getattr(listing, 'job_url', None)
            external_id = getattr(listing, 'external_job_id', 'unknown')

        logger.info(f"KForce: Applying to {job_title} ({external_id})...")
        
        if not job_url:
            logger.error("KForce: No job URL provided")
            return False

        applicant = self.config_data.get('applicant', {})
        apply_initiator = self.get_sel('application', 'apply_initiator')
        
        try:
            # 1. Navigate to job URL with retry
            logger.info(f"KForce: Navigating to {job_url}")
            for attempt in range(2):
                try:
                    self.driver.get(job_url)
                    WebDriverWait(self.driver, 20).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    break
                except Exception as e:
                    if attempt == 1: raise
                    logger.warning(f"Navigation to {job_url} failed, retrying... ({e})")
                    time.sleep(5)

            time.sleep(3)
            
            # 2. Click 'Apply Today' initiator
            logger.info("KForce [Step 2]: Searching for Apply initiator")
            initiator = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, apply_initiator))
            )
            logger.info("  ✓ Found initiator, clicking...")
            self.human.human_click(initiator)
            time.sleep(2)
            
            # 3. Click 'Apply Today' dropdown option (KForce specific)
            logger.info("KForce [Step 3]: Searching for 'Apply Today' dropdown option")
            apply_link_sel = self.get_sel('application', 'apply_link_option')
            apply_link = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, apply_link_sel))
            )
            logger.info("  ✓ Found dropdown option, clicking...")
            self.human.human_click(apply_link)
            
            # Wait for application form to load
            first_field_sel = self.get_sel('application', 'form_fields', 'first_name')
            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, first_field_sel))
            )
            logger.info("KForce: Application form loaded")
            
            # 4. Fill personal details
            fields_map = {
                'first_name': applicant.get('first_name'),
                'last_name': applicant.get('last_name'),
                'email': applicant.get('email'),
                'email_verify': applicant.get('email'),
                'phone': applicant.get('phone'),
                'zip_code': applicant.get('zip_code')
            }
            
            for field, value in fields_map.items():
                logger.info(f"KForce [Step 4]: Filling field '{field}'")
                selector = self.get_sel('application', 'form_fields', field)
                if selector and value:
                    elem = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    self.human.fill_text_field(elem, value)
                    time.sleep(random.uniform(0.7, 1.2))
                else:
                    logger.warning(f"  ⚠️ Skipping field '{field}': missing selector or value")
            
            # 5. Handle State dropdown
            state_val = applicant.get('state')
            state_selector = self.get_sel('application', 'form_fields', 'state')
            if state_val and state_selector:
                state_dropdown = self.driver.find_element(By.CSS_SELECTOR, state_selector)
                from selenium.webdriver.support.ui import Select
                select = Select(state_dropdown)
                try:
                    select.select_by_visible_text(state_val)
                except:
                    # Fallback to value if text fails
                    select.select_by_value(state_val)
                logger.debug(f"Selected state: {state_val}")
            
            # 6. Upload Resume
            logger.info("KForce [Step 6]: Resolving resume path")
            resume_path = self.get_resume_path()
            resume_selector = self.get_sel('application', 'form_fields', 'resume_upload')
            
            if resume_path and resume_selector:
                logger.info(f"  ✓ Found resume: {os.path.basename(resume_path)}")
                try:
                    file_input = self.driver.find_element(By.CSS_SELECTOR, resume_selector)
                    # Unhide if necessary
                    self.driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", file_input)
                    file_input.send_keys(resume_path)
                    logger.info("  ✓ Resume attached successfully")
                except Exception as e:
                    logger.error(f"  ❌ Resume upload failed: {e}")
            else:
                logger.warning("  ⚠️ Skipping resume upload: path or selector missing")
            
            # 7. Questionnaire / Eligibility Radios
            answers = self.selectors.get('application', {}).get('questionnaire_answers', {})
            for field, target_val in answers.items():
                logger.info(f"KForce [Step 7]: Handling questionnaire field '{field}'")
                selector = self.get_sel('application', 'form_fields', field, required=False)
                if not selector:
                    continue
                
                try:
                    # Multi-pronged approach for radio buttons:
                    # 1. Try value match
                    # 2. Try text match (label/span)
                    # 3. Fallback to selector direct click
                    
                    selected = False
                    try:
                        # Common values for Radios: 'AuthorizedForAny', 'No', '0', 'False'
                        values_to_try = [target_val]
                        if target_val == "No": 
                            values_to_try.extend(['0', 'False', 'no'])
                        
                        for v in values_to_try:
                            try:
                                radio = self.driver.find_element(By.CSS_SELECTOR, f"{selector}[value='{v}']")
                                self.driver.execute_script("arguments[0].click();", radio)
                                selected = True
                                break
                            except: continue
                    except: pass
                    
                    if not selected:
                        # Fallback strings for common kforce labels
                        search_texts = [target_val]
                        if field == 'eligibility_auth' and target_val == 'AuthorizedForAny':
                            search_texts.append("I am authorized to work in the United States for any employer.")
                        
                        for txt in search_texts:
                            xpath_text = f"//label[contains(., '{txt}')] | //span[contains(., '{txt}')]"
                            elements = self.driver.find_elements(By.XPATH, xpath_text)
                            if elements:
                                self.driver.execute_script("arguments[0].click();", elements[0])
                                selected = True
                                break
                    
                    if not selected:
                        radio = self.driver.find_element(By.CSS_SELECTOR, selector)
                        self.driver.execute_script("arguments[0].click();", radio)
                        selected = True
                        
                    if selected:
                        logger.info(f"  ✓ Selected '{target_val}' for {field}")
                except Exception as e:
                    logger.warning(f"  ⚠️ Could not handle {field}: {e}")

            # 8. Click 'Next' if it exists (Multi-step form support)
            next_sel = self.get_sel('application', 'form_fields', 'next_btn', required=False)
            if next_sel:
                try:
                    # Try CSS first, then check if it's an XPath
                    if next_sel.startswith('//') or next_sel.startswith('('):
                        next_btns = self.driver.find_elements(By.XPATH, next_sel)
                    else:
                        next_btns = self.driver.find_elements(By.CSS_SELECTOR, next_sel)
                    
                    if next_btns and next_btns[0].is_displayed():
                        logger.info("KForce: Clicking 'Next' button")
                        self.human.human_click(next_btns[0])
                        time.sleep(2) # Wait for next step
                except Exception as e:
                    logger.debug(f"Next button not clickable/found: {e}")
            
            # 9. Submit (with Dry Run guard)
            submit_sel = self.get_sel('application', 'form_fields', 'submit_btn')
            if submit_sel:
                try:
                    submit_btn = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, submit_sel))
                    )
                    # Visual Feedback: Scroll to button so user can see it
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_btn)
                    time.sleep(2) # Pause so user can see the button
                    
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
                        submit_btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, submit_sel)))
                        self.human.human_click(submit_btn)
                        logger.info("KForce: Application submitted, waiting for verification...")
                        
                        # 9. Verify Submission
                        success = self._verify_submission()
                        if success:
                            self._record_application(listing, job_url, job_title, "success")
                            return True
                        else:
                            raise Exception("Submission verification failed")
                except Exception as e:
                    if "Dry run simulation" in str(e): return True # Already handled
                    logger.error(f"Submit interaction failed: {e}")
                    raise
                
        except Exception as e:
            logger.error(f"KForce: Error applying to {job_title}: {e}")
            # Log page source on critical failure (first 1000 chars)
            try:
                logger.debug(f"Page content snippet: {self.driver.page_source[:1000]}")
            except: pass
            
            self._record_application(listing, job_url, job_title, "failed", str(e))
            return False

    def _verify_submission(self):
        """
        Verifies if the application was successfully submitted.
        Checks for confirmation text or URL redirection.
        """
        success_indicators = self.get_sel('application', 'success_indicators')
        
        try:
            # Wait for content to change/load
            time.sleep(5)
            
            # 1. Check URL change (common in KForce/ATS)
            if "Success" in self.driver.current_url or "confirmation" in self.driver.current_url.lower():
                logger.info("  ✓ Verified via URL redirection")
                return True
            
            # 2. Check page content
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
        csv_tracker.update_job_status('kforce', job_url, 
                                    'applied' if status == 'success' else 'failed',
                                    attempts_inc=1,
                                    last_error=error)
        
        # Database Update
        if self.db_session:
            try:
                # Update listing status if it exists in DB
                db_listing = self.db_session.query(JobListing).filter(
                    JobListing.job_url == job_url
                ).first()
                
                listing_id = None
                if db_listing:
                    db_listing.status = 'applied' if status == 'success' else 'failed'
                    db_listing.attempts += 1
                    db_listing.last_error = error
                    listing_id = db_listing.id
                    
                # Create application record
                app = Application(
                    job_site_id=self.job_site.id,
                    job_listing_id=listing_id,
                    job_title=job_title,
                    job_url=job_url,
                    status=status,
                    error_message=error
                )
                self.db_session.add(app)
                # Retry commit in case of transient DuckDB locks
                for i in range(3):
                    try:
                        self.db_session.commit()
                        break
                    except Exception as commit_error:
                        if i == 2: raise
                        logger.warning(f"  ⚠️ Database commit failed (attempt {i+1}), retrying... {commit_error}")
                        time.sleep(1)
                logger.info(f"  📊 Application record saved to database ({status})")
            except Exception as e:
                logger.error(f"Failed to record application in DB: {e}")
                self.db_session.rollback()
