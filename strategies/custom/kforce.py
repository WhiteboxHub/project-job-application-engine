import os
import random
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.captcha_handler import CaptchaHandler
from core.human_behavior import HumanBehavior
from core.logger import logger
from core.safe_actions import SafeActions
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from models.history_models import Application
from strategies.base import BaseStrategy


class KForceStrategy(BaseStrategy):
    """
    KForce automation strategy.

    Features:
    - Custom job search parsing
    - Human-like form filling
    - Guest application support
    """
    use_single_phase = True

    def __init__(
        self, driver, job_site, selectors, db_session=None, candidate_data=None
    ):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.use_single_phase = True
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
            logger.info("[OK] KForce: Database session available")
        else:
            logger.warning(
                "[WARNING] KForce: No database session - strategy may fail if selectors not pre-loaded"
            )

    def _load_selectors(self):
        """
        Loads selectors directly from the database configuration.
        No hardcoded fallbacks allowed here anymore.
        """
        listing = self.selectors.get("listing", {})
        application = self.selectors.get("application", {})

        if not listing or not application:
            logger.error("[ERROR] KForce: Missing critical selectors in database!")
            # We still return the dict, but major methods should check for keys

        return {"listing": listing, "application": application}

    def _by(self, selector):
        """
        Auto-detect locator strategy: XPath if selector starts with '/' or '(',
        otherwise use CSS_SELECTOR.
        Returns a (By, selector) tuple for use in WebDriverWait / find_element.
        """
        if selector and (selector.startswith("/") or selector.startswith("(")):
            return (By.XPATH, selector)
        return (By.CSS_SELECTOR, selector)

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
                msg = (
                    f"[ERROR] KForce: Critical selector '{key}'"
                    + (f"['{subkey}']" if subkey else "")
                    + f" missing in database '{category}' config!"
                )
                logger.error(msg)
                raise RuntimeError(msg)
            return None

        return val

    def _load_config(self):
        """Return dynamically injected candidate data."""
        if self.candidate_data is not None:
            logger.info("Using dynamically injected candidate_data")
            return self.candidate_data
        logger.error("No candidate_data was injected into the strategy.")
        return {}

    def login(self):
        """KForce typically allows guest browsing/applications."""
        logger.info("KForce: Checking login requirements...")
        return True

    def find_and_apply_jobs(self):
        """
        Two-phase workflow:
          Phase 1 — Collect all unique job listings across all keywords.
          Phase 2 — Apply to each collected job sequentially.
        Returns the number of successful applications.
        """
        logger.info("[SEARCH] KForce: Starting two-phase find-and-apply workflow")

        # STRICTION: Use ONLY keywords from run_parameters (Whitebox API)
        _search = self.config_data.get("search", {})
        keywords = _search.get("keywords")
        
        if not keywords:
            logger.error(
                "[ERROR] KForce: No keywords found in run_parameters (search.keywords)! "
                "Ensure Whitebox API is sending keywords."
            )
            return 0

        logger.info(f"  [STATS] Using {len(keywords)} keyword(s): {keywords}")

        # ── PHASE 1: Collect all jobs ──────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: Discovering all jobs across all keywords...")
        logger.info("=" * 60)

        all_listings = []
        seen_urls = set()

        for keyword in keywords:
            logger.info(f"\n[SEARCH] Executing Portal Search: '{keyword}'")
            listings = self._perform_search(keyword, all_keywords=keywords)

            new_count = 0
            for listing in listings:
                url = listing.get("job_url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_listings.append(listing)
                    new_count += 1
                else:
                    logger.debug(f"  Duplicate skipped: {listing.get('job_title')}")

            logger.info(
                f"  [+] {new_count} new jobs added (total so far: {len(all_listings)})"
            )

        logger.info(
            f"\n[OK] Phase 1 complete. Found {len(all_listings)} unique jobs total."
        )
        
        from core.execution_logger import execution_tracker
        execution_tracker.add_jobs_found(len(all_listings))

        # ── PHASE 2: Apply to each job ─────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info(f"PHASE 2: Applying to {len(all_listings)} jobs...")
        logger.info("=" * 60)

        total_applied = 0
        for i, listing in enumerate(all_listings, 1):
            logger.info(
                f"\n[{i}/{len(all_listings)}] Applying to: {listing.get('job_title')}"
            )
            if self.apply(listing):
                total_applied += 1
                logger.info(f"  [YES] Applied! ({total_applied} successful so far)")
                time.sleep(
                    random.uniform(2, 4)
                )  # Human-like pause between applications

        logger.info(
            f"\n[OK] Phase 2 complete. Total applications submitted: {total_applied}/{len(all_listings)}"
        )
        return total_applied

    def find_jobs(self):
        """
        Legacy discovery-only method.
        Maintained for backward compatibility, though Runner now prefers find_and_apply_jobs.
        """
        logger.info("KForce: Starting job discovery phase...")

        keywords = self.config_data.get("keywords", ["AI Engineer"])
        location = None

        all_listings = []
        seen_urls = set()

        for keyword in keywords:
            logger.info(f"\n{'=' * 60}")
            logger.info(f"[SEARCH] KForce Search: {keyword} (Location: {location})")
            logger.info(f"{'=' * 60}")

            listings = self._perform_search(keyword, location)

            # De-duplicate results across different search iterations
            new_jobs = 0
            for listing in listings:
                url = listing.get("job_url")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_listings.append(listing)
                    new_jobs += 1
                else:
                    logger.debug(
                        f"KForce: Skipping duplicate job: {listing.get('job_title')}"
                    )

            logger.info(f"KForce: Added {new_jobs} unique jobs from this search")

            # Delay between searches
            if len(keywords) > 1:
                time.sleep(random.uniform(2, 4))

        logger.info(
            f"KForce: Finished discovery. Total unique jobs to process: {len(all_listings)}"
        )
        return all_listings

    def _perform_search(self, keyword, location=None, all_keywords=None):
        """Internal method for a single optimized search iteration."""

        # Database-provided selectors — 'search_button' is the correct DB key
        db_input = self.get_sel("listing", "search_input", required=False)
        # DB key is 'search_button', fallback to the known XPath from the site
        db_button = (
            self.get_sel("listing", "search_button", required=False)
            or "//*[@id='site-content']/div/section/div[2]/div/div/div[2]/form/div/div[3]/div/input"
        )

        INPUT_SELECTORS = [db_input] if db_input else [
            "input[id*='keyword' i]",
            "input[placeholder*='search' i]",
            "input[type='text']:first-of-type",
        ]
        BUTTON_SELECTORS = [db_button] if db_button else [
            "button[type='submit']",
            "button[class*='search' i]",
            "input[type='submit']",
        ]
        LINK_SELECTORS = [
            "a[href*='/candidate/jobs/'],",
            "a[href*='/find-work/'][href*='job']",
            "a[class*='job-title' i]",
            "a[class*='title' i][href*='job']",
            "h4 > a, h3 > a, h2 > a",
        ]

        def _find_first(selectors, timeout=4):
            """Return the first element found from a list of selectors."""
            for sel in selectors:
                if not sel: continue
                try:
                    el = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located(self._by(sel)) # use _by for DB xpath support
                    )
                    return el, sel
                except Exception:
                    continue
            return None, None

        try:
            # Only navigate to search URL on the FIRST keyword or if we aren't on it
            search_url = "https://www.kforce.com/find-work/search-jobs/"
            if search_url not in self.driver.current_url:
                logger.info(f"KForce: Navigating to {search_url}")
                self.driver.get(search_url)
                time.sleep(4)
            else:
                logger.info("KForce: Already on search page, performing next search inplace.")

            # Try to find and fill the search input
            input_el, used_sel = _find_first(INPUT_SELECTORS, timeout=5)
            if input_el:
                logger.info(f"KForce: Found search input via '{used_sel}'")
                
                # Use JS clear + Native send_keys for stability across searches
                try:
                    self.human.human_click(input_el)
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].value = '';", input_el) # Force clear
                    input_el.clear() # Standard clear
                    input_el.send_keys(keyword)
                    logger.info(f"  [YES] Entered keyword: {keyword}")
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"  [ERROR] Failed to fill search box: {e}")
            else:
                # Fallback: navigate directly to search URL with query param
                encoded = keyword.replace(" ", "+")
                fallback_url = f"https://www.kforce.com/find-work/search-jobs/?keyword={encoded}&location=United+States"
                logger.warning(
                    f"  [WARNING] Could not find search input — navigating to URL: {fallback_url}"
                )
                self.driver.get(fallback_url)
                time.sleep(4)

            # Try to click search button explicitly as requested by user
            btn_el, _ = _find_first(BUTTON_SELECTORS, timeout=3)
            if btn_el:
                try:
                    # Scroll to button and click
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn_el)
                    time.sleep(0.5)
                    self.human.human_click(btn_el)
                    logger.info("  [YES] Clicked search button")
                    time.sleep(5) # Wait for search results
                except Exception as be:
                    logger.debug(f"KForce: Button click failed: {be}")
            else:
                logger.info("  [INFO] No search button found, pressing ENTER instead")
                try:
                    from selenium.webdriver.common.keys import Keys
                    if input_el:
                        input_el.send_keys(Keys.RETURN)
                        logger.info("  [YES] Pressed ENTER to search")
                        time.sleep(5)
                except Exception:
                    time.sleep(3)

            # 1. Sort by Newest
            try:
                logger.info("  [INFO] Sorting by Newest")
                sort_dropdown = None
                dropdown_xpaths = [
                    '//*[@id="react-select-12--value"]/div[1]',
                    '//*[@id="react-select-12--value-item"]',
                    '//*[@id="react-select-3--value"]/div[1]',
                    '//*[@id="react-select-3--value-item"]'
                ]
                for xpath in dropdown_xpaths:
                    try:
                        sort_dropdown = WebDriverWait(self.driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        if sort_dropdown: break
                    except:
                        pass
                
                if sort_dropdown:
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", sort_dropdown)
                    self.human.human_click(sort_dropdown)
                    time.sleep(1)
                    
                    from selenium.webdriver.common.keys import Keys
                    from selenium.webdriver.common.action_chains import ActionChains
                    ac = ActionChains(self.driver)
                    ac.send_keys(Keys.ARROW_DOWN).pause(0.5).send_keys(Keys.RETURN).perform()
                    time.sleep(3)
                    logger.info("  [YES] Selected Newest sort option")
                else:
                    logger.warning("  [WARNING] Could not find the Newest dropdown element on screen")
            except Exception as e:
                logger.warning(f"  [WARNING] Could not sort by Newest: {e}")

            # 2. Extract listings using Load More
            all_keywords_lower = [kw.lower() for kw in (all_keywords or [keyword])]
            listings = []
            seen_urls = set()
            
            logger.info("  [INFO] Starting 'Load More' pagination engine...")
            import re
            from datetime import datetime
            
            # The Load More loop
            consecutive_failures = 0
            while consecutive_failures < 3:
                # Find the last job's date
                try:
                    last_date_el = self.driver.find_element(By.XPATH, '//*[@id="site-content"]/div/main/div/div/div/div[2]/ul/li[last()]/h2/span')
                    job_date_str = last_date_el.text.strip()
                    logger.info(f"    [DEBUG] Checking oldest loaded job date: '{job_date_str}'")
                    
                    match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", job_date_str)
                    if match:
                        job_date_parsed = datetime.strptime(match.group(1), "%m/%d/%Y")
                        days_old = (datetime.now() - job_date_parsed).days
                        
                        if days_old > 7:
                            logger.info(f"    [INFO] Reached jobs older than 7 days ({days_old}). Stopping engine.")
                            break
                    else:
                        logger.warning(f"    [WARNING] Could not parse date format: '{job_date_str}'")
                except Exception as e:
                    logger.debug(f"    [DEBUG] bottom job date error/missing")
                
                # Click Load More
                try:
                    load_more_btn = self.driver.find_element(By.XPATH, '//*[@id="site-content"]/div/main/div/div/div/div[2]/div[1]/p[2]/span')
                    if load_more_btn.is_displayed():
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", load_more_btn)
                        time.sleep(1)
                        self.human.human_click(load_more_btn)
                        logger.info("    [INFO] Clicked 'Load More' button")
                        time.sleep(3) # Wait for new jobs to load
                        consecutive_failures = 0
                    else:
                        logger.info("    [INFO] 'Load More' button is not visible. End of list.")
                        break
                except Exception as e:
                    logger.info(f"    [INFO] 'Load More' button vanishing. End of list.")
                    consecutive_failures += 1
                    time.sleep(2)

            # 3. Read ALL loaded job cards and filter them
            logger.info("  [INFO] Extracting and filtering all loaded jobs...")
            try:
                job_cards = self.driver.find_elements(By.XPATH, '//*[@id="site-content"]/div/main/div/div/div/div[2]/ul/li')
                logger.info(f"  [INFO] Found {len(job_cards)} total job cards on screen")
                
                for card in job_cards:
                    try:
                        title_el = card.find_element(By.CSS_SELECTOR, "h3 > a, a[class*='job-title' i], a[class*='title' i]")
                    except:
                        try:
                            title_el = card.find_element(By.XPATH, ".//a")
                        except:
                            continue
                            
                    title = title_el.text.strip()
                    url = title_el.get_attribute("href") or ""
                    
                    if not title or not url or url in seen_urls:
                        continue
                        
                    # Title filter check
                    if any(kw.lower() in title.lower() for kw in all_keywords_lower):
                        
                        # Verify Date limit check on individual card
                        days_old = 0
                        try:
                            date_el = card.find_element(By.XPATH, ".//h2/span")
                            date_str = date_el.text.strip()
                            match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", date_str)
                            if match:
                                job_date_parsed = datetime.strptime(match.group(1), "%m/%d/%Y")
                                days_old = (datetime.now() - job_date_parsed).days
                        except:
                            pass
                            
                        if days_old <= 7:
                            seen_urls.add(url)
                            external_id = url.rstrip("/").split("/")[-1] or "unknown"
                            listings.append({"job_title": title, "job_url": url, "external_id": external_id})
                            
            except Exception as e:
                logger.error(f"  [ERROR] Failed to extract job cards: {e}")

            if listings:
                logger.info(
                    f"KForce: Found {len(listings)} job(s) for keyword '{keyword}'"
                )
                csv_tracker.add_discovered_jobs("kforce", listings)
            else:
                logger.warning(
                    f"KForce: No jobs found for '{keyword}'  selectors may need updating for current site layout"
                )

            return listings

        except Exception as e:
            logger.error(f"KForce: Error during search for {keyword}: {e}")
            return []

    def apply(self, listing):
        """
        Apply to a specific job listing.
        """
        # Support both dictionary and object (JobListing) inputs
        if isinstance(listing, dict):
            job_title = listing.get("job_title", "Unknown Title")
            job_url = listing.get("job_url")
            external_id = listing.get("external_id", "unknown")
        else:
            job_title = getattr(listing, "job_title", "Unknown Title")
            job_url = getattr(listing, "job_url", None)
            external_id = getattr(listing, "external_job_id", "unknown")

        logger.info(f"KForce: Applying to {job_title} ({external_id})...")

        if not job_url:
            logger.error("KForce: No job URL provided")
            return False

        # Build a unified applicant dict:
        # Priority 1: top-level fields from run_parameters
        # Priority 2: flat 'applicant' sub-dict
        # Priority 3: applicant.address (where state/zip live in run_parameters)
        _applicant_raw = self.config_data.get("applicant", {})
        _address = _applicant_raw.get("address", {})
        applicant = {
            "first_name": (
                self.config_data.get("first_name")
                or _applicant_raw.get("first_name")
            ),
            "last_name": (
                self.config_data.get("last_name")
                or _applicant_raw.get("last_name")
            ),
            "email": (
                self.config_data.get("email")
                or _applicant_raw.get("email")
            ),
            "phone": (
                self.config_data.get("phone")
                or _applicant_raw.get("phone")
            ),
            # state lives inside applicant.address in run_parameters
            "state": (
                self.config_data.get("state")
                or _applicant_raw.get("state")
                or _address.get("state")
            ),
            # zip_code lives inside applicant.address in run_parameters
            # Fallback to "75034" (Frisco, TX) when backend sends null
            "zip_code": (
                self.config_data.get("zip_code")
                or _applicant_raw.get("zip_code")
                or _address.get("zip_code")
                or "75034"
            ),
            "country": (
                self.config_data.get("country")
                or _applicant_raw.get("country")
                or _address.get("country", "United States")
            ),
        }
        apply_initiator = self.get_sel("application", "apply_initiator")

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
                    if attempt == 1:
                        raise
                    logger.warning(f"Navigation to {job_url} failed, retrying... ({e})")
                    time.sleep(5)

            time.sleep(3)

            # 2. Click 'Apply Now' button
            logger.info("KForce [Step 2]: Searching for Apply initiator")
            initiator = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(self._by(apply_initiator))
            )
            logger.info("  [YES] Found initiator, clicking...")
            self.human.human_click(initiator)
            time.sleep(2)

            # 3. Click 'Apply Today' dropdown option (KForce specific)
            logger.info("KForce [Step 3]: Searching for 'Apply Today' dropdown option")
            apply_link_sel = self.get_sel("application", "apply_link_option")
            apply_link = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable(self._by(apply_link_sel))
            )
            logger.info("  [YES] Found dropdown option, clicking...")
            self.human.human_click(apply_link)

            # 1. Page Initialization
            first_field_sel = self.get_sel("application", "form_fields", "first_name")
            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located(self._by(first_field_sel))
            )
            logger.info("KForce: Application form loaded")
            time.sleep(2)  # Buffer delay to stabilize React

            # 2. Cookie Banner Handling
            try:
                cookie_selectors = [
                    "button#onetrust-accept-btn-handler",
                    "button[class*='cookie'][class*='accept']",
                    "//*[contains(text(), 'Accept') or contains(text(), 'Agree') or contains(text(), 'Allow')]"
                ]
                for sel in cookie_selectors:
                    by_type = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                    btn = self.driver.find_elements(by_type, sel)
                    if btn and btn[0].is_displayed():
                        logger.info("KForce [Step 2]: Clicking Cookie Banner Accept...")
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn[0])
                        time.sleep(0.5)
                        btn[0].click()
                        time.sleep(1)
                        break
            except Exception as e:
                logger.debug(f"Cookie banner handling skipped: {e}")

            # 3. Text Fields (First, Last, Email)
            fields_map = {
                "first_name": applicant.get("first_name"),
                "last_name":  applicant.get("last_name"),
                "email":      applicant.get("email"),
                "email_verify": applicant.get("email")
            }

            for field, value in fields_map.items():
                logger.info(f"KForce [Step 3]: Filling '{field}' = '{value}'")
                selector = self.get_sel("application", "form_fields", field)
                if not selector or not value:
                    continue
                try:
                    el = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable(self._by(selector))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                    time.sleep(0.3)
                    el.click()
                    time.sleep(0.3)
                    
                    from selenium.webdriver.common.keys import Keys
                    el.send_keys(Keys.CONTROL + "a")
                    el.send_keys(Keys.BACKSPACE)
                    time.sleep(0.3)
                    
                    el.send_keys(str(value))
                    time.sleep(0.5)
                    # Verify
                    if el.get_attribute("value") != str(value):
                        logger.warning(f"  [WARNING] send_keys failed for {field}, dispatching React event fallback")
                        self.driver.execute_script(
                            """
                            var niv = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            if(niv) {
                                niv.call(arguments[0], arguments[1]);
                                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                            }
                            """, el, str(value)
                        )
                except Exception as e:
                    logger.error(f"  [ERROR] Failed to fill {field}: {e}")

            # 4. Country Dropdown
            country_val = applicant.get("country", "United States")
            country_selector = self.get_sel("application", "form_fields", "country", required=False)
            if country_val and country_selector:
                logger.info(f"KForce [Step 4]: Filling Country = '{country_val}'")
                try:
                    country_dropdown = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable(self._by(country_selector))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", country_dropdown)
                    time.sleep(0.5)
                    from selenium.webdriver.support.ui import Select
                    try:
                        select = Select(country_dropdown)
                        select.select_by_visible_text(country_val)
                    except Exception:
                        country_dropdown.click()
                        time.sleep(0.5)
                        from selenium.webdriver.common.action_chains import ActionChains
                        from selenium.webdriver.common.keys import Keys
                        ac = ActionChains(self.driver)
                        ac.send_keys(country_val).pause(0.5).send_keys(Keys.RETURN).perform()
                    logger.info(f"  [YES] Country set: {country_val}")
                    time.sleep(0.5)
                except Exception as ce:
                    logger.warning(f"  [WARNING] Could not set country: {ce}")

            # 5. Phone Number (Masked Input)
            raw_phone = str(applicant.get("phone", ""))
            import re
            phone_digits = re.sub(r'\D', '', raw_phone)
            phone_selector = self.get_sel("application", "form_fields", "phone", required=False)
            if phone_selector and phone_digits:
                logger.info(f"KForce [Step 5]: Filling Phone Number")
                for attempt in range(2):
                    try:
                        el = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable(self._by(phone_selector))
                        )
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                        time.sleep(0.5)
                        el.click()
                        time.sleep(0.3)
                        # Clear field comprehensively
                        from selenium.webdriver.common.keys import Keys
                        el.send_keys(Keys.CONTROL + "a")
                        el.send_keys(Keys.BACKSPACE)
                        time.sleep(0.5)
                        
                        if attempt == 0:
                            # Primary: slow typing
                            for digit in phone_digits:
                                el.send_keys(digit)
                                time.sleep(random.uniform(0.1, 0.3))
                        else:
                            # Fallback: formatted inject
                            formatted_phone = ""
                            if len(phone_digits) >= 10:
                                formatted_phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:10]}"
                            else:
                                formatted_phone = phone_digits
                            logger.info(f"  [INFO] Attempting fallback format: {formatted_phone}")
                            el.send_keys(formatted_phone)
                        
                        time.sleep(0.8)
                        current_val = el.get_attribute("value")
                        if current_val and len(re.sub(r'\D', '', current_val)) >= 10:
                            logger.info(f"  [YES] Phone typed successfully: {current_val}")
                            break
                        else:
                            logger.warning(f"  [WARNING] Phone typed incorrectly: '{current_val}', retrying...")
                    except Exception as e:
                        logger.error(f"  [ERROR] Phone fill failed: {e}")

            # 6. State Dropdown (React Select)
            state_val = applicant.get("state")
            state_selector = self.get_sel("application", "form_fields", "state")
            if state_val and state_selector:
                logger.info(f"KForce [Step 6]: Filling State = '{state_val}'")
                for attempt in range(2):
                    try:
                        state_dropdown = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable(self._by(state_selector))
                        )
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", state_dropdown)
                        time.sleep(0.5)
                        
                        from selenium.webdriver.support.ui import Select
                        try:
                            # Primary DOM selection if it's actually a native select disguised
                            select = Select(state_dropdown)
                            select.select_by_visible_text(state_val)
                            logger.info(f"  [YES] State selected using native Select: {state_val}")
                            break
                        except Exception:
                            # Fallback React-Select ActionChains
                            state_dropdown.click()
                            time.sleep(1)
                            from selenium.webdriver.common.action_chains import ActionChains
                            from selenium.webdriver.common.keys import Keys
                            ac = ActionChains(self.driver)
                            ac.send_keys(state_val).pause(0.5).send_keys(Keys.RETURN).perform()
                            time.sleep(1.5)
                            logger.info(f"  [YES] State selected via React-Select ActionChains: {state_val}")
                            break
                    except Exception as e:
                        logger.warning(f"  [WARNING] State selection attempt {attempt+1} failed: {e}")
            else:
                logger.warning("  [WARNING] Skipping state: missing value or selector")

            # 7. Zip Code
            zip_val = applicant.get("zip_code")
            zip_selector = self.get_sel("application", "form_fields", "zip_code")
            if zip_val and zip_selector:
                logger.info(f"KForce [Step 7]: Filling Zip Code = '{zip_val}'")
                try:
                    zip_el = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable(self._by(zip_selector))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", zip_el)
                    time.sleep(0.5)
                    zip_el.click()
                    time.sleep(0.3)
                    
                    from selenium.webdriver.common.keys import Keys
                    zip_el.send_keys(Keys.CONTROL + "a")
                    zip_el.send_keys(Keys.BACKSPACE)
                    time.sleep(0.3)
                    zip_el.send_keys(str(zip_val))
                    time.sleep(0.5)
                    logger.info(f"  [YES] Zip filled: {zip_val}")
                except Exception as ze:
                    logger.warning(f"  [WARNING] Zip fill failed: {ze}")
            else:
                logger.warning(f"  [WARNING] Skipping zip: val='{zip_val}' sel='{zip_selector}'")

            # 6. Upload Resume
            logger.info("KForce [Step 6]: Resolving resume path")
            resume_path = self.get_resume_path()
            resume_selector = self.get_sel(
                "application", "form_fields", "resume_upload"
            )

            if resume_path and resume_selector:
                logger.info(f"  [YES] Found resume: {os.path.basename(resume_path)}")
                try:
                    file_input = self.driver.find_element(*self._by(resume_selector))
                    # Unhide if necessary
                    self.driver.execute_script(
                        "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                        file_input,
                    )
                    file_input.send_keys(resume_path)
                    logger.info("  [YES] Resume attached successfully")
                except Exception as e:
                    logger.error(f"  [ERROR] Resume upload failed: {e}")
            else:
                logger.warning(
                    "  [WARNING] Skipping resume upload: path or selector missing"
                )

            # 7. Questionnaire / Eligibility Radios
            answers = self.selectors.get("application", {}).get(
                "questionnaire_answers", {}
            )
            for field, target_val in answers.items():
                logger.info(f"KForce [Step 7]: Handling questionnaire field '{field}'")
                selector = self.get_sel(
                    "application", "form_fields", field, required=False
                )
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
                            values_to_try.extend(["0", "False", "no"])

                        for v in values_to_try:
                            try:
                                radio = self.driver.find_element(
                                    By.CSS_SELECTOR, f"{selector}[value='{v}']"
                                )
                                self.driver.execute_script(
                                    "arguments[0].click();", radio
                                )
                                selected = True
                                break
                            except:
                                continue
                    except:
                        pass

                    if not selected:
                        # Fallback strings for common kforce labels
                        search_texts = [target_val]
                        if (
                            field == "eligibility_auth"
                            and target_val == "AuthorizedForAny"
                        ):
                            search_texts.append(
                                "I am authorized to work in the United States for any employer."
                            )

                        for txt in search_texts:
                            xpath_text = f"//label[contains(., '{txt}')] | //span[contains(., '{txt}')]"
                            elements = self.driver.find_elements(By.XPATH, xpath_text)
                            if elements:
                                self.driver.execute_script(
                                    "arguments[0].click();", elements[0]
                                )
                                selected = True
                                break

                    if not selected:
                        radio = self.driver.find_element(By.CSS_SELECTOR, selector)
                        self.driver.execute_script("arguments[0].click();", radio)
                        selected = True

                    if selected:
                        logger.info(f"  [YES] Selected '{target_val}' for {field}")
                except Exception as e:
                    logger.warning(f"  [WARNING] Could not handle {field}: {e}")

            # 8. Click 'Next' if it exists (Multi-step form support)
            next_sel = self.get_sel(
                "application", "form_fields", "next_btn", required=False
            )
            if next_sel:
                try:
                    # Try CSS first, then check if it's an XPath
                    if next_sel.startswith("//") or next_sel.startswith("("):
                        next_btns = self.driver.find_elements(By.XPATH, next_sel)
                    else:
                        next_btns = self.driver.find_elements(By.CSS_SELECTOR, next_sel)

                    if next_btns and next_btns[0].is_displayed():
                        logger.info("KForce: Clicking 'Next' button")
                        self.human.human_click(next_btns[0])
                        time.sleep(2)  # Wait for next step
                except Exception as e:
                    logger.debug(f"Next button not clickable/found: {e}")

            # 9. Submit (with Dry Run guard)
            submit_sel = self.get_sel("application", "form_fields", "submit_btn")
            if submit_sel:
                try:
                    submit_btn = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located(self._by(submit_sel))
                    )
                    # Visual Feedback: Scroll to button so user can see it
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                        submit_btn,
                    )
                    time.sleep(2)  # Pause so user can see the button

                    from engine.guards import guards

                    if guards.is_dry_run():
                        # Highlight button in dry run
                        self.driver.execute_script(
                            "arguments[0].style.border = '5px solid orange';",
                            submit_btn,
                        )
                        logger.info("\n" + "!" * 60)
                        logger.info("! DRY RUN SIMULATION: FOUND SUBMIT BUTTON")
                        logger.info(
                            "! NO REAL SUBMISSION WILL BE PERFORMED IN THIS MODE"
                        )
                        logger.info("!" * 60 + "\n")
                        self._record_application(
                            listing, job_url, job_title, "success", "Dry run simulation"
                        )
                        return True
                    else:
                        submit_btn = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable(self._by(submit_sel))
                        )
                        self.human.human_click(submit_btn)
                        logger.info(
                            "KForce: Application submitted, waiting for verification..."
                        )

                        # 9. Verify Submission
                        success = self._verify_submission()
                        if success:
                            self._record_application(
                                listing, job_url, job_title, "success"
                            )
                            return True
                        else:
                            raise Exception("Submission verification failed")
                except Exception as e:
                    if "Dry run simulation" in str(e):
                        return True  # Already handled
                    logger.error(f"Submit interaction failed: {e}")
                    raise

        except Exception as e:
            logger.error(f"KForce: Error applying to {job_title}: {e}")
            # Log page source on critical failure (first 1000 chars)
            try:
                logger.debug(f"Page content snippet: {self.driver.page_source[:1000]}")
            except:
                pass

            self._record_application(listing, job_url, job_title, "failed", str(e))
            return False

    def _verify_submission(self):
        """
        Verifies if the application was successfully submitted.
        Checks for confirmation text or URL redirection.
        """
        success_indicators = self.get_sel("application", "success_indicators")

        try:
            # Wait for content to change/load
            time.sleep(5)

            # 1. Check URL change (common in KForce/ATS)
            if (
                "Success" in self.driver.current_url
                or "confirmation" in self.driver.current_url.lower()
            ):
                logger.info("  [YES] Verified via URL redirection")
                return True

            # 2. Check page content
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            for indicator in success_indicators:
                if indicator.lower() in page_text.lower():
                    logger.info(
                        f"  [YES] Verified via confirmation text: '{indicator}'"
                    )
                    return True

            logger.warning(
                "  [WARNING] Submission verification could not find success indicators"
            )
            return False
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False

    def _record_application(self, listing, job_url, job_title, status, error=None):
        """Record application in DB and CSV"""
        from core.execution_logger import execution_tracker
        
        # safely extract external_id
        if isinstance(listing, dict):
            external_id = listing.get("external_id", "unknown")
        elif listing:
            external_id = getattr(listing, "external_job_id", "unknown")
        else:
            external_id = "unknown"
            
        if status == "success":
            execution_tracker.record_success("KForce", str(external_id), str(job_title), str(job_url))
        else:
            execution_tracker.record_error("KForce", str(external_id), str(job_title), str(job_url), str(error))

        # CSV Update
        csv_tracker.update_job_status(
            "kforce",
            job_url,
            "applied" if status == "success" else "failed",
            attempts_inc=1,
            last_error=error,
        )

        # Database Update
        if self.db_session:
            try:
                # Update listing status if it exists in DB
                db_listing = (
                    self.db_session.query(JobListing)
                    .filter(JobListing.job_url == job_url)
                    .first()
                )

                listing_id = None
                if db_listing:
                    db_listing.status = "applied" if status == "success" else "failed"
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
                    error_message=error,
                )
                self.db_session.add(app)
                # Retry commit in case of transient DuckDB locks
                for i in range(3):
                    try:
                        self.db_session.commit()
                        break
                    except Exception as commit_error:
                        if i == 2:
                            raise
                        logger.warning(
                            f"  [WARNING] Database commit failed (attempt {i + 1}), retrying... {commit_error}"
                        )
                        time.sleep(1)
                logger.info(
                    f"  [STATS] Application record saved to database ({status})"
                )
            except Exception as e:
                logger.error(f"Failed to record application in DB: {e}")
                self.db_session.rollback()