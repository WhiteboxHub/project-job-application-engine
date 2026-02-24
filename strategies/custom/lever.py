"""
Lever ATS Strategy
Reads job listings from hiring_cafe_output.json,
filters only jobs with 'jobs.lever.co' in the ats_url,
and applies to each one using Lever's standard apply form.
"""

from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
import time
import os
import json
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from data.csv_tracker import tracker as csv_tracker


# URL pattern that identifies Lever job apply pages
LEVER_URL_PATTERN = "jobs.lever.co"


class LeverStrategy(BaseStrategy):
    """
    Lever ATS automation strategy.

    Lever (jobs.lever.co) has a standardized apply form:
      - Full Name, Email, Phone, Current Company
      - Resume upload
      - Optional links (LinkedIn, GitHub, Portfolio)
      - Custom text/dropdown questions
      - Submit button

    Workflow:
      1. Read hiring_cafe_output.json
      2. Keep only jobs whose ats_url contains 'jobs.lever.co'
      3. For each job, navigate to the /apply URL and fill + submit the form
    """

    # Tells EngineRunner to call find_and_apply_jobs() directly
    use_single_phase = True

    def __init__(self, driver, job_site=None, selectors=None, db_session=None, candidate_data=None):
        # Minimal job_site stub so BaseStrategy.__init__ won't fail
        if job_site is None:
            class _StubSite:
                company_name = "Lever"
                search_url_template = "https://jobs.lever.co"
            job_site = _StubSite()

        super().__init__(driver, job_site, selectors or {}, db_session, candidate_data)
        self.use_single_phase = True          # redundant but explicit
        self.human = HumanBehavior(driver)
        self.safe_actions = SafeActions(driver)

        # Load applicant data: candidate_data (from runner) takes priority,
        # otherwise fall back to guest_form_data.json
        if candidate_data:
            self.config_data = candidate_data
            logger.info("Lever: Using candidate_data supplied by runner")
        else:
            self.config_data = self._load_guest_form_data()

    # ------------------------------------------------------------------ #
    #  Config Helpers
    # ------------------------------------------------------------------ #

    def _load_guest_form_data(self):
        """Fallback: load applicant info from data/guest_form_data.json."""
        try:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'data', 'guest_form_data.json'
            )
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Lever: Loaded guest_form_data.json from {path}")
            return data
        except Exception as e:
            logger.error(f"Lever: Failed to load guest_form_data.json: {e}")
            return {}

    def _load_hiring_cafe_output(self):
        """Load all jobs from hiring_cafe_output.json (project root)."""
        try:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                'hiring_cafe_output.json'
            )
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            jobs = data.get('jobs', [])
            logger.info(f"Lever: Loaded hiring_cafe_output.json — {len(jobs)} total jobs")
            return jobs
        except Exception as e:
            logger.error(f"Lever: Failed to load hiring_cafe_output.json: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  BaseStrategy Abstract Methods
    # ------------------------------------------------------------------ #

    def login(self):
        """Lever apply pages are public — no login required."""
        logger.info("Lever: No login required (public apply pages)")
        return True

    def find_jobs(self):
        """
        Filter hiring_cafe_output.json for Lever jobs only.

        A job qualifies if its ats_url contains 'jobs.lever.co'.
        It is skipped if it has already been applied to (checked via DuckDB).

        Returns:
            list[dict]: Each dict has keys: job_id, title, ats_url, hiring_cafe_url
        """
        all_jobs = self._load_hiring_cafe_output()
        from data.db_duckdb import db_duckdb

        lever_jobs = []
        skipped_count = 0
        for job in all_jobs:
            ats_url = (job.get('ats_url') or '').strip()
            if LEVER_URL_PATTERN in ats_url:
                job_id = job.get('job_id', 'unknown')
                
                # Check if already applied
                if db_duckdb.is_already_applied(job_id, 'lever'):
                    skipped_count += 1
                    continue

                lever_jobs.append({
                    'job_id':          job_id,
                    'title':           job.get('title', 'Unknown Title'),
                    'ats_url':         ats_url,
                    'hiring_cafe_url': job.get('hiring_cafe_url', ''),
                    'ats_platform':    'lever',
                })

        logger.info(f"Lever: {len(lever_jobs)} new Lever job(s) found (skipped {skipped_count} already applied)")
        for j in lever_jobs:
            logger.info(f"  [{j['job_id']}] {j['title'][:70]} -> {j['ats_url']}")
        return lever_jobs

    def apply(self, listing):
        """BaseStrategy interface — delegates to _apply_to_lever_job()."""
        if isinstance(listing, dict):
            job = listing
        else:
            job = {
                'job_id': getattr(listing, 'external_job_id', None) or getattr(listing, 'job_id', 'unknown'),
                'title':  getattr(listing, 'job_title', 'Unknown'),
                'ats_url': getattr(listing, 'job_url', ''),
            }
        return self._apply_to_lever_job(job)

    # ------------------------------------------------------------------ #
    #  Main Workflow (Single-Phase)
    # ------------------------------------------------------------------ #

    def find_and_apply_jobs(self):
        """
        Called by EngineRunner when use_single_phase=True.
        Finds all Lever jobs and applies to each one.

        Returns:
            int: Number of successfully submitted applications
        """
        logger.info("=" * 60)
        logger.info("LeverStrategy: Starting find_and_apply_jobs")
        logger.info("=" * 60)

        if not self.config_data:
            logger.error("Lever: No applicant config available — aborting")
            return 0

        lever_jobs = self.find_jobs()
        if not lever_jobs:
            logger.warning("Lever: No jobs.lever.co URLs found in hiring_cafe_output.json")
            return 0

        logger.info(f"\nLever: Processing {len(lever_jobs)} job(s)...")
        total_applied = 0

        for idx, job in enumerate(lever_jobs, 1):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"[{idx}/{len(lever_jobs)}] {job['title'][:70]}")
            logger.info(f"URL: {job['ats_url']}")
            logger.info(f"{'=' * 60}")

            try:
                success = self._apply_to_lever_job(job)
                if success:
                    total_applied += 1
                    logger.info(f"Lever: Application #{total_applied} submitted successfully")
                else:
                    logger.warning(f"Lever: Application failed for job_id={job['job_id']}")
            except Exception as e:
                logger.error(f"Lever: Unexpected error for job_id={job['job_id']}: {e}")
                import traceback
                traceback.print_exc()

            # Polite delay between applications
            if idx < len(lever_jobs):
                delay = random.uniform(3, 6)
                logger.info(f"Lever: Waiting {delay:.1f}s before next job...")
                time.sleep(delay)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Lever: Done — {total_applied}/{len(lever_jobs)} applications submitted")
        logger.info(f"{'=' * 60}")
        return total_applied

    # ------------------------------------------------------------------ #
    #  Lever Form Application
    # ------------------------------------------------------------------ #

    def _apply_to_lever_job(self, job):
        """
        Navigate to the Lever /apply URL and fill + submit the form.

        Lever's standard form fields:
          - name        (full name)
          - email       (email address)
          - phone       (phone number)
          - org         (current company)
          - resume      (file upload — hidden input)
          - urls        (LinkedIn, GitHub, Portfolio — optional)
          - custom Q&A  (textareas / dropdowns — best-effort)
          - submit btn

        Args:
            job (dict): Must contain 'ats_url', 'job_id', 'title'

        Returns:
            bool: True if form was submitted (or dry-run simulated)
        """
        from engine.guards import guards

        ats_url = job.get('ats_url', '')
        job_id  = job.get('job_id', 'unknown')
        title   = job.get('title', 'Unknown')

        # Ensure the URL ends with /apply
        apply_url = ats_url if '/apply' in ats_url else ats_url.rstrip('/') + '/apply'

        # Resolve applicant details
        # Support both raw guest_form_data.json structure and CandidateLoader structure
        applicant = (
            self.config_data.get('applicant')          # guest_form_data.json
            or self.config_data                        # CandidateLoader flat dict
            or {}
        )
        first_name = applicant.get('first_name', '') or self.config_data.get('first_name', '')
        last_name  = applicant.get('last_name', '')  or self.config_data.get('last_name', '')
        email      = applicant.get('email', '')      or self.config_data.get('email', '')
        phone      = applicant.get('phone', '')      or self.config_data.get('phone', '')
        experience = applicant.get('experience', []) or self.config_data.get('work', [])
        company    = experience[0].get('company', '') if experience else ''

        full_name  = f"{first_name} {last_name}".strip()

        # Resolve resume path using the BaseStrategy helper
        resume_path = self.get_resume_path()

        try:
            # ── Step 1: Navigate ──────────────────────────────────────────
            logger.info(f"  Navigating to: {apply_url}")
            self.driver.get(apply_url)
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            logger.info("  Page loaded")

            # ── Step 2: Fill standard Lever fields ────────────────────────
            self._fill_field(
                ['input[name="name"]', 'input[placeholder*="name" i]', '#name'],
                full_name, label="Full Name"
            )
            self._fill_field(
                ['input[name="email"]', 'input[type="email"]', '#email'],
                email, label="Email"
            )
            self._fill_field(
                ['input[name="phone"]', 'input[type="tel"]', 'input[placeholder*="phone" i]', '#phone'],
                phone, label="Phone"
            )
            if company:
                self._fill_field(
                    ['input[name="org"]', 'input[placeholder*="company" i]',
                     'input[placeholder*="organization" i]', '#org'],
                    company, label="Current Company", required=False
                )

            # ── Step 3: Upload resume ─────────────────────────────────────
            if resume_path:
                self._upload_resume(resume_path)
            else:
                logger.warning("  Resume not found — skipping upload")

            # ── Step 4: Handle specific sections (USA Forms) ──────────────
            self._handle_usa_form_section()
            self._handle_general_usa_form_section()
            
            # ── Step 5: Handle other custom questions (best-effort) ────────
            self._handle_custom_questions()

            # ── Step 5: Dry run guard ─────────────────────────────────────
            if guards.is_dry_run():
                logger.info("\n" + "!" * 60)
                logger.info("! DRY RUN: Would submit Lever application now")
                logger.info(f"! Job: {title[:70]}")
                logger.info(f"! URL: {apply_url}")
                logger.info("!" * 60 + "\n")
                self._track_application(job, status='dry_run')
                return True  # Counts as success in dry-run

            # ── Step 6: Submit form ────────────────────────────────────────
            submitted = self._submit_form()

            # ── Step 7: Record result ──────────────────────────────────────
            status = 'applied' if submitted else 'failed'
            self._track_application(job, status=status)
            return submitted

        except Exception as e:
            logger.error(f"  Lever: Error during application for job_id={job_id}: {e}")
            import traceback
            traceback.print_exc()
            self._track_application(job, status='error')
            return False

    # ------------------------------------------------------------------ #
    #  Form Helpers
    # ------------------------------------------------------------------ #

    def _fill_field(self, selectors, value, label="Field", required=True):
        """
        Try selectors in order until one matches a visible, enabled input,
        then type `value` into it using human-like behavior.
        """
        if not value:
            logger.debug(f"  Skipping {label}: empty value")
            return False

        for selector in selectors:
            try:
                elem = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if elem.is_displayed() and elem.is_enabled():
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", elem
                    )
                    time.sleep(0.3)
                    elem.clear()
                    self.human.fill_text_field(elem, value)
                    logger.info(f"  Filled {label}: {value[:50]}")
                    return True
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                logger.debug(f"  Selector '{selector}' failed for {label}: {e}")
                continue

        if required:
            logger.warning(f"  Could not find field: {label}")
        return False

    def _upload_resume(self, resume_full_path):
        """
        Lever uses a hidden <input type="file"> — use send_keys directly
        (after making it visible via JS).
        """
        selectors = [
            'input[type="file"]',
            'input[name="resume"]',
            'input[accept*="pdf"]',
            'input[accept*="doc"]',
        ]
        for selector in selectors:
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                self.driver.execute_script(
                    "arguments[0].style.display='block'; arguments[0].style.visibility='visible';",
                    file_input
                )
                time.sleep(0.3)
                file_input.send_keys(resume_full_path)
                logger.info(f"  Resume uploaded: {os.path.basename(resume_full_path)}")
                time.sleep(2)  # Let upload complete
                return True
            except NoSuchElementException:
                continue
            except Exception as e:
                logger.debug(f"  Upload selector '{selector}' failed: {e}")
                continue

        logger.warning("  Could not find resume file input")
        return False

    def _handle_usa_form_section(self):
        """
        Specific handler for 'Application Form (USA)' section found on Lever.
        Fills out 6 questions in order based on the user-provided HTML structure.
        """
        logger.info("  Processing 'Application Form (USA)' section...")
        
        # Load values from config (e.g. within applicant.custom_questions or flat usa_form key)
        applicant = (
            self.config_data.get('applicant') 
            or self.config_data 
            if isinstance(self.config_data, dict) else {}
        )
        details = applicant.get('usa_form', {})
        
        # Mapping labels to default values or config keys
        questions = [
            ("Where do you currently reside", details.get('residence', "Piscataway, NJ")),
            ("travel are you open to", details.get('travel', "25%")),
            ("willing to relocate", details.get('relocate', "Yes")),
            ("where would you be open to relocating", details.get('relocation_destinations', "Open to all major US hubs")),
            ("industry related certifications", details.get('certifications', "None")),
            ("Expected Salary", details.get('expected_salary', "$120,000 - $150,000")),
        ]

        for label_text, value in questions:
            try:
                # Find the label that contains the text (case-insensitive-ish)
                xpath = f"//div[contains(@class, 'application-label')]//div[contains(text(), '{label_text}')]"
                label_elems = self.driver.find_elements(By.XPATH, xpath)
                if not label_elems:
                    # Try a broader search if specific div structure fails
                    xpath = f"//li[contains(@class, 'application-question')]//div[contains(text(), '{label_text}')]"
                    label_elems = self.driver.find_elements(By.XPATH, xpath)
                
                if not label_elems:
                    continue

                label_elem = label_elems[0]
                
                # Find the parent question container
                question_container = label_elem.find_element(By.XPATH, "./ancestor::li[contains(@class, 'application-question')]")
                
                # Scroll into view
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", question_container)
                time.sleep(0.3)

                # Check if it's a radio or text input
                inputs = question_container.find_elements(By.TAG_NAME, "input")
                textareas = question_container.find_elements(By.TAG_NAME, "textarea")
                
                if inputs and inputs[0].get_attribute("type") == "radio":
                    # Handle multiple choice (radio)
                    radio_found = False
                    for radio in inputs:
                        parent_label = radio.find_element(By.XPATH, "./parent::label")
                        if str(value).lower() == parent_label.text.strip().lower():
                            radio.click()
                            logger.info(f"    Selected radio '{value}' for: '{label_text}'")
                            radio_found = True
                            break
                    
                    if not radio_found:
                        # Best effort: if "Yes" is requested but not found exactly, try contains
                        for radio in inputs:
                            parent_label = radio.find_element(By.XPATH, "./parent::label")
                            if str(value).lower() in parent_label.text.strip().lower():
                                radio.click()
                                logger.info(f"    Selected radio containing '{value}' for: '{label_text}'")
                                radio_found = True
                                break
                                
                elif inputs:
                    # Handle text input
                    text_input = inputs[0]
                    text_input.clear()
                    self.human.fill_text_field(text_input, str(value))
                    logger.info(f"    Filled: '{label_text}' -> '{value}'")
                
                elif textareas:
                    # Handle textarea
                    textarea = textareas[0]
                    textarea.clear()
                    self.human.fill_text_field(textarea, str(value))
                    logger.info(f"    Filled Textarea: '{label_text}' -> '{value}'")
                
                self.human.random_delay(0.5, 1.0)
                
            except Exception as e:
                logger.debug(f"    Could not handle USA Form question '{label_text}': {e}")

    def _handle_general_usa_form_section(self):
        """
        Handler for 'General Application Form (USA)' section.
        Fills out 5 questions including education formatting and acknowledgments.
        """
        logger.info("  Processing 'General Application Form (USA)' section...")
        
        applicant = (
            self.config_data.get('applicant') 
            or self.config_data 
            if isinstance(self.config_data, dict) else {}
        )
        gen_details = applicant.get('general_usa_form', {})
        
        # Construct education string: "University of Sindh; BA"
        edu_list = applicant.get('education', [])
        edu_str = ""
        if edu_list:
            edu_items = [f"{e.get('University', e.get('school', 'Unknown'))}; {e.get('degree', 'BA')}" for e in edu_list]
            edu_str = " | ".join(edu_items) # or just first? Let's join or pick first.
            # User example: University of Somewhere; Bachelor of Science
            if len(edu_list) > 1:
                edu_str = "; ".join(edu_items) # Better formatting
            else:
                e = edu_list[0]
                edu_str = f"{e.get('University', e.get('school', 'Unknown'))}; {e.get('degree', 'BA')}"

        questions = [
            ("Primary Residence Address", gen_details.get('address', applicant.get('street_address', ''))),
            ("Post-Secondary Education", gen_details.get('education_formatted', edu_str)),
            ("reasonable accommodations", gen_details.get('ability_to_perform', 'Yes')),
            ("Work Authorization status", gen_details.get('authorization', applicant.get('visa_status', 'US Citizen'))),
            ("AHEAD will consider", gen_details.get('acknowledge', True)),
        ]

        for label_text, value in questions:
            try:
                xpath = f"//div[contains(@class, 'application-label')]//div[contains(text(), '{label_text}')]"
                label_elems = self.driver.find_elements(By.XPATH, xpath)
                if not label_elems:
                    xpath = f"//li[contains(@class, 'application-question')]//div[contains(text(), '{label_text}')]"
                    label_elems = self.driver.find_elements(By.XPATH, xpath)
                
                if not label_elems:
                    continue

                label_elem = label_elems[0]
                question_container = label_elem.find_element(By.XPATH, "./ancestor::li[contains(@class, 'application-question')]")
                
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", question_container)
                time.sleep(0.3)

                inputs = question_container.find_elements(By.TAG_NAME, "input")
                textareas = question_container.find_elements(By.TAG_NAME, "textarea")
                selects = question_container.find_elements(By.TAG_NAME, "select")
                
                if selects:
                    from selenium.webdriver.support.ui import Select
                    sel = Select(selects[0])
                    # Try to select by text
                    try:
                        sel.select_by_visible_text(str(value))
                    except:
                        # Fallback to index 1 if text fails
                        if len(sel.options) > 1: sel.select_by_index(1)
                    logger.info(f"    Selected dropdown '{value}' for: '{label_text}'")

                elif inputs and inputs[0].get_attribute("type") == "checkbox":
                    # Handle checkbox
                    if value:
                        if not inputs[0].is_selected():
                            inputs[0].click()
                            logger.info(f"    Checked checkbox for: '{label_text}'")

                elif inputs and inputs[0].get_attribute("type") == "radio":
                    radio_found = False
                    for radio in inputs:
                        parent_label = radio.find_element(By.XPATH, "./parent::label")
                        if str(value).lower() == parent_label.text.strip().lower():
                            radio.click()
                            logger.info(f"    Selected radio '{value}' for: '{label_text}'")
                            radio_found = True
                            break
                    if not radio_found:
                        for radio in inputs:
                            parent_label = radio.find_element(By.XPATH, "./parent::label")
                            if str(value).lower() in parent_label.text.strip().lower():
                                radio.click()
                                logger.info(f"    Selected radio containing '{value}' for: '{label_text}'")
                                radio_found = True
                                break
                                
                elif inputs:
                    text_input = inputs[0]
                    text_input.clear()
                    self.human.fill_text_field(text_input, str(value))
                    logger.info(f"    Filled: '{label_text}' -> '{value[:30]}...'")
                
                elif textareas:
                    textarea = textareas[0]
                    textarea.clear()
                    self.human.fill_text_field(textarea, str(value))
                    logger.info(f"    Filled Textarea: '{label_text}' -> '{value[:30]}...'")
                
                self.human.random_delay(0.5, 1.0)
                
            except Exception as e:
                logger.debug(f"    Could not handle question '{label_text}': {e}")

    def _handle_custom_questions(self):
        """
        Best-effort handler for Lever custom questions:
        - Fills visible textareas with a generic cover sentence
        - Picks the first real option in visible <select> dropdowns
        """
        try:
            # Text questions
            textareas = [
                t for t in self.driver.find_elements(By.CSS_SELECTOR, 'textarea')
                if t.is_displayed() and t.is_enabled()
            ]
            if textareas:
                generic = (
                    "I am excited about this opportunity and believe my background "
                    "in AI/ML makes me a strong fit. I look forward to discussing further."
                )
                logger.info(f"  Handling {len(textareas)} custom textarea(s)")
                for i, ta in enumerate(textareas):
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", ta
                        )
                        time.sleep(0.2)
                        ta.clear()
                        self.human.fill_text_field(ta, generic)
                        logger.info(f"  Filled textarea {i + 1}")
                    except Exception as e:
                        logger.debug(f"  Textarea {i + 1} failed: {e}")

            # Dropdown questions
            selects = [
                s for s in self.driver.find_elements(By.CSS_SELECTOR, 'select')
                if s.is_displayed() and s.is_enabled()
            ]
            if selects:
                from selenium.webdriver.support.ui import Select
                logger.info(f"  Handling {len(selects)} custom dropdown(s)")
                for i, sel_elem in enumerate(selects):
                    try:
                        sel = Select(sel_elem)
                        # Skip the blank placeholder (index 0) and pick index 1
                        if len(sel.options) > 1:
                            sel.select_by_index(1)
                            logger.info(f"  Selected option for dropdown {i + 1}")
                    except Exception as e:
                        logger.debug(f"  Dropdown {i + 1} failed: {e}")

        except Exception as e:
            logger.debug(f"  Custom questions handler error: {e}")

    def _submit_form(self):
        """
        Click the Lever submit button.
        Checks for a thank-you / confirmation page to confirm success.

        Returns:
            bool: True if submission likely succeeded
        """
        submit_selectors_css = [
            'button[type="submit"]',
            'button.postings-btn',
            'button[data-qa="btn-submit"]',
            'input[type="submit"]',
        ]
        submit_selectors_xpath = [
            '//button[contains(normalize-space(.), "Submit application")]',
            '//button[contains(normalize-space(.), "Submit")]',
        ]

        all_selectors = [
            ('css',   s) for s in submit_selectors_css
        ] + [
            ('xpath', s) for s in submit_selectors_xpath
        ]

        for (by_type, selector) in all_selectors:
            by = By.CSS_SELECTOR if by_type == 'css' else By.XPATH
            try:
                elem = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((by, selector))
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", elem
                )
                time.sleep(0.5)
                logger.info("  Clicking submit button...")
                try:
                    elem.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", elem)

                time.sleep(3)

                # Detect confirmation
                page_text = self.driver.page_source.lower()
                current_url = self.driver.current_url.lower()
                for signal in ['thank you', 'application submitted', 'successfully submitted',
                               "we've received", '/confirmation', 'your application']:
                    if signal in page_text or signal in current_url:
                        logger.info(f"  Submission confirmed (signal: '{signal}')")
                        return True

                logger.info("  Submit clicked — treating as success")
                return True

            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                logger.debug(f"  Submit selector '{selector}' error: {e}")
                continue

        logger.warning("  Could not find a Submit button on this page")
        return False

    # ------------------------------------------------------------------ #
    #  Tracking
    # ------------------------------------------------------------------ #

    def _track_application(self, job, status='applied'):
        """Log result to CSV tracker and DuckDB."""
        try:
            from data.db_duckdb import db_duckdb
            job_id = job.get('job_id', 'unknown')
            job_title = job.get('title', 'Unknown')
            job_url = job.get('ats_url', '')
            
            # 1. Update CSV
            company = self._company_from_url(job_url)
            csv_tracker.log_application(
                company=company,
                job_title=job_title[:100],
                job_url=job_url,
                status=status,
                platform='lever',
                notes=f"job_id={job_id}"
            )
            
            # 2. Update DuckDB (for dedup)
            if status in ['applied', 'dry_run']:
                db_duckdb.mark_applied(job_id, 'lever', job_title)
                
            logger.info(f"  Tracked: {status}")
        except Exception as e:
            logger.debug(f"  Tracking failed: {e}")

    @staticmethod
    def _company_from_url(url):
        """
        Extract company name from a jobs.lever.co URL.
        e.g. 'https://jobs.lever.co/dnb/...' => 'dnb'
        """
        try:
            parts = url.split('jobs.lever.co/')
            if len(parts) > 1:
                return parts[1].split('/')[0]
        except Exception:
            pass
        return 'Unknown'
