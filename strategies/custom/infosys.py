from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler
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
    """

    def __init__(self, driver, job_site, selectors, db_session=None):
        super().__init__(driver, job_site, selectors)
        self.db_session = db_session
        self.job_site = job_site
        self.config_data = self._load_config()
        self.resume_data = self._load_resume_json()

        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=30)

        if self.db_session:
            logger.info("✅ Database session available - tracking enabled.")

    # -------------------------
    # Config loaders
    # -------------------------
    def _load_config(self):
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data",
                "guest_form_data.json",
            )
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def _load_resume_json(self):
        try:
            resume_json_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "resume",
                "resume.json",
            )
            if os.path.exists(resume_json_path):
                with open(resume_json_path, "r") as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Failed to load resume JSON: {e}")
            return {}

    # -------------------------
    # Base hooks
    # -------------------------
    def login(self):
        logger.info("Infosys: Guest flow selected (no login).")
        return True

    def find_jobs(self):
        search = self.config_data.get("search", {})
        kw = search.get("keyword", "AI Engineer")
        loc = search.get("location", "USA")
        dist = search.get("distance", "50")
        urls = self._search_jobs(kw, loc, dist)
        return [{"job_url": u, "job_title": "Infosys Job"} for u in urls]

    def apply(self, listing):
        url = listing.get("job_url") if isinstance(listing, dict) else getattr(listing, "job_url", None)
        return self._apply_to_job(url)

    # -------------------------
    # Job Search
    # -------------------------
    def _search_jobs(self, keyword, location, distance):
        loc_param = location if location else "USA"
        base_url = f"https://digitalcareers.infosys.com/infosys/global-careers?location={loc_param}"

        logger.info(f"Searching Infosys: {keyword} in {loc_param}")
        self.driver.get(base_url)
        time.sleep(5)
        logger.info(f"Current URL after navigation: {self.driver.current_url}")
        self._close_common_popups()

        try:
            # open search if needed
            self._click_any(
                [
                    "button.search-toggle",
                    "button.search",
                    "//button[contains(text(), 'SEARCH JOBS')]",
                    "//span[contains(text(), 'SEARCH JOBS')]",
                ]
            )
            time.sleep(2)

            # keyword input
            search_box = self.driver.find_element(
                By.CSS_SELECTOR, "input.js_search_cp_jobs, input[placeholder*='Search']"
            )
            self.human.fill_text_field(search_box, keyword)
            search_box.send_keys(Keys.ENTER)
            time.sleep(5)

            job_urls = []
            seen = set()
            max_pages = 5

            for page in range(1, max_pages + 1):
                logger.info(f"Processing Page {page}")
                links = self.driver.find_elements(By.CSS_SELECTOR, "a.job[href*='/description/reqid/']")

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
                next_btn = self._find_element_safe(["a.next", "li.next a", "a[title='Next']"])
                if next_btn and "disabled" not in (next_btn.get_attribute("class") or ""):
                    self.human.human_click(next_btn)
                    time.sleep(3)
                else:
                    break

            return job_urls

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def _is_target_job(self, title):
        if not title:
            return False
        t = title.lower()
        targets = ["ai", "machine learning", "ml", "data science", "engineer", "developer", "technology", "software"]
        blocks = ["nurse", "sales", "hr", "marketing", "finance", "legal", "doctor"]
        if any(b in t for b in blocks):
            return False
        
        # Location check (Basic - ideally we'd check a location field in the DOM)
        # If the search results include non-USA despite the URL, we might need to check 'USA' or 'United States'
        # The user specifically mentioned Canada and Brazil.
        non_usa = ["canada", "brazil", "india", "mexico", "united kingdom", "uk", "australia"]
        if any(loc in t for loc in non_usa):
            logger.debug(f"Skipping non-USA job: {title}")
            return False

        return any(tr in t for tr in targets)

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

        # 1) Apply
        if not self._click_any(
            [
                "a.infosys-apply-link",
                ".apply-button-container a",
                "//a[contains(text(), 'Apply')]",
                "//button[contains(text(), 'Apply Now')]",
            ]
        ):
            logger.error("Could not find Apply button")
            return False

        time.sleep(5)
        self._ensure_active_window()
        time.sleep(5)

        # 2) First-time user + privacy
        self._handle_first_time_user()
        time.sleep(2)
        self._handle_privacy_modal()
        time.sleep(2)

        # 3) Personal info
        self._fill_personal_info()
        self.human.random_delay(2, 4)

        # 4) Resume upload
        self._upload_resume_with_retry()
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
        selectors = [
            ".apply-first-time-button",
            "a.apply-first-time-button",
            "//a[contains(@class, 'apply-first-time-button')]",
            "input[value='FirstTime']",
            "#rdoFirstTime",
            "//span[contains(text(), 'First time')]",
            "//label[contains(text(), 'applying for the first time')]",
        ]
        if self._click_any(selectors):
            logger.info("✓ Selected 'Applying for first time'")
            time.sleep(2)
            return True
        return False

    def _handle_privacy_modal(self):
        logger.info("Handling Privacy/Consent Modal...")
        consent_selectors = [
            "a.consent-button",
            ".consent-button",
            "//a[contains(@class, 'consent-button') and contains(text(), 'Proceed')]",
            "button.agree",
            "button.proceed",
            "//button[contains(text(), 'Proceed')]",
        ]
        if self._click_any(consent_selectors):
            logger.info("✓ Clicked Proceed/Consent button")
            time.sleep(3)
        else:
            logger.warning("Could not find Proceed button.")

    # -------------------------
    # Personal Info + Smart Fill
    # -------------------------
    def _fill_personal_info(self):
        logger.info("Filling Personal Information...")
        applicant = self.config_data.get("applicant", {})
        resume_data = self.resume_data.get("basics", {})

        full_name = resume_data.get("name", "")
        name_parts = full_name.split()

        first_name = applicant.get("first_name") or (name_parts[0] if name_parts else "")
        last_name = applicant.get("last_name") or (name_parts[-1] if len(name_parts) > 1 else "")
        email = applicant.get("email") or resume_data.get("email", "")
        phone = applicant.get("phone") or resume_data.get("phone", "")
        city = applicant.get("city") or resume_data.get("location", {}).get("city", "")
        address = applicant.get("address") or resume_data.get("location", {}).get("address", "")
        zip_code = applicant.get("zip_code") or resume_data.get("location", {}).get("postalCode", "")

        self.driver.switch_to.default_content()
        self._switch_to_form_frame()

        logger.info("Selecting Country & State...")
        self._select_dropdown(["select[name*='country']", "select#country"], ["United States", "USA", "US"])
        time.sleep(1)
        self._select_dropdown(["select#state", "select[name*='state']"], ["California", "CA"])
        time.sleep(1)

        self._smart_fill(["first name", "firstname", "given name"], first_name)
        self._smart_fill(["last name", "lastname", "surname", "family name"], last_name)
        self._smart_fill(["email", "email address"], email)
        self._smart_fill(["phone", "mobile", "contact number", "cell"], phone)
        self._smart_fill(["city"], city)
        self._smart_fill(["address", "address 1", "address line 1"], address)
        self._smart_fill(["zip", "zip code", "postal", "postal code"], zip_code)

        logger.info("Proceeding to next section...")
        self._click_any(
            [
                "a#forward-navigation",
                "a.form-next-button",
                "//button[contains(text(), 'Next')]",
                "//a[contains(text(), 'Next')]",
            ]
        )

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
        end = time.time() + timeout
        while time.time() < end:
            try:
                fields = self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), select, textarea")
                if len(fields) >= 3:
                    return True
            except Exception:
                pass
            time.sleep(0.4)
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
            edu_keywords = ["education", "school", "institution", "university", "college", "degree", "qualification", "major"]
            if "education" not in filled_sections and self._page_has_any_field(edu_keywords):
                logger.info("Detected Education section by fields → filling...")
                self._fill_education_parsed()
                filled_sections.add("education")
                did_something = True

            # EXPERIENCE
            exp_keywords = [
                "work",
                "experience",
                "employer",
                "company",
                "designation",
                "job_title",
                "position",
                "responsibilities",
            ]
            if "experience" not in filled_sections and self._page_has_any_field(exp_keywords):
                logger.info("Detected Experience section by fields → filling...")
                self._fill_experience_parsed()
                filled_sections.add("experience")
                did_something = True

            # SKILLS
            skills_keywords = ["skills", "technologies", "tool", "stack"]
            if "skills" not in filled_sections and self._page_has_any_field(skills_keywords):
                logger.info("Detected Skills section by fields → filling...")
                self._fill_skills_parsed()
                filled_sections.add("skills")
                did_something = True

            # EEO / DIVERSITY / OTHER INFO
            # We allow this to run multiple times (by not checking filled_sections) 
            # because EEO and Agreement/Other Info often appear on separate pages 
            # but share similar field types/keywords.
            eeo_keywords = ["ethnicity", "race", "gender", "veteran", "disability", "eeo", "employed", "contract", "arbitration", "other", "additional", "signature", "mutual", "source", "authorized", "relocate", "travel", "sponsorship"]
            if self._page_has_any_field(eeo_keywords):
                logger.info("Detected EEO / Other Info section by fields → filling...")
                applicant = self.config_data.get("applicant", {})
                full_name = f"{applicant.get('first_name', '')} {applicant.get('last_name', '')}"
                
                eeo_data = [
                    (["ethnicity"], "No"),
                    (["race"], "Asian"), 
                    (["gender"], "Female"),
                    (["veteran"], "No"),
                    (["disability", "custom[eeo][disability]"], "No, I do not have a disability and have not had one in the past"),
                    (["employed", "custom[other][employed]", "employed by infosys"], "No"),
                    (["contractual", "custom[other][contract_restriction]", "contractual restrictions"], "No"),
                    (["mutual arbitration", "custom[other][arbitration]", "arbitration"], "1"),
                    (["source", "how did you hear", "hear about us", "infosys career website", "reference"], "Infosys Careers Site"),
                    (["authorized", "work in the united states"], "Yes"),
                    (["relocate", "custom[other][relocate]"], "Yes"),
                    (["travel", "custom[other][travel]"], "Yes"),
                    (["sponsorship", "custom[other][sponsorship]"], "No"),
                    (["minimum qualification", "custom[other][degree]", "degree"], "Yes"),
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
                logger.info("No Next/Save/Continue found → stopping dynamic section loop.")
                break

            time.sleep(4)

            page_after = self.driver.page_source
            if page_after == page_before:
                logger.warning("Page did not change after Next → retrying once...")
                if not self._click_next_best_effort():
                    logger.warning("Retry failed → stopping.")
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

        all_skills = ", ".join([s.get("name", "") for s in skills if s.get("name")])

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
                logger.warning("Element #file_resume not found via JS.")
                return False
            
            # 2. Send keys
            elem = self.driver.find_element(By.ID, "file_resume")
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
        resume_path = self.config_data.get('resume_path')
        if not resume_path or not os.path.exists(resume_path):
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
                    # Poll for the popup for 5 seconds to ensure we catch it
                    for _ in range(5):
                        self._close_common_popups()
                        time.sleep(1)
                    
                    # TRUST METHOD 0: If specific ID upload worked and we waited 40s, assume success.
                    if method == self._upload_resume_method_id_file_resume:
                        logger.info("Method 0 (Targeted ID) finished. Trusting success and proceeding.")
                        return True

                    # Verify for other methods
                    if self._verify_upload_success():
                        logger.info("Resume upload verified!")
                        return True
                    else:
                        logger.warning(f"{method.__name__} sent keys but verification failed.")
            except Exception as e:
                logger.warning(f"{method.__name__} failed: {e}")

        logger.error("❌ All resume upload methods failed or could not be verified.")
        return False

        logger.error("❌ All resume upload methods failed or could not be verified.")
        return False

    def _verify_upload_success(self):
        success_indicators = [
            ".dz-filename",
            ".dz-success",
            ".dz-complete",
            ".upload-success",
            ".dz-preview",
            "div.dz-image",
            "//span[contains(@class, 'dz-filename')]",
            "//div[contains(@class, 'success-message')]",
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
                        logger.info(f"✓ Upload verified via indicator: {sel}")
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
        success = self._click_any(
            [
                ".form-submit-button", 
                "//button[contains(text(), 'Apply Now')]", 
                "input[type='submit']", 
                "//button[contains(text(), 'Submit')]"
            ]
        )
        if success:
            logger.info("✅ Application Submitted!")
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
        logger.info("🚀 Starting Infosys Strategy Standalone Launch...")
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
                logger.info(f"🔄 Processing job {i+1}/{len(jobs)}: {job_url}")
                try:
                    success = strategy.apply(job_url)
                    if success:
                        logger.info(f"✓ Successfully applied to {job_url}")
                        applied_count += 1
                    else:
                        logger.warning(f"× Failed to apply to {job_url}")
                        failed_count += 1
                except Exception as e:
                    logger.error(f"Error applying to {job_url}: {e}")
                    failed_count += 1
                
                # Small pause between jobs
                time.sleep(5)
            
            logger.info("=" * 60)
            logger.info(f"🏁 Execution Summary: Applied to {applied_count} jobs, {failed_count} failed.")
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
