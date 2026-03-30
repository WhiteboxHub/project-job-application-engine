import os
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.captcha_handler import CaptchaHandler
from core.human_behavior import HumanBehavior
from core.logger import logger
from core.safe_actions import SafeActions
from data.csv_tracker import tracker as csv_tracker
from data.db_duckdb import db_duckdb
from models.config_models import JobListing
from strategies.base import BaseStrategy


class WiproStrategy(BaseStrategy):
    """
    Wipro job application automation strategy.

    This strategy handles:
    - Job search and discovery on Wipro's careers portal
    - Automated form filling with human-like behavior
    - Resume upload automation
    - reCAPTCHA detection and handling
    - Application tracking in database and CSV

    Wipro typically uses a custom ATS platform, so this implementation
    includes flexible selectors that can be adjusted based on the actual
    portal structure.
    """

    def __init__(
        self, driver, job_site, selectors, db_session=None, candidate_data=None
    ):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.db_session = db_session
        self.job_site = job_site
        self.config_data = self._load_config()
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=120)
        self.safe_actions = SafeActions(driver)
        self._duckdb = db_duckdb

        # Wipro careers portal base URL
        self.portal_url = "https://careers.wipro.com/"

        # Use selectors from database (passed via parent class)
        # selectors dict contains 'listing' and 'application' keys with JSON configs
        # Flatten them for easier access
        self.selectors_config = {}
        if selectors:
            for selector_type, config in selectors.items():
                if isinstance(config, dict):
                    self.selectors_config.update(config)

        logger.info(f"Loaded {len(self.selectors_config)} selector(s) from database")

        # Debug logging
        if self.db_session:
            logger.info("[OK] Database session available - will save to DuckDB")
        else:
            logger.warning("[WARNING] No database session - will only use CSV tracking")

    def save_screenshot(self, name):
        """Screenshots disabled for Wipro automation."""
        return

    def _load_config(self):
        """Return dynamically injected candidate data."""
        if self.candidate_data is not None:
            logger.info("Using dynamically injected candidate_data")
            return self.candidate_data
        logger.error("No candidate_data was injected into the strategy.")
        return {}

    # _load_selectors method removed - selectors are now loaded from database

    def login(self):
        """
        Check if login is required for Wipro portal.
        Most career portals allow guest applications.
        """
        logger.info("Wipro: Checking login requirements...")

        try:
            # Robust navigation loop (max 3 tries)
            for attempt in range(3):
                logger.info(
                    f"Opening Wipro careers portal (Attempt {attempt + 1}): {self.portal_url}"
                )
                self.driver.get(self.portal_url)

                # Wait for page response - give it more time on slow networks
                time.sleep(8)

                # Verify URL and content
                current_url = getattr(self.driver, "current_url", "")
                body_text = ""
                try:
                    body_el = self.driver.find_element(By.TAG_NAME, "body")
                    body_text = body_el.text.strip()
                    body_len = len(body_text)
                except:
                    body_len = 0

                if current_url and "about:blank" not in current_url and body_len > 100:
                    logger.info(
                        f"  [OK] Portal loaded successfully: {current_url} (Body: {body_len} chars)"
                    )
                    break
                else:
                    logger.warning(
                        f"  [!] Found blank or empty page ({current_url}). Body length: {body_len}"
                    )
                    if body_len > 0:
                        snippet = body_text[:100].replace("\n", " ")
                        logger.warning(f"  [!] Content snippet: '{snippet}'")

                    if attempt == 2:
                        logger.error("  [FATAL] Failed to load portal after 3 attempts")
                        return False

            logger.info("[OK] Portal loaded - no login required (guest mode)")
            return True

        except Exception as e:
            logger.error(f"Error accessing Wipro portal: {e}")
            return False

    def find_jobs(self):
        """
        Search for jobs on Wipro careers portal.
        Returns list of job dicts with: {'job_title': '...', 'external_id': '...', 'job_url': '...'}
        """
        if not self.config_data:
            logger.error("No configuration data available")
            return []

        # Get search parameters
        search = self.config_data.get("search", {})
        
        # STRICTION: Use ONLY keywords from run_parameters (Whitebox API)
        keywords_list = search.get("keywords", [])
        keyword = search.get("keyword")
        
        # Use first array item if plural 'keywords' is provided but singular isn't
        if keywords_list and not keyword:
            keyword = keywords_list[0]
            
        if not keyword:
            logger.error(
                "[ERROR] Wipro: No search keywords found in candidate data! "
                "Ensure Whitebox API is sending keywords."
            )
            return []
            
        location = search.get("location", "")

        logger.info(f"\n{'=' * 60}")
        logger.info(f"[SEARCH] Searching Wipro Jobs: '{keyword}' in '{location}'")
        logger.info(f"{'=' * 60}")

        all_jobs = []
        seen_urls = set()

        try:
            # Navigate to the main careers portal with retry
            for attempt in range(3):
                logger.info(
                    f"  [>] Navigating to Wipro Careers portal to begin search (Attempt {attempt + 1}): {self.portal_url}"
                )
                self.driver.get(self.portal_url)
                time.sleep(8)  # Increased wait

                current_url = self.driver.current_url
                if current_url and "about:blank" not in current_url:
                    break
                logger.warning(
                    f"  [!] Navigation failed (lands on {current_url}). Retrying..."
                )
                if attempt == 2:
                    logger.error(
                        "  [!] Could not escape about:blank. Page might be blocked or driver broken."
                    )
                    return []

            self._wait_for_loading_spinner(timeout=15)
            time.sleep(2)  # Brief stabilize

            # Debug: Log current URL to verify navigation worked
            logger.info(f"  [>] Current URL: {self.driver.current_url}")

            # Accept cookies if banner present (common on many pages)
            try:
                cookie_selectors = self.selectors_config.get(
                    "cookie_accept_button", ""
                ).split(", ")
                for selector in cookie_selectors:
                    if not selector:
                        continue
                    try:
                        cookie_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if cookie_btn.is_displayed():
                            cookie_btn.click()
                            logger.info("  [+] Accepted cookies")
                            time.sleep(1)
                            break
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Cookie acceptance skipped: {e}")

            # Fill search form
            try:
                logger.info("  [>] Attempting manual search form fill...")

                # Expand search options if necessary
                expand_selectors = self.selectors_config.get("expand_search_button", "")
                if expand_selectors:
                    try:
                        expand_search_btn = self._find_element_by_selectors(
                            expand_selectors, timeout=3
                        )
                        if expand_search_btn and expand_search_btn.is_displayed():
                            self.human.human_click(expand_search_btn)
                            logger.info("  [+] Clicked to expand search options")
                            time.sleep(1)
                    except Exception:
                        pass

                # Enter keyword
                keyword_selectors = self.selectors_config.get("keyword_input", "")
                if keyword_selectors:
                    logger.info(
                        f"  [>] Looking for keyword field: {keyword_selectors[:50]}..."
                    )
                    keyword_input = self._find_element_by_selectors(
                        keyword_selectors, timeout=10
                    )
                    if keyword_input:
                        self.human.fill_text_field(keyword_input, keyword)
                        logger.info(f"  [+] Entered keyword: {keyword}")
                        time.sleep(1)
                    else:
                        logger.warning("  [!] Keyword input field not found")

                # Enter location
                if location:
                    location_selectors = self.selectors_config.get("location_input", "")
                    if location_selectors:
                        logger.info(
                            f"  [>] Looking for location field: {location_selectors[:50]}..."
                        )
                        loc_el = self._find_element_by_selectors(
                            location_selectors, timeout=5
                        )
                        if loc_el:
                            self.human.fill_text_field(loc_el, location)
                            logger.info(f"  [+] Entered location: {location}")
                            time.sleep(1)
                        else:
                            logger.warning("  [!] Location input field not found")

                # Click search button
                search_btn_selectors = self.selectors_config.get("search_button", "")
                if search_btn_selectors:
                    logger.info(
                        f"  [>] Looking for search button: {search_btn_selectors[:50]}..."
                    )
                    search_btn = self._find_element_by_selectors(
                        search_btn_selectors, timeout=5
                    )
                    if search_btn:
                        try:
                            search_btn.click()
                        except:
                            self.driver.execute_script(
                                "arguments[0].click();", search_btn
                            )
                        logger.info("  [+] Clicked search button")
                        self._wait_for_loading_spinner(timeout=20)
                        # We explicitly wait for job cards right after this block anyway
                    else:
                        logger.warning("  [!] Search button not found")

            except Exception as e:
                logger.debug(f"Search form fill check failed: {e}")

            # ------------------------------------------------------------------ #
            # Pagination Loop                                                    #
            # ------------------------------------------------------------------ #
            # Wait explicitly for job cards to appear before polling (max 20s)
            logger.info("  [>] Waiting for job cards to render (a.jobCardTitle)...")
            try:
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, 'a.jobCardTitle, a[class*="jobCardTitle"]')
                    )
                )
                logger.info("  [OK] Job cards detected on page")
            except Exception:
                logger.warning(
                    "  [!] Job cards not detected within 20s - will still attempt JS extraction"
                )

            page_num = 1
            while True:
                # ---- Extract jobs using direct Selenium find_elements (reliable) ----
                logger.info(
                    f"  [+] (Page {page_num}) Extracting job cards with Selenium..."
                )
                page_job_elements = []

                # Wait for job cards to appear (up to 30s)
                try:
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located(
                            (
                                By.CSS_SELECTOR,
                                'a.jobCardTitle, a[class*="jobCardTitle"]',
                            )
                        )
                    )
                    page_job_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, 'a.jobCardTitle, a[class*="jobCardTitle"]'
                    )
                    logger.info(
                        f"  [+] Found {len(page_job_elements)} job card elements on page {page_num}"
                    )
                except Exception as e:
                    logger.warning(f"  [!] No job cards found on page {page_num}: {e}")
                    self.save_screenshot(f"debug_wipro_no_jobs_p{page_num}")
                    break

                if not page_job_elements:
                    logger.warning(f"  [!] No job cards on page {page_num}. Stopping.")
                    self.save_screenshot(f"debug_wipro_no_jobs_p{page_num}")
                    break

                # Process extracted job cards
                page_jobs_count = 0
                for el in page_job_elements:
                    try:
                        title = (
                            el.text
                            or el.get_attribute("title")
                            or el.get_attribute("aria-label")
                            or ""
                        ).strip()
                        job_url = el.get_attribute("href") or ""

                        if not title or not job_url:
                            continue
                        if job_url in seen_urls:
                            continue

                        # Dedup check via DuckDB
                        try:
                            # Extract external ID for DB check
                            job_id = (
                                job_url.split("/")[-2]
                                if "/job/" in job_url
                                else job_url
                            )
                            if self._duckdb.is_already_applied(job_id, "wipro"):
                                logger.info(
                                    f"  ⏭️ Already applied (DB check) — skipping: {title}"
                                )
                                continue
                        except Exception as de:
                            logger.debug(f"DuckDB deduplication check failed: {de}")

                        seen_urls.add(job_url)

                        job_entry = {
                            "job_title": title,
                            "job_url": job_url,
                            "external_id": job_url.split("/")[-2]
                            if "/job/" in job_url
                            else "N/A",
                        }

                        all_jobs.append(job_entry)
                        self._save_job_to_db(job_entry)
                        page_jobs_count += 1
                    except Exception as e:
                        logger.debug(f"  Error processing job element: {e}")
                        continue

                logger.info(
                    f"  [+] Collected {page_jobs_count} new jobs from page {page_num}"
                )

                # Try to go to next page
                try:
                    next_btn = self._find_element_by_selectors(
                        self.selectors_config.get("next_page", ""), timeout=5
                    )

                    if next_btn and next_btn.is_displayed():
                        # SAP sometimes uses custom attributes or classes to disable buttons
                        is_disabled = next_btn.get_attribute(
                            "aria-disabled"
                        ) == "true" or "sapMBtnDisabled" in (
                            next_btn.get_attribute("class") or ""
                        )

                        if is_disabled:
                            logger.info("  - No more pages (Next button disabled)")
                            break

                        # Try standard click first, fallback to JS
                        try:
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center'});",
                                next_btn,
                            )
                            time.sleep(1)
                            self.human.human_click(next_btn)
                        except Exception as e:
                            logger.debug(
                                f"  Standard click failed, attempting JS click: {e}"
                            )
                            self.driver.execute_script(
                                "arguments[0].click();", next_btn
                            )

                        logger.info(f"  > Navigating to page {page_num + 1}...")
                        self._wait_for_loading_spinner(timeout=15)
                        time.sleep(1)  # Brief stabilize
                        page_num += 1
                    else:
                        logger.info(
                            "  - No more pages (Next button not found or not visible)"
                        )
                        break

                except Exception as e:
                    logger.debug(f"  - Pagination error (stopping): {e}")
                    break

            logger.info(f"\n{'=' * 60}")
            logger.info(f"[OK] Job Discovery Complete: {len(all_jobs)} jobs found")
            logger.info(f"{'=' * 60}\n")

        except Exception as e:
            logger.error(f"Error during job search: {e}")
            import traceback

            traceback.print_exc()

        return all_jobs

    def apply(self, listing):
        """
        Apply to a single job listing.

        Args:
            listing: JobListing object or dictionary

        Returns:
            True if application successful, False otherwise
        """
        # Ensure listing is a JobListing object or has dict access
        if hasattr(listing, "job_url"):
            url = listing.job_url
            title = getattr(listing, "job_title", "Unknown")
        else:
            url = listing.get("job_url", "")
            title = listing.get("job_title", "Unknown")

        # --- PRE-CHECK: Skip if already applied ---
        try:
            # Check CSV tracker
            status_info = csv_tracker.get_job_status("wipro", url)
            if status_info and status_info.get("status") == "applied":
                logger.info(f"  [SKIPPED] Already applied to: {title}")
                return True  # Treat as success so we move to next job
        except Exception as e:
            logger.debug(f"Pre-check failed: {e}")

        from types import SimpleNamespace

        from config.settings import settings
        from engine.guards import guards

        # Normalize listing to handle both JobListing object and dictionary
        if isinstance(listing, dict):
            listing = SimpleNamespace(**listing)

        # Check if we can apply
        if not guards.can_apply():
            logger.info("Application limit reached - stopping")
            return False

        # Pre-check: skip if already applied (DuckDB)
        try:
            job_url = listing.job_url
            job_id = job_url.split("/")[-2] if "/job/" in job_url else job_url
            if self._duckdb.is_already_applied(job_id, "wipro"):
                logger.info(
                    f"  ⏭️ Already applied (DB check) — skipping: {listing.job_title}"
                )
                return True  # Treat as success so we move to next job
        except Exception as e:
            logger.debug(f"DuckDB pre-check failed: {e}")

        # Check CSV tracker
        try:
            status = csv_tracker.get_job_status("wipro", listing.job_url)
            if status and status.get("status") == "applied":
                logger.info(
                    f"Already applied to this job (CSV check), skipping: {listing.job_url}"
                )
                return True  # Treat as success so we move to next job
        except Exception:
            pass

        logger.info(f"\n{'=' * 60}")
        logger.info(f"[APPLY] Applying to: {listing.job_title}")
        logger.info(f"URL: {listing.job_url}")
        logger.info(f"{'=' * 60}")

        try:
            # Navigate to job posting
            logger.info(f"  [>] Loading job URL: {listing.job_url}")
            self.driver.get(listing.job_url)

            # --- Robust Navigation Guard ---
            # Wait for any response, check for blank page
            time.sleep(3)
            current_url = getattr(self.driver, "current_url", "Unknown")
            if not current_url or "about:blank" in current_url:
                logger.warning("  [!] Landed on blank page. Triggering JS reload...")
                self.driver.execute_script("window.location.reload();")
                time.sleep(5)

            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(4)  # Wait for SAP UI5 hydration

            # Check for "Already Applied" message before proceeding
            if self._check_already_applied(listing.job_url):
                return True

            # Click Apply button (TWO-STEP PROCESS for Wipro)
            # Step 1: Click the dropdown button to open menu
            apply_selectors = self.selectors_config.get("apply_button_dropdown")
            if not apply_selectors:
                logger.error("Selector 'apply_button_dropdown' not found in config")
                return False

            apply_dropdown_btn = self._find_element_by_selectors(
                apply_selectors,
                wait_for_visible=False,  # Wait manually for hydration
                timeout=10,
            )

            if not apply_dropdown_btn:
                # One last check for "Already Applied" if button is missing
                if self._check_already_applied(listing.job_url):
                    return True
                logger.error("Could not find Apply dropdown button")
                return False

            # Use a more robust click for the dropdown
            try:
                # 1. Scroll and Focus first
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});",
                    apply_dropdown_btn,
                )
                time.sleep(1)
                self.driver.execute_script("arguments[0].focus();", apply_dropdown_btn)
                time.sleep(0.5)

                # 2. Try Human Click
                self.human.human_click(apply_dropdown_btn)
            except Exception as e:
                logger.warning(f"  [!] Human click for dropdown failed, using JS: {e}")
                self.driver.execute_script("arguments[0].click();", apply_dropdown_btn)

            logger.info("  [+] Clicked Apply dropdown button")
            time.sleep(3)  # Wait for dropdown menu to appear

            # Step 2: Click "Apply Now" in the menu
            menu_item_selectors = self.selectors_config.get("apply_button_menu_item")
            # Normalize menu item selectors to a list for thorough searching
            if isinstance(menu_item_selectors, str):
                menu_item_selectors = [
                    s.strip() for s in menu_item_selectors.split(",")
                ]
            elif not menu_item_selectors:
                menu_item_selectors = []

            # Add broad fallback selectors for "Apply Now"
            menu_item_selectors.extend(
                [
                    "//a[contains(@class, 'apply')]",
                    "//button[contains(@class, 'apply')]",
                    "//span[contains(text(), 'Apply Now')]/..",
                    "a[data-testid='apply_now_link']",
                    ".apply-now-link",
                ]
            )

            apply_menu_item = self._find_element_by_selectors(
                menu_item_selectors, wait_for_visible=True, timeout=8
            )

            if apply_menu_item:
                try:
                    # Focus menu item as well
                    self.driver.execute_script("arguments[0].focus();", apply_menu_item)
                    self.human.human_click(apply_menu_item)
                except Exception:
                    self.driver.execute_script("arguments[0].click();", apply_menu_item)
                logger.info("  [+] Clicked Apply Now menu item")
            else:
                logger.error("Could not find Apply Now menu item in dropdown")
                self.save_screenshot("apply_menu_not_found")
                return False
            self._wait_for_loading_spinner(timeout=15)
            time.sleep(1)  # Brief stabilize after hydration

            # --- 1. Login check FIRST (Fastest path if redirected) ---
            try:
                logger.info("Checking for login requirement...")
                login_email = self._find_element_by_selectors(
                    self.selectors_config.get("login_email_input", ""),
                    timeout=3,  # Reduced timeout for initial check
                )

                # Verify it's actually a login field, not just an email field in a form
                is_real_login = False
                if login_email:
                    # Check URL or if it's near a password field
                    current_url = self.driver.current_url.lower()
                    if "login" in current_url or "auth" in current_url:
                        is_real_login = True
                    else:
                        # Check if password field is actually present
                        pass_el = self._find_element_by_selectors(
                            self.selectors_config.get("login_password_input", ""),
                            timeout=1,
                        )
                        if pass_el:
                            is_real_login = True

                if login_email and is_real_login:
                    logger.info("Login page detected - signing in...")

                    # Get credentials from config
                    wipro_creds = self.config_data.get("wipro_credentials", {})
                    email = wipro_creds.get("email", "")
                    password = wipro_creds.get("password", "")

                    if not email or not password:
                        logger.error("Wipro credentials missing from config!")
                        return False

                    # Fill email - Restore human-like typing
                    self.human.fill_text_field(login_email, email)
                    logger.info(f"  [+] Filled email: {email}")

                    # Fill password
                    password_selectors = self.selectors_config.get(
                        "login_password_input"
                    )
                    if password_selectors:
                        login_password = self._find_element_by_selectors(
                            password_selectors
                        )
                    if login_password:
                        self.human.fill_text_field(login_password, password)
                        logger.info("  [+] Filled password")

                    # Click Sign In button
                    submit_selectors = self.selectors_config.get("login_submit_button")
                    if submit_selectors:
                        sign_in_btn = self._find_element_by_selectors(
                            submit_selectors, wait_for_visible=True
                        )
                    if sign_in_btn:
                        self.human.human_click(sign_in_btn)
                        logger.info("  [+] Clicked Sign In button")
                        self._wait_for_loading_spinner(timeout=15)
                        time.sleep(1)  # Brief stabilize after login

                        # After login, we might need a fresh "Already Applied" check
                        if self._check_already_applied(listing.job_url):
                            return False
                    else:
                        logger.error("Could not find Sign In button")
                        return False
                else:
                    logger.info(
                        "No login page detected - proceeding to application form"
                    )
            except Exception as e:
                logger.warning(
                    f"Login page check failed (may be already logged in): {e}"
                )

            # --- 2. Check for "Already Applied" message (Post-navigation or Post-login) ---
            if self._check_already_applied(listing.job_url):
                return True

            # --- 3. Expand all sections ---
            self._ensure_sections_expanded()

            # DEBUG: Save page source after expansion
            try:
                with open("debug_application_form.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                logger.info(
                    "  [DEBUG] Saved application form source to debug_application_form.html"
                )
            except Exception as e:
                logger.warning(f"  [DEBUG] Failed to save page source: {e}")

            # Debug: List sections found
            try:
                section_headers = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".rcmFormSectionTopBar span, .rcmFormSection h2, .rcmFormSection h3, .rcmFormSection h4, span.rcmFormSectionTopBar",
                )
                if not section_headers:
                    logger.warning(
                        "  [!] No form sections or headers found. Checking for 'Already Applied' again..."
                    )
                    if self._check_already_applied(listing.job_url):
                        return True
                    # If still not found, we might just be on a slow-loading page
                    logger.debug(
                        "Still no sections found, but no 'Already Applied' message. Continuing cautiously."
                    )
                else:
                    logger.info(
                        f"  [DEBUG] Found {len(section_headers)} section headers:"
                    )
                    for header in section_headers:
                        h_text = header.text.strip()
                        if h_text:
                            h_tag = header.tag_name
                            h_class = header.get_attribute("class")
                            logger.info(
                                f"    - '{h_text}' (Tag: {h_tag}, Class: {h_class})"
                            )
            except:
                pass

            # Fill application form
            applicant = self.config_data.get("applicant", {})
            search_config = self.config_data.get("search", {})

            # --- Form Initialization (Resume Upload First) ---
            # We upload the resume first because it often triggers a form reset or page refresh.
            resume_path = self.config_data.get("resume_path", "")
            if resume_path:
                success = self._upload_resume(resume_path)
                if not success:
                    logger.warning(
                        "[WARNING] Resume upload may have failed, but continuing..."
                    )
                else:
                    logger.info(
                        "  [+] Resume uploaded successfully - waiting for parsing/hydration..."
                    )
                    self._wait_for_loading_spinner(timeout=15)
                    time.sleep(
                        5
                    )  # Give SAP/SuccessFactors more time to parse and refresh fields

            # --- Profile Information Section ---
            # 1. First Name (Mandatory)
            self._fill_field("first_name_input", applicant.get("first_name", ""))

            # 2. Last Name (Mandatory)
            self._fill_field("last_name_input", applicant.get("last_name", ""))

            # 3. Email (Mandatory)
            self._fill_field("email_input", applicant.get("email", ""))

            # 4. Phone (Mandatory)
            self._fill_field("phone_input", applicant.get("phone", ""))

            # 4a. Preferred Name and Social URL (Optional)
            self._fill_field(
                "preferred_name_input", applicant.get("preferred_name", "")
            )
            self._fill_field(
                "social_account_url_input", applicant.get("social_account_url", "")
            )

            # 4b. Country Code (Dropdown)
            country_code = applicant.get("countrycode", "")
            self._handle_dropdown("country_code_select", country_code)

            # 4b. Gender (Dropdown)
            gender = applicant.get("gender", "")
            self._handle_dropdown("gender_select", gender)

            # 4c. Disability Assistance (Optional)
            disability_assist = applicant.get("disability_assistance", "No")
            self._handle_dropdown("disability_assistance_select", disability_assist)
            if disability_assist.lower() == "yes":
                self._fill_field(
                    "disability_assistance_explain_input",
                    applicant.get("disability_assistance_explain", ""),
                )

            # --- Dropdowns FIRST to avoid AJAX resetting inputs ---
            # 8. Country (Mandatory - Dropdown)
            country = applicant.get("country", "")
            self._handle_dropdown("country_select", country)

            # 9. State (Mandatory - Dropdown)
            state = applicant.get("state", "")
            self._handle_dropdown("state_select", state)

            # 10. Employment Question (Mandatory)
            employed_before = applicant.get("employed_before_wipro", "")
            self._handle_dropdown("employed_before_select", employed_before)

            # --- Inputs AFTER Dropdowns ---
            # 5. Address (Mandatory)
            address = applicant.get("address", "")
            self._fill_field("address_input", address)

            # 6. City (Mandatory)
            city = applicant.get("city", "")
            self._fill_field("city_input", city)

            # 7. Postal Code (Mandatory)
            zip_code = applicant.get("zip_code", "")
            self._fill_field("zip_input", zip_code)

            # Employee ID Logic
            emp_id = applicant.get("wipro_employee_id", "")
            self._fill_field("employee_id_input", emp_id if emp_id else "NA")

            # --- Professional Experience Section ---
            self._ensure_section_expanded("experience_section_trigger")

            # Remove any auto-populated experience rows from resume parsing
            self._remove_extra_experience_rows()

            try:
                # Fill latest experience if available
                experience = applicant.get("experience", [])
                if experience:
                    latest_job = experience[0]

                    # Fill Title
                    self._fill_field("job_title_input", latest_job.get("title", ""))

                    # Fill Company
                    self._fill_field("company_input", latest_job.get("company", ""))

                    # Fill Dates
                    self._fill_field(
                        "start_date_input", latest_job.get("start_date", "")
                    )
                    self._fill_field("end_date_input", latest_job.get("end_date", ""))

                    # Fill Country/Region for Experience
                    exp_country = latest_job.get("country", "")
                    self._handle_dropdown("exp_country_select", exp_country)

                    # Fill State for Experience
                    exp_state = latest_job.get("state", "")
                    self._handle_dropdown("exp_state_select", exp_state)

                    # Fill City for Experience
                    exp_city = latest_job.get("city", "")
                    self._fill_field("exp_city_input", exp_city)

                    # Debug screenshot
                    self.save_screenshot("debug_exp_section")

                    logger.info("  [+] Filled Professional Experience section")
            except Exception as e:
                logger.warning(f"Failed to fill experience section: {e}")

            # --- Education Section ---
            self._ensure_section_expanded("education_section_trigger")
            try:
                education = applicant.get("education", [])
                if education:
                    latest_edu = education[0]

                    # Fill Education Type
                    edu_type = latest_edu.get("education_type", "")
                    self._handle_dropdown("edu_type_select", edu_type)

                    # Fill Degree
                    degree = latest_edu.get("degree", "")
                    self._handle_dropdown("edu_degree_select", degree)

                    # Fill School/University
                    # Using case-insensitive get to support both 'school' and 'university' from JSON
                    school_val = latest_edu.get("university") or latest_edu.get(
                        "school", ""
                    )
                    self._fill_field("edu_school_input", school_val)

                    # Fill Major (if present in selectors)
                    major = latest_edu.get("major", "")
                    if major:
                        self._handle_dropdown("edu_major_select", major)

                    # Fill Dates
                    self._fill_field("edu_start_date", latest_edu.get("start_date", ""))
                    self._fill_field("edu_end_date", latest_edu.get("end_date", ""))

                    # Fill Year of Passing
                    grad_date = latest_edu.get("year_of_passing", "")
                    self._fill_field("edu_grad_date", grad_date)

                    # Fill Country/Region for Education
                    edu_country = latest_edu.get("country", "")
                    self._handle_dropdown("edu_country_select", edu_country)

                    # Fill State for Education
                    edu_state = latest_edu.get("state", "")
                    self._handle_dropdown("edu_state_select", edu_state)

                    # Fill City for Education
                    edu_city = latest_edu.get("city", "")
                    self._fill_field("edu_city_input", edu_city)

                    # Debug screenshot (moved to end of section)
                    self.save_screenshot("debug_edu_section")

                    logger.info("  [+] Filled Education section")
            except Exception as e:
                logger.warning(f"Failed to fill education section: {e}")

            # --- Job Specific Information & Voluntary Self-ID ---
            try:
                logger.info("  [>] Entering Job Specific Information section...")
                self._wait_for_loading_spinner(timeout=10)
                time.sleep(2)  # Final stabilization before compliance questions

                # Work Authorization
                auth_val = applicant.get("auth_country_select", "")
                self._handle_dropdown("auth_country_select", auth_val)

                auth_work_country = applicant.get("auth_work_country", "")
                self._handle_dropdown("auth_work_country_select", auth_work_country)

                visa_status = applicant.get("visa_status", "")
                self._handle_dropdown("visa_status_select", visa_status)

                sponsorship = applicant.get("sponsorship_future", "")
                self._handle_dropdown("sponsorship_future_select", sponsorship)

                citizenship = applicant.get("citizenship", "")
                self._handle_dropdown("citizenship_select", citizenship)

                govt_employed = applicant.get("govt_employed", "")
                self._handle_dropdown("govt_employed_select", govt_employed)

                # Compliance / Self-ID
                race = applicant.get("race", "")
                self._handle_dropdown("race_select", race)

                veteran = applicant.get("veteran", "")
                self._handle_dropdown("veteran_select", veteran)

                disability = applicant.get("disability", "")
                self._handle_dropdown("disability_select", disability)

                logger.info("  [+] Filled Job Specific & Compliance sections")
            except Exception as e:
                logger.warning(f"Failed to fill job specific section: {e}")

            # Check for terms/consent checkbox
            try:
                terms_selectors = self.selectors_config.get("terms_checkbox", "")
                if terms_selectors:
                    terms_checkbox = self._find_element_by_selectors(
                        terms_selectors.split(", ")
                        if isinstance(terms_selectors, str)
                        else terms_selectors
                    )
                    if terms_checkbox and not terms_checkbox.is_selected():
                        self.human.human_click(terms_checkbox)
                        logger.info("  [+] Accepted terms and conditions")
            except Exception:
                logger.debug("No terms checkbox found (optional)")

            # Check for reCAPTCHA
            if self.captcha_handler.detect_recaptcha():
                logger.warning(
                    "[WARNING] reCAPTCHA detected - waiting for manual solve..."
                )
                self.captcha_handler.wait_for_manual_solve()

            # Save application (Explicitly requested by user for persistence)
            # try:
            #     save_btn_selectors = [
            #         "span.rcmSaveButton",
            #         "span[id*='_saveBtn']",
            #         "//span[contains(@class, 'rcmSaveButton')]",
            #         "//span[contains(text(), 'Save')]"
            #     ]
            #     save_btn = self._find_element_by_selectors(save_btn_selectors, timeout=5)
            #     if save_btn:
            #         self.human.human_click(save_btn)
            #         logger.info("  [+] Clicked 'Save' button before submission")
            #         self._wait_for_loading_spinner(timeout=15)
            #         time.sleep(2)  # Wait for save/AJAX to complete
            # except Exception as e:
            #     logger.debug(f"Save action failed (optional): {e}")

            # Submit application (skip if dry-run mode)
            if settings.DRY_RUN:
                logger.info(f"[SEARCH] DRY RUN MODE - Skipping submission.")
                csv_tracker.update_job_status(
                    "wipro", listing.job_url, "skipped (dry-run)"
                )
                return True

            # Find and click submit button
            # NOTE: Using multiple robust selectors for the final Submit/Apply button
            # Also re-locating after Save/AJAX wait to avoid Staleness
            submit_selectors = [
                "span[id*='_submitBtn']",
                "button[id*='_submitBtn']",
                "span[id*='_applyBtn']",
                "button.rcmSubmitButton",
                "//span[text()='Apply' or contains(text(), 'Submit')]",
                "//button[contains(text(), 'Apply') or contains(text(), 'Submit')]",
                "//span[contains(@class, 'rcmSubmitButton')]",
            ]

            submit_btn = self._find_element_by_selectors(
                submit_selectors, timeout=5, wait_for_visible=True
            )

            if submit_btn:
                self.human.human_click(submit_btn)
                logger.info("  [+] Clicked Submit button")

                logger.info(
                    "  [*] Waiting 15s for submission results / validation errors..."
                )
                time.sleep(15)

                # Validate form AFTER submitting (errors appear now)
                if not self._validate_form():
                    logger.error(
                        "[VALIDATION] Submission failed - validation errors detected after submit"
                    )
                    csv_tracker.update_job_status(
                        "wipro",
                        listing.job_url,
                        "failed",
                        attempts_inc=1,
                        last_error="Validation failed after submit",
                    )
                    return False

                # Check for success message explicitly
                if self._check_submission_success():
                    # Mark as applied
                    csv_tracker.update_job_status("wipro", listing.job_url, "applied")
                    logger.info("  [SUCCESS] Application submitted successfully!")
                    return True
                else:
                    logger.error(
                        "  [!] Submitted but could not confirm success message 'Your application has been sent'"
                    )
                    # Take screenshot for debugging missing success message
                    self.save_screenshot("failed_success_message")
                    csv_tracker.update_job_status(
                        "wipro",
                        listing.job_url,
                        "failed",
                        attempts_inc=1,
                        last_error="Submitted but no confirmation message",
                    )
                    return False
            else:
                logger.error("Could not find Submit button")
                csv_tracker.update_job_status(
                    "wipro",
                    listing.job_url,
                    "failed",
                    attempts_inc=1,
                    last_error="No Submit button",
                )
                return False

        except Exception as e:
            logger.error(f"Application failed: {e}")
            self.save_screenshot("application_error")
            return False

    def _wait_for_loading_spinner(self, timeout=10):
        """Wait for SAP UI5 loading indicators to disappear to avoid static sleep times."""
        try:
            spinner_selectors = [
                ".sapUiBlockLayer",
                "div[id*='sap-ui-blocklayer']",
                ".sapMLoadingIndicator",
                ".sapUiLocalBusyIndicator",
                ".sapUiBlyIcon",
            ]
            for selector in spinner_selectors:
                WebDriverWait(self.driver, timeout).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, selector))
                )
        except Exception:
            pass

    def _check_already_applied(self, listing_url):
        """Check for the 'You already applied for this position' message."""
        try:
            from data.csv_tracker import tracker as csv_tracker

            already_applied_selectors = [
                ".rcmJobApplyExceptionMsg",
                "div[id$='_jobApplyExceptionMsg']",
                "//div[contains(@class, 'sapMMessageStrip')]//span[contains(text(), 'already applied')]",
                "//div[contains(@class, 'sapMMessageStrip')]//span[contains(text(), 'submitted')]",
                "//*[contains(text(), 'You already applied for this position')]",
            ]

            msg_el = self._find_element_by_selectors(
                already_applied_selectors, timeout=2, wait_for_visible=False
            )
            if msg_el:
                msg_text = ""
                # Wait briefly for text if it's empty but element exists
                for _ in range(3):
                    try:
                        msg_text = msg_el.text.strip()
                        if not msg_text:
                            content = msg_el.get_attribute("textContent")
                            msg_text = content.strip() if content else ""
                    except Exception:
                        pass

                    if msg_text:
                        break
                    time.sleep(1)

                if msg_text and any(
                    x in msg_text.lower() for x in ["already applied", "submitted"]
                ):
                    logger.info(f"  [!] Detected 'Already Applied' message: {msg_text}")
                    # Update tracker so we don't try this job again
                    csv_tracker.update_job_status("wipro", listing_url, "applied")
                    try:
                        job_id = (
                            listing_url.split("/")[-2]
                            if "/job/" in listing_url
                            else listing_url
                        )
                        self._duckdb.mark_applied(job_id, "wipro")
                    except Exception as de:
                        logger.debug(f"DuckDB mark_applied (pre-check) failed: {de}")
                    return True
        except Exception as e:
            logger.debug(f"Error checking 'already applied' message: {e}")
        return False

    def _check_submission_success(self):
        """Checks if the application success message is present on the page."""
        try:
            logger.info("  [*] Checking for submission success message...")
            # Wait briefly for transition
            time.sleep(3)

            success_msg_selectors = [
                "#applyConfirmMsg",
                "//div[@id='applyConfirmMsg'][contains(text(), 'Your application has been sent')]",
                "#rcmJobApplicationCtr",
                ".msgContent",
                "div.success-message",
                "//span[contains(text(), 'Your application has been sent')]",
            ]

            success_element = self._find_element_by_selectors(
                success_msg_selectors, timeout=10
            )
            if success_element:
                text = (
                    success_element.text
                    or success_element.get_attribute("textContent")
                    or ""
                ).strip()
                if "your application has been sent" in text.lower():
                    logger.info(
                        f"  [SUCCESS] Confirmation message found: '{text[:60]}...'"
                    )
                    return True

            # Final fallback check for the entire container text (case-insensitive)
            container = self.driver.find_elements(By.ID, "rcmJobApplicationCtr")
            if container:
                container_text = container[0].text.lower()
                if "your application has been sent" in container_text:
                    logger.info("  [SUCCESS] Confirmation found in container text.")
                    return True

            # Universal text search as last resort
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if "your application has been sent" in body_text:
                    logger.info("  [SUCCESS] Confirmation found in page body text.")
                    return True
            except:
                pass

            logger.warning("  [!] Success message NOT found on current page.")
            return False
        except Exception as e:
            logger.debug(f"Error checking submission success: {e}")
            return False

    def _validate_form(self):
        """
        Validate the form by checking for section error indicators.
        Returns True if valid, False if errors found.
        """
        logger.info("Validating form sections...")
        try:
            # Find all section headers that might contain error icons
            # Selector based on user provided HTML: .rcmFormSectionTopBar contains .sectionError
            section_headers = self.driver.find_elements(
                By.CSS_SELECTOR, ".rcmFormSectionTopBar"
            )

            has_errors = False
            for header in section_headers:
                try:
                    # check for text to identify section
                    section_name = header.text.strip().split("\n")[0]

                    # Check if error icon is present and NOT hidden
                    # The user snippet shows: class="... sectionError" (visible) vs "... sectionNoError displayNone"
                    # We look for .sectionError. If it exists and does not have 'displayNone' class (or is displayed), it's an error.

                    error_icon = header.find_elements(By.CSS_SELECTOR, ".sectionError")

                    if error_icon:
                        elem = error_icon[0]
                        # Check classes
                        classes = elem.get_attribute("class")
                        is_hidden = "displayNone" in classes or not elem.is_displayed()

                        if not is_hidden:
                            logger.warning(
                                f"  [!] Validation Error in section: '{section_name}'"
                            )
                            has_errors = True
                except Exception as e:
                    continue

            # Also check for any global error messages or standard required field errors
            # Common pattern: .fieldError, .error, etc.
            visible_field_errors = self.driver.find_elements(
                By.CSS_SELECTOR, ".fieldError, .errorContent, .validatorStatusError"
            )
            visible_field_errors = [e for e in visible_field_errors if e.is_displayed()]

            if visible_field_errors:
                logger.warning(
                    f"  [!] Found {len(visible_field_errors)} visible field errors"
                )
                has_errors = True

            if has_errors:
                # Take screenshot of errors
                self.save_screenshot("validation_failed")
                return False

            logger.info("  [OK] Form validation passed")
            return True

        except Exception as e:
            logger.error(f"Error during validation: {e}")
            return False

    def _remove_extra_experience_rows(self):
        """
        Remove any auto-populated professional experience rows from resume parsing.
        Clicks all 'Remove' buttons found in the Professional Experience section.
        """
        try:
            logger.info(
                "  [*] Checking for auto-populated experience rows to remove..."
            )

            # Find all remove buttons in the Professional Experience section
            # Based on HTML: div[role="button"][title="Delete Row"] with class "iconHolder"
            remove_buttons = self.driver.find_elements(
                By.CSS_SELECTOR, 'div[role="button"][title="Delete Row"] .delete_icon'
            )

            if remove_buttons:
                logger.info(
                    f"  [*] Found {len(remove_buttons)} experience row(s) to remove"
                )

                # Click each remove button (iterate in reverse to avoid stale elements)
                for i in range(len(remove_buttons) - 1, -1, -1):
                    try:
                        # Re-find buttons each iteration to avoid stale element issues
                        current_buttons = self.driver.find_elements(
                            By.CSS_SELECTOR, 'div[role="button"][title="Delete Row"]'
                        )

                        if i < len(current_buttons):
                            button = current_buttons[i]
                            if button.is_displayed():
                                self.human.human_click(button)
                                logger.info(f"  [+] Removed experience row {i + 1}")
                                time.sleep(0.5)  # Brief pause after removal
                    except Exception as e:
                        logger.debug(f"Could not remove row {i + 1}: {e}")
                        continue

                logger.info("  [+] Cleared all auto-populated experience rows")
            else:
                logger.info("  [*] No auto-populated experience rows found")

        except Exception as e:
            logger.warning(f"Error removing experience rows: {e}")

    def _fill_field(self, selector_key, value):
        """Helper to fill a form field if selector exists"""
        if not value:
            return False

        try:
            selector = self.selectors_config.get(selector_key)

            # Refine Education date selectors to be section-specific to avoid overlap with Experience
            if selector_key == "edu_start_date" and (
                "ui5-date-picker" in str(selector) or not selector
            ):
                selector = "//div[contains(@class, 'rcmFormSection')][.//*[contains(text(), 'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='Start Date']"
            elif selector_key == "edu_end_date" and (
                "ui5-date-picker" in str(selector) or not selector
            ):
                selector = "//div[contains(@class, 'rcmFormSection')][.//*[contains(text(), 'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='End Date']"
            elif selector_key == "edu_grad_date" and (
                "ui5-date-picker" in str(selector) or not selector
            ):
                selector = "//div[contains(@class, 'rcmFormSection')][.//*[contains(text(), 'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='Year Of Passing']"

            field = self._find_element_by_selectors(
                selector, timeout=5, wait_for_visible=True
            )
            if field:
                # Check current value to see if it already matches target
                current_val = field.get_attribute("value") or ""
                if current_val.strip().lower() == str(value).strip().lower():
                    logger.info(
                        f"  [+] Field {selector_key} already has correct value, skipping..."
                    )
                    return True

                # Handle ui5-date-picker widgets and date fields specially
                is_date_field = (
                    field.tag_name == "ui5-date-picker-xweb-calendar-widget"
                    or "_date" in selector_key.lower()
                    or "date_input" in selector_key.lower()
                    or "grad_date" in selector_key.lower()
                )

                if is_date_field:
                    logger.debug(
                        f"  [>] Special handling for date field {selector_key} (tag: {field.tag_name})"
                    )
                    # More robust event sequence for UI5/SuccessFactors
                    # Specifically for ui5-date-picker, we must ensure the 'value' property is set and 'change' is fired on the widget
                    self.driver.execute_script(
                        """
                        var element = arguments[0];
                        var value = arguments[1];
                        
                        // Set basic attributes
                        element.setAttribute('value', value);
                        element.value = value;
                        
                        // For ui5-date-picker web components
                        if (element.tagName.toLowerCase().includes('date-picker')) {
                            // Some UI5 versions use a specific method or property
                            if (typeof element.setProperty === 'function') {
                                element.setProperty('value', value);
                            }
                        }
                        
                        // Dispatch events standardly
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        element.dispatchEvent(new Event('blur', { bubbles: true }));
                        
                        // Custom juic fire if possible (SuccessFactors specific)
                        if (window.juic && element.id) {
                            var id = element.id.split(':')[0] + ':';
                            try {
                                juic.fire(id, '_handleChange', {target: element});
                            } catch(e) {}
                        }
                    """,
                        field,
                        value,
                    )
                elif "city" in selector_key.lower() or "VFLD" in str(
                    field.get_attribute("name")
                ):
                    logger.debug(
                        f"  [>] Special handling for autocomplete/text field {selector_key}"
                    )
                    self.human.fill_text_field(field, value)
                    self.driver.execute_script(
                        """
                        var element = arguments[0];
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        element.dispatchEvent(new Event('blur', { bubbles: true }));
                    """,
                        field,
                    )
                else:
                    self.human.fill_text_field(field, value)

                logger.info(f"  [+] Filled {selector_key}")
                # Synchronization delay to ensure SAP UI5 backend registers the input
                time.sleep(1)
                HumanBehavior.random_delay(0.2, 0.4)
                return True
        except Exception as e:
            logger.warning(f"Failed to fill {selector_key}: {e}")

        return False

    def _handle_dropdown(self, selector_key, value):
        """
        Handle searchable dropdowns (SuccessFactors style).
        Clicks input, types value, and selects matching option.
        """
        if not value:
            return False

        try:
            # Find the input element (combobox)
            input_element = self._find_element_by_selectors(
                self.selectors_config.get(selector_key),
                timeout=7,
                wait_for_visible=True,
            )

            if not input_element:
                return False

            logger.info(f"  [*] Attempting to select '{value}' for {selector_key}")

            # Scroll and click to open dropdown
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", input_element
            )
            time.sleep(0.5)

            try:
                # Check current value before clicking
                current_val = input_element.get_attribute("value") or ""
                if current_val.strip().lower() == str(value).strip().lower():
                    logger.info(
                        f"  [+] Dropdown {selector_key} already has correct value, skipping..."
                    )
                    return True

                self.human.human_click(input_element)
            except:
                self.driver.execute_script("arguments[0].click();", input_element)
            time.sleep(1.5)

            # Use backspaces to clear instead of .clear() as it's more reliable for some frameworks
            from selenium.webdriver.common.keys import Keys

            input_element.send_keys(Keys.CONTROL + "a")
            input_element.send_keys(Keys.BACKSPACE)
            time.sleep(0.5)

            # Type the value
            self.human.human_type(input_element, value)
            time.sleep(2.5)  # Wait for results to filter

            # SuccessFactors often uses a list box that appears
            # 1. Try to find the exact option with targeted XPaths (Fastest)
            option_selectors = [
                f"//li[@role='option'][normalize-space()='{value}']",
                f"//div[contains(@class, 'sapMListBoxItem')][normalize-space()='{value}']",
                f"//span[contains(text(), '{value}')]",
            ]

            # Use a short timeout for direct XPaths to trigger fallback quickly if missing
            matching_option = self._find_element_by_selectors(
                option_selectors, timeout=4
            )

            if matching_option:
                try:
                    self.human.human_click(matching_option)
                    logger.info(f"  [+] Selected option: {value} (direct match)")
                    time.sleep(1.5)  # Wait for AJAX update
                    return True
                except:
                    self.driver.execute_script("arguments[0].click();", matching_option)
                    time.sleep(1.5)
                    return True

            # 2. Fallback: Find ALL options and filter (Slowest but thorough)
            logger.info(
                f"  [!] Direct match not found, searching all options for '{value}'..."
            )
            all_options = self.driver.find_elements(
                By.CSS_SELECTOR, "li[role='option'], div.sapMListBoxItem, span.sapMText"
            )

            # Step 2a: Strict case-insensitive equality
            for opt in all_options:
                try:
                    opt_text = opt.text.strip()
                    if value.lower() == opt_text.lower():
                        logger.info(
                            f"  [+] Found exact case-insensitive match: '{opt_text}'"
                        )
                        self.human.human_click(opt)
                        time.sleep(1)
                        return True
                except:
                    continue

            # Step 2b: Partial match with guards
            # Do not use partial match for very short strings ("No", "Yes") which easily collide
            if len(value) > 3:
                for opt in all_options:
                    try:
                        opt_text = opt.text.strip()
                        if (
                            value.lower() in opt_text.lower()
                            or opt_text.lower() in value.lower()
                        ):
                            # Guard: 'Male' should not match 'Female'
                            if value.lower() == "male" and "female" in opt_text.lower():
                                continue
                            logger.info(f"  [+] Found partial match: '{opt_text}'")
                            self.human.human_click(opt)
                            time.sleep(1)
                            return True
                    except:
                        continue

            # 3. Final Fallback: Arrow Down + Enter
            logger.info(
                f"  [+] Using keyboard fallback (ARROW_DOWN + ENTER) for {selector_key}"
            )
            input_element.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.5)
            input_element.send_keys(Keys.ENTER)
            time.sleep(1.5)
            return True

        except Exception as e:
            logger.warning(f"Failed to handle dropdown {selector_key}: {e}")

        return False

    def _ensure_sections_expanded(self):
        """Find and click the 'Expand All' sections button to ensure fields are visible."""
        logger.info("  [>] Ensuring all sections are expanded...")
        try:
            # Use a short timeout as this button might not always be present
            expand_btn = self._find_element_by_selectors(
                self.selectors_config.get("expand_all_sections", ""), timeout=5
            )

            if expand_btn:
                btn_text = expand_btn.text.lower()
                # If text exists and says 'collapse', it's already expanded
                if btn_text and "collapse" in btn_text:
                    logger.info("  [OK] Sections already expanded")
                else:
                    logger.info("  [+] Clicking Expand All sections...")
                    # Scroll into view and click
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", expand_btn
                    )
                    time.sleep(0.5)
                    self.human.human_click(expand_btn)
                    time.sleep(3)  # Wait for expansion animation
            else:
                logger.debug(
                    "  [!] Expand All button not found (it might already be in expanded state or doesn't exist on this page)"
                )

        except Exception as e:
            logger.debug(f"  [!] Failed to ensure sections are expanded: {e}")

    def _ensure_section_expanded(self, selector_key):
        """Verify if a section is expanded (via aria-expanded) and click header if closed."""
        try:
            trigger = self._find_element_by_selectors(
                self.selectors_config.get(selector_key),
                timeout=5,
                wait_for_visible=True,
            )

            if trigger:
                # SuccessFactors often puts aria-expanded on the button OR a parent/child
                expanded = trigger.get_attribute("aria-expanded")

                # If we can't find aria-expanded, check if it's on a child span or parent button
                if expanded is None:
                    try:
                        parent = trigger.find_element(By.XPATH, "./..")
                        expanded = parent.get_attribute("aria-expanded")
                    except:
                        pass

                if expanded == "false":
                    logger.info(
                        f"  [*] Section {selector_key} is collapsed (aria-expanded=false) - Expanding..."
                    )
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", trigger
                    )
                    time.sleep(0.5)
                    self.human.human_click(trigger)
                    time.sleep(2)
                else:
                    logger.info(
                        f"  [OK] Section {selector_key} already expanded or state unknown (aria-expanded={expanded})"
                    )

        except Exception as e:
            logger.warning(f"Failed to ensure section {selector_key} is expanded: {e}")

    def _find_element_by_selectors(self, selectors, timeout=10, wait_for_visible=False):
        """
        Try multiple selectors to find an element with XPath/CSS auto-detection.
        Optimized with a 'fast-poll' pass to avoid sequential timeout delays.
        """
        # Convert string to list if needed
        if isinstance(selectors, str):
            if selectors.startswith("//") or selectors.startswith("(//"):
                selector_list = [selectors]
            else:
                selector_list = [s.strip() for s in selectors.split(",")]
        else:
            selector_list = selectors if isinstance(selectors, list) else [selectors]

        # --- PASS 1: Fast-poll (No waiting) ---
        # This prevents waiting 3-10s for multiple stale selectors in a row
        for selector in selector_list:
            if not selector:
                continue
            try:
                by_type = (
                    By.XPATH
                    if (selector.startswith("//") or selector.startswith("(//"))
                    else By.CSS_SELECTOR
                )
                # find_elements is immediate and doesn't throw TimeoutException
                elements = self.driver.find_elements(by_type, selector)
                if elements:
                    for el in elements:
                        if not wait_for_visible or el.is_displayed():
                            logger.debug(f"Found element immediately: {selector}")
                            return el
            except Exception:
                continue

        # --- PASS 2: Sequential Wait (Only if Fast-poll failed) ---
        # We only reach here if the element isn't immediately found
        for selector in selector_list:
            if not selector:
                continue
            try:
                by_type = (
                    By.XPATH
                    if (selector.startswith("//") or selector.startswith("(//"))
                    else By.CSS_SELECTOR
                )

                # Reduced timeout for sequential waits to avoid long hangs
                short_timeout = min(timeout, 3)

                if wait_for_visible:
                    element = WebDriverWait(self.driver, short_timeout).until(
                        EC.visibility_of_element_located((by_type, selector))
                    )
                else:
                    element = WebDriverWait(self.driver, short_timeout).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                return element
            except Exception:
                continue

        return None

    def _find_element_within_parent(self, parent_element, selectors, timeout=3):
        """
        Find an element within a parent container using multiple selectors.

        Args:
            parent_element: Parent WebElement to search within
            selectors: String of comma-separated selectors or list
            timeout: Not used for parent searches (included for consistency)

        Returns:
            WebElement or None
        """
        # Convert string to list if needed
        if isinstance(selectors, str):
            # If it's a single XPath starting with // or (, don't split by commas
            if selectors.startswith("//") or selectors.startswith("(//"):
                selector_list = [selectors]
            else:
                selector_list = [s.strip() for s in selectors.split(",")]
        else:
            selector_list = selectors if isinstance(selectors, list) else [selectors]

        for selector in selector_list:
            if not selector:
                continue

            try:
                # Auto-detect XPath vs CSS
                if selector.startswith("//") or selector.startswith("(//"):
                    by_type = By.XPATH
                    # For XPath within parent, need to add ./ prefix
                    if not selector.startswith("."):
                        selector = "." + selector
                else:
                    by_type = By.CSS_SELECTOR

                element = parent_element.find_element(by_type, selector)
                return element

            except Exception:
                continue

        return None

    def _upload_resume(self, resume_path):
        """Upload resume file using multiple fallback methods."""
        if not resume_path:
            return False

        try:
            # Ensure absolute path
            if not os.path.isabs(resume_path):
                # If it's a relative path, assume it's relative to the project root
                # strategies/custom/wipro.py -> strategies/custom -> strategies -> root
                current_dir = os.path.dirname(os.path.abspath(__file__))
                project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
                resume_path = os.path.join(project_root, resume_path)

            if not os.path.exists(resume_path):
                logger.error(f" Resume file not found: {resume_path}")
                return False

            logger.info(f" Uploading resume from: {resume_path}")

            # 1. Check for file input directly first
            file_input = self._find_element_by_selectors(
                self.selectors_config.get("resume_upload_input"), timeout=2
            )

            # 2. If not found, click the trigger button
            if not file_input:
                logger.info(
                    "  File input not found immediately - checking for trigger button..."
                )
                trigger = self._find_element_by_selectors(
                    self.selectors_config.get("resume_upload_trigger"),
                    timeout=3,
                    wait_for_visible=True,
                )

                if trigger:
                    logger.info("   Found resume upload trigger - clicking...")
                    # Scroll to trigger to ensure visibility
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", trigger
                    )
                    time.sleep(0.5)
                    try:
                        trigger.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", trigger)

                    time.sleep(2)  # Wait for dialog/input to appear

                    # Try to find input again
                    file_input = self._find_element_by_selectors(
                        self.selectors_config.get("resume_upload_input"), timeout=5
                    )

            if file_input:
                # Unhide if necessary (common in modern UIs)
                self.driver.execute_script(
                    "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';",
                    file_input,
                )

                file_input.send_keys(resume_path)
                logger.info("   Sent file path to input element")
                time.sleep(2)

                # Verify success (optional)
                success_indicator = self._find_element_by_selectors(
                    self.selectors_config.get("upload_success_indicator"), timeout=5
                )
                if success_indicator:
                    logger.info("   Upload success indicator detected")

                return True
            else:
                logger.error(
                    " Could not find file input element even after clicking trigger"
                )
                return False

        except Exception as e:
            logger.error(f"Resume upload error: {e}")
            return False

    def _save_job_to_db(self, job_data):
        """Save job to DuckDB for deduplication"""
        try:
            job_url = job_data["job_url"]
            job_id = job_url.split("/")[-2] if "/job/" in job_url else job_url
            job_title = job_data["job_title"]

            # We don't mark as 'applied' here, just ensure it's in the system if needed.
            # However, WiproStrategy and DuckDBManager use 'applied_jobs' table for deduplication.
            # If we want to 'discover' it without marking as applied, we can just skip or add a status.
            # For now, DuckDBManager.mark_applied is only for SUCCESSFUL applications.
            # We'll just let the CSV tracker handle 'discovered' status,
            # and only use DuckDB for the final 'applied' state.
            pass
        except Exception as e:
            logger.debug(f"DuckDB discovery skip/log failed: {e}")
            if self.db_session:
                self.db_session.rollback()

    def _wait_for_loading_spinner(self, timeout=15):
        """Wait for SAP UI5/Wipro loading indicators to disappear."""
        logger.debug("  [*] Waiting for loading spinner to clear...")
        try:
            # Common SAP UI5 block layers or spinners used by Wipro
            spinner_selectors = [
                ".sapUiBlockLayer",
                "div[id*='sap-ui-blocklayer']",
                ".sapMLoadingIndicator",
                "#sap-ui-static .sapMLoadingIndicator",
                "//div[contains(@class, 'sapUiBlockLayer')]",
            ]

            # Small initial wait to allow transient spinners to appear
            time.sleep(1)

            for selector in spinner_selectors:
                try:
                    by_type = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                    WebDriverWait(self.driver, 3).until(
                        EC.invisibility_of_element_located((by_type, selector))
                    )
                except:
                    continue
            logger.debug("  [OK] Spinner cleared or not found")
        except Exception:
            pass

    def _update_job_status(self, job_id, status):
        """Update job status in database"""
        try:
            if not self.db_session or not self.job_site:
                return

            job = (
                self.db_session.query(JobListing)
                .filter(
                    JobListing.job_site_id == self.job_site.id,
                    JobListing.external_job_id == job_id,
                )
                .first()
            )

            if job:
                job.status = status
                self.db_session.commit()
                logger.debug(f"  Updated job status to: {status}")
        except Exception as e:
            logger.warning(f"   Status update failed: {e}")
            if self.db_session:
                self.db_session.rollback()
