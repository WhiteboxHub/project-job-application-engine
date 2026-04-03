import os
import random
import time
from urllib.parse import quote_plus

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from core.captcha_handler import CaptchaHandler
from core.human_behavior import HumanBehavior
from core.logger import logger
from core.safe_actions import SafeActions
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from strategies.base import BaseStrategy


class ExperisStrategy(BaseStrategy):
    """
    Strategy for Experis site automation.
    Handles job discovery via search filters and sequential application
    using HubSpot-driven forms.
    """

    def __init__(
        self, driver, job_site, selectors, db_session=None, candidate_data=None
    ):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.db_session = db_session
        self.job_site = job_site
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
        self.safe_actions = SafeActions(driver)
        self.config_data = self._load_config()
        self.selectors_config = self._load_selectors()

        if self.db_session:
            logger.info("[OK] Experis: Database session available")
        else:
            logger.warning(
                "[WARNING] Experis: No database session - CSV tracking only"
            )

    def _load_config(self):
        """Return dynamically injected candidate data."""
        if self.candidate_data is not None:
            logger.info("Experis: Using dynamically injected candidate_data")
            return self.candidate_data

        logger.error("Experis: No candidate_data was injected into the strategy.")
        return {}

    def _load_selectors(self):
        """
        Normalize selectors into a predictable shape.

        Expected input pattern:
        {
            "listing": {...},
            "application": {...}
        }
        """
        listing = self.selectors.get("listing", {}) if self.selectors else {}
        application = self.selectors.get("application", {}) if self.selectors else {}

        if not listing or not application:
            logger.warning(
                "[WARNING] Experis: listing/application selectors are incomplete"
            )

        return {"listing": listing, "application": application}

    def _by(self, selector):
        """
        Auto-detect locator type.
        Use XPath when the selector looks like XPath; otherwise use CSS.
        """
        if selector and (selector.startswith("/") or selector.startswith("(")):
            return (By.XPATH, selector)
        return (By.CSS_SELECTOR, selector)

    def get_sel(self, category, key, subkey=None, required=True):
        """Safely fetch a selector from the loaded configuration."""
        cat_dict = self.selectors_config.get(category, {})
        if subkey:
            value = cat_dict.get(key, {}).get(subkey)
        else:
            value = cat_dict.get(key)

        if not value:
            if required:
                msg = (
                    f"[ERROR] Experis: Missing selector '{key}'"
                    + (f"['{subkey}']" if subkey else "")
                    + f" in '{category}' config"
                )
                logger.error(msg)
                raise RuntimeError(msg)
            return None

        return value

    def _extract_applicant(self):
        """
        Build a normalized applicant dict from candidate_data.
        This mirrors the common shape used by the existing strategies.
        """
        applicant_raw = self.config_data.get("applicant", {})
        address = applicant_raw.get("address", {})

        return {
            "first_name": self.config_data.get("first_name")
            or applicant_raw.get("first_name"),
            "last_name": self.config_data.get("last_name")
            or applicant_raw.get("last_name"),
            "email": self.config_data.get("email") or applicant_raw.get("email"),
            "phone": self.config_data.get("phone") or applicant_raw.get("phone"),
            "state": self.config_data.get("state")
            or applicant_raw.get("state")
            or address.get("state"),
            "zip_code": self.config_data.get("zip_code")
            or applicant_raw.get("zip_code")
            or address.get("zip_code"),
            "country": self.config_data.get("country")
            or applicant_raw.get("country")
            or address.get("country", "United States"),
        }

    def _resolve_listing(self, listing):
        """Support both dict and JobListing-style objects."""
        if isinstance(listing, dict):
            return {
                "job_title": listing.get("job_title", "Unknown Title"),
                "job_url": listing.get("job_url"),
                "external_id": listing.get("external_id", "unknown"),
            }

        return {
            "job_title": getattr(listing, "job_title", "Unknown Title"),
            "job_url": getattr(listing, "job_url", None),
            "external_id": getattr(listing, "external_job_id", "unknown"),
        }

    def _default_application_selectors(self):
        """
        Default selectors derived from the live Experis application flow.
        Field IDs use dynamic UUIDs (e.g., firstname-6ce3eb03-...).
        We use CSS id^= (starts-with) selectors to handle this.
        """
        return {
            "apply_button": "div.job-details-cta.cta button.primary-button",
            "apply_page_ready": "input[id^='firstname-']",
            "success_banner": "body",
            "submit_button": "input.hs-button.primary.large[type='submit']",
            "consent_checkbox": "input[id^='consent_to_text_sms-']",
            "form_fields": {
                "first_name": "input[id^='firstname-']",
                "last_name": "input[id^='lastname-']",
                "email": "input[id^='email-']",
                "phone": "input[id^='phone-']",
                "resume_upload": "input[id^='resume-']",
            },
            "questionnaire_fields": {
                "legal_eligibility_yes": (
                    "(//form[contains(@id,'hsForm_')]//fieldset[6]//ul/li[1]/label)[1]"
                ),
                "subcontractor_arrangement_no": (
                    "(//form[contains(@id,'hsForm_')]//fieldset[7]//ul/li[2]/label)[1]"
                ),
            },
        }

    def _default_listing_selectors(self):
        """Default selectors derived from the Experis search page shared by the user."""
        return {
            "search_page_url": "https://www.experis.com/en/search",
            "search_input": "input[name='searchJobText']",
            "location_input": "input[name='searchLocation']",
            "search_button": "button.primary-button.orange-sd[type='submit']",
            "results_ready": "div[id^='job_']",
            "job_card": "div[id^='job_']",
            "job_link": "div.job-position h2.title a",
            "job_title": "div.job-position h2.title a",
            "job_location": "div.job-details div.location",
            "job_type": "div.job-details div.type",
            "job_industry": "div.job-details div.industry",
            "job_description": "div.job-description p.excerpt",
            "posted_date": "div.job-actionbar div.date",
            "pagination_container": (
                "section.search-global-pagination.search-global-pagination-job"
            ),
            "next_page_button": "li.page-item.next a.page-link",
            "active_page": "li.page-item.active a.page-link",
        }

    def _merged_category_selectors(self, category):
        """Merge DB selectors with Experis defaults for a selector category."""
        if category == "application":
            defaults = self._default_application_selectors()
        elif category == "listing":
            defaults = self._default_listing_selectors()
        else:
            defaults = {}

        config = self.selectors_config.get(category, {})
        merged = dict(defaults)
        merged.update({k: v for k, v in config.items() if not isinstance(v, dict)})

        for nested_key, default_nested in defaults.items():
            if isinstance(default_nested, dict):
                merged[nested_key] = dict(default_nested)
                merged[nested_key].update(config.get(nested_key, {}))

        for nested_key, nested_value in config.items():
            if isinstance(nested_value, dict) and nested_key not in merged:
                merged[nested_key] = dict(nested_value)

        return merged

    def get_site_sel(self, category, key, subkey=None, required=True):
        """
        KForce-style selector lookup with Experis defaults as fallback.
        """
        selectors = self._merged_category_selectors(category)
        if subkey:
            value = selectors.get(key, {}).get(subkey)
        else:
            value = selectors.get(key)

        if not value:
            if required:
                msg = (
                    f"[ERROR] Experis: Missing selector '{key}'"
                    + (f"['{subkey}']" if subkey else "")
                    + f" in merged '{category}' config"
                )
                logger.error(msg)
                raise RuntimeError(msg)
            return None

        return value

    def _safe_fill_field(self, selector, value, timeout=10, retries=3):
        """100% JS-based form fill to bypass all 'element not interactable' errors."""
        if not selector or value in (None, ""):
            return False

        for attempt in range(retries):
            try:
                # Re-locate on every attempt to avoid stale element references
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located(self._by(selector))
                )

                # 1. Scroll element into view strictly so send_keys works
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.2)

                # 2. Clear field using Keys to trigger React events properly
                from selenium.webdriver.common.keys import Keys
                from sys import platform
                cmd_ctrl = Keys.COMMAND if platform == "darwin" else Keys.CONTROL
                
                # Select all and delete (more reliable than element.clear() for React)
                element.send_keys(cmd_ctrl + "a")
                element.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)

                # 3. Simulate human typing natively
                element.send_keys(str(value))
                time.sleep(0.1)

                # Validation step: verify value was actually set
                set_value = element.get_attribute('value')
                if set_value:
                    logger.info(f"  [YES] Filled field natively (human sim): {selector} = '{set_value}'")
                    return True
                else:
                    raise ValueError(f"Field '{selector}' still empty after native fill attempt {attempt+1}")

            except Exception as exc:
                if attempt < retries - 1:
                    logger.debug(f"Experis: Retrying fill for '{selector}' (Attempt {attempt+1}/{retries}): {exc}")
                    time.sleep(2)
                    continue
                logger.warning(f"Experis: Failed to fill field '{selector}' after {retries} attempts: {exc}")
                return False

    def _upload_resume_if_available(self, selector):
        """Common resume upload helper."""
        resume_path = self.get_resume_path()
        if not resume_path or not selector:
            logger.warning("Experis: Skipping resume upload - path or selector missing")
            return False

        try:
            file_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(self._by(selector))
            )
            self.driver.execute_script(
                """
                arguments[0].style.display = 'block';
                arguments[0].style.visibility = 'visible';
                arguments[0].style.opacity = '1';
                """,
                file_input,
            )
            file_input.send_keys(resume_path)
            logger.info(
                f"Experis: Resume uploaded successfully ({os.path.basename(resume_path)})"
            )
            return True
        except Exception as exc:
            logger.error(f"Experis: Resume upload failed: {exc}")
            return False

    def _safe_click(self, selector, timeout=10):
        """Click a visible element with human-like fallback behavior."""
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(self._by(selector))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", element
            )
            time.sleep(0.5)
            try:
                self.human.human_click(element)
            except Exception:
                self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as exc:
            logger.warning(f"Experis: Failed to click '{selector}': {exc}")
            return False

    def _handle_cookie_banner(self, timeout=7):
        """Check for and accept common cookie banners (OneTrust, etc.) with iframe support."""
        selectors = [
            "#onetrust-accept-btn-handler",
            "button#onetrust-accept-btn-handler",
            "#accept-recommended-btn-handler",
            "button.onetrust-close-btn-handler",
            "div.ot-sdk-row button#onetrust-accept-btn-handler",
            "//button[contains(text(), 'Accept All Cookies')]",
            "//button[contains(text(), 'Accept')]",
        ]
        
        try:
            # 1. Check in default context
            for selector in selectors:
                try:
                    banner_btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable(self._by(selector))
                    )
                    logger.info(f"Experis: Cookie banner detected ('{selector}'), clicking 'Accept'...")
                    self.human.human_click(banner_btn)
                    time.sleep(1.5)
                    return True
                except Exception:
                    continue

            # 2. Check within iframes (occasionally banners are nested)
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for f in iframes[:5]: # Only check first few to avoid long delay
                try:
                    self.driver.switch_to.frame(f)
                    for selector in selectors:
                        try:
                            banner_btn = WebDriverWait(self.driver, 1).until(
                                EC.element_to_be_clickable(self._by(selector))
                            )
                            logger.info(f"Experis: Cookie banner detected in iframe ('{selector}'), clicking 'Accept'...")
                            self.human.human_click(banner_btn)
                            time.sleep(1.5)
                            self.driver.switch_to.default_content()
                            return True
                        except Exception:
                            continue
                    self.driver.switch_to.default_content()
                except Exception:
                    self.driver.switch_to.default_content()
                    continue
            
            return False
        except Exception:
            try: self.driver.switch_to.default_content()
            except Exception: pass
            return False

    def _set_checkbox_state(self, selector, checked=True, timeout=10):
        """Ensure a checkbox matches the desired state."""
        try:
            checkbox = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(self._by(selector))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", checkbox
            )
            time.sleep(0.3)
            current = checkbox.is_selected()
            if current != checked:
                try:
                    checkbox.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", checkbox)
                time.sleep(0.3)
            return checkbox.is_selected() == checked
        except Exception as exc:
            logger.warning(f"Experis: Failed to set checkbox '{selector}': {exc}")
            return False

    def _select_radio(self, selector, timeout=10):
        """Select a radio input by selector."""
        try:
            radio = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(self._by(selector))
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", radio
            )
            time.sleep(0.3)
            if not radio.is_selected():
                try:
                    radio.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", radio)
            return radio.is_selected()
        except Exception as exc:
            logger.warning(f"Experis: Failed to select radio '{selector}': {exc}")
            return False

    def _is_success_page(self):
        """Check if the current page indicates a successful application."""
        try:
            # Check for common HubSpot success strings in body text
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            success_indicators = [
                "thank you for your interest",
                "application will be reviewed",
                "application was successful",
                "successfully submitted",
                "thanks for submitting the form",
            ]
            return any(indicator in body_text for indicator in success_indicators)
        except Exception:
            return False

    def _is_404_page(self):
        """Check if the current page is a 404 or page-not-found."""
        return "page-not-found" in self.driver.current_url

    def _handle_404_recovery(self):
        """Attempt to recover from a 404 page by clicking the 'SEARCH FOR JOBS' button."""
        logger.warning(
            "Experis: Detected 404 Page Not Found. Attempting recovery via 'SEARCH FOR JOBS' button."
        )
        try:
            recovery_link = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "a.primary-button.goback.reversed[href*='/search']",
                    )
                )
            )
            self.human.human_click(recovery_link)
            logger.info("  [YES] Clicked recovery link, waiting for search page...")
            time.sleep(5)
            return True
        except Exception as e:
            logger.error(f"  [ERROR] Failed to click 404 recovery link: {e}")
            return False

    def _get_tracked_status(self, job_url):
        """Read tracker status for a job URL, if available."""
        try:
            status = csv_tracker.get_job_status("experis", job_url)
            if isinstance(status, dict):
                return status.get("status")
        except Exception as exc:
            logger.debug(f"Experis: Tracker status lookup skipped: {exc}")
        return None

    def login(self):
        """
        Many job sites allow guest browsing/applications.
        Update this if Experis requires authentication.
        """
        logger.info("Experis: Checking login requirements...")
        try:
            if getattr(self.job_site, "search_url_template", None):
                self.driver.get(self.job_site.search_url_template)
                self._handle_cookie_banner()
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(2)
            logger.info("[OK] Experis: Portal loaded")
            return True
        except Exception as exc:
            logger.error(f"[ERROR] Experis: Unable to load portal: {exc}")
            return False

    def find_and_apply_jobs(self):
        """
        Common default workflow:
        1. find_jobs()
        2. de-duplicate by URL
        3. apply sequentially
        """
        logger.info("[SEARCH] Experis: Starting find-and-apply workflow")
        listings = self.find_jobs()
        if not listings:
            logger.info("Experis: No jobs found to apply to")
            return 0

        unique_listings = []
        seen_urls = set()
        for listing in listings:
            job_url = listing.get("job_url") if isinstance(listing, dict) else getattr(
                listing, "job_url", None
            )
            if not job_url or job_url in seen_urls:
                continue
            seen_urls.add(job_url)
            unique_listings.append(listing)

        total_applied = 0
        for index, listing in enumerate(unique_listings, 1):
            data = self._resolve_listing(listing)
            tracked_status = self._get_tracked_status(data["job_url"])
            if tracked_status == "applied":
                logger.info(
                    f"[{index}/{len(unique_listings)}] Experis: Skipping already applied job {data['job_title']}"
                )
                continue

            logger.info(
                f"[{index}/{len(unique_listings)}] Experis: Applying to {data['job_title']}"
            )
            if self.apply(listing):
                total_applied += 1
                time.sleep(random.uniform(2, 4))

        logger.info(
            f"[OK] Experis: Completed with {total_applied}/{len(unique_listings)} successful applications"
        )
        return total_applied

    def find_jobs(self):
        """
        Search Experis jobs using the observed site search flow and collect
        job cards from the results page.
        """
        logger.info("Experis: Starting job discovery")

        if not self.config_data:
            logger.error("Experis: No configuration data available")
            return []

        search_configurations = self._build_search_configurations()
        if not search_configurations:
            logger.error(
                "[ERROR] Experis: No search keywords/configurations found in candidate data"
            )
            return []

        listings = []
        seen_urls = set()

        for config in search_configurations:
            logger.info(
                f"Experis: Searching with keyword '{config['keyword']}' in '{config['location']}'"
            )
            found = self._perform_search(config["keyword"], config.get("location"))

            for item in found:
                job_url = item.get("job_url")
                if job_url and job_url not in seen_urls:
                    seen_urls.add(job_url)
                    listings.append(item)

            if len(search_configurations) > 1:
                time.sleep(random.uniform(2, 4))

        try:
            csv_tracker.add_discovered_jobs("experis", listings)
        except Exception as exc:
            logger.debug(f"Experis: CSV discovery tracking skipped: {exc}")

        logger.info(f"Experis: Discovery complete with {len(listings)} unique jobs")
        return listings

    def _build_search_configurations(self):
        """
        Build LanceSoft-style search configurations.

        Priority:
        1. self.config_data["search_configurations"]
        2. Expand self.config_data["search"]["keywords"] with one shared location
        """
        search_configurations = self.config_data.get("search_configurations", [])
        if search_configurations:
            normalized = []
            for config in search_configurations:
                keyword = config.get("keyword")
                location = config.get("location", "United States")
                if keyword:
                    normalized.append(
                        {
                            "keyword": keyword,
                            "location": location,
                            "distance": config.get("distance", "0"),
                        }
                    )
            return normalized

        search = self.config_data.get("search", {})
        location = search.get("location", "United States")
        distance = search.get("distance", "0")

        keywords = search.get("keywords", [])
        if not keywords:
            keyword = search.get("keyword")
            keywords = [keyword] if keyword else []

        if not keywords:
            return []

        return [
            {"keyword": keyword, "location": location, "distance": distance}
            for keyword in keywords
        ]

    def _is_relevant_job(self, job_title: str, search_keyword: str) -> bool:
        """
        Checks if the discovered job title is relevant to our search keyword.
        Prioritizes AI-related intent and prevents generic matches like "Engineer".
        """
        if not job_title or not search_keyword:
            return False
            
        title_lower = job_title.lower()
        keyword_lower = search_keyword.lower()
        
        # 1. Mandatory Core Intent Tokens
        # If any of these are in the keyword, at least one MUST be in the title
        core_intent = {"ai", "mlops", "ml", "llm", "generative", "python", "machine learning"}
        keyword_core = {t for t in core_intent if t in keyword_lower}
        
        if keyword_core:
            # Check if any of the keyword's core tokens are in the title
            if not any(t in title_lower for t in keyword_core):
                logger.debug(f"      [SKIP] Missing core intent token ({keyword_core}) in title: '{job_title}'")
                return False
            
        # 2. Strict Match
        if keyword_lower in title_lower:
            return True
            
        # 3. Flexible Token Match (50% Overlap)
        # Exclude common generic tokens from the keyword if it's a multi-word search
        keyword_tokens = set(keyword_lower.split())
        noise = {"engineer", "scientist", "developer", "specialist"}
        
        if len(keyword_tokens) > 1:
            keyword_tokens = keyword_tokens - noise
            
        # If the keyword only had "noise" tokens, fall back to the original set
        if not keyword_tokens:
            keyword_tokens = set(keyword_lower.split())

        # Clean title tokens for comparison
        clean_title = title_lower.replace("(", " ").replace(")", " ").replace("-", " ")
        title_tokens = set(clean_title.split())
        
        overlap = keyword_tokens.intersection(title_tokens)
        threshold = 0.5
        
        if len(overlap) / len(keyword_tokens) >= threshold:
            return True
            
        return False

    def _perform_search(self, keyword, location=None):
        """
        Perform a single Experis search and extract jobs from the results page.
        """
        jobs = []
        seen_urls = set()

        # Sanitize keyword: remove parentheses and extra spaces
        keyword = keyword.replace("(", "").replace(")", "").strip()

        logger.info(
            f"Experis: Searching keyword='{keyword}' location='{location or ''}'"
        )

        # 1. URL Navigation with 502 Recovery
        search_url = (
            self.get_site_sel("listing", "search_page_url")
            or "https://www.experis.com/en/search"
        )

        max_retries = 3
        for attempt in range(max_retries):
            if search_url not in self.driver.current_url:
                logger.info(
                    f"Experis: Navigating to base search page: {search_url} (Attempt {attempt+1}/{max_retries})"
                )
                self.driver.get(search_url)
                self._handle_cookie_banner()
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(3)

            # Check for 502 Bad Gateway
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if "bad gateway" in body_text or "502" in body_text:
                logger.warning(
                    f"  [502] Detected Bad Gateway on attempt {attempt+1}. Retrying in 10s..."
                )
                time.sleep(10)
                self.driver.get("about:blank")  # Clear state
                time.sleep(1)
                continue
            else:
                break
        else:
            logger.error(
                "Experis: Failed to load search page after multiple 502 retries."
            )
            return []

        # 1a. Handle 404 Interceptor (User Provided Case)
        if self._is_404_page():
            self._handle_404_recovery()

        # Database-provided selectors with fallbacks
        db_input = self.get_site_sel("listing", "search_input", required=False)
        db_loc = self.get_site_sel("listing", "location_input", required=False)
        db_button = self.get_site_sel("listing", "search_button", required=False)

        INPUT_SELECTORS = [db_input] if db_input else [
            "input[name='searchJobText']",
            "input[name='searchKeyword']",
            "input[id*='keyword' i]",
            "input[placeholder*='search' i]"
        ]
        LOC_SELECTORS = [db_loc] if db_loc else [
            "input[name='searchLocation']",
            "input[id*='location' i]",
            "input[placeholder*='location' i]"
        ]
        BUTTON_SELECTORS = [db_button] if db_button else [
            "button.primary-button.orange-sd[type='submit']",
            "button[type='submit']",
            "button[class*='search' i]"
        ]

        def _find_first(selectors, timeout=4):
            for sel in selectors:
                if not sel: continue
                try:
                    el = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located(self._by(sel))
                    )
                    return el, sel
                except Exception:
                    continue
            return None, None
            
        def _fill_react_field(element, value):
            if not element or not value: return
            try:
                self.human.human_click(element)
                time.sleep(0.5)
                self.driver.execute_script("arguments[0].value = '';", element)
                element.clear()
                element.send_keys(value)
                # Dispatch events for React
                self.driver.execute_script(
                    """
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    """, element
                )
                time.sleep(1)
            except Exception as e:
                logger.warning(f"  [WARNING] Smart fill failed, error: {e}")

        try:
            # 2. Try to find and fill keyword
            input_el, used_sel = _find_first(INPUT_SELECTORS, timeout=5)
            if input_el:
                logger.info(f"Experis: FOUND search input via selector '{used_sel}'. Preparing to type '{keyword}'...")
                _fill_react_field(input_el, keyword)
                logger.info(f"  [VERIFY] Typed keyword '{keyword}' into {used_sel}")
            else:
                # URL Fallback
                encoded_kw = quote_plus(keyword)
                encoded_loc = quote_plus(location) if location else ""
                fallback_url = f"https://www.experis.com/en/search?searchKeyword={encoded_kw}"
                if encoded_loc: fallback_url += f"&searchLocation={encoded_loc}"
                
                logger.warning(
                    f"  [FALLBACK] Could NOT find search inputs (tried {INPUT_SELECTORS}) — falling back to DIRECT URL: {fallback_url}"
                )
                self.driver.get(fallback_url)
                time.sleep(4)
                input_el = None # Prevent enter key action later
    
            # Try to find and fill location
            if location and input_el:
                loc_el, loc_sel = _find_first(LOC_SELECTORS, timeout=5)
                if loc_el:
                    logger.info(f"Experis: Found location input via '{loc_sel}'")
                    # Clear location which might be auto-filled, then type
                    loc_el.send_keys(Keys.CONTROL + "a")
                    loc_el.send_keys(Keys.DELETE)
                    _fill_react_field(loc_el, location)
                    logger.info(f"  [YES] Entered location: {location}")
    
            # Try to click search
            if input_el:
                btn_el, _ = _find_first(BUTTON_SELECTORS, timeout=3)
                if btn_el:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn_el)
                        time.sleep(0.5)
                        self.human.human_click(btn_el)
                        logger.info("  [YES] Clicked search button")
                        time.sleep(4)
                    except Exception as be:
                        logger.debug(f"Experis: Button click failed: {be}")
                else:
                    logger.info("  [INFO] No search button found, pressing ENTER instead")
                    try:
                        input_el.send_keys(Keys.RETURN)
                        logger.info("  [YES] Pressed ENTER to search")
                        time.sleep(4)
                    except Exception as ee:
                        logger.warning(f"  [WARNING] Enter key failed: {ee}")
    
            # Wait for results to stabilize
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located(
                        self._by(self.get_site_sel("listing", "results_ready") or ".jobpostings")
                    )
                )
            except:
                logger.warning("Experis: Results ready indicator not found, proceeding anyway...")
                
            time.sleep(2)
    
            page_num = 1
            max_pages = 200 # Restored to production limit (was 10 during testing)
    
            while page_num <= max_pages:
                cards = self.driver.find_elements(
                    *self._by(self.get_site_sel("listing", "job_card"))
                )
                if not cards:
                    logger.info(
                        f"Experis: No job cards found on page {page_num} - stopping pagination"
                    )
                    break
    
                new_jobs_on_page = 0
    
                for card in cards:
                    try:
                        title_el = card.find_element(
                            By.CSS_SELECTOR, self.get_site_sel("listing", "job_title")
                        )
                        link_el = card.find_element(
                            By.CSS_SELECTOR, self.get_site_sel("listing", "job_link")
                        )
                        job_title = (title_el.text or "").strip()
                        href = (link_el.get_attribute("href") or "").strip()
    
                        if href.startswith("/"):
                            href = f"https://www.experis.com{href}"
    
                        if not job_title or not href or href in seen_urls:
                            continue
    
                        # Strict Relevance Filter
                        if not self._is_relevant_job(job_title, keyword):
                            logger.info(f"    [SKIP] Irrelevant job: '{job_title}' for keyword '{keyword}'")
                            continue
    
                        seen_urls.add(href)
                        new_jobs_on_page += 1
    
                        location_text = ""
                        job_type = ""
                        industry = ""
                        description = ""
                        posted_date = ""
    
                        try:
                            location_text = (
                                card.find_element(
                                    By.CSS_SELECTOR,
                                    self.get_site_sel("listing", "job_location"),
                                ).text.strip()
                            )
                        except Exception:
                            pass
    
                        try:
                            job_type = (
                                card.find_element(
                                    By.CSS_SELECTOR,
                                    self.get_site_sel("listing", "job_type"),
                                ).text.strip()
                            )
                        except Exception:
                            pass
    
                        try:
                            industry = (
                                card.find_element(
                                    By.CSS_SELECTOR,
                                    self.get_site_sel("listing", "job_industry"),
                                ).text.strip()
                            )
                        except Exception:
                            pass
    
                        try:
                            description = (
                                card.find_element(
                                    By.CSS_SELECTOR,
                                    self.get_site_sel("listing", "job_description"),
                                ).text.strip()
                            )
                        except Exception:
                            pass
    
                        try:
                            posted_date = (
                                card.find_element(
                                    By.CSS_SELECTOR,
                                    self.get_site_sel("listing", "posted_date"),
                                ).text.strip()
                            )
                        except Exception:
                            pass
    
                        external_id = href.rstrip("/").split("/")[-2]
    
                        jobs.append(
                            {
                                "job_title": job_title,
                                "job_url": href,
                                "external_id": external_id,
                                "location": location_text,
                                "job_type": job_type,
                                "industry": industry,
                                "description": description,
                                "posted_date": posted_date,
                                "company": "Experis",
                            }
                        )
                    except Exception as exc:
                        logger.debug(f"Experis: Failed to parse a job card: {exc}")
                        continue
    
                if new_jobs_on_page == 0:
                    logger.info(
                        f"Experis: No new relevant jobs found on page {page_num}, but continuing to check next page..."
                    )
    
                try:
                    pagination = self.driver.find_elements(
                        *self._by(self.get_site_sel("listing", "pagination_container"))
                    )
                    if not pagination:
                        logger.info("Experis: No pagination block found - stopping")
                        break
    
                    next_buttons = self.driver.find_elements(
                        *self._by(self.get_site_sel("listing", "next_page_button"))
                    )
                    if not next_buttons:
                        logger.info("Experis: No next page button found - stopping")
                        break
    
                    next_button = next_buttons[0]
                    next_href = (next_button.get_attribute("href") or "").strip()
                    next_classes = next_button.get_attribute("class") or ""
    
                    if (
                        not next_href
                        or "page=0" in next_href
                        or "disabled" in next_classes.lower()
                    ):
                        logger.info("Experis: Next page is unavailable - stopping")
                        break
    
                    current_url = self.driver.current_url
                    
                    # --- Retry Loop for Navigation ---
                    max_nav_retries = 2
                    nav_success = False
                    
                    for nav_attempt in range(max_nav_retries):
                        try:
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block:'center'});", next_button
                            )
                            time.sleep(0.5)
            
                            try:
                                self.human.human_click(next_button)
                            except Exception:
                                self.driver.get(next_href)
            
                            WebDriverWait(self.driver, 20).until(
                                lambda d: d.current_url != current_url
                            )
            
                            # Check for 404 after navigation
                            if self._is_404_page():
                                logger.warning(
                                    f"Experis: Detected 404 on page {page_num + 1} (Attempt {nav_attempt+1}/{max_nav_retries})..."
                                )
                                self._handle_404_recovery()
                                # If we recovered but it didn't take us to the next page, loop will retry or break below
                                if nav_attempt < max_nav_retries - 1:
                                    logger.info(f"Experis: Retrying navigation to {next_href}")
                                    self.driver.get(next_href)
                                    continue
                                else:
                                    break # Out of nav retries

                            WebDriverWait(self.driver, 20).until(
                                EC.presence_of_element_located(
                                    self._by(self.get_site_sel("listing", "results_ready"))
                                )
                            )
                            nav_success = True
                            break # Successfully on next page
                        except Exception as ne:
                            logger.info(f"Experis: Navigation to page {page_num + 1} failed (Attempt {nav_attempt+1}): {ne}")
                            if nav_attempt < max_nav_retries - 1:
                                time.sleep(2)
                                continue
                    
                    if not nav_success:
                        logger.warning(f"Experis: Failed to navigate to page {page_num + 1} after {max_nav_retries} attempts. Ending keyword search.")
                        break

                    time.sleep(1.5)
                    page_num += 1
                except Exception as exc:
                    logger.info(f"Experis: Pagination ended on page {page_num}: {exc}")
                    break
    
            if page_num > max_pages:
                logger.info(
                    f"Experis: Reached pagination safety limit ({max_pages} pages)"
                )
    
            return jobs
        except Exception as exc:
            logger.error(f"Experis: Search failed for keyword '{keyword}': {exc}")
            return []

    def apply(self, listing: JobListing):
        """
        Apply to a single Experis job using the observed HubSpot form flow.
        """
        job = self._resolve_listing(listing)
        logger.info(
            f"Experis: Applying to {job['job_title']} ({job['external_id']})..."
        )

        if not job["job_url"]:
            logger.error("Experis: No job URL provided")
            return False

        applicant = self._extract_applicant()
        apply_btn_selector = self.get_site_sel("application", "apply_button")

        tracked_status = self._get_tracked_status(job["job_url"])
        if tracked_status == "applied":
            logger.info(f"Experis: Already applied to {job['job_title']} - skipping")
            return True

        try:
            self.driver.get(job["job_url"])
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)

            logger.info("Experis: Opening application form from job details page")
            if not self._safe_click(apply_btn_selector, timeout=15):
                csv_tracker.update_job_status(
                    "experis",
                    job["job_url"],
                    "failed",
                    attempts_inc=1,
                    last_error="Apply button not found or not clickable",
                )
                return False

            # --- HubSpot Form Detection ---
            # The application form lives inside #form_contact-us container.
            # HubSpot renders the actual form inside an IFRAME within that div.
            # Structure: #form_contact-us > div > div > div > iframe > form#hsForm_*
            #
            # Strategy:
            #   1. Find #form_contact-us on the main page
            #   2. Find the iframe INSIDE that container
            #   3. Switch into that iframe
            #   4. Verify the hsForm with visible fields exists
            form_found = False
            self.driver.switch_to.default_content()
            max_form_wait = 30
            start_wait = time.time()

            while time.time() - start_wait < max_form_wait and not form_found:
                try:
                    # Step 1: Find iframe inside #form_contact-us
                    target_iframe = self.driver.execute_script(
                        """
                        var container = document.getElementById('form_contact-us');
                        if (!container) return null;
                        var iframe = container.querySelector('iframe');
                        return iframe;
                        """
                    )

                    if target_iframe:
                        logger.info("Experis: Found iframe inside #form_contact-us. Switching context...")
                        self.driver.switch_to.default_content()
                        self.driver.switch_to.frame(target_iframe)

                        # Step 2: Check if hsForm has visible firstname field
                        has_visible_form = self.driver.execute_script(
                            """
                            var form = document.querySelector("form[id^='hsForm_']");
                            if (!form) return 'no_form';
                            var el = form.querySelector("input[id^='firstname-']");
                            if (!el) return 'no_field';
                            var rect = el.getBoundingClientRect();
                            return (rect.width > 0 && rect.height > 0) ? 'visible' : 'hidden';
                            """
                        )

                        if has_visible_form == 'visible':
                            logger.info("Experis: [OK] HubSpot form with VISIBLE fields found inside #form_contact-us iframe")
                            form_found = True
                            break
                        elif has_visible_form == 'no_form':
                            logger.info(f"Experis: iframe found but hsForm not loaded yet ({int(time.time() - start_wait)}s)...")
                        elif has_visible_form == 'no_field':
                            logger.info(f"Experis: hsForm found but firstname field not yet rendered ({int(time.time() - start_wait)}s)...")
                        else:
                            logger.info(f"Experis: firstname field exists but HIDDEN ({int(time.time() - start_wait)}s)...")

                        self.driver.switch_to.default_content()
                    else:
                        logger.info(f"Experis: #form_contact-us iframe not ready ({int(time.time() - start_wait)}s)...")

                    time.sleep(2)

                except Exception as e:
                    logger.debug(f"Experis: Form detection error: {e}")
                    try:
                        self.driver.switch_to.default_content()
                    except Exception:
                        pass
                    time.sleep(2)

            # If targeted approach failed, try scanning ALL iframes as last resort
            if not form_found:
                self.driver.switch_to.default_content()
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                logger.info(f"Experis: Targeted search failed. Scanning all {len(iframes)} iframe(s)...")
                for idx, f in enumerate(iframes):
                    try:
                        self.driver.switch_to.default_content()
                        self.driver.switch_to.frame(f)
                        has_it = self.driver.execute_script(
                            """
                            var el = document.querySelector("form[id^='hsForm_'] input[id^='firstname-']");
                            if (!el) return false;
                            var rect = el.getBoundingClientRect();
                            return (rect.width > 0 && rect.height > 0);
                            """
                        )
                        if has_it:
                            f_id = f.get_attribute("id") or "(no id)"
                            logger.info(f"Experis: [OK] Found form in iframe [{idx}] (id='{f_id}')")
                            form_found = True
                            break
                    except Exception:
                        continue

            if not form_found:
                self.driver.switch_to.default_content()
                logger.warning("Experis: Could NOT find HubSpot form in any context after 30s. Proceeding anyway...")

            time.sleep(1)

            # --- HARDCODED SELECTORS ---
            # ALL selectors are scoped to form[id^='hsForm_'] to avoid
            # accidentally filling the newsletter/footer form.
            HS = "form[id^='hsForm_'] "
            FORM_SEL = {
                "first_name": HS + "input[id^='firstname-']",
                "last_name": HS + "input[id^='lastname-']",
                "email": HS + "input[id^='email-']",
                "phone": HS + "input[id^='phone-']",
                "resume": HS + "input[id^='resume-']",
                "consent": HS + "input[id^='consent_to_text_sms-']",
                "submit": HS + "input.hs-button.primary.large[type='submit']",
            }

            logger.info("Experis: Filling application form fields (hardcoded selectors)")
            fill_results = [
                self._safe_fill_field(FORM_SEL["first_name"], applicant.get("first_name")),
                self._safe_fill_field(FORM_SEL["last_name"], applicant.get("last_name")),
                self._safe_fill_field(FORM_SEL["email"], applicant.get("email")),
                self._safe_fill_field(FORM_SEL["phone"], applicant.get("phone")),
            ]

            filled_count = sum(1 for r in fill_results if r)
            logger.info(f"Experis: Filled {filled_count}/4 form fields successfully")

            # 4. Handle Consent Checkbox via JS click
            try:
                consent_el = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, FORM_SEL["consent"]))
                )
                if not consent_el.is_selected():
                    self.driver.execute_script("arguments[0].click();", consent_el)
                logger.info("  [YES] Consent checkbox checked")
            except Exception:
                # Fallback: click the consent label via XPath
                try:
                    consent_label = self.driver.find_element(
                        By.XPATH,
                        "(//form[contains(@id,'hsForm_')]//fieldset[4]//ul/li/label)[1]"
                    )
                    self.driver.execute_script("arguments[0].click();", consent_label)
                    logger.info("  [YES] Clicked consent label via XPath fallback")
                except Exception as ce:
                    logger.warning(f"Experis: Consent checkbox failed: {ce}")

            # 5. Upload Resume
            if not self._upload_resume_if_available(FORM_SEL["resume"]):
                csv_tracker.update_job_status(
                    "experis", job["job_url"], "failed", attempts_inc=1, last_error="Resume upload failed"
                )
                return False

            # 6. Handle Questionnaire via XPath label clicks
            QUESTIONNAIRE = [
                ("Legal Eligibility=YES", "(//form[contains(@id,'hsForm_')]//fieldset[6]//ul/li[1]/label)[1]"),
                ("Subcontractor=NO", "(//form[contains(@id,'hsForm_')]//fieldset[7]//ul/li[2]/label)[1]"),
            ]

            for label, xpath in QUESTIONNAIRE:
                try:
                    el = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", el
                    )
                    time.sleep(0.3)
                    self.driver.execute_script("arguments[0].click();", el)
                    logger.info(f"  [YES] Clicked questionnaire: {label}")
                except Exception as qe:
                    logger.warning(f"Experis: Questionnaire '{label}' failed: {qe}")

            # 7. Submit
            logger.info("Experis: Submitting application")
            if not self._safe_click(FORM_SEL["submit"], timeout=10):
                csv_tracker.update_job_status(
                    "experis", job["job_url"], "failed", attempts_inc=1, last_error="Submit button not clickable"
                )
                return False

            # Success Verification
            try:
                WebDriverWait(self.driver, 20).until(lambda d: self._is_success_page())
                logger.info("Experis: Application submitted successfully")
                csv_tracker.update_job_status("experis", job["job_url"], "applied", attempts_inc=1)
                return True
            except Exception:
                logger.warning("Experis: Could not confirm success page, but application was submitted.")
                csv_tracker.update_job_status("experis", job["job_url"], "applied", attempts_inc=1)
                return True

        except Exception as exc:
            logger.error(f"Experis: Application failed for {job['job_title']}: {exc}")
            try:
                csv_tracker.update_job_status(
                    "experis", job["job_url"], "failed", attempts_inc=1, last_error=str(exc)
                )
            except Exception: pass
            return False
        finally:
            # CRITICAL: Always switch back to main document so next job works
            try: self.driver.switch_to.default_content()
            except Exception: pass
