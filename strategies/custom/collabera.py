import os
import random
import time
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.human_behavior import HumanBehavior
from core.logger import logger
from core.safe_actions import SafeActions
from core.execution_logger import execution_tracker
from data.csv_tracker import tracker as csv_tracker
from data.db_duckdb import db_duckdb
from engine.guards import guards
from models.config_models import JobListing
from strategies.base import BaseStrategy

class CollaberaStrategy(BaseStrategy):
    """
    Collabera automation strategy.
    Target: https://collabera.com/job-search/
    """

    def __init__(
        self, driver, job_site, selectors, db_session=None, candidate_data=None
    ):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.safe_actions = SafeActions(driver)
        self.use_single_phase = True

        # Load applicant data from dynamically injected data
        self.config_data = self._load_config()

        # Merge in candidate-specific data (overrides JSON defaults)
        if candidate_data and isinstance(candidate_data, dict):
            self.config_data = {**self.config_data, **candidate_data}
            logger.info("[OK] Collabera: Candidate-specific data merged into config")

        self.selectors_config = self._load_selectors()

        self.portal_url = "https://collabera.com/job-search/"

        if self.db_session:
            logger.info("[OK] Collabera: Database session available")
        else:
            logger.warning("[WARNING] Collabera: No database session")

    def _load_config(self):
        """Return dynamically injected candidate data."""
        if self.candidate_data is not None:
            return self.candidate_data
        logger.error("No candidate_data was injected into the strategy.")
        return {}

    def _load_selectors(self):
        """
        Load selectors directly from the database configuration.
        Merges listing and application selectors into a unified config.
        """
        listing = dict(self.selectors.get("listing", {}))
        application = dict(self.selectors.get("application", {}))

        # Fallback to tmp_selectors.json if selectors are empty (useful for local testing)
        if not listing or not application:
            try:
                import json
                tmp_path = os.path.join(os.getcwd(), "tmp_selectors.json")
                if os.path.exists(tmp_path):
                    with open(tmp_path, "r") as f:
                        tmp_data = json.load(f)
                        if not listing: listing = tmp_data.get("listing", {})
                        if not application: application = tmp_data.get("application", {})
                        logger.info("Collabera: Loaded selectors from tmp_selectors.json fallback.")
            except Exception as e:
                logger.debug(f"Collabera: Could not load tmp_selectors.json fallback: {e}")

        # Flatten the structure for easier access in apply()
        # Some DB entries have 'application' nested inside 'listing' or as a top-level key.
        # We ensure form_fields is extracted from whichever config has it.
        app_config = application if application else listing.get("application", {})
        
        # If form_fields is missing from app_config, check if it's direct in listing
        form_fields = app_config.get("form_fields", {})
        if not form_fields and listing.get("form_fields"):
            form_fields = listing.get("form_fields", {})
            logger.info("Collabera: Using form_fields from listing directly.")

        if not form_fields:
            logger.error("[ERROR] Collabera: No form_fields found in database! Strategy will likely fail.")
        else:
            logger.info(f"Collabera: Successfully loaded {len(form_fields)} application field(s).")

        return {
            "listing": listing,
            "application": app_config,
            "form_fields": form_fields
        }

    def _get_search_location(self):
        """Read the preferred location from run parameters."""
        search = self.config_data.get("search", {})
        applicant = self.config_data.get("applicant", {})
        address = applicant.get("address", {})
        return (
            search.get("location")
            or address.get("state")
            or address.get("city")
            or ""
        )

    def _open_job_search_page(self):
        """Open the Collabera search page directly."""
        logger.info(f"Collabera: Opening job search page: {self.portal_url}")
        self.driver.get(self.portal_url)
        time.sleep(5)

    def _by(self, selector):
        """Auto-detect locator strategy (XPath vs CSS)."""
        if selector and (selector.startswith("/") or selector.startswith("(")):
            return (By.XPATH, selector)
        return (By.CSS_SELECTOR, selector)

    def _wait_for_field_value(self, sel, expected_value, timeout=8):
        """Wait until an input reflects the expected value."""
        expected = (expected_value or "").strip().lower()
        by, locator = self._by(sel)

        def _value_matches(driver):
            try:
                current = driver.find_element(by, locator).get_attribute("value") or ""
                current = current.strip().lower()
                if not expected:
                    return current == ""
                return current == expected or expected in current
            except Exception:
                return False

        WebDriverWait(self.driver, timeout).until(_value_matches)

    def _wait_for_search_results(self, link_selector, previous_url=None, timeout=15):
        """Wait until the search navigates away or results begin rendering."""
        by, locator = self._by(link_selector)

        def _results_ready(driver):
            try:
                if previous_url and driver.current_url != previous_url:
                    return True
                return len(driver.find_elements(by, locator)) > 0
            except Exception:
                return False

        WebDriverWait(self.driver, timeout).until(_results_ready)

    def _open_search_results_url(self, keyword, location, page=1):
        """Fallback to the direct results URL when form submission is unavailable."""
        encoded_kw = quote_plus((keyword or "").strip())
        encoded_location = quote_plus((location or "").strip())
        # Use Posteddays=7 for "Last Week" filtering
        search_url = (
            f"{self.portal_url}?Posteddays=7&industry=&keyword={encoded_kw}"
            f"&location={encoded_location}&sort_by=relevance&q={page}"
        )
        logger.info(f"Collabera: Opening search results URL for page {page}: {search_url}")
        self.driver.get(search_url)
        return search_url

    def _submit_search_form(
        self,
        keyword,
        search_input_sel,
        location_input_sel,
        search_location,
        search_btn_sel,
        link_selector,
    ):
        """Fill the Collabera search form and wait for results."""
        logger.info(f"Collabera: Entering keyword '{keyword}' into search form")
        if not self.react_fill(search_input_sel, keyword):
            raise RuntimeError("keyword input did not accept the value")
        time.sleep(1)

        if location_input_sel and search_location:
            logger.info(f"Collabera: Entering location '{search_location}' into search form")
            if not self.react_fill(location_input_sel, search_location):
                raise RuntimeError("location input did not accept the value")
            time.sleep(1)

        previous_url = self.driver.current_url
        logger.info("Collabera: Clicking search button")
        if not self.safe_actions.safe_click(
            search_btn_sel, by=self._by(search_btn_sel)[0]
        ):
            raise RuntimeError("search button click failed")

        self._wait_for_search_results(
            link_selector,
            previous_url=previous_url,
            timeout=15,
        )
        time.sleep(2)

    def _apply_date_filter(self):
        """Clicks the 'Date Posted' filter and selects 'Last Week'."""
        try:
            logger.info("Collabera: Applying 'Last Week' date filter via UI...")
            # 1. Click "Date Posted" to expand accordion
            date_btn_sel = "button.design[data-target='#collapseOne']"
            if self.safe_actions.safe_click(date_btn_sel, by=By.CSS_SELECTOR):
                time.sleep(2)  # Wait for toggle animation
                # 2. Click the specific "Last Week" paragraph provided by the user
                last_week_sel = "//p[contains(text(), 'Last Week')]"
                if self.safe_actions.safe_click(last_week_sel, by=By.XPATH):
                    logger.info("Collabera: 'Last Week' filter selected through UI.")
                    time.sleep(4)  # Wait for AJAX results to refresh
                    return True
            return False
        except Exception as e:
            logger.warning(f"Collabera: Could not apply date filter UI click: {e}")
            return False

    def _get_total_pages(self):
        """Extract the total number of pages from the 'Last' link in pagination."""
        import re
        try:
            # Selector from user's HTML: <li class="page-item align-self-center"><a class="page-link" href="...&q=41">Last</a></li>
            # Multiple attempts for robustness (By text and by class)
            last_selectors = [
                (By.XPATH, "//ul[contains(@class,'pagination')]//a[contains(text(),'Last')]"),
                (By.CSS_SELECTOR, "ul.pagination li.align-self-center a.page-link"),
                (By.XPATH, "//a[contains(@href, 'q=')]") # generic fallback to find highest q value
            ]
            
            for by, sel in last_selectors:
                try:
                    elements = self.driver.find_elements(by, sel)
                    if not elements: continue
                    
                    # If using generic fallback, we might pick the highest q value from all pagination links
                    if by == By.XPATH and "q=" in sel:
                        highest_q = 1
                        for el in elements:
                            href = el.get_attribute("href")
                            match = re.search(r"q=(\d+)", href or "")
                            if match:
                                highest_q = max(highest_q, int(match.group(1)))
                        if highest_q > 1:
                            logger.info(f"Collabera: Detected {highest_q} max pages via generic links.")
                            return highest_q
                    else:
                        # Direct "Last" link extraction
                        href = elements[0].get_attribute("href")
                        match = re.search(r"q=(\d+)", href or "")
                        if match:
                            total = int(match.group(1))
                            logger.info(f"Collabera: Detected {total} total pages from 'Last' button.")
                            return total
                except:
                    continue
        except Exception as e:
            logger.debug(f"Collabera: Could not detect total pages from UI: {e}")
        return None

    def react_fill(self, sel, value):
        """
        React-compatible field filler.
        Uses JavaScript to ensure the underlying React/Vue component
        registers the input change, with keyboard fallback.
        """
        if not sel:
            return False

        value = "" if value is None else str(value).strip()
        by, locator = self._by(sel)

        try:
            el = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((by, locator))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                el,
            )
            self.driver.execute_script(
                """
                const element = arguments[0];
                const nextValue = arguments[1];
                const prototype = element.tagName === 'TEXTAREA'
                    ? window.HTMLTextAreaElement.prototype
                    : window.HTMLInputElement.prototype;
                const valueSetter = Object.getOwnPropertyDescriptor(prototype, 'value').set;

                element.focus();
                valueSetter.call(element, '');
                element.dispatchEvent(new Event('input', { bubbles: true }));
                valueSetter.call(element, nextValue);
                element.dispatchEvent(new Event('input', { bubbles: true }));
                element.dispatchEvent(new Event('change', { bubbles: true }));
                element.blur();
                """,
                el,
                value,
            )
            self._wait_for_field_value(sel, value)
            logger.debug(f"Collabera: Filled field '{sel}' via react_fill")
            return True
        except Exception as e:
            logger.warning(
                f"Collabera: react_fill failed for '{sel}' ({e}), falling back to keyboard typing"
            )

        try:
            el = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((by, locator))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});",
                el,
            )
            el.click()
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.BACKSPACE)
            if value:
                el.send_keys(value)
            el.send_keys(Keys.TAB)
            self._wait_for_field_value(sel, value)
            logger.debug(f"Collabera: Filled field '{sel}' via keyboard fallback")
            return True
        except Exception as fallback_error:
            logger.error(
                f"Collabera: Failed to fill field '{sel}' after fallback ({fallback_error})"
            )
            return False

    def login(self):
        """
        Collabera does not require an authenticated login step.
        No-op so navigation only happens during the actual search flow.
        """
        logger.info("Collabera: No login step required. Search flow will handle navigation.")
        try:
            return True
        except Exception as e:
            logger.error(f"Collabera: Failed to reach portal: {e}")
            return False

    def find_and_apply_jobs(self):
        """
        Two-phase workflow:
          Phase 1 — Collect all unique job listings across all keywords.
          Phase 2 — Apply to each collected job sequentially.
        Returns the number of successful applications.
        """
        logger.info("\n" + "=" * 60)
        logger.info("[SEARCH] Collabera: Starting two-phase find-and-apply workflow")
        logger.info("=" * 60)

        if not self.config_data:
            logger.error("Collabera: No configuration data available")
            return 0

        # Support both 'keywords' list and legacy 'keyword' string
        search_config = self.config_data.get("search", {})
        keywords = search_config.get("keywords", [])
        if not keywords:
            keywords = [kw for kw in [search_config.get("keyword")] if kw]

        # FALLBACK: Check if selectors_config has 'search_keywords' (from tmp_selectors.json)
        if not keywords:
            keywords = self.selectors_config.get("listing", {}).get("search_keywords", [])

        if not keywords:
            logger.error("[ERROR] Collabera: No search keywords found!")
            return 0

        # ── PHASE 1: Collect all jobs ──────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: Discovering all unique jobs across all keywords...")
        logger.info("=" * 60)

        all_listings = []
        seen_urls = set()

        for keyword in keywords:
            logger.info(f"\n[SEARCH] Keyword: '{keyword}'")
            listings = self.find_jobs_for_keyword(keyword)

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
        
        execution_tracker.add_jobs_found(len(all_listings))

        # ── PHASE 2: Apply to each job ─────────────────────────────────────
        logger.info("\n" + "=" * 60)
        logger.info(f"PHASE 2: Applying to {len(all_listings)} unique jobs...")
        logger.info("=" * 60)

        total_attempted = 0
        total_applied = 0
        for i, listing in enumerate(all_listings, 1):
            if not guards.can_apply():
                logger.warning("[LIMIT] Application limit reached. Stopping.")
                break

            job_id = listing.get("external_id")
            logger.debug(f"[{i}/{len(all_listings)}] Checking job_id: {job_id}")
            
            # Allow re-attempt if we're in a live run and previous was dry-run, or if previously failed
            if db_duckdb.is_already_applied(job_id, "Collabera"):
                if guards.is_dry_run():
                    logger.info(f"[{i}/{len(all_listings)}] [SKIP] Already applied (Dry Run): {listing.get('job_title')}")
                    continue
                else:
                    logger.info(f"[{i}/{len(all_listings)}] [SKIP] Already applied: {listing.get('job_title')}")
                    continue

            logger.info(
                f"\n[{i}/{len(all_listings)}] Applying to: {listing.get('job_title')}"
            )
            total_attempted += 1
            try:
                if self.apply(listing):
                    total_applied += 1
                    guards.increment_counter()
                    logger.info(f"  [YES] Applied! ({total_applied} successful so far)")
                    time.sleep(random.uniform(4, 8))
                else:
                    logger.warning(f"  [NO] Failed to apply to: {listing.get('job_title')}")
            except Exception as e:
                logger.error(f"  [ERROR] Exception applying to {listing.get('job_title')}: {e}")

        logger.info(
            f"\n[OK] Phase 2 complete. Total applications attempted: {total_attempted}, submitted: {total_applied}/{len(all_listings)}"
        )
        # Update execution tracker with attempts for non-zero reports
        execution_tracker.add_applications_attempted(total_attempted)
        return total_applied

    def find_jobs_for_keyword(self, keyword):
        """
        Search for jobs on Collabera with multi-page support.
        """
        all_listings = []
        seen_urls = set()
        max_pages = self.config_data.get("search", {}).get("max_pages", 3)
        detected_pages = None # Will be populated once we hit page 1
        
        listing_selectors = self.selectors_config.get("listing", {})
        link_selector = listing_selectors.get("job_link")

        if not link_selector:
            logger.error("Collabera: 'job_link' selector is missing!")
            return []

        page = 1
        while True:
            # Termination condition
            limit = detected_pages or max_pages
            if page > limit:
                logger.info(f"Collabera: Reached search limit of {limit} pages.")
                break

            try:
                if page == 1:
                    logger.info(f"Collabera: [PAGE 1] Opening job search page at {self.portal_url}")
                    self._open_job_search_page()

                    search_input_sel   = listing_selectors.get("search_input")
                    location_input_sel = listing_selectors.get("location_input")
                    search_btn_sel     = listing_selectors.get("search_button")
                    search_location    = self._get_search_location()

                    if search_input_sel and search_btn_sel:
                        try:
                            self._submit_search_form(
                                keyword,
                                search_input_sel,
                                location_input_sel,
                                search_location,
                                search_btn_sel,
                                link_selector,
                            )
                        except Exception as e:
                            logger.warning(f"Collabera: Form-based search failed ({e}), falling back to direct URL")
                            self._open_search_results_url(keyword, search_location, page=1)
                    else:
                        self._open_search_results_url(keyword, search_location, page=1)
                else:
                    self._open_search_results_url(
                        keyword, self._get_search_location(), page=page
                    )

                time.sleep(random.uniform(5, 7))

                # On the first page, attempt to detect total pages and apply the date filter
                if page == 1:
                    # Apply the "Last Week" filter as requested by clicking the button/option
                    self._apply_date_filter()
                    
                    total = self._get_total_pages()
                    if total:
                        detected_pages = total
                        logger.info(f"Collabera: Updated search range to 1-{detected_pages} pages.")

                elements = self.driver.find_elements(*self._by(link_selector))
                logger.info(f"Collabera: [PAGE {page}] Found {len(elements)} elements with selector: {link_selector}")

                if not elements:
                    logger.info(f"Collabera: No more jobs on page {page}. Stopping.")
                    break

                page_count = 0
                keyword_lower = keyword.lower()
                for el in elements:
                    try:
                        # Harden title extraction: Try .text, then innerText attribute
                        title = el.text.strip()
                        if not title:
                            title = (el.get_attribute("innerText") or "").strip()
                        if not title:
                            title = (el.get_attribute("textContent") or "").strip()
                        
                        url   = el.get_attribute("href")
                        if title and url and url not in seen_urls:
                            # TITLE FILTERING: Include jobs that match the specific keyword OR core terms (AI, AIML, PYTHON)
                            import re
                            core_terms = ["ai", "aiml", "python"]
                            pattern_parts = [re.escape(keyword_lower)] + [re.escape(t) for t in core_terms]
                            pattern = rf"(?i)(?:^|[^a-zA-Z0-9])({'|'.join(pattern_parts)})(?:[^a-zA-Z0-9]|$)"
                            
                            if not re.search(pattern, title):
                                logger.debug(f"  [SKIP] Title mismatch: '{title}' does not match keyword '{keyword}' or core terms")
                                continue

                            seen_urls.add(url)
                            
                            # Robust external_id extraction (handles ?post=XXXXX or slugs)
                            if "post=" in url:
                                external_id = url.split("post=")[-1].split("&")[0]
                            elif "-" in url:
                                external_id = url.split("-")[-1].replace("/", "")
                            else:
                                from hashlib import md5
                                external_id = md5(url.encode()).hexdigest()[:12]

                            all_listings.append({
                                "job_title":   title,
                                "job_url":     url,
                                "external_id": external_id,
                            })
                            page_count += 1
                    except Exception:
                        continue

                logger.debug(f"Collabera: Found {page_count} new keyword-matching jobs on page {page}.")
                
                # NAVIGATION: Move to the next page
                page += 1

            except Exception as e:
                logger.error(f"Collabera: Error on page {page}: {e}")
                break

        if all_listings:
            logger.info(f"Collabera: Found {len(all_listings)} total unique jobs for '{keyword}'.")
            csv_tracker.add_discovered_jobs("collabera", all_listings)

        return all_listings

    def find_jobs(self):
        """Legacy compatibility wrapper."""
        return []

    def apply(self, listing):
        """
        Structured application flow mimicking KForce/Lancesoft patterns.
        """
        if isinstance(listing, dict):
            job_url = listing.get("job_url")
            job_title = listing.get("job_title", "Unknown")
            external_id = listing.get("external_id", "Unknown")
        else:
            job_url = getattr(listing, "job_url", None)
            job_title = getattr(listing, "job_title", "Unknown")
            external_id = getattr(listing, "external_id", "Unknown")

        if not job_url:
            logger.error("Collabera: No job URL provided for application.")
            return False

        logger.info(f"\n[APPLY] Collabera [Step 1]: Navigating to job: {job_title}")
        logger.info(f"  URL: {job_url}")

        try:
            # Step 1: Navigation
            self.driver.get(job_url)
            time.sleep(random.uniform(4, 6))

            # Initial Global Body Scroll (Triggers lazy-loading for iframes)
            logger.info("Collabera: Scrolling to bottom of page...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # Step 2: Candidate profile
            logger.info(
                "Collabera [Step 2]: Preparing candidate profile for dynamic form filling..."
            )
            candidate_profile = self._build_candidate_profile()

            # Step 3: Handle Application Form / Iframe
            # IMPORTANT: In Collabera, 'Apply Now' is often a TITLE, not a button.
            # The form is typically visible immediately or hidden in an iframe.
            logger.info("Collabera [Step 3]: Accessing application form...")
            application_selectors = self.selectors_config.get("application", {})
            form_fields = self.selectors_config.get("form_fields", {})
            
            # Default to 'iframe' if no specific selector is provided in DB
            iframe_sel = application_selectors.get("iframe_selector") or form_fields.get("iframe_selector") or "iframe"
            
            # If no form fields are found at all, we can't proceed.
            if not form_fields:
                logger.error("  [FATAL] No form_fields found in selectors. Check DuckDB configuration.")
                return False

            # ALWAYS attempt to switch to iframe on Collabera (it's nearly always required)
            try:
                logger.info(f"  Attempting to switch to iframe context (selector: {iframe_sel})...")
                
                # Robust Switch logic combining the specific selector with a generic iframe fallback
                if iframe_sel and iframe_sel != "iframe":
                    by, locator = self._by(iframe_sel)
                    try:
                        WebDriverWait(self.driver, 15).until(
                            EC.frame_to_be_available_and_switch_to_it((by, locator))
                        )
                        logger.info(f"  [OK] Successfully switched to specified iframe: {iframe_sel}")
                    except Exception as specific_e:
                        logger.warning(f"  [!] Failed to switch to specific iframe ({specific_e}). Attempting generic iframe switch...")
                        WebDriverWait(self.driver, 10).until(
                            EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe"))
                        )
                        logger.info("  [OK] Switched to first available iframe (generic fallback).")
                else:
                    # Pure generic switch if no selector was provided
                    logger.info("  No specific iframe selector provided. Searching for any iframe...")
                    WebDriverWait(self.driver, 15).until(
                        EC.frame_to_be_available_and_switch_to_it((By.TAG_NAME, "iframe"))
                    )
                    logger.info("  [OK] Switched to first available iframe (pure generic).")

            except Exception as e:
                logger.warning(f"  [WARNING] All iframe switch attempts failed: {e}")
                logger.debug("    Form might be on the main page. Continuing anyway...")

            # Wait for any primary field to load inside iframe (or main page)
            logger.info("  Waiting for form fields to render...")
            first_field_key = "txtName" if "txtName" in form_fields else "fullName"
            first_field_sel = form_fields.get(first_field_key)
            if first_field_sel:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(self._by(first_field_sel))
                    )
                    logger.info(f"  [OK] Form field '{first_field_key}' detected.")
                except:
                    logger.warning(f"  [!] Timeout waiting for field '{first_field_key}'. Continuing anyway...")

            # Step 4: Fill Form Fields (Hardened Selectors)
            logger.info("Collabera [Step 4]: Filling form fields...")
            
            # Use explicit mappings based on verified Collabera field names (txtName, txtEmail, txtPhone)
            # These keys typically exist in the 'form_fields' dictionary in DuckDB
            field_mappings = [
                ("fullName", candidate_profile.get("full_name")),
                ("email",    candidate_profile.get("email")),
                ("phone",    candidate_profile.get("phone")),
            ]

            for field_key, value in field_mappings:
                selector = form_fields.get(field_key)
                if not value: continue

                filled = False
                if selector:
                    logger.info(f"  Filling {field_key} via DB selector...")
                    if self.react_fill(selector, value):
                        filled = True

                # Fallback to ChatGPT-style By.NAME selectors if DB selector fails or is missing
                if not filled:
                    logger.info(f"  [FALLBACK] Attempting By.NAME discovery for {field_key}...")
                    for name_attr in [field_key, f"txt{field_key.capitalize()}", field_key.lower(), f"txt{field_key}"]:
                        try:
                            # Use basic ID or Name search
                            sel = f"[name='{name_attr}'], [id='{name_attr}']"
                            if self.react_fill(sel, value):
                                logger.info(f"    [OK] Found and filled {field_key} via {name_attr}")
                                filled = True
                                break
                        except: pass
                
                if not filled:
                    logger.warning(f"  [!] Could not fill {field_key} after all attempts.")
                
                time.sleep(random.uniform(0.6, 1.2))

            # Optional: Dynamic filling for any other fields not in the core mapping
            # but defined in form_fields (e.g. LinkedIn, City if they appear)
            core_keys = {"fullName", "email", "phone", "resume_upload", "terms_checkbox", "alert_checkbox", "submit_btn"}
            for field_key, selector in form_fields.items():
                if field_key in core_keys: 
                    continue
                
                value = self._resolve_field_value(field_key, candidate_profile)
                if selector and value:
                    logger.info(f"  Filling dynamic field: {field_key}")
                    self.react_fill(selector, value)
                    time.sleep(0.5)

            # Step 5: Resume Upload (Moved BEFORE checkboxes per user request)
            logger.info("Collabera [Step 5]: Uploading resume...")
            resume_path = self.get_resume_path()
            resume_sel = form_fields.get("resume_upload") or "input[type='file']"
            if resume_path:
                try:
                    file_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(self._by(resume_sel))
                    )
                    self.driver.execute_script(
                        "arguments[0].style.display='block'; arguments[0].style.visibility='visible'; arguments[0].style.opacity='1';",
                        file_input,
                    )
                    file_input.send_keys(resume_path)
                    logger.info("  [OK] Resume attached.")
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"  [ERROR] Resume upload failed: {e}")

            # Step 6: Handle ALL Checkboxes (Dual handling for Terms and Alerts)
            logger.info("Collabera [Step 6]: Handling consent checkboxes (Both Terms and Alerts)...")
            
            # Use specific XPATH text-based selectors for high precision
            checkbox_configs = [
                {"name": "terms_checkbox", "sel": '//label[contains(., "Terms of Service")]', "desc": "Consent/Privacy"},
                {"name": "alert_checkbox", "sel": '//label[contains(., "job alert notifications")]', "desc": "Job Alerts"}
            ]

            for cb in checkbox_configs:
                try:
                    logger.info(f"  Attempting to click {cb['desc']} checkbox...")
                    cb_el = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(self._by(cb['sel']))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", cb_el)
                    time.sleep(1)

                    # Click the label / container to trigger the custom checkbox
                    self.driver.execute_script("arguments[0].click();", cb_el)
                    logger.info(f"    [OK] Clicked {cb['desc']}.")
                    time.sleep(1) # Small delay between clicks to prevent UI race conditions
                except Exception as e:
                    logger.warning(f"    [SKIP] {cb['desc']} failed or not found: {e}")

            # Step 7: Submit
            logger.info("Collabera [Step 7]: Submitting application...")
            submit_btn_sel = form_fields.get("submit_btn") or "#Submit"
            
            try:
                # FIX: Handle "invalid selector" by checking if it's an illegal CSS selector
                try:
                    submit_btn = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(self._by(submit_btn_sel))
                    )
                except Exception as locator_error:
                    if "invalid selector" in str(locator_error).lower():
                        logger.warning(f"  [!] Invalid CSS Selector '{submit_btn_sel}'. Falling back to #Submit or Text-based XPath.")
                        fallback_sel = "#Submit"
                        submit_btn = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located(self._by(fallback_sel))
                        )
                    else:
                        raise locator_error

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
                time.sleep(1)

                if guards.is_dry_run():
                    self.driver.execute_script("arguments[0].style.border = '5px solid orange';", submit_btn)
                    logger.info("  [DRY RUN] Submit button highlighted. Not clicking.")
                    # Don't mark as permanently applied in dry run to allow easier testing
                    return True
                else:
                    self.human.human_click(submit_btn)
                    logger.info("  [OK] Submit button clicked.")

                    # Waiting for verification
                    time.sleep(3)
                    
                    # Fallback for click verification — Submit some more if text logic suggests it
                    if not self._verify_submission():
                        logger.info("  [!] Initial verification failed. Re-attempting submit with text-based fallback...")
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(1)
                        
                        try:
                            # Direct check for #Submit if it's still clickable
                            alt_btn = self.driver.find_element(By.ID, "Submit")
                            self.driver.execute_script("arguments[0].click();", alt_btn)
                            logger.info("    [OK] Fired click via #Submit fallback.")
                            time.sleep(3)
                        except:
                            try:
                                apply_btn_text_sel = "//button[contains(text(),'Apply') or contains(text(),'Submit')]"
                                alt_btn = self.driver.find_element(By.XPATH, apply_btn_text_sel)
                                self.driver.execute_script("arguments[0].click();", alt_btn)
                                logger.info("    [OK] Fired click via XPATH text discovery fallback.")
                                time.sleep(3)
                            except: pass

                    if self._verify_submission():
                        logger.info("  [SUCCESS] Application verified.")
                        self._record_application(listing, job_url, job_title, "success")
                        return True
                    else:
                        logger.warning("  [FAIL] Verification failed. Success message not found.")
                        return False
            except Exception as e:
                logger.error(f"  [ERROR] Submit button interaction failed: {e}")
                return False

            return False

        except Exception as e:
            logger.error(f"Collabera Application Flow failed: {e}")
            self._record_application(listing, job_url, job_title, "failed", str(e))
            return False

        finally:
            try:
                self.driver.switch_to.default_content()
                logger.debug("Collabera: Switched back to default content.")
            except Exception:
                pass

    def _build_candidate_profile(self):
        """Build a normalized profile dict from config/candidate data."""
        applicant_data = self.config_data.get("applicant", {}) or {}
        address_block = applicant_data.get("address", {}) or {}

        def _first_value(*values):
            for value in values:
                if value is None:
                    continue
                text = str(value).strip()
                if text:
                    return text
            return None

        first_name = _first_value(
            self.config_data.get("first_name"),
            applicant_data.get("first_name"),
        )
        last_name = _first_value(
            self.config_data.get("last_name"),
            applicant_data.get("last_name"),
        )
        full_name = " ".join(
            part for part in (first_name, last_name) if part
        ).strip()
        if not full_name:
            full_name = first_name or last_name

        email = _first_value(
            self.config_data.get("email"),
            applicant_data.get("email"),
        )
        phone = _first_value(
            self.config_data.get("phone"),
            applicant_data.get("phone"),
        )
        street = _first_value(
            address_block.get("street"),
            address_block.get("street_address"),
            applicant_data.get("street_address"),
        )
        city = _first_value(
            address_block.get("city"),
            applicant_data.get("city"),
        )
        state = _first_value(
            address_block.get("state"),
            applicant_data.get("state"),
        )
        zip_code = _first_value(
            address_block.get("zip_code"),
            address_block.get("postal_code"),
            applicant_data.get("zip_code"),
            self.config_data.get("zip_code"),
        )
        country = _first_value(
            address_block.get("country"),
            address_block.get("country"),
            self.config_data.get("country"),
            "United States",
        )

        return {
            "first_name": first_name,
            "last_name": last_name,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "street": street,
            "city": city,
            "state": state,
            "zip_code": zip_code,
            "country": country,
            "workstatus": _first_value(
                applicant_data.get("workstatus"),
                self.config_data.get("workstatus"),
            ),
            "linkedin": _first_value(
                applicant_data.get("linkedin"),
                self.config_data.get("linkedin"),
            ),
            "title": _first_value(
                applicant_data.get("title"),
                self.config_data.get("title"),
            ),
            "summary": _first_value(
                applicant_data.get("summary"),
                self.config_data.get("summary"),
            ),
        }

    def _resolve_field_value(self, field_key, profile):
        """Map form field keys to candidate profile values."""
        if not field_key or not profile:
            return None

        normalized = field_key.lower().replace("_", "").replace("-", "").strip()
        if not normalized:
            return None

        skip_terms = (
            "resume",
            "submit",
            "checkbox",
            "label",
            "button",
            "iframe",
            "frame",
            "link",
        )
        if any(term in normalized for term in skip_terms):
            return None

        if "lastname" in normalized or "surname" in normalized:
            return profile.get("last_name")
        if "firstname" in normalized or normalized in ("fname", "first") or (
            "first" in normalized and "name" in normalized
        ):
            return profile.get("first_name")
        if "fullname" in normalized or "yourname" in normalized or normalized == "name":
            return (
                profile.get("full_name")
                or profile.get("first_name")
                or profile.get("last_name")
            )
        if "email" in normalized:
            return profile.get("email")
        if "phone" in normalized or "mobile" in normalized:
            return profile.get("phone")
        if "street" in normalized or normalized.endswith("address") or "addr" in normalized:
            return profile.get("street")
        if "city" in normalized and "citizenship" not in normalized:
            return profile.get("city")
        if "state" in normalized and "statement" not in normalized:
            return profile.get("state")
        if "zip" in normalized or "postal" in normalized:
            return profile.get("zip_code")
        if "country" in normalized:
            return profile.get("country")
        if "workstatus" in normalized:
            return profile.get("workstatus")
        if "linkedin" in normalized:
            return profile.get("linkedin")
        if "title" in normalized:
            return profile.get("title")
        if "summary" in normalized:
            return profile.get("summary")

        return None

    def _verify_submission(self, timeout=25):
        """Verify successful application submission on Collabera."""
        logger.info("Collabera: Verifying submission...")
        
        # Give the page a bit of time to transition/redirect
        time.sleep(7)
        
        # 1. URL change verification (Common Collabera thank-you page)
        current_url = self.driver.current_url.lower()
        if any(term in current_url for term in ["thank", "success", "confirmed", "submitted"]):
            logger.info(f"  [OK] Verified via URL: {current_url}")
            return True

        # 2. Presence of a success message / modal / text indicator
        success_indicators = [
            "thank you",
            "application submitted",
            "successfully applied",
            "received your application",
            "will get back to you",
            "congratulations",
            "job alert has been set",
            "application status",
            "confirmation",
            "your application has been received",
        ]
        
        try:
            # Check the full body content for any of the patterns
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            for indicator in success_indicators:
                if indicator in page_text:
                    logger.info(f"  [OK] Verified via page text indicator: '{indicator}'")
                    return True
        except: pass

        # 3. Check for specific success icons or messages hidden in the DOM
        try:
            if self.driver.find_elements(By.XPATH, "//*[contains(@class, 'success') or contains(@id, 'success')]"):
                logger.info("  [OK] Verified via success class/ID hint.")
                return True
        except: pass

        return False

    def _record_application(self, listing, job_url, job_title, status, error_msg=None):
        """Record the application result in trackers."""
        from core.execution_logger import execution_tracker
        
        job_id = listing.get("external_id") if isinstance(listing, dict) else getattr(listing, "external_id", "N/A")
        
        # Log to execution tracker
        if status == "success":
            execution_tracker.record_success("Collabera", str(job_id), str(job_title), str(job_url))
        else:
            execution_tracker.record_error("Collabera", str(job_id), str(job_title), str(job_url), str(error_msg))

        # Log to CSV/DuckDB Tracker
        csv_tracker.update_job_status(
            "Collabera",
            job_url,
            "applied" if status == "success" else "failed",
            attempts_inc=1,
            last_error=error_msg
        )
        
        # Also mark in Collabera-specific table for legacy compatibility
        if status == "success":
             db_duckdb.mark_applied(job_id, "Collabera", job_title)
             
        logger.debug(f"Collabera: Recorded {status} application for {job_id}")
