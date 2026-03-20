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

    def __init__(
        self, driver, job_site, selectors, db_session=None, candidate_data=None
    ):
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

        # Keywords come from the database (init_db.py seeds them)
        keywords = self.selectors.get("listing", {}).get("search_keywords")
        if not keywords:
            logger.error(
                "[ERROR] KForce: No 'search_keywords' found in database! Run init_db.py."
            )
            return 0

        logger.info(f"  [STATS] Using {len(keywords)} keyword(s) from database")

        # ── PHASE 1: Collect all jobs ──────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: Discovering all jobs across all keywords...")
        logger.info("=" * 60)

        all_listings = []
        seen_urls = set()

        for keyword in keywords:
            logger.info(f"\n[SEARCH] Keyword: '{keyword}'")
            listings = self._perform_search(keyword)

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

            # Human-like pause between searches
            if len(keywords) > 1:
                time.sleep(random.uniform(3, 6))

        logger.info(
            f"\n[OK] Phase 1 complete. Found {len(all_listings)} unique jobs total."
        )

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

    def _perform_search(self, keyword, location=None):
        """Internal method for a single search iteration  uses multi-fallback selectors."""

        # Database-provided selectors with fallbacks (make optional to avoid crash)
        db_input = self.get_sel("listing", "search_input", required=False)
        db_button = self.get_sel("listing", "search_btn", required=False)

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

            # Extract job links from results
            listings = []
            seen_urls = set()
            for sel in LINK_SELECTORS:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for link in links:
                        url = link.get_attribute("href") or ""
                        title = link.text.strip()
                        if not url or not title or url in seen_urls:
                            continue
                        if "kforce.com" not in url and not url.startswith("/"):
                            continue
                        seen_urls.add(url)
                        external_id = url.rstrip("/").split("/")[-1] or "unknown"
                        listings.append(
                            {
                                "job_title": title,
                                "job_url": url,
                                "external_id": external_id,
                            }
                        )
                except Exception:
                    continue

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
        # Priority 1: top-level fields from run_parameters (set by backend/CandidateLoader)
        # Priority 2: the flat 'applicant' sub-dict (from guest_form_data.json)
        _applicant_raw = self.config_data.get("applicant", {})
        applicant = {
            "first_name":  self.config_data.get("first_name")  or _applicant_raw.get("first_name"),
            "last_name":   self.config_data.get("last_name")   or _applicant_raw.get("last_name"),
            "email":       self.config_data.get("email")       or _applicant_raw.get("email"),
            "phone":       self.config_data.get("phone")       or _applicant_raw.get("phone"),
            # Backend puts state and zip_code at the top level of the JSON
            "zip_code":    self.config_data.get("zip_code")    or _applicant_raw.get("zip_code"),
            "state":       self.config_data.get("state")       or _applicant_raw.get("state"),
            "country":     self.config_data.get("country")     or _applicant_raw.get("country", "United States"),
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

            # Wait for application form to load
            first_field_sel = self.get_sel("application", "form_fields", "first_name")
            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located(self._by(first_field_sel))
            )
            logger.info("KForce: Application form loaded")

            # 4. Fill personal details
            # KForce uses React-controlled inputs. Plain send_keys / clear() don't
            # trigger React's state — we must set the native value via JS and then
            # dispatch an 'input' event so React re-syncs.
            def _fill_react_field(sel, value):
                """Set value on a React-controlled input field."""
                if not sel or not value:
                    logger.warning(f"  [SKIP] Missing selector or value for field")
                    return
                try:
                    el = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(self._by(sel))
                    )
                    self.driver.execute_script(
                        """
                        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value').set;
                        nativeInputValueSetter.call(arguments[0], arguments[1]);
                        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        el, str(value)
                    )
                    time.sleep(random.uniform(0.4, 0.8))
                    logger.info(f"    [YES] Filled via JS React-compatible method")
                except Exception as e:
                    logger.warning(f"  [WARNING] JS fill failed, trying send_keys: {e}")
                    try:
                        el = self.driver.find_element(*self._by(sel))
                        el.clear()
                        el.send_keys(str(value))
                        time.sleep(0.4)
                    except Exception as e2:
                        logger.error(f"  [ERROR] send_keys fallback also failed: {e2}")

            fields_map = {
                "first_name": applicant.get("first_name"),
                "last_name":  applicant.get("last_name"),
                "email":      applicant.get("email"),
                "email_verify": applicant.get("email"),
                "phone":      applicant.get("phone"),
            }

            for field, value in fields_map.items():
                logger.info(f"KForce [Step 4]: Filling '{field}' = '{value}'")
                selector = self.get_sel("application", "form_fields", field)
                _fill_react_field(selector, value)


            # 5. Handle State dropdown — slow, explicit, scroll first
            state_val = applicant.get("state")
            state_selector = self.get_sel("application", "form_fields", "state")
            zip_val = applicant.get("zip_code")
            zip_selector = self.get_sel("application", "form_fields", "zip_code")
            
            logger.info("=" * 50)
            logger.info(f"[DEBUG] State Value Resolves To: '{state_val}'")
            logger.info(f"[DEBUG] State Selector: '{state_selector}'")
            logger.info(f"[DEBUG] Zip Value Resolves To: '{zip_val}'")
            logger.info(f"[DEBUG] Zip Selector: '{zip_selector}'")
            logger.info("=" * 50)

            logger.info(f"KForce [Step 5]: Filling state = '{state_val}'")
            if state_val and state_selector:
                try:
                    state_dropdown = WebDriverWait(self.driver, 15).until(
                        EC.element_to_be_clickable(self._by(state_selector))
                    )
                    # Scroll to element so it's visible
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", state_dropdown
                    )
                    time.sleep(1)

                    from selenium.webdriver.support.ui import Select
                    select = Select(state_dropdown)

                    selected = False
                    # Strategy 1: visible text exact match
                    try:
                        select.select_by_visible_text(state_val)
                        selected = True
                        logger.info(f"  [YES] State selected by text: {state_val}")
                    except Exception:
                        pass

                    # Strategy 2: value attribute
                    if not selected:
                        try:
                            select.select_by_value(state_val)
                            selected = True
                            logger.info(f"  [YES] State selected by value: {state_val}")
                        except Exception:
                            pass

                    # Strategy 3: JS partial text match + fire change event
                    if not selected:
                        self.driver.execute_script(
                            """
                            var sel = arguments[0];
                            var target = arguments[1].toLowerCase().trim();
                            for (var i = 0; i < sel.options.length; i++) {
                                if (sel.options[i].text.toLowerCase().trim().indexOf(target) !== -1) {
                                    sel.selectedIndex = i;
                                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                                    sel.dispatchEvent(new Event('input',  {bubbles: true}));
                                    break;
                                }
                            }
                            """,
                            state_dropdown, state_val
                        )
                        logger.info(f"  [YES] State set via JS text-match: {state_val}")

                    time.sleep(1.5)  # Wait for React re-render after dropdown change
                except Exception as se:
                    logger.warning(f"  [WARNING] State selection failed: {se}")
            else:
                logger.warning("  [WARNING] Skipping state: missing value or selector")

            # 5b. Handle Country dropdown
            country_val = applicant.get("country", "United States")
            country_selector = self.get_sel("application", "form_fields", "country", required=False)
            if country_val and country_selector:
                try:
                    from selenium.webdriver.support.ui import Select
                    country_dropdown = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable(self._by(country_selector))
                    )
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", country_dropdown
                    )
                    time.sleep(0.5)
                    select = Select(country_dropdown)
                    try:
                        select.select_by_visible_text(country_val)
                    except Exception:
                        try:
                            select.select_by_value(country_val)
                        except Exception:
                            self.driver.execute_script(
                                """
                                var sel = arguments[0];
                                var target = arguments[1].toLowerCase();
                                for (var i = 0; i < sel.options.length; i++) {
                                    if (sel.options[i].text.toLowerCase().indexOf(target) !== -1) {
                                        sel.selectedIndex = i;
                                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                                        break;
                                    }
                                }
                                """,
                                country_dropdown, country_val
                            )
                    logger.info(f"  [YES] Country set: {country_val}")
                    time.sleep(0.5)
                except Exception as ce:
                    logger.warning(f"  [WARNING] Could not set country: {ce}")

            # 5c. Fill zip LAST — after all dropdowns so React re-renders don't clear it
            zip_val = applicant.get("zip_code")
            zip_selector = self.get_sel("application", "form_fields", "zip_code")
            logger.info(f"KForce [Step 5c]: Filling zip_code = '{zip_val}'")
            if zip_val and zip_selector:
                try:
                    zip_el = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable(self._by(zip_selector))
                    )
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", zip_el
                    )
                    time.sleep(0.5)
                    # Click to focus, then clear and type
                    zip_el.click()
                    time.sleep(0.3)
                    zip_el.clear()
                    time.sleep(0.2)
                    zip_el.send_keys(str(zip_val))
                    time.sleep(0.3)
                    # Also fire via JS native setter for React
                    self.driver.execute_script(
                        """
                        var niv = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value').set;
                        niv.call(arguments[0], arguments[1]);
                        arguments[0].dispatchEvent(new Event('input',  {bubbles:true}));
                        arguments[0].dispatchEvent(new Event('change', {bubbles:true}));
                        """,
                        zip_el, str(zip_val)
                    )
                    logger.info(f"  [YES] Zip filled: {zip_val}")
                    time.sleep(0.5)
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
