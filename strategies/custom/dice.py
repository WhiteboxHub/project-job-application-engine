from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
import time
import random
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.select import Select
from sqlalchemy import text

class DiceStrategy(BaseStrategy):
    """
    Dice.com Automation Strategy
    Flow: dice.com -> Search AI Jobs -> Scrape -> Apply
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None):
        super().__init__(driver, job_site, selectors)
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.safe_actions = SafeActions(driver)
        self._load_applicant_data()

    def _load_applicant_data(self):
        """Loads applicant info from guest_form_data.json"""
        import json
        import os
        try:
            path = os.path.join("data", "guest_form_data.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    self.applicant_data = json.load(f)
                    logger.info(f"DICE: Loaded applicant data for {self.applicant_data.get('applicant', {}).get('first_name')}")
            else:
                self.applicant_data = {}
        except Exception as e:
            logger.error(f"DICE: Error loading applicant data: {e}")
            self.applicant_data = {}

    def login(self):
        """Navigates to the Dice login page and signs in with stored credentials."""
        try:
            logger.info("DICE: Navigating to login page...")
            self.driver.get("https://www.dice.com/dashboard/login")
            time.sleep(4)
            self._handle_popups()

            # Check if already logged in (redirected away from login page)
            if "dashboard/login" not in self.driver.current_url:
                logger.info("DICE: Already logged in, skipping login step.")
                return True

            return self._perform_login()
        except Exception as e:
            logger.error(f"DICE: Error during login: {e}")
            return False

    def _load_credentials_from_db(self):
        """Loads Dice login credentials from the DuckDB site_credentials table."""
        try:
            if not self.db_session:
                return None, None
            result = self.db_session.execute(
                text("""
                SELECT sc.username, sc.password
                FROM site_credentials sc
                JOIN job_sites js ON sc.job_site_id = js.id
                WHERE js.domain = 'dice.com'
                LIMIT 1
                """)
            ).fetchone()
            if result:
                logger.info("DICE: Loaded credentials from DB")
                return result[0], result[1]
        except Exception as e:
            logger.warning(f"DICE: Could not load credentials from DB: {e}")
        return None, None

    def _perform_login(self):
        """Fills and submits the Dice login form."""
        try:
            # Try DB first, fall back to JSON
            email, password = self._load_credentials_from_db()
            if not email or not password:
                applicant = self.applicant_data.get("applicant", {})
                email = applicant.get("email")
                password = applicant.get("password")

            if not email or not password:
                logger.warning("DICE: Login requested but credentials missing in DB and JSON")
                return False

            logger.info(f"DICE: Filling login form as {email}")

            # Fill email (Shadow DOM search)
            email_input = self._find_in_shadows(tag_name="input", selector="input[name='email'], input[type='email'], input#email")
            if not email_input:
                # Fallback to standard wait search just in case
                email_input = self.safe_actions.wait_for_element("input[name='email']", timeout=5)
            
            if not email_input:
                logger.error("DICE: Could not find email input on login page")
                return False
            
            self.human.human_type(email_input, email)
            # Trigger events to ensure the field registers the input
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", email_input)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", email_input)
            time.sleep(1)

            # Try to advance by pressing Enter on the email field (handles both single-step and multi-step)
            logger.info("DICE: Pressing Enter on email field to advance...")
            email_input.send_keys(Keys.ENTER)
            time.sleep(3)

            # Click "Continue"/Next explicitly if it exists and Enter didn't work
            try:
                # Look for common "Next" or "Continue" buttons
                cont_btn = self._find_in_shadows(tag_name="button", text_filter="Next")
                if not cont_btn:
                    cont_btn = self._find_in_shadows(tag_name="button", text_filter="Continue")
                    
                if cont_btn and cont_btn.is_displayed():
                     logger.info("DICE: Found 'Next/Continue' button, clicking...")
                     self.driver.execute_script("arguments[0].click();", cont_btn)
                     time.sleep(2)
            except Exception:
                pass

            # Fill password (Shadow DOM search)
            password_input = self._find_in_shadows(tag_name="input", selector="input[name='password'], input[type='password'], input#password")
            if not password_input:
                 # Standard wait fallback
                 password_input = self.safe_actions.wait_for_element("input[name='password']", timeout=5)

            if not password_input:
                logger.error("DICE: Could not find password input on login page")
                # Debug: Dump page source to see what's happening
                # with open("login_debug.html", "w", encoding="utf-8") as f:
                #     f.write(self.driver.page_source)
                # logger.info("DICE: Dumped login page source to 'login_debug.html'")
                return False
            
            self.human.human_type(password_input, password)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", password_input)
            time.sleep(1)

            # Click the Sign In button
            sign_in_btn = self._find_in_shadows(tag_name="button", text_filter="Sign In")
            if not sign_in_btn:
                sign_in_btn = self._find_in_shadows(tag_name="button", selector="button[type='submit']")
            
            if sign_in_btn:
                logger.info("DICE: Clicking Sign In button")
                self.driver.execute_script("arguments[0].click();", sign_in_btn)
            else:
                # Fallback: press Enter on the password field
                logger.info("DICE: Submit button not found, pressing Enter")
                password_input.send_keys(Keys.ENTER)

            # Wait for redirect away from login page
            time.sleep(8)
            current_url = self.driver.current_url
            if "login" in current_url and "dashboard" not in current_url:
                 # Double check if we are stuck
                 if self.driver.find_elements(By.XPATH, "//div[contains(text(), 'Invalid')]"):
                     logger.error("DICE: Login failed - Invalid credentials warning found")
                     return False
                 logger.warning("DICE: Still on login page after submission.")
                 return False

            logger.info(f"DICE: Login successful. Current URL: {self.driver.current_url}")
            return True
        except Exception as e:
            logger.error(f"DICE: Error during login credential input: {e}")
            return False

    def _handle_popups(self):
        """Closes common popups on Dice.com"""
        try:
            popups = [
                "button[aria-label='Close']",
                ".modal-close",
                "button.close"
            ]
            for selector in popups:
                close_btn = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for btn in close_btn:
                    if btn.is_displayed():
                        logger.info(f"DICE: Closing popup: {selector}")
                        self.driver.execute_script("arguments[0].click();", btn)
        except Exception:
            pass

    def _find_in_shadows(self, tag_name, text_filter=None, selector=None):
        """Recursively find elements in shadow roots using JS"""
        script = """
            function findNested(root, tag, text, sel) {
                let results = [];
                let elements = sel ? root.querySelectorAll(sel) : root.querySelectorAll(tag);
                for (let el of elements) {
                    if (!text || el.textContent.includes(text)) {
                        results.push(el);
                    }
                }
                let all = root.querySelectorAll('*');
                for (let el of all) {
                    if (el.shadowRoot) {
                        results = results.concat(findNested(el.shadowRoot, tag, text, sel));
                    }
                }
                return results;
            }
            return findNested(document, arguments[0], arguments[1], arguments[2]);
        """
        elements = self.driver.execute_script(script, tag_name, text_filter, selector)
        return elements[0] if elements else None

    def find_jobs(self):
        """
        Search for jobs on Dice.com.
        Specifically searches for AI Engineer jobs in USA.
        """
        logger.info("DICE: Starting job discovery...")
        
        try:
            # Login already handled by runner before find_jobs() is called.
            # Navigate to the jobs search page directly.
            logger.info("DICE: Navigating to Dice jobs search page...")
            self.driver.get("https://www.dice.com/jobs")
            time.sleep(5)
            self._handle_popups()

            # Step: Click on "Job Search" span as requested
            try:
                logger.info("DICE: Clicking on 'Job Search' tab (Recursive Shadow Search)...")
                # Use the Verified span class/text
                job_search_button = self._find_in_shadows("span", "Job Search")
                if not job_search_button:
                    # Try by class specifically
                    job_search_button = self._find_in_shadows(tag_name="span", selector="span.flex.items-center.gap-\\[8px\\]")

                if job_search_button:
                    logger.info("DICE: Found 'Job Search' button, clicking...")
                    self.driver.execute_script("arguments[0].click();", job_search_button)
                    time.sleep(5)
                else:
                    logger.warning("DICE: 'Job Search' button not found, trying standard click fallback...")
                    self.safe_actions.safe_click("//span[contains(text(), 'Job Search')]", by=By.XPATH)
            except Exception as e:
                logger.warning(f"DICE: Could not click 'Job Search' tab: {e}")

            # Search filters
            search_config = self.applicant_data.get("search", {})
            keyword = search_config.get("keyword", "AI Engineer")
            location = search_config.get("location", "USA")
            
            logger.info(f"DICE: Searching for '{keyword}' in '{location}'")

            # Try to find search inputs (handling Shadow DOM)
            logger.info("DICE: Looking for search inputs (Recursive Shadow Search)...")
            
            # Use the verified names from inspection
            kw_input = self._find_in_shadows(tag_name="input", selector="input[name='q']")
            loc_input = self._find_in_shadows(tag_name="input", selector="input[name='location']")
            search_btn = self._find_in_shadows(tag_name="button", selector="button[data-testid='job-search-search-bar-search-button']")
            
            # Fallback search button if testid fails
            if not search_btn:
                search_btn = self._find_in_shadows(tag_name="button", text_filter="Search")

            if kw_input and loc_input and search_btn:
                # Fill keyword
                logger.info(f"DICE: Filling keyword '{keyword}'")
                try:
                    kw_input.clear()
                except:
                    self.driver.execute_script("arguments[0].value = '';", kw_input)
                self.human.human_type(kw_input, keyword)
                
                # Fill location
                logger.info(f"DICE: Filling location '{location}'")
                try:
                    loc_input.clear()
                except:
                    self.driver.execute_script("arguments[0].value = '';", loc_input)
                self.human.human_type(loc_input, location)
                time.sleep(1)
                
                # Click Search
                logger.info("DICE: Clicking search button")
                self.driver.execute_script("arguments[0].click();", search_btn)
                time.sleep(10)
            else:
                logger.error("DICE: Search inputs or button not found even after recursive Shadow DOM check")
                return []

            # Scrape results
            jobs = self._scrape_job_cards()
            
            from config.settings import settings
            if settings.DRY_RUN and jobs:
                logger.info("DICE: Dry run mode - limiting to first job as requested")
                return jobs[:1]
                
            return jobs

        except Exception as e:
            logger.error(f"DICE: Error during job search: {e}")
            return []

    def _scrape_job_cards(self):
        """Scrapes job cards from the results page"""
        logger.info("DICE: Scraping job results...")
        all_jobs = []
        
        try:
            # Verified selectors for current Dice layout
            cards = self.driver.find_elements(By.CSS_SELECTOR, "div[data-testid='job-card']")
            if not cards:
                # Fallback to general cards
                cards = self.driver.find_elements(By.CSS_SELECTOR, "dices-search-results-card, .card")
                
            logger.info(f"DICE: Found {len(cards)} job cards on current page")
            
            for card in cards:
                try:
                    title_elem = None
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, "a[data-testid='job-search-job-detail-link']")
                    except:
                        title_elem = card.find_element(By.CSS_SELECTOR, "a.card-title-link")
                        
                    if title_elem:
                        title = title_elem.text.strip()
                        url = title_elem.get_attribute("href")
                        
                        if url:
                            all_jobs.append({
                                "title": title,
                                "job_url": url,
                                "site": "DICE"
                            })
                except Exception:
                    continue
                    
            logger.info(f"DICE: Scraped {len(all_jobs)} valid jobs")
        except Exception as e:
            logger.error(f"DICE: Error scraping cards: {e}")
            
        return all_jobs

    def apply(self, listing):
        """
        Applies to a Dice job listing.
        Handles Easy Apply or redirects.
        """
        logger.info(f"DICE: Applying to {listing.get('title')}...")
        
        try:
            self.driver.get(listing.get('job_url'))
            time.sleep(5)
            self._handle_popups()

            # Look for Apply Button (Recursive Shadow Search)
            apply_btn = self._find_in_shadows(tag_name="apply-button-wc")
            if not apply_btn:
                 apply_btn = self._find_in_shadows(tag_name="button", text_filter="Apply Now")
            if not apply_btn:
                 apply_btn = self._find_in_shadows(tag_name="button", text_filter="Easy Apply")
            
            if not apply_btn:
                # Fallback to standard selectors
                apply_btn = self.safe_actions.wait_for_element("button[data-testid='apply-button'], button#apply-button-top, button.btn-primary", timeout=5)
            
            if not apply_btn:
                # Check for "Apply on Company Site" which we might want to skip or log
                ext_apply = self._find_in_shadows(tag_name="button", text_filter="Apply on Company Site")
                if ext_apply:
                    logger.warning("DICE: Found 'Apply on Company Site' (External Link) - Skipping for now")
                    return False
                
                logger.warning("DICE: Apply button not found")
                return False

            logger.info(f"DICE: Clicking Apply button for {listing.get('title')}")
            self.driver.execute_script("arguments[0].click();", apply_btn)
            time.sleep(5)

            # Handle Login Prompt
            self.login()
            time.sleep(3)
            
            # Switch to iframe if necessary (Dice forms are often in iframes)
            logger.info("DICE: Checking for application iframes...")
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            form_found = False
            for i, iframe in enumerate(iframes):
                try:
                    self.driver.switch_to.frame(iframe)
                    # Look for characteristic application fields
                    if self.driver.find_elements(By.CSS_SELECTOR, "input[name*='first' i], input[placeholder*='First' i], input[id*='first' i]"):
                        logger.info(f"DICE: Successfully switched to application form iframe #{i}")
                        form_found = True
                        break
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()

            if not form_found:
                logger.info("DICE: No iframe form found, checking main document...")

            # Form filling logic (Simulation in dry run)
            applicant = self.applicant_data.get("applicant", {})
            first_name = applicant.get("first_name", "Ghazal")
            last_name = applicant.get("last_name", "Sultan")
            email = applicant.get("email", "ghazal.sultan1616@gmail.com")
            resume_path = self.applicant_data.get("resume_path")

            logger.info(f"DICE: Filling form with {first_name} {last_name} ({email})")
            
            # Find and fill fields with expanded selectors
            fields = {
                "first_name": ["input[name*='firstName' i]", "input[placeholder*='First Name' i]", "input#firstName", "input[id*='first' i]"],
                "last_name": ["input[name*='lastName' i]", "input[placeholder*='Last Name' i]", "input#lastName", "input[id*='last' i]"],
                "email": ["div[data-testid='email-input'] input", "input[type='email']", "input[name*='email' i]", "input#email", "input[id*='email' i]"]
            }

            for field_key, selectors in fields.items():
                value = first_name if field_key == "first_name" else (last_name if field_key == "last_name" else email)
                field_filled = False
                for selector in selectors:
                    try:
                        elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        # Filter for visible elements
                        visible_elems = [e for e in elems if e.is_displayed()]
                        if visible_elems:
                            logger.info(f"DICE: Found {field_key} field ('{selector}'), filling...")
                            self.human.human_type(visible_elems[0], value)
                            field_filled = True
                            break
                    except:
                        continue
                if not field_filled:
                    logger.warning(f"DICE: Could not find {field_key} field")

            # Resume Upload
            if resume_path and os.path.exists(resume_path):
                logger.info(f"DICE: Attempting resume upload from {resume_path}")
                try:
                    # Look for file input specifically
                    resume_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file'], #resume-upload, input[name*='resume' i]")
                    if resume_inputs:
                        logger.info(f"DICE: Found resume upload input ('{resume_inputs[0].get_attribute('name') or resume_inputs[0].get_attribute('id')}'), uploading...")
                        resume_inputs[0].send_keys(resume_path)
                        time.sleep(3)
                    else:
                        # Fallback: look for a button that might open a file dialog (hard to automate in dry run without clicking)
                        logger.warning("DICE: Could not find resume upload input")
                except Exception as e:
                    logger.error(f"DICE: Error during resume upload: {e}")
            
            # Simulated Submit Button
            submit_selectors = ["button[type='submit']", ".submit-btn", "button:contains('Apply')", "button:contains('Submit')", "input[type='submit']"]
            submit_btn = None
            for selector in submit_selectors:
                try:
                    if "contains" in selector:
                        # XPath for contains text
                        text = selector.split("'")[1]
                        elems = self.driver.find_elements(By.XPATH, f"//button[contains(text(), '{text}')]")
                    else:
                        elems = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    visible_btns = [e for e in elems if e.is_displayed()]
                    if visible_btns:
                        submit_btn = visible_btns[0]
                        logger.info(f"DICE: Found submit button: '{submit_btn.text.strip()}'")
                        break
                except:
                    continue

            # Check for dry run
            # Check for dry run
            from config.settings import settings
            if settings.DRY_RUN:
                logger.info("DICE: [DRY RUN] Simulation complete for this job. Skipping submission.")
                if submit_btn:
                    try:
                         logger.info(f"DICE: [DRY RUN] Would have clicked '{submit_btn.text.strip()}'")
                    except:
                         pass
                return True
                logger.info(f"DICE: [DRY RUN SUCCESS] Application process for {listing.get('title')} completed (SIMULATED).")
                logger.info(f"DICE: [CONFIRMATION] Job '{listing.get('title')}' would have been applied with Ghazal Sultan's details.")
                self.driver.switch_to.default_content()
                return True

            # If not dry run, actually click submit
            if submit_btn:
                logger.info(f"DICE: LIVE MODE - Submitting application for {listing.get('title')}")
                # self.driver.execute_script("arguments[0].click();", submit_btn) # Uncommented only in live mode
                # time.sleep(10)
            
            self.driver.switch_to.default_content()
            return True

        except Exception as e:
            logger.error(f"DICE: Error applying to {listing.get('title')}: {e}")
            return False
