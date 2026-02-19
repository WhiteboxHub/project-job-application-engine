from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler
from core.config_manager import ConfigManager
import time
import os
import json
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC

from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from config.settings import settings


class InfosysStrategy(BaseStrategy):
    """
    Infosys strategy (recreated, template-aligned).
    Fixes included:
    - Single (non-duplicated) _click_any() with iframe awareness.
    - Field-based section detection (Education/Experience/Skills) so it doesn't "skip" Education.
    - Stable waits before scanning/next.
    - _smart_fill cleaned (no unreachable code).
    - Database-driven configuration via ConfigManager.
    """

    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.db_session = db_session
        self.job_site = job_site
        self.config_data = self._load_config()
        self.resume_data = self._load_resume_json()

        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)
        
        # Initialize ConfigManager for database-driven configuration
        if self.db_session and job_site:
            self.config = ConfigManager(db_session, job_site.id)
            logger.info("✅ ConfigManager initialized - using database-driven configuration")
        else:
            self.config = None
            logger.warning("⚠️ ConfigManager not available - falling back to hardcoded values")

        if self.db_session:
            logger.info("✅ Database session available - tracking enabled.")

        # State for multi-pass sequential search
        self._current_keyword_index = 0
        self._all_keywords = []

    # -------------------------
    # Config loaders
    # -------------------------
    def _load_config(self):
        """Load configuration from candidate_data (database) or fallback to JSON file"""
        # Priority 1: Use candidate_data from database
        if self.candidate_data:
            logger.info("✅ Using candidate data from database")
            return self.candidate_data
        
        # Priority 2: Fallback to JSON file for backward compatibility
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data",
                "guest_form_data.json",
            )
            if os.path.exists(config_path):
                logger.info("⚠️ Using fallback config from guest_form_data.json")
                with open(config_path, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def _load_resume_json(self):
        try:
            resume_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "resume"
            )
            # Try both names
            for name in ["parsed_resume.json", "resume.json"]:
                path = os.path.join(resume_dir, name)
                if os.path.exists(path):
                    with open(path, "r") as f:
                        data = json.load(f)
                        logger.info(f"Loaded resume data from {name}")
                        return self._normalize_resume_data(data)
            return {}
        except Exception as e:
            logger.error(f"Failed to load resume JSON: {e}")
            return {}

    def _normalize_resume_data(self, data):
        """Standardizes structure between different parser outputs"""
        # Map 'work_experience' or 'workExperience' to 'work'
        if "work_experience" in data and "work" not in data:
            data["work"] = data["work_experience"]
        
        # Map 'professional_info.skills' to 'skills' if needed
        if "professional_info" in data and "skills" not in data:
            data["skills"] = data.get("professional_info", {}).get("skills", [])

        if "work" in data and isinstance(data["work"], list):
            for item in data["work"]:
                if "company" in item and "name" not in item:
                    item["name"] = item["company"]
                if "title" in item and "position" not in item:
                    item["position"] = item["title"]
                if "start_date" in item and "startDate" not in item:
                    item["startDate"] = item["start_date"]
                if "end_date" in item and "endDate" not in item:
                    item["endDate"] = item["end_date"]
                if "description" in item and "summary" not in item:
                    item["summary"] = item["description"]

        if "education" in data and isinstance(data["education"], list):
            for item in data["education"]:
                if "field_of_study" in item and "area" not in item:
                    item["area"] = item["field_of_study"]
                if "degree" in item and "studyType" not in item:
                    item["studyType"] = item["degree"]
                if "graduation_year" in item and "endDate" not in item:
                    item["endDate"] = item["graduation_year"]

        return data

    # -------------------------
    # Database Config Helpers
    # -------------------------
    def _get_selectors(self, key, fallback=None):
        """Get selectors from database with fallback"""
        if self.config:
            selectors = self.config.get_selectors(key)
            if selectors:
                return selectors
        return fallback or []

    def _get_keywords(self, field_name, fallback=None):
        """Get field keywords from database with fallback"""
        if self.config:
            keywords = self.config.get_field_keywords(field_name)
            if keywords:
                return keywords
        return fallback or []

    def _get_value(self, field_name, context=None, fallback=None):
        """Get field value from database with fallback"""
        if self.config:
            value = self.config.get_field_value(field_name, context)
            if value:
                return value
        return fallback or ""

    def _get_section_keywords(self, section_name, fallback=None):
        """Get section keywords from database with fallback"""
        if self.config:
            keywords = self.config.get_section_keywords(section_name)
            if keywords:
                return keywords
        return fallback or []

    # -------------------------
    # Base hooks
    # -------------------------
    def login(self):
        logger.info("Infosys: Guest flow selected (no login).")
        return True

    def find_and_apply_jobs(self):
        """
        MAIN ENTRY POINT: Single-phase workflow for Infosys.
        
        Searches for all jobs matching keywords, then applies to each one.
        This ensures all 24 jobs are processed instead of stopping after first keyword.
        
        Returns:
            int: Number of successful applications
        """
        from engine.guards import guards
        
        logger.info("🔍 Starting Infosys single-phase workflow...")
        
        if not self.config_data:
            logger.error("No configuration data available")
            return 0
        
        # Get all keywords
        search = self.config_data.get("search", {})
        keywords = search.get("keywords", [])
        if not keywords:
            keywords = [search.get("keyword", "AI")]
        
        loc = search.get("location", "USA")
        dist = search.get("distance", "50")
        
        logger.info(f"📋 Keywords: {keywords}")
        logger.info(f"📍 Location: {loc}")
        
        # Collect ALL jobs from ALL keywords
        all_jobs = []
        seen_urls = set()
        
        for kw in keywords:
            logger.info(f"\n🔍 Searching for: '{kw}'...")
            try:
                urls = self._search_jobs(kw, loc, dist)
                logger.info(f"✅ Found {len(urls)} jobs for '{kw}'")
                
                for u in urls:
                    if u not in seen_urls:
                        job_id = u.split("/")[-1] if u else None
                        
                        # Store discovered job
                        if job_id:
                            self._record_discovered_job(job_id)
                        
                        # Skip if already applied
                        if job_id and self._is_already_applied(job_id):
                            logger.debug(f"Skipping {job_id} (already applied)")
                            continue
                        
                        seen_urls.add(u)
                        all_jobs.append({
                            "job_url": u,
                            "job_title": f"Infosys Job ({kw})",
                            "job_id": job_id
                        })
            except Exception as e:
                logger.error(f"❌ Search for '{kw}' failed: {e}")
                continue
        
        logger.info(f"\n📊 Total unique jobs found: {len(all_jobs)}")
        
        # Apply to each job
        applied_count = 0
        for idx, job in enumerate(all_jobs, 1):
            if not guards.can_apply():
                logger.warning(f"⛔ Application limit reached after {applied_count} applications")
                break
            
            logger.info(f"\n{'='*60}")
            logger.info(f"📝 Job {idx}/{len(all_jobs)}: {job['job_id']}")
            logger.info(f"{'='*60}")
            
            try:
                success = self._apply_to_job(job["job_url"])
                
                if success:
                    guards.increment_counter()
                    applied_count += 1
                    if job["job_id"]:
                        self._record_applied_job(job["job_id"])
                    logger.info(f"✅ Application #{applied_count} successful")
                else:
                    logger.warning("⚠️ Application failed")
                    
            except Exception as e:
                logger.error(f"❌ Error applying to job: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Infosys workflow complete: {applied_count}/{len(all_jobs)} applications submitted")
        logger.info(f"{'='*60}\n")
        
        return applied_count

    def find_jobs(self):
        # Initialize keywords on first pass
        if not self._all_keywords:
            search = self.config_data.get("search", {})
            self._all_keywords = search.get("keywords", [])
            if not self._all_keywords:
                self._all_keywords = [search.get("keyword", "AI")]
            
            logger.info(f"≡ƒôï Multi-Pass Setup: {len(self._all_keywords)} keywords found: {self._all_keywords}")

        # Check if we have more keywords to process
        if self._current_keyword_index >= len(self._all_keywords):
            logger.info("≡ƒÅü All keywords processed.")
            return []

        kw = self._all_keywords[self._current_keyword_index]
        self._current_keyword_index += 1
        
        search = self.config_data.get("search", {})
        loc = search.get("location", "USA")
        dist = search.get("distance", "50")
        
        logger.info(f"≡ƒöì Search Pass for: '{kw}' (Keyword {self._current_keyword_index}/{len(self._all_keywords)})")
        
        all_job_listings = []
        seen_urls = set()

        try:
            urls = self._search_jobs(kw, loc, dist)
            for u in urls:
                if u not in seen_urls:
                    job_id = u.split("/")[-1] if u else None
                    
                    # Store every discovered job ID as requested
                    if job_id:
                        self._record_discovered_job(job_id)
                    
                    # Pre-filter applied jobs
                    if job_id and self._is_already_applied(job_id):
                        logger.debug(f"Pre-skipping {job_id} (already in applied_jobs.json)")
                        continue
                        
                    seen_urls.add(u)
                    all_job_listings.append({"job_url": u, "job_title": f"Infosys Job ({kw})"})
        except Exception as e:
            logger.error(f"Γ¥î Search for keyword '{kw}' failed: {e}")
            # We return [] for this pass to let Runner know nothing was found for THIS kw, 
            # but next call to find_jobs will move to the next kw.
        
        return all_job_listings

    def apply(self, listing):
        url = listing.get("job_url") if isinstance(listing, dict) else getattr(listing, "job_url", None)
        job_id = url.split("/")[-1] if url else None
        
        if job_id and self._is_already_applied(job_id):
            logger.info(f"ΓÅ⌐ Skipping {job_id} - already applied (found in JSON tracker).")
            return True # Treat as success to proceed in loop
            
        success = self._apply_to_job(url)
        
        if success and job_id:
            self._record_applied_job(job_id)
            
        return success

    # -------------------------
    # Job Search
    # -------------------------
    def _search_jobs(self, keyword, location, distance):
        # Normalize location → Infosys URL only accepts "USA"
        _loc_map = {
            "united states": "USA",
            "united states of america": "USA",
            "us": "USA",
            "u.s.": "USA",
            "u.s.a.": "USA",
            "america": "USA",
        }
        loc_param = _loc_map.get((location or "").strip().lower(), location or "USA")
        
        # Build URL with keyword directly in query string
        # Format: https://digitalcareers.infosys.com/infosys/global-careers?location=USA&keyword=AI
        import urllib.parse
        keyword_encoded = urllib.parse.quote_plus(keyword)
        
        if self.config:
            base_url = self.config.get_url('search_base', location=loc_param)
            if not base_url:
                base_url = f"https://digitalcareers.infosys.com/infosys/global-careers?location={loc_param}"
        else:
            base_url = f"https://digitalcareers.infosys.com/infosys/global-careers?location={loc_param}"

        # Strip any existing keyword param and add fresh one
        if "keyword=" in base_url:
            base_url = base_url.split("&keyword=")[0].split("?keyword=")[0]
        
        search_url = f"{base_url}&keyword={keyword_encoded}"
        
        logger.info(f"Searching Infosys: {keyword} in {loc_param}")
        logger.info(f"Opening URL: {search_url}")
        self.driver.get(search_url)
        time.sleep(6)
        logger.info(f"Current URL after navigation: {self.driver.current_url}")
        self._close_common_popups()
        time.sleep(3)

        try:

            job_urls = []
            seen = set()
            max_pages = 10 # Increased for better discovery

            for page in range(1, max_pages + 1):
                logger.info(f"Processing Page {page}")
                links = self.driver.find_elements(By.CSS_SELECTOR, "a.job[href*='/description/reqid/']")

                if not links:
                    logger.warning(f"No job links found on page {page}")

                for link in links:
                    try:
                        href = link.get_attribute("href")
                        title = link.text.strip()
                        if href and href not in seen:
                            if self._is_target_job(title):
                                seen.add(href)
                                job_urls.append(href)
                                job_id = href.split("/")[-1]

                                csv_tracker.add_discovered_jobs(
                                    "infosys",
                                    [{"external_id": job_id, "job_title": title, "job_url": href}],
                                )
                                if self.db_session:
                                    self._save_job_to_db(job_id, title, href)
                    except Exception:
                        continue

                # next page
                try:
                    next_selectors = self._get_selectors("next_button", ["a.next", "li.next a", "a[title='Next']", "button.next"])
                    next_btn = self._find_element_safe(next_selectors)
                    if next_btn and "disabled" not in (next_btn.get_attribute("class") or ""):
                        logger.info("Moving to next page...")
                        self.human.human_click(next_btn)
                        time.sleep(5) # More time for page load
                    else:
                        logger.info("No more pages found.")
                        break
                except Exception as e:
                    logger.warning(f"Failed to navigate to next page: {e}")
                    break

            return job_urls

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _is_target_job(self, title):
        if not title:
            return False
        t = title.lower()
        
        # Get filters from database
        targets = []
        blocks = []
        location_filters = []
        
        if self.config:
            targets = self.config.get_search_filters('target_keyword')
            blocks = self.config.get_search_filters('blocked_keyword')
            location_filters = self.config.get_search_filters('location_filter')
            
        # Fallbacks if DB empty
        if not targets:
            targets = ["ai", "machine learning", "ml", "data science", "engineer", "developer", "technology", "software"]
        if not blocks:
            blocks = ["nurse", "sales", "hr", "marketing", "finance", "legal", "doctor"]
        if not location_filters:
            location_filters = ["canada", "brazil", "india", "mexico", "united kingdom", "uk", "australia"]
            
        if any(b.lower() in t for b in blocks if b):
            return False
            
        if any(loc.lower() in t for loc in location_filters if loc):
            logger.debug(f"Skipping non-USA job: {title}")
            return False

        return any(tr.lower() in t for tr in targets if tr)

    def _save_job_to_db(self, job_id, title, href, description=None):
        try:
            if not self.db_session: return
            existing = self.db_session.query(JobListing).filter(JobListing.job_url == href).first()
            if not existing:
                listing = JobListing(
                    job_site_id=self.job_site.id,
                    external_job_id=job_id,
                    job_title=title,
                    job_url=href,
                    job_description=description,
                    status="discovered",
                )
                self.db_session.add(listing)
                self.db_session.commit()
                logger.info(f"Saved to DuckDB: {title}")
        except Exception as e:
            logger.error(f"DB save failed: {e}")
            try:
                self.db_session.rollback()
            except Exception:
                pass

    # -------------------------
    # Apply flow
    # -------------------------
    def _apply_to_job(self, job_url):
        from engine.guards import guards

        if not job_url:
            logger.error("No job_url provided to apply.")
            return False

        if not guards.can_apply():
            return False

        logger.info(f"--- Applying to: {job_url} ---")
        self.driver.get(job_url)
        time.sleep(3)
        self._close_common_popups()

        # Capture job description for DuckDB before starting apply flow
        job_description = ""
        try:
            desc_elem = self._find_element_safe([".job-description", "#jobDescription", ".description", "article"])
            if desc_elem:
                job_description = desc_elem.text.strip()
                logger.info("Captured job description.")
        except Exception:
            pass

        if self.db_session:
            try:
                listing = self.db_session.query(JobListing).filter(JobListing.job_url == job_url).first()
                if listing:
                    listing.job_description = job_description
                    self.db_session.commit()
                    logger.info("Updated description in DuckDB.")
            except Exception:
                self.db_session.rollback()

        # 1) Apply - Get selectors from database (with proper fallback)
        db_selectors = self.config.get_selectors('apply_button') if self.config else []
        
        # Use database selectors if available, otherwise use hardcoded fallback
        if db_selectors:
            apply_selectors = db_selectors
            logger.info("Using Apply button selectors from database")
        else:
            apply_selectors = [
                # Exact XPath from browser inspection (user-confirmed)
                "//*[@id='sortableHeader']/li/div/div/div/div[2]/a",
                # CSS equivalents
                "#sortableHeader li div div div div:nth-child(2) a",
                "#sortableHeader > li > div > div > div > div.apply-button-container > a",
                ".apply-button-container a",
                "a.infosys-apply-link",
                "//a[contains(@class, 'apply')]",
                "//a[contains(text(), 'Apply')]",
                "//button[contains(text(), 'Apply Now')]",
            ]
            logger.info("Using hardcoded Apply button selectors (database empty)")
        
        logger.info(f"🔍 Testing {len(apply_selectors)} Apply button selectors...")
        logger.info(f"Selectors: {apply_selectors}")
        
        # Wait longer for page to fully load
        time.sleep(5)
        
        # Try to scroll to find the button
        try:
            self.driver.execute_script("window.scrollTo(0, 0);")  # Scroll to top
            time.sleep(1)
        except:
            pass
        
        if not self._click_any(apply_selectors):
            logger.error("Could not find Apply button")
            logger.error(f"Page URL: {self.driver.current_url}")
            logger.error(f"Page Title: {self.driver.title}")
            return False

        time.sleep(10) # Wait for new window to fully open and stabilize
        
        # Robust window switching
        try:
            handles = self.driver.window_handles
            logger.info(f"Window handles after apply: {len(handles)}")
            if len(handles) > 1:
                # Switch and verify window is still open
                self.driver.switch_to.window(handles[-1])
                try:
                    _ = self.driver.title
                except Exception:
                    logger.warning("Latest window handle seems invalid, trying middle handle...")
                    if len(handles) > 2:
                        self.driver.switch_to.window(handles[-2])
        except Exception as e:
            logger.warning(f"Window switch logic failed: {e}")

        self._ensure_active_window()
        time.sleep(5)

        # 2) First-time user + privacy
        if not self._handle_first_time_user():
            logger.warning("Could not click 'First Time User' - checking if we are already on form...")
        
        time.sleep(2)
        
        self._handle_privacy_modal()
        time.sleep(2)

        # CRITICAL VERIFICATION: Ensure we are actually on the application form
        # We look for personal info fields or specific form headers
        if not self._wait_for_form_stable(timeout=10):
            logger.error("STUCK: Remained on 'First Time' or 'Privacy' page. Form fields not detected.")
            
            # Try once more to click 'Proceed' or 'Next' just in case
            self._click_any(["button.proceed", "//button[contains(text(), 'Proceed')]", "a.consent-button"])
            time.sleep(3)
            
            if not self._wait_for_form_stable(timeout=5):
                logger.error("FATAL: Could not reach Personal Information section. Aborting this job.")
                return False

        # 3) Personal info
        self._fill_personal_info()
        self.human.random_delay(2, 4)

        # 4) Resume upload
        if not self._upload_resume_with_retry():
            logger.error("Resume upload failed!")
            # If we are stuck, we might want to pause or just fail
            # The user reported "Success" in terminal but stuck UI, so we must return False here
            return False
            
        time.sleep(2)

        # 5) Dynamic sections
        self._handle_dynamic_application_sections()

        # 6) Submit
        return self._submit_final(job_url)

    # -------------------------
    # Click + Frame helpers (IMPORTANT: SINGLE VERSION ONLY)
    # -------------------------
    def js_click(self, element):
        try:
            self.driver.execute_script(
                """
                arguments[0].style.border = '3px solid green';
                var clickEvent = new MouseEvent('click', {
                    view: window,
                    bubbles: true,
                    cancelable: true
                });
                arguments[0].dispatchEvent(clickEvent);
                """,
                element,
            )
            return True
        except Exception as e:
            logger.warning(f"JS Click failed: {e}")
            return False

    def _click_any(self, selectors):
        """
        Click first visible element from a list of selectors.
        - Checks root
        - Checks iframes
        """
        for s in selectors:
            try:
                by = By.XPATH if s.startswith("//") else By.CSS_SELECTOR

                # Root
                elements = self.driver.find_elements(by, s)
                for elem in elements:
                    if elem.is_displayed():
                        logger.info(f"Clicking: {s}")
                        self.human.human_click(elem)
                        return True

                # Iframes
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for frame in iframes:
                    try:
                        self.driver.switch_to.frame(frame)
                        inner_elements = self.driver.find_elements(by, s)
                        for inner_elem in inner_elements:
                            if inner_elem.is_displayed():
                                logger.info(f"Clicking in iframe: {s}")
                                self.human.human_click(inner_elem)
                                self.driver.switch_to.default_content()
                                return True
                        self.driver.switch_to.default_content()
                    except Exception:
                        self.driver.switch_to.default_content()
                        continue
            except Exception:
                continue
        return False

    def _ensure_active_window(self):
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                logger.info(f"Switching to latest window (Total: {len(handles)})")
                self.driver.switch_to.window(handles[-1])
            return True
        except Exception:
            return False

    def _wait_for_form_stable(self, timeout=10):
        """
        Wait until the application form (Personal Info section) is visible.
        Returns True if form fields are detected within the timeout, False otherwise.
        """
        logger.info(f"Waiting up to {timeout}s for application form to appear...")
        form_indicators = [
            "input[name*='firstName']",
            "input[name*='first']",
            "input[name*='email']",
            "input[placeholder*='First']",
            "input[placeholder*='Email']",
            "input[placeholder*='Name']",
            "form input:not([type='hidden'])",
            "#form_application input",
        ]
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # Also check inside iframes
                self.driver.switch_to.default_content()
                for sel in form_indicators:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        logger.info(f"✔ Form detected via: {sel}")
                        return True
                # Check inside iframes
                iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
                for frame in iframes:
                    try:
                        self.driver.switch_to.frame(frame)
                        for sel in form_indicators:
                            elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                            if any(e.is_displayed() for e in elems):
                                logger.info(f"✔ Form detected in iframe via: {sel}")
                                self.driver.switch_to.default_content()
                                return True
                        self.driver.switch_to.default_content()
                    except Exception:
                        self.driver.switch_to.default_content()
            except Exception:
                pass
            time.sleep(1)
        logger.warning("Form not detected within timeout.")
        return False

    def _is_already_applied(self, job_id):
        """Check if job_id exists in data/applied_jobs.json"""
        try:
            tracker_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data",
                "applied_jobs.json"
            )
            if not os.path.exists(tracker_path):
                return False
            with open(tracker_path, "r") as f:
                data = json.load(f)
                return job_id in data.get("applied_ids", [])
        except Exception as e:
            logger.warning(f"Failed to check application tracker: {e}")
            return False

    def _record_applied_job(self, job_id):
        """Save job_id to data/applied_jobs.json"""
        try:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data"
            )
            tracker_path = os.path.join(data_dir, "applied_jobs.json")
            
            applied_data = {"applied_ids": []}
            if os.path.exists(tracker_path):
                with open(tracker_path, "r") as f:
                    applied_data = json.load(f)
            
            if job_id not in applied_data["applied_ids"]:
                applied_data["applied_ids"].append(job_id)
                with open(tracker_path, "w") as f:
                    json.dump(applied_data, f, indent=4)
                logger.info(f"≡ƒÆ╛ Job {job_id} recorded in applied_jobs.json")
        except Exception as e:
            logger.error(f"Failed to record applied job: {e}")

    def _record_discovered_job(self, job_id):
        """Save job_id to data/discovered_jobs.json"""
        try:
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data"
            )
            tracker_path = os.path.join(data_dir, "discovered_jobs.json")
            
            discovered_data = {"discovered_ids": []}
            if os.path.exists(tracker_path):
                with open(tracker_path, "r") as f:
                    discovered_data = json.load(f)
            
            if job_id not in discovered_data["discovered_ids"]:
                discovered_data["discovered_ids"].append(job_id)
                with open(tracker_path, "w") as f:
                    json.dump(discovered_data, f, indent=4)
                logger.debug(f"Recorded discovered job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to record discovered job: {e}")

    def _switch_to_form_frame(self):
        """
        Switch to recruitment iframe if present (best-effort).
        Returns True if switched.
        """
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            for frame in iframes:
                fid = frame.get_attribute("id") or ""
                src = frame.get_attribute("src") or ""
                hay = (fid + " " + src).lower()
                if any(x in hay for x in ["career", "recruit", "icims", "apply", "smartdreamers", "brassring"]):
                    logger.info(f"Switching to recruitment iframe: {fid or src[:60]}")
                    self.driver.switch_to.frame(frame)
                    return True
        except Exception:
            pass
        return False

    def _find_element_safe(self, selectors):
        for s in selectors:
            try:
                by = By.XPATH if s.startswith("//") else By.CSS_SELECTOR
                elems = self.driver.find_elements(by, s)
                for elem in elems:
                    if elem.is_displayed():
                        return elem
            except Exception:
                continue
        return None

    # -------------------------
    # First-time + privacy
    # -------------------------
    def _handle_first_time_user(self):
        logger.info("Selecting 'I am applying for the first time'...")
        # Get selectors from database
        db_selectors = self.config.get_selectors('first_time_user_button') if self.config else []
        if db_selectors:
            selectors = db_selectors
        else:
            selectors = [
                # Exact XPath from user inspection: second apply-type-container's Apply button
                "//*[@id='form_application']/div[2]/div[2]//a[contains(@class,'apply-selector-button') or contains(@class,'apply-btn') or contains(text(),'Apply')]",
                "//*[@id='form_application']/div[2]/div[2]//button",
                # Target the Apply button inside the 'first time' container
                ".apply-type-container:nth-of-type(2) .apply-selector-button-container a",
                ".apply-type-container:nth-of-type(2) .apply-selector-button-container button",
                ".apply-type-container:last-of-type .apply-selector-button-container a",
                # Broader fallbacks
                ".apply-selector-button-container a",
                ".apply-selector-button-container button",
                "//div[contains(@class,'apply-type-container')][2]//a",
                "//div[contains(@class,'apply-type-container')][2]//button",
                "//p[contains(text(),'applying for the first time')]/following-sibling::div//a",
                "//p[contains(text(),'applying for the first time')]/following-sibling::div//button",
                # Legacy fallbacks
                ".apply-first-time-button",
                "a.apply-first-time-button",
                "input[value='FirstTime']",
                "#rdoFirstTime",
            ]
        if self._click_any(selectors):
            logger.info("✔ Selected 'Applying for first time'")
            time.sleep(2)
            return True
        return False

    def _handle_privacy_modal(self):
        logger.info("Handling Privacy/Consent Modal...")
        # Get selectors from database
        db_consent = self.config.get_selectors('consent_button') if self.config else []
        if db_consent:
            consent_selectors = db_consent
        else:
            consent_selectors = [
                # Exact selector from user inspection: <a class="consent-button" href="#">Proceed</a>
                "a.consent-button",
                ".consent-button",
                "//a[@class='consent-button' and text()='Proceed']",
                "//a[contains(@class, 'consent-button')]",
                "//a[contains(text(), 'Proceed')]",
                "button.agree",
                "button.proceed",
                "//button[contains(text(), 'Proceed')]",
            ]
        if self._click_any(consent_selectors):
            logger.info("✔ Clicked Proceed/Consent button")
            time.sleep(3)
        else:
            logger.warning("Could not find Proceed button.")

    # -------------------------
    # Personal Info + Smart Fill
    # -------------------------
    def _fill_personal_info(self):
        logger.info("Filling Personal Information...")
        applicant = self.config_data.get("applicant", {})
        
        # Use centralized resume_data and normalized keys
        res = self.resume_data
        pers = res.get("personal_info", {})
        addr = res.get("address", {})

        first_name = applicant.get("first_name") or pers.get("first_name", "")
        last_name = applicant.get("last_name") or pers.get("last_name", "")
        email = applicant.get("email") or pers.get("email", "")
        phone = applicant.get("phone") or pers.get("phone", "")
        
        street_address = applicant.get("street_address") or addr.get("street_address", "")
        city = applicant.get("city") or addr.get("city", "")
        zip_code = applicant.get("zip_code") or addr.get("zip_code", "")

        # Sanitize phone number (remove non-digits)
        if phone:
            import re
            phone = re.sub(r'\D', '', phone)
            # Optional: Ensure it's not too long or short if needed, but digits-only is usually safe
            logger.info(f"Sanitized phone number: {phone}")

        self.driver.switch_to.default_content()
        self._switch_to_form_frame()

        logger.info("Selecting Country & State...")
        self._select_dropdown(["select[name*='country']", "select#country"], ["United States", "USA", "US"])
        time.sleep(1)
        self._select_dropdown(["select#state", "select[name*='state']"], ["California", "CA"])
        time.sleep(1)

        self._select_dropdown(["select#state", "select[name*='state']"], ["California", "CA"])
        time.sleep(1)

        self._smart_fill(self._get_keywords("first_name", ["first name", "firstname", "given name"]), first_name)
        self._smart_fill(self._get_keywords("last_name", ["last name", "lastname", "surname", "family name"]), last_name)
        self._smart_fill(self._get_keywords("email", ["email", "email address"]), email)
        self._smart_fill(self._get_keywords("phone", ["phone", "mobile", "contact number", "cell"]), phone)
        
        self._enterprise_fill(self._get_keywords("city", ["city", "addrCity", "town"]), city)
        self._enterprise_fill(self._get_keywords("address", ["address_1", "address", "address 1", "address line 1", "street", "street address", "addr1", "address1"]), street_address)
        self._enterprise_fill(self._get_keywords("zip", ["zip", "zip code", "zipcode", "postal", "postal code", "postalcode"]), zip_code)

        # -------------------------
        # Legal / Authorization (Often required for 'Next')
        # -------------------------
        logger.info("Filling Legal/Authorization questions...")
        auth_keywords = self._get_keywords("authorized_us", ["authorized to work", "legally authorized", "right to work"])
        sponsorship_keywords = self._get_keywords("sponsorship", ["sponsorship", "require sponsorship", "visa sponsorship", "h1-b"])
        
        # Default to 'Yes' for authorization, 'No' for sponsorship based on applicant profiles usually handled
        # Use existing robust _enterprise_fill for these
        self._enterprise_fill(auth_keywords, "Yes")
        self._enterprise_fill(sponsorship_keywords, "No")

        logger.info("Proceeding to next section (Personal Info -> Resume)...")
        # Robust Next Click with JS Fallback
        next_selectors = [
                "a#forward-navigation",
                "a.form-next-button",
                "//button[contains(text(), 'Next')]",
                "//a[contains(text(), 'Next')]",
        ]
        
        # Click and wait for stale
        try:
            btn = self._find_element_safe(next_selectors)
            if btn:
                logger.info("Found Next button. Attempting robust click sequence...")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(1)
                
                # 1. Standard Click
                try:
                    self.human.human_click(btn)
                except:
                    pass
                time.sleep(1)
                
                # 2. JS Click (Force)
                self.js_click(btn)
                logger.info("Executed JS Click on Next button.")
                
                # Wait for page transition
                time.sleep(5)
            else:
                logger.warning("Next button not found in Personal Info section!")
        except Exception as e:
            logger.error(f"Error clicking Next: {e}")

        self.driver.switch_to.default_content()

    def _select_dropdown(self, selectors, values):
        for sel in selectors:
            try:
                by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                dropdown = self.driver.find_element(by, sel)
                select = Select(dropdown)

                for val in values:
                    if not val:
                        continue

                    try:
                        select.select_by_visible_text(val)
                        logger.info(f"Dropdown: Selected '{val}'")
                        return True
                    except Exception:
                        pass

                    try:
                        for option in select.options:
                            if val.lower() in option.text.lower() or option.text.lower() in val.lower():
                                select.select_by_visible_text(option.text)
                                logger.info(f"Dropdown: Selected '{option.text}' (partial for '{val}')")
                                return True
                    except Exception:
                        pass

                    try:
                        select.select_by_value(val)
                        logger.info(f"Dropdown: Selected value '{val}'")
                        return True
                    except Exception:
                        pass
            except Exception:
                continue
        return False

    def _enterprise_fill(self, keywords, value):
        if not value:
            return False

        candidates = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), select, textarea")
        best_candidate = None
        best_score = 0

        norm_keywords = [k.lower() for k in keywords]

        # REVERSE candidates to prioritize fields at the bottom (newly added dynamic sections)
        # This fixes the issue of "End Year" matching the previous (top) experience entry.
        candidates = candidates[::-1]

        for elem in candidates:
            try:
                if not elem.is_displayed():
                    continue

                score = 0
                attr_text = " ".join(
                    [
                        elem.get_attribute("name") or "",
                        elem.get_attribute("id") or "",
                        elem.get_attribute("placeholder") or "",
                        elem.get_attribute("aria-label") or "",
                        elem.get_attribute("class") or "",
                    ]
                ).lower()

                for kw in norm_keywords:
                    if kw in attr_text:
                        score += 2

                try:
                    parent_text = elem.find_element(By.XPATH, "./..").text.lower()
                    for kw in norm_keywords:
                        if kw in parent_text:
                            score += 1
                except Exception:
                    pass

                if score > best_score:
                    best_score = score
                    best_candidate = elem
                elif score == best_score and best_candidate:
                    # Prefer empty fields if scores are tied (fixes duplicate filling in lists)
                    try:
                        if best_candidate.get_attribute('value') and not elem.get_attribute('value'):
                            best_candidate = elem
                    except:
                        pass
            except Exception:
                continue

        if best_candidate and best_score > 0:
            tag = best_candidate.tag_name.lower()
            logger.info(f"Enterprise Fill: Matched '{tag}' (score {best_score}) for keywords {keywords}")

            if tag == "select":
                select = Select(best_candidate)
                try:
                    select.select_by_visible_text(value)
                    logger.info(f"Select: Selected '{value}' (Exact)")
                    return True
                except Exception:
                    # Try partial/fuzzy match
                    for opt in select.options:
                        o_text = opt.text.lower()
                        v_text = value.lower()
                        if v_text in o_text or o_text in v_text:
                            select.select_by_visible_text(opt.text)
                            logger.info(f"Select: Selected '{opt.text}' (Partial match for '{value}')")
                            return True
                    
                    # Try fallback list for Degree/Education - ONLY if keywords suggest it
                    is_education = any(k in " ".join(keywords).lower() for k in ["degree", "qualification", "education", "school"])
                    if is_education:
                        fallbacks = ["Bachelor's", "Bachelor", "Bachelors", "Master's", "Master", "University", "B.Tech", "B.E."]
                        for fb in fallbacks:
                            for opt in select.options:
                                if fb.lower() in opt.text.lower():
                                    select.select_by_visible_text(opt.text)
                                    logger.info(f"Select: Selected '{opt.text}' via fallback '{fb}'")
                                    return True

                    try:
                        select.select_by_value(value)
                        logger.info(f"Select: Selected value '{value}'")
                        return True
                    except Exception:
                        opts = [o.text for o in select.options][:10]
                        logger.warning(f"Select: Failed to select '{value}'. Available: {opts}")
                        return False
            
            # RADIO BUTTON SUPPORT
            elif best_candidate.get_attribute("type") == "radio":
                name_attr = best_candidate.get_attribute("name")
                if name_attr:
                    radios = self.driver.find_elements(By.NAME, name_attr)
                    for r in radios:
                        r_val = r.get_attribute("value") or ""
                        r_text = ""
                        try:
                            # Check labeling text or parent text
                            r_text = r.find_element(By.XPATH, "./..").text or ""
                        except: pass

                        if value.lower() == r_val.lower() or value.lower() in r_text.lower():
                            self.js_click(r)
                            logger.info(f"Radio: Selected choice matching '{value}' for name='{name_attr}'")
                            return True
                
                # Fallback if name-based loop fails
                self.js_click(best_candidate)
                logger.info(f"Radio: Clicked best candidate (Fallback)")
                return True
            
            # CHECKBOX SUPPORT
            elif best_candidate.get_attribute("type") == "checkbox":
                if not best_candidate.is_selected():
                    self.js_click(best_candidate)
                logger.info(f"Checkbox: Selected best candidate")
                return True

            else:
                self.human.fill_text_field(best_candidate, value)
                return True

        return False

    def _smart_fill(self, label_texts, value):
        return self._enterprise_fill(label_texts, value)

    # -------------------------
    # Dynamic sections (FIXED)
    # -------------------------
    def _page_has_any_field(self, keywords):
        kws = [k.lower() for k in keywords]
        elems = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), select, textarea")

        for el in elems:
            try:
                if not el.is_displayed():
                    continue

                hay = " ".join(
                    [
                        el.get_attribute("name") or "",
                        el.get_attribute("id") or "",
                        el.get_attribute("placeholder") or "",
                        el.get_attribute("aria-label") or "",
                        el.get_attribute("class") or "",
                    ]
                ).lower()

                if any(k in hay for k in kws):
                    return True

                try:
                    parent_text = el.find_element(By.XPATH, "./..").text.lower()
                    if any(k in parent_text for k in kws):
                        return True
                except Exception:
                    pass
            except Exception:
                continue

        return False

    def _wait_for_form_stable(self, timeout=12):
        """
        Waits for specific keys that indicate the Personal Information form is loaded.
        Prevents false positives from the 'Login / First Time' page.
        """
        end = time.time() + timeout
        critical_keywords = ["first", "last", "email", "phone", "address", "city"]
        
        while time.time() < end:
            try:
                # Check for inputs with specific attributes matching personal info
                fields = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden'])")
                
                matches = 0
                for f in fields:
                    # Check name/id/placeholder/aria-label
                    attr_text = " ".join([
                        f.get_attribute("name") or "",
                        f.get_attribute("id") or "",
                        f.get_attribute("placeholder") or "",
                        f.get_attribute("aria-label") or ""
                    ]).lower()
                    
                    if any(k in attr_text for k in critical_keywords):
                        matches += 1
                
                # We expect at least 2-3 specific matches (e.g. First Name, Last Name, Email)
                if matches >= 2:
                    logger.info(f"Form validation succeeded: Found {matches} relevant fields.")
                    return True
                    
            except Exception:
                pass
            time.sleep(0.5)
            
        logger.warning(f"Form validation failed. Could not find personal info fields.")
        return False

    def _click_next_best_effort(self):
        next_selectors = [
            "#forward-navigation",
            "a.form-next-button",
            "button.save-continue",
            "button.next",
            "//button[contains(., 'Next')]",
            "//a[contains(., 'Next')]",
            "//button[contains(., 'Continue')]",
            "//a[contains(., 'Continue')]",
            "//button[contains(., 'Save')]",
            "//a[contains(., 'Save')]",
        ]

        if self._click_any(next_selectors):
            return True

        # JS fallback (root only)
        for sel in next_selectors:
            try:
                by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                btns = self.driver.find_elements(by, sel)
                for b in btns:
                    if b.is_displayed():
                        self.driver.execute_script("arguments[0].click();", b)
                        return True
            except Exception:
                continue

        return False

    def _handle_dynamic_application_sections(self):
        logger.info("Processing dynamic application sections...")

        filled_sections = set()

        for step_idx in range(25):
            self.driver.switch_to.default_content()
            self._switch_to_form_frame()

            self._wait_for_form_stable(timeout=12)

            page_before = self.driver.page_source
            did_something = False

            # EDUCATION
            edu_keywords = self._get_section_keywords("education", ["education", "school", "institution", "university", "college", "degree", "qualification", "major"])
            if "education" not in filled_sections and self._page_has_any_field(edu_keywords):
                logger.info("Detected Education section by fields ΓåÆ filling...")
                self._fill_education_parsed()
                filled_sections.add("education")
                did_something = True

            # EXPERIENCE
            exp_keywords = self._get_section_keywords("experience", ["work", "experience", "employer", "company", "designation", "job_title", "position", "responsibilities"])
            if "experience" not in filled_sections and self._page_has_any_field(exp_keywords):
                logger.info("Detected Experience section by fields ΓåÆ filling...")
                self._fill_experience_parsed()
                filled_sections.add("experience")
                did_something = True

            # SKILLS
            skills_keywords = self._get_section_keywords("skills", ["skills", "technologies", "tool", "stack"])
            if "skills" not in filled_sections and self._page_has_any_field(skills_keywords):
                logger.info("Detected Skills section by fields ΓåÆ filling...")
                self._fill_skills_parsed()
                filled_sections.add("skills")
                did_something = True

            # EEO / DIVERSITY / OTHER INFO
            # We allow this to run multiple times (by not checking filled_sections) 
            # because EEO and Agreement/Other Info often appear on separate pages 
            # but share similar field types/keywords.
            eeo_keywords = self._get_section_keywords("eeo", ["ethnicity", "race", "gender", "veteran", "disability", "eeo", "employed", "contract", "arbitration", "other", "additional", "signature", "mutual", "source", "authorized", "relocate", "travel", "sponsorship", "voluntary", "identification", "self-identification", "agreement", "terms", "acknowledge"])
            if self._page_has_any_field(eeo_keywords):
                logger.info("Detected EEO / Other Info section by fields ΓåÆ filling...")
                applicant = self.config_data.get("applicant", {})
                full_name = f"{applicant.get('first_name', '')} {applicant.get('last_name', '')}"
                
                eeo_data = [
                    (self._get_keywords("ethnicity", ["ethnicity"]), self._get_value("ethnicity", "eeo", "No")),
                    (self._get_keywords("race", ["race"]), self._get_value("race", "eeo", "Asian")), 
                    (self._get_keywords("gender", ["gender"]), self._get_value("gender", "eeo", "Female")),
                    (self._get_keywords("veteran", ["veteran"]), self._get_value("veteran", "eeo", "No")),
                    (self._get_keywords("disability", ["disability", "custom[eeo][disability]"]), self._get_value("disability", "eeo", "No, I do not have a disability and have not had one in the past")),
                    (self._get_keywords("employed", ["employed", "custom[other][employed]", "employed by infosys"]), self._get_value("employed", "other", "No")),
                    (self._get_keywords("contractual", ["contractual", "custom[other][contract_restriction]", "contractual restrictions"]), self._get_value("contractual", "other", "No")),
                    (self._get_keywords("arbitration", ["mutual arbitration", "custom[other][arbitration]", "arbitration"]), self._get_value("arbitration", "other", "1")),
                    (self._get_keywords("source", ["source", "how did you hear", "hear about us", "infosys career website", "reference"]), self._get_value("source", "other", "Infosys Careers Site")),
                    (self._get_keywords("authorized", ["authorized", "work in the united states"]), self._get_value("authorized", "other", "Yes")),
                    (self._get_keywords("relocate", ["relocate", "custom[other][relocate]"]), self._get_value("relocate", "other", "Yes")),
                    (self._get_keywords("travel", ["travel", "custom[other][travel]"]), self._get_value("travel", "other", "Yes")),
                    (self._get_keywords("sponsorship", ["sponsorship", "custom[other][sponsorship]"]), self._get_value("sponsorship", "other", "No")),
                    (self._get_keywords("minimum_qualification", ["minimum qualification", "custom[other][degree]", "degree"]), self._get_value("minimum_qualification", "other", "Yes")),
                    (["signature", "legal name"], full_name)
                ]
                for keywords, val in eeo_data:
                    if self._enterprise_fill(keywords, val):
                        did_something = True
                    
                filled_sections.add("eeo")

            if did_something:
                time.sleep(2)

            logger.info("Attempting to move forward (Next/Save/Continue)...")
            if not self._click_next_best_effort():
                logger.info("No Next/Save/Continue found ΓåÆ stopping dynamic section loop.")
                break

            time.sleep(4)

            page_after = self.driver.page_source
            if page_after == page_before:
                logger.warning("Page did not change after Next ΓåÆ retrying once...")
                if not self._click_next_best_effort():
                    logger.warning("Retry failed ΓåÆ stopping.")
                    break
                time.sleep(5)

    # -------------------------
    # Education / Experience / Skills fill
    # -------------------------
    def _fill_education_parsed(self):
        logger.info("Parsing and filling Education via Enterprise Logic...")
        edu_list = self.resume_data.get("education", [])
        if not edu_list:
            logger.info("No education in resume.json")
            return

        edu = edu_list[0]
        self._enterprise_fill(
            ["school", "institution", "university", "college", "education][0][school", "education][0][institution"],
            edu.get("institution", ""),
        )
        self._enterprise_fill(
            ["major", "area", "study", "program", "education][0][major", "education][0][program"],
            edu.get("area", ""),
        )
        self._enterprise_fill(
            ["degree", "qualification", "education][0][degree", "level"],
            edu.get("studyType", ""),
        )

        if edu.get("endDate"):
            match = re.search(r"(\d{4})", edu.get("endDate"))
            if match:
                self._enterprise_fill(
                    ["graduation", "year", "end_date", "education][0][year", "education][0][end_date"],
                    match.group(1),
                )

    def _fill_experience_parsed(self):
        logger.info("Parsing and filling Experience via Enterprise Logic...")
        work_list = self.resume_data.get("work", [])
        if not work_list:
            logger.info("No work experience in resume.json")
            return

        max_exp = 3
        for i, job in enumerate(work_list[:max_exp]):
            company_name = job.get("name", "")
            logger.info(f"Filling experience #{i+1}: {company_name}")

            # If there's an "Add other work experience" button for additional entries
            if i > 0:
                self._click_any(["//span[contains(text(), '+ Add other work experience')]", "//button[contains(., 'Add')]"])
                time.sleep(2)

            suffix = f"][{i}]"

            self._enterprise_fill(
                [f"work]{suffix}[company", f"work]{suffix}[name", "company", "employer"],
                company_name,
            )
            self._enterprise_fill(
                [f"work]{suffix}[job_title", f"work]{suffix}[position", "job_title", "position", "title"],
                job.get("position", ""),
            )

            if job.get("startDate"):
                match = re.search(r"(\d{4})", job.get("startDate"))
                if match:
                    self._enterprise_fill(
                        [f"work]{suffix}[start_year", f"work]{suffix}[from", "start_year", "from_year"],
                        match.group(1),
                    )

            if job.get("endDate"):
                match = re.search(r"(\d{4})", job.get("endDate"))
                if match:
                    self._enterprise_fill(
                        [f"work]{suffix}[end_year", f"work]{suffix}[to", "end_year", "to_year"],
                        match.group(1),
                    )

            # Summary can be list or string in some resume.json formats
            summary_val = job.get("summary", "")
            if isinstance(summary_val, list):
                summary_val = "\n".join([str(x) for x in summary_val if x])

            self._enterprise_fill(
                [f"work]{suffix}[description", f"work]{suffix}[summary", "description", "responsibilities"],
                summary_val,
            )

    def _fill_skills_parsed(self):
        skills = self.resume_data.get("skills", [])
        if not skills:
            logger.info("No skills in resume.json")
            return

        all_skills = ""
        if skills and isinstance(skills[0], dict):
            all_skills = ", ".join([s.get("name", "") for s in skills if s.get("name")])
        else:
            all_skills = ", ".join([str(s) for s in skills])

        try:
            elems = self.driver.find_elements(By.CSS_SELECTOR, "textarea[name*='skills'], #skills-input, input[name*='skills']")
            for elem in elems:
                if elem.is_displayed():
                    self.human.fill_text_field(elem, all_skills)
                    logger.info("Filled skills.")
                    return
        except Exception:
            pass

    # -------------------------
    # Resume upload (multi-method + popup handling)
    # -------------------------
    def _upload_resume_method_id_file_resume(self, file_path):
        """Method 0: Target specific ID 'file_resume' identified by user"""
        logger.info("Method 0: Targeting ID 'file_resume'...")
        try:
            # 1. Unhide the specific element
            js_unhide = """
            var elem = document.getElementById('file_resume');
            if(elem) {
                elem.style.display = 'block';
                elem.style.visibility = 'visible';
                elem.style.opacity = '1';
                elem.style.width = 'auto';
                elem.style.height = 'auto';
                return true;
            }
            return false;
            """
            found = self.driver.execute_script(js_unhide)
            if not found:
                logger.info("Element #file_resume not found in root, scanning iframes...")
                frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                for idx, frame in enumerate(frames):
                    try:
                        self.driver.switch_to.default_content()
                        # Refresh frames list
                        current_frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                        if idx >= len(current_frames): break
                        self.driver.switch_to.frame(current_frames[idx])
                        
                        found = self.driver.execute_script(js_unhide)
                        if found:
                            logger.info(f"Found #file_resume in iframe {idx}")
                            break
                    except Exception:
                        continue
                
                if not found:
                    self.driver.switch_to.default_content()
                    logger.warning("Element #file_resume not found anywhere.")
                    return False
            
            # 2. Send keys to the element (we are already in the correct context)
            elem = self.driver.find_element(By.ID, "file_resume")
            if elem.get_attribute("type") != "file":
                logger.warning("#file_resume is not a file input. Type: " + str(elem.get_attribute("type")))
                # Optional: Try to inject type='file' if it's somehow different
                self.driver.execute_script("arguments[0].setAttribute('type', 'file');", elem)

            elem.send_keys(file_path)
            
            # 3. Trigger events
            self.driver.execute_script("""
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            """, elem)

            logger.info("SUCCESS: Uploaded to #file_resume and triggered events!")
            return True
        except Exception as e:
            logger.warning(f"Failed to upload to #file_resume: {e}")
            return False

    def _upload_resume_method_brute_force_iframes(self, file_path):
        """Method 7: Aggressively search ALL iframes for any file input"""
        logger.info("Method 7: Brute Force Iframe Scan...")
        
        frames = self.driver.find_elements(By.TAG_NAME, "iframe")
        logger.info(f"Found {len(frames)} iframes to scan.")
        
        for idx, frame in enumerate(frames):
            try:
                self.driver.switch_to.default_content()
                current_frames = self.driver.find_elements(By.TAG_NAME, "iframe")
                if idx >= len(current_frames): break
                
                self.driver.switch_to.frame(current_frames[idx])
                
                inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if inputs:
                    for file_input in inputs:
                        try:
                            # Make visible
                            self.driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", file_input)
                            file_input.send_keys(file_path)
                            logger.info(f"SUCCESS: Uploaded to iframe {idx} input!")
                            self.driver.switch_to.default_content()
                            return True
                        except Exception as e:
                            logger.warning(f"Failed to upload to iframe {idx} input: {e}")
            except Exception as e:
                logger.warning(f"Could not switch/scan iframe {idx}: {e}")
                self.driver.switch_to.default_content()
                continue
        
        self.driver.switch_to.default_content()
        return False

    def _upload_resume_with_retry(self):
        """Tries multiple methods to upload resume"""
        resume_input = self.config_data.get('resume_path', 'resume/')
        
        # Resolve absolute path and find PDF if directory
        abs_resume_path = os.path.abspath(resume_input)
        if os.path.isdir(abs_resume_path):
            pdfs = [f for f in os.listdir(abs_resume_path) if f.lower().endswith('.pdf')]
            if pdfs:
                resume_path = os.path.join(abs_resume_path, pdfs[0])
            else:
                logger.error(f"No PDF found in resume directory: {abs_resume_path}")
                return False
        else:
            resume_path = abs_resume_path

        if not os.path.exists(resume_path):
            logger.warning(f"Resume file not found: {resume_path}")
            return False

        logger.info(f"Uploading Resume: {resume_path}")

        # Correct method names from class definitions
        methods = [
            self._upload_resume_method_id_file_resume,
            self._method_direct_input,
            self._method_visible_input,
            self._method_click_dropzone,
            self._method_js_manipulation,
            self._method_nested_input,
            self._upload_resume_method_brute_force_iframes
        ]
        
        for method in methods:
            try:
                logger.info(f"Trying {method.__name__}...")
                if method(resume_path):
                    # Infosys Double Popup Logic (User Request)
                    logger.info("Closing 1st popup (Immediate post-upload)...")
                    time.sleep(2) # Brief pause for UI
                    self._close_common_popups()
                    
                    logger.info("Waiting for processing 'on their end' (2nd popup trigger)...")
                    time.sleep(40) # Wait for backend processing/virus scan (User requested 40s)
                    
                    logger.info("Closing 2nd popup (Post-save/processing)...")
                    # Poll for the popup for 10 seconds to ensure we catch it
                    for _ in range(10):
                        self._close_common_popups()
                        time.sleep(1)
                    
                    # Verify for all methods
                    is_verified = self._verify_upload_success()
                    
                    # NEW: Click "Import fields" if present (User Request)
                    logger.info("Checking for 'Import fields' button...")
                    import_selectors = [
                        "button.save-button", 
                        "//button[contains(text(), 'Import fields')]",
                        "//button[contains(., 'Import fields')]"
                    ]
                    if self._click_any(import_selectors):
                        logger.info("Γ£ô Clicked 'Import fields' button.")
                        time.sleep(5) # Wait for import to process
                    else:
                        logger.info("Did not find 'Import fields' button (might be auto-imported or not present).")

                    # TRUST METHOD 0: If specific ID upload worked and we waited 40s, proceed.
                    if method == self._upload_resume_method_id_file_resume:
                        logger.info("Method 0 (Targeted ID) finished. Proceeding to next section.")
                        # Click Next to proceed to dynamic sections
                        logger.info("Clicking Next/Proceed after resume section...")
                        # More aggressive click and wait
                        self._click_any(["a#forward-navigation", "button#next", "//button[contains(text(), 'Next')]", "//a[contains(text(), 'Next')]", "//span[contains(text(), 'Proceed')]"])
                        time.sleep(5)
                        return True

                    if is_verified:
                        logger.info(f"Resume upload verified after {method.__name__}!")
                        # Click Next to proceed
                        self._click_any(["a#forward-navigation", "button#next", "//button[contains(text(), 'Next')]", "//a[contains(text(), 'Next')]"])
                        return True
                    else:
                        logger.warning(f"{method.__name__} finished but verification failed.")
            except Exception as e:
                logger.warning(f"{method.__name__} failed: {e}")

        logger.error("Γ¥î All resume upload methods failed or could not be verified.")
        return False

        logger.error("Γ¥î All resume upload methods failed or could not be verified.")
        return False

    def _verify_upload_success(self):
        success_indicators = [
            ".dz-filename",
            ".dz-success",
            ".dz-complete",
            ".upload-success",
            ".dz-preview",
            "div.dz-image",
            ".resume-preview",
            ".file-name",
            "[id*='resume_name']",
            "//span[contains(@class, 'dz-filename')]",
            "//div[contains(@class, 'success-message')]",
            "//span[contains(text(), '.pdf')]",
            "//div[contains(text(), 'uploaded successfully')]",
            "button.remove",
            "a.remove", 
            "//a[contains(text(), 'Remove')]",
            "//button[contains(text(), 'Remove')]",
            "//span[contains(text(), 'Remove')]"
        ]
        for sel in success_indicators:
            try:
                by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                elems = self.driver.find_elements(by, sel)
                for e in elems:
                    if e.is_displayed():
                        logger.info(f"Γ£ô Upload verified via indicator: {sel}")
                        return True
            except Exception:
                continue
        
        # DEBUG: Log HTML context on failure
        try:
            body_html = self.driver.find_element(By.TAG_NAME, "body").get_attribute('innerHTML')
            snippet = body_html[:5000] # Grab first 5000 chars
            logger.warning(f"DEBUG: Verification Failed. Body Start: {snippet}...")
        except:
            pass

        return False

    def _method_direct_input(self, path):
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if not inputs:
            return False
        for inp in inputs:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", inp)
                inp.send_keys(path)
                return True
            except Exception:
                continue
        return False

    def _method_visible_input(self, path):
        try:
            self.driver.execute_script(
                """
                document.querySelectorAll('input[type="file"]').forEach(i => {
                    i.style.display='block';
                    i.style.visibility='visible';
                    i.style.height='1px';
                    i.style.width='1px';
                    i.style.opacity='1';
                });
                """
            )
        except Exception:
            pass
        return self._method_direct_input(path)

    def _method_click_dropzone(self, path):
        selectors = [".dropzone", "#pnlResumeDrop", ".upload-container", ".upload-area"]
        if self._click_any(selectors):
            time.sleep(2)
            return self._method_direct_input(path)
        return False

    def _method_js_manipulation(self, path):
        # Best effort: send_keys, then dispatch change
        ok = self._method_visible_input(path)
        try:
            self.driver.execute_script(
                """
                var input = document.querySelector('input[type="file"]');
                if(input) {
                    var event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);
                }
                """
            )
        except Exception:
            pass
        return bool(ok)

    def _method_nested_input(self, path):
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for i, frame in enumerate(iframes):
            try:
                self.driver.switch_to.frame(frame)
                logger.info(f"Checking iframe {i} for file input...")
                if self._method_direct_input(path):
                    self.driver.switch_to.default_content()
                    return True
                self.driver.switch_to.default_content()
            except Exception:
                self.driver.switch_to.default_content()
                continue
        return False

    def _method_user_simulation(self, path):
        dz = self._find_element_safe([".dropzone", "#pnlResumeDrop", ".upload-area", ".upload-container"])
        if dz:
            self.human.human_click(dz)
            time.sleep(1)
            return self._method_direct_input(path)
        return False

    # -------------------------
    # Popups (aggressive)
    # -------------------------
    def _close_common_popups(self):
        popups = [
            "span.x-icon",
            ".x-icon",
            "div.close-item button.close",
            "//div[contains(@class, 'close-item')]//button",
            "button[aria-label='Close']",
            "button.close",
            "button#onetrust-accept-btn-handler",
            "//button[contains(text(), 'Close')]",
            "//span[contains(@class, 'x-icon')]/..",
        ]

        logger.info("Scanning for popups to close...")

        # root
        self._check_and_js_click(popups)

        # iframes
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        for i, frame in enumerate(iframes):
            try:
                self.driver.switch_to.frame(frame)
                if self._check_and_js_click(popups):
                    logger.info(f"Closed popup inside iframe {i}")
                self.driver.switch_to.default_content()
            except Exception:
                self.driver.switch_to.default_content()
                continue

    def _check_and_js_click(self, selectors):
        clicked = False
        for sel in selectors:
            try:
                by = By.XPATH if sel.startswith("//") else By.CSS_SELECTOR
                elements = self.driver.find_elements(by, sel)
                for elem in elements:
                    try:
                        if elem.is_displayed():
                            logger.info(f"Attempting JS Click on: {sel}")
                            self.driver.execute_script(
                                """
                                arguments[0].style.border = '3px solid green';
                                var clickEvent = new MouseEvent('click', {
                                    view: window,
                                    bubbles: true,
                                    cancelable: true
                                });
                                arguments[0].dispatchEvent(clickEvent);
                                """,
                                elem,
                            )
                            time.sleep(0.6)
                            clicked = True
                    except Exception:
                        continue
            except Exception:
                continue
        return clicked

    # -------------------------
    # Submit
    # -------------------------
    def _submit_final(self, job_url):
        if settings.DRY_RUN:
            logger.info("DRY RUN: Skipping final submit.")
            csv_tracker.update_job_status("infosys", job_url, "dry_run")
            return True

        # Click final button
        # Removing generic "Apply Now" to avoid clicking the initial button if we never left the page
        success = self._click_any(
            [
                ".form-submit-button", 
                "input[type='submit']", 
                "//button[contains(text(), 'Submit Application')]",
                "//button[contains(text(), 'Submit')]"
            ]
        )
        if success:
            logger.info("Γ£à Application Submitted!")
            csv_tracker.update_job_status("infosys", job_url, "success")
            
            # User requirement: Wait 20s after submission
            logger.info("Waiting 20 seconds for confirmation/processing...")
            time.sleep(20)
            return True

        logger.warning("Submit button not found / submit failed.")
        return False


