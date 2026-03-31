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
        """Load selectors directly from the database configuration."""
        listing = dict(self.selectors.get("listing", {}))
        listing.pop("for_job_seekers_link", None)
        application = self.selectors.get("application", {})
        return {"listing": listing, "application": application}

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
        Search for jobs and apply sequentially (Single-Phase).
        This matches the robust patterns used in LanceSoft and Kforce.
        """
        from engine.guards import guards
        logger.info("[SEARCH] Collabera: Starting single-phase find-and-apply workflow")

        if not self.config_data:
            logger.error("Collabera: No configuration data available")
            return 0

        # Support both 'keywords' list and legacy 'keyword' string
        search_config = self.config_data.get("search", {})
        keywords = search_config.get("keywords", [])
        if not keywords:
            keywords = [kw for kw in [search_config.get("keyword")] if kw]

        if not keywords:
            logger.error("[ERROR] Collabera: No search keywords found in candidate data!")
            return 0

        total_applied = 0
        for keyword in keywords:
            if not guards.can_apply():
                logger.warning("[LIMIT] Application limit reached. Stopping searches.")
                break

            logger.info(f"\n{'=' * 60}")
            logger.info(f"[SEARCH] Collabera: Search for '{keyword}'")
            logger.info(f"{'=' * 60}")

            applied_count = self._search_and_apply_immediately(keyword)
            total_applied += applied_count

            # Human-like delay between keyword searches
            if len(keywords) > 1:
                time.sleep(random.uniform(5, 10))

        logger.info(f"\n[OK] Collabera workflow complete: {total_applied} applications submitted")
        return total_applied

    def _search_and_apply_immediately(self, keyword):
        """
        Search and apply to jobs immediately on each page.
        """
        from engine.guards import guards
        
        applied_in_search = 0
        seen_urls = set()
        max_pages = self.config_data.get("search", {}).get("max_pages", 3)
        listing_selectors = self.selectors_config.get("listing", {})
        link_selector = listing_selectors.get("job_link")

        if not link_selector:
            logger.error("Collabera: 'job_link' selector is missing!")
            return 0

        for page in range(1, max_pages + 1):
            if not guards.can_apply():
                break

            try:
                if page == 1:
                    logger.info(f"Collabera: [PAGE 1] Opening job search page")
                    self._open_job_search_page()

                    search_input_sel   = listing_selectors.get("search_input")
                    location_input_sel = listing_selectors.get("location_input")
                    search_btn_sel     = listing_selectors.get("search_button")
                    search_location    = self._get_search_location()

                    if search_input_sel and search_btn_sel:
                        try:
                            self._submit_search_form(
                                keyword, search_input_sel, location_input_sel,
                                search_location, search_btn_sel, link_selector
                            )
                        except Exception as e:
                            logger.warning(f"Collabera: Form-based search failed ({e}), falling back to direct URL")
                            self._open_search_results_url(keyword, search_location, page=1)
                    else:
                        self._open_search_results_url(keyword, search_location, page=1)
                else:
                    self._open_search_results_url(keyword, self._get_search_location(), page=page)

                time.sleep(random.uniform(5, 7))

                elements = self.driver.find_elements(*self._by(link_selector))
                logger.info(f"Collabera: [PAGE {page}] Found {len(elements)} jobs")

                if not elements:
                    logger.info(f"Collabera: No jobs on page {page}. Stopping.")
                    break

                # Extract URLs beforehand to avoid stale elements during navigations
                listings_on_page = []
                for el in elements:
                    try:
                        url = el.get_attribute("href")
                        title = el.text.strip()
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            external_id = url.split("-")[-1].replace("/", "") if "-" in url else url
                            listings_on_page.append({
                                "job_title": title,
                                "job_url": url,
                                "external_id": external_id
                            })
                    except: continue

                execution_tracker.add_jobs_found(len(listings_on_page))

                # Now apply to each job found on this page
                for listing in listings_on_page:
                    if not guards.can_apply():
                        break

                    job_id = listing["external_id"]
                    if db_duckdb.is_already_applied(job_id, "Collabera"):
                        logger.info(f"  [SKIP] Already applied: {listing['job_title']}")
                        continue

                    if self.apply(listing):
                        applied_in_search += 1
                        guards.increment_counter()
                        db_duckdb.mark_applied(job_id, "Collabera", listing["job_title"])
                        logger.info(f"  [YES] Applied! ({applied_in_search} for this keyword)")
                        time.sleep(random.uniform(3, 6))

                    # Navigate back to search results if necessary (or rely on self.apply to stay in session)
                    # For Collabera, self.apply navigates to job_url, so we MUST go back or re-search for the next page.
                    # Re-searching is safer for session health.

                # After processing a page, the next iteration of the 'page' loop will navigate to the next results URL.

            except Exception as e:
                logger.error(f"Collabera: Error on page {page}: {e}")
                break

        return applied_in_search

    def find_jobs_for_keyword(self, keyword):
        """
        Search for jobs on Collabera with multi-page support.
        """
        all_listings = []
        seen_urls = set()
        max_pages = self.config_data.get("search", {}).get("max_pages", 3)
        listing_selectors = self.selectors_config.get("listing", {})
        link_selector = listing_selectors.get("job_link")

        if not link_selector:
            logger.error("Collabera: 'job_link' selector is missing!")
            return []

        for page in range(1, max_pages + 1):
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

                elements = self.driver.find_elements(*self._by(link_selector))
                logger.info(f"Collabera: [PAGE {page}] Found {len(elements)} elements with selector: {link_selector}")

                if not elements:
                    logger.info(f"Collabera: No more jobs on page {page}. Stopping.")
                    break

                page_count = 0
                for el in elements:
                    try:
                        title = el.text.strip()
                        url   = el.get_attribute("href")
                        if title and url and url not in seen_urls:
                            seen_urls.add(url)
                            external_id = url.split("-")[-1].replace("/", "") if "-" in url else url
                            all_listings.append({
                                "job_title":   title,
                                "job_url":     url,
                                "external_id": external_id,
                            })
                            page_count += 1
                    except Exception:
                        continue

                logger.debug(f"Collabera: Found {page_count} new jobs on page {page}.")
                if page_count == 0:
                    logger.info(f"Collabera: No new unique jobs on page {page}. Stopping.")
                    break

            except Exception as e:
                logger.error(f"Collabera: Error on page {page}: {e}")
                break

        logger.info(f"Collabera: Found {len(all_listings)} total unique jobs for '{keyword}'.")
        return all_listings

    def find_jobs(self):
        """Legacy compatibility wrapper."""
        return []

    def apply(self, listing):
        """
        Fill out the application form on Collabera for a specific job.

        Flow:
          Step 1 — Navigate to job URL and click Apply button
          Step 2 — Fill: fullName (#txtName), email (#txtEmail), phone (#txtPhone)
          Step 3 — Click acknowledgement labels / consent checkboxes
          Step 4 — Upload resume
          Step 5 — Submit (#Submit)
        """
        if isinstance(listing, dict):
            job_url = listing.get("job_url")
        else:
            job_url = getattr(listing, "job_url", None)

        if not job_url:
            return False

        logger.info(f"Collabera: Navigating to job posting {job_url}")
        job_title = (
            listing.get("job_title", "Unknown")
            if isinstance(listing, dict)
            else getattr(listing, "job_title", "Unknown")
        )
        try:
            # SESSION HEALTH CHECK
            try:
                _ = self.driver.current_window_handle
            except Exception:
                logger.error("Collabera: Browser session lost before page load!")
                return False

            self.driver.get(job_url)
            time.sleep(5)

            # ── Step 1: Click Apply Button on Job Posting (if needed) ───────────
            apply_btn_sel = self.selectors_config.get("application", {}).get("apply_button")
            form_fields = self.selectors_config.get("application", {}).get("form_fields", {})
            first_field_sel = form_fields.get("fullName")

            # Check if form is already visible
            form_visible = False
            if first_field_sel:
                try:
                    self.driver.find_element(*self._by(first_field_sel))
                    form_visible = True
                    logger.info("Collabera: Application form already visible. Skipping trigger click.")
                except Exception:
                    form_visible = False

            if not form_visible and apply_btn_sel:
                try:
                    logger.info(f"Collabera: Looking for Apply trigger: {apply_btn_sel}")
                    apply_btn = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located(self._by(apply_btn_sel))
                    )[0]
                    
                    # Scroll to the apply trigger
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
                    time.sleep(1)

                    try:
                        self.human.human_click(apply_btn)
                    except Exception:
                        logger.warning("Collabera: Standard click failed, using JavaScript click.")
                        self.driver.execute_script("arguments[0].click();", apply_btn)
                        
                    logger.info("Collabera: Clicked Apply trigger.")
                    time.sleep(4)
                except Exception as e:
                    logger.warning(f"Collabera: Could not click Apply trigger: {e}")
                    # Continue anyway in case the form is already open

            # ── Step 2: Fill Name / Email / Phone ─────────────────────────────
            # Robust data resolution (matching Kforce pattern)
            _raw = self.config_data.get("applicant", {})
            applicant = {
                "first_name": self.config_data.get("first_name") or _raw.get("first_name", ""),
                "last_name":  self.config_data.get("last_name")  or _raw.get("last_name", ""),
                "email":      self.config_data.get("email")      or _raw.get("email", ""),
                "phone":      self.config_data.get("phone")      or _raw.get("phone", ""),
            }
            full_name = f"{applicant['first_name']} {applicant['last_name']}".strip()
            email = applicant["email"]
            phone = applicant["phone"]

            # form_fields already loaded in Step 1

            logger.info("Collabera: Filling applicant details...")
            for field_key, value in [("fullName", full_name), ("email", email), ("phone", phone)]:
                sel = form_fields.get(field_key)
                if sel and value:
                    try:
                        el = self.driver.find_element(*self._by(sel))
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", el
                        )
                        time.sleep(0.5)
                        self.react_fill(sel, value)
                        logger.info(f"  [OK] Filled '{field_key}'")
                    except Exception as fe:
                        logger.warning(f"  [WARNING] Could not fill '{field_key}': {fe}")

            # ── Step 3: Click acknowledgement labels / consent checkboxes ──────
            # label_1          → main acknowledgement label
            # checkbox_1_label → first consent label  (div[4]/label)
            # checkbox_2_label → second consent label (div[5]/label)
            logger.info("Collabera: Clicking acknowledgement labels...")
            for cb_key in ["label_1", "checkbox_1_label", "checkbox_2_label"]:
                cb_sel = form_fields.get(cb_key)
                if cb_sel:
                    try:
                        try:
                            # Scroll to make label visible
                            label_el = self.driver.find_element(*self._by(cb_sel))
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", label_el)
                            time.sleep(0.5)
                            
                            self.safe_actions.safe_click(cb_sel, by=self._by(cb_sel)[0])
                        except Exception as e:
                            logger.warning(f"Collabera: Failed to click consent label {cb_key}: {e}")
                        logger.info(f"  [OK] Clicked [{cb_key}]")
                        time.sleep(0.5)
                    except Exception as inner_e:
                        logger.debug(f"  [SKIP] [{cb_key}] not found: {inner_e}")

            # ── Step 4: Upload Resume ──────────────────────────────────────────
            resume_path = self.get_resume_path()
            resume_sel  = form_fields.get("resume_upload")
            if resume_path and resume_sel:
                try:
                    file_input = self.driver.find_element(*self._by(resume_sel))
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", file_input
                    )
                    time.sleep(1)
                    self.driver.execute_script(
                        "arguments[0].style.display='block'; arguments[0].style.visibility='visible';",
                        file_input,
                    )
                    file_input.send_keys(resume_path)
                    logger.info("  [OK] Resume attached successfully.")
                    time.sleep(2.5)
                except Exception as e:
                    logger.error(f"  [ERROR] Resume upload failed: {e}")

            # ── Step 5: Submit Form (with DRY_RUN guard) ───────────────────────
            submit_btn_sel = form_fields.get("submit_btn")
            if submit_btn_sel:
                submit_btn = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(self._by(submit_btn_sel))
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    submit_btn,
                )
                time.sleep(1.5)

                if guards.is_dry_run():
                    self.driver.execute_script(
                        "arguments[0].style.border = '5px solid orange';", submit_btn
                    )
                    logger.info("! DRY RUN — Submit button highlighted but NOT clicked.")
                    self._record_application(listing, job_url, job_title, "success", "Dry run")
                    return True
                else:
                    submit_btn = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable(self._by(submit_btn_sel))
                    )
                    self.human.human_click(submit_btn)
                    logger.info("Collabera: Submit clicked — waiting for confirmation...")

                    if self._verify_submission():
                        logger.info("Collabera: Successfully verified application submission!")
                        self._record_application(listing, job_url, job_title, "success")
                        return True
                    else:
                        raise Exception("Submission verification failed: Confirmation not found after click.")

            return False

        except Exception as e:
            logger.error(f"Collabera Apply Form failed: {e}")
            self._record_application(listing, job_url, job_title, "failed", str(e))
            return False

    def _verify_submission(self):
        """Checks if the application was actually submitted by looking for success indicators."""
        time.sleep(5)

        # 1. Check URL for common success patterns
        if "success" in self.driver.current_url.lower() or "confirm" in self.driver.current_url.lower():
            logger.info("  [YES] Verified via URL redirection")
            return True

        # 2. Check for common success text on the page
        success_indicators = ["thank you", "received", "submitted", "success"]
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            for indicator in success_indicators:
                if indicator in page_text:
                    logger.info(f"  [YES] Verified via page text: '{indicator}'")
                    return True
        except Exception:
            pass

        return False

    def _record_application(self, listing, job_url, job_title, status, error=None):
        """Record application outcome in execution tracker and CSV."""
        external_id = (
            listing.get("external_id", "unknown")
            if isinstance(listing, dict)
            else getattr(listing, "external_job_id", "unknown")
        )
        if status == "success":
            execution_tracker.record_success("Collabera", str(external_id), str(job_title), str(job_url))
        else:
            execution_tracker.record_error("Collabera", str(external_id), str(job_title), str(job_url), str(error))

        csv_tracker.update_job_status(
            "collabera",
            job_url,
            "applied" if status == "success" else "failed",
            attempts_inc=1,
            last_error=error,
        )