if __name__ == "__main__":
    import sys

    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from core.browser import browser_service

    try:
        logger.info("≡ƒÜÇ Starting Infosys Strategy Standalone Launch...")
        driver = browser_service.start_browser()

        class MockSite:
            id = 1
            name = "Infosys"

        strategy = InfosysStrategy(driver, MockSite(), {}, db_session=None) # We could pass session here if needed
        jobs = strategy.find_jobs()
        if jobs:
            logger.info(f"Discovered {len(jobs)} target jobs.")
            applied_count = 0
            failed_count = 0
            for i, job_url in enumerate(jobs):
                logger.info(f"≡ƒöä Processing job {i+1}/{len(jobs)}: {job_url}")
                try:
                    success = strategy.apply(job_url)
                    if success:
                        logger.info(f"Γ£ô Successfully applied to {job_url}")
                        applied_count += 1
                    else:
                        logger.warning(f"├ù Failed to apply to {job_url}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error applying to {job_url}: {e}")
                    failed_count += 1
                
                # Small pause between jobs
                time.sleep(5)
            
            logger.info("=" * 60)
            logger.info(f"≡ƒÅü Execution Summary: Applied to {applied_count} jobs, {failed_count} failed.")
            logger.info("=" * 60)
        else:
            logger.info("No target jobs found.")

    except Exception as e:
        logger.error(f"Execution Error: {e}")
    finally:
        if not settings.DRY_RUN:
            browser_service.stop_browser()
        else:
            logger.info("Dry run enabled - keeping browser open for 60s for review...")
            time.sleep(60)
            browser_service.stop_browser()
