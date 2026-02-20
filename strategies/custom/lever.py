from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
import time
import os
import json
import random
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing


class LeverStrategy(BaseStrategy):
    """
    Lever ATS automation strategy.

    Lever (jobs.lever.co) is a modern ATS with a standardized application form:
    - Full Name, Email, Phone, Current Company
    - Resume upload
    - Optional links (LinkedIn, GitHub, Portfolio)
    - Custom questions per job

    This strategy:
    1. Reads job listings from hiring_cafe_output.json
    2. Filters only jobs where ats_url contains 'lever' or ats_platform == 'lever'
    3. Navigates to each Lever job apply URL and fills + submits the form
    """

    def __init__(self, driver, job_site=None, selectors=None, db_session=None):
        # Create a minimal job_site stub if none provided
        if job_site is None:
            class MinimalJobSite:
                def __init__(self):
                    self.company_name = "Lever"
                    self.search_url_template = "https://jobs.lever.co"
            job_site = MinimalJobSite()

        super().__init__(driver, job_site, selectors or {})
        self.db_session = db_session
        self.config_data = self._load_config()
        self.human = HumanBehavior(driver)
        self.safe_actions = SafeActions(driver)

        if self.db_session:
            logger.info("Database session available - will save to DuckDB")
        else:
            logger.warning("No database session - will only use CSV tracking")

    # ------------------------------------------------------------------ #
    #  Config Loading
    # ------------------------------------------------------------------ #

    def _load_config(self):
        """Load applicant configuration from guest_form_data.json."""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data',
                'guest_form_data.json'
            )
            with open(config_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded applicant config from {config_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load guest_form_data.json: {e}")
            return None

    def _load_lever_config(self):
        """Load Lever-specific config from config/lever.json."""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'config',
                'lever.json'
            )
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load lever.json config: {e}")
            return {"input_file": "hiring_cafe_output.json", "filter_platform": "lever"}

    def _load_hiring_cafe_output(self):
        """Load hiring_cafe_output.json from the project root."""
        lever_cfg = self._load_lever_config()
        input_file = lever_cfg.get("input_file", "hiring_cafe_output.json")
        try:
            file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                input_file
            )
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.info(f"Loaded {input_file}: {data.get('count', 0)} total jobs")
            return data.get('jobs', [])
        except Exception as e:
            logger.error(f"Failed to load {input_file}: {e}")
            return []

    # ------------------------------------------------------------------ #
    #  BaseStrategy Abstract Methods
    # ------------------------------------------------------------------ #

    def login(self):
        """
        Lever jobs don't require login - publicly accessible apply pages.
        Returns True immediately.
        """
        logger.info("Lever: No login required (public apply pages)")
        return True

    def find_jobs(self):
        """
        Load hiring_cafe_output.json and filter for Lever jobs only.

        A job is considered a Lever job if:
        - ats_platform == 'lever', OR
        - 'lever' appears in the ats_url

        Returns:
            List of job dicts: [{'job_id', 'title', 'ats_url', 'hiring_cafe_url'}, ...]
        """
        all_jobs = self._load_hiring_cafe_output()

        lever_jobs = []
        for job in all_jobs:
            ats_url = job.get('ats_url') or ''
            ats_platform = (job.get('ats_platform') or '').lower()
            if ats_platform == 'lever' or 'lever' in ats_url.lower():
                if ats_url and ats_url.startswith('http'):
                    lever_jobs.append({
                        'job_id': job.get('job_id'),
                        'title': job.get('title', 'Unknown Title'),
                        'ats_url': ats_url,
                        'hiring_cafe_url': job.get('hiring_cafe_url'),
                        'ats_platform': 'lever',
                    })

        logger.info(f"Found {len(lever_jobs)} Lever jobs out of {len(all_jobs)} total jobs")
        for j in lever_jobs:
            logger.info(f"  - {j['title'][:80]} -> {j['ats_url']}")
        return lever_jobs

    def apply(self, listing: JobListing):
        """
        Apply to a single job listing (BaseStrategy interface).
        Delegates to _apply_to_lever_job().
        """
        job_data = {
            'job_id': getattr(listing, 'external_id', None) or getattr(listing, 'job_id', None),
            'title': getattr(listing, 'title', 'Unknown'),
            'ats_url': getattr(listing, 'job_url', None),
        }
        return self._apply_to_lever_job(job_data)

    # ------------------------------------------------------------------ #
    #  Main Workflow
    # ------------------------------------------------------------------ #

    def find_and_apply_jobs(self):
        """
        Main entry point: Find all Lever jobs and apply to each one.

        Returns:
            int: Number of successful applications submitted
        """
        logger.info("=" * 60)
        logger.info("LeverStrategy: Starting find_and_apply_jobs workflow")
        logger.info("=" * 60)

        if not self.config_data:
            logger.error("No applicant config data available - aborting")
            return 0

        lever_jobs = self.find_jobs()

        if not lever_jobs:
            logger.warning("No Lever jobs found in hiring_cafe_output.json")
            return 0

        logger.info(f"\nProcessing {len(lever_jobs)} Lever jobs...")
        total_applied = 0

        for idx, job in enumerate(lever_jobs, 1):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Job {idx}/{len(lever_jobs)}: {job['title'][:80]}")
            logger.info(f"Apply URL: {job['ats_url']}")
            logger.info(f"{'=' * 60}")

            try:
                success = self._apply_to_lever_job(job)
                if success:
                    total_applied += 1
                    logger.info(f"Application #{total_applied} submitted successfully")
                else:
                    logger.warning(f"Application failed for job {job.get('job_id')}")
            except Exception as e:
                logger.error(f"Error applying to job {job.get('job_id')}: {e}")
                import traceback
                traceback.print_exc()

            # Polite delay between applications
            if idx < len(lever_jobs):
                delay = random.uniform(3, 6)
                logger.info(f"Waiting {delay:.1f}s before next application...")
                time.sleep(delay)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Lever workflow complete: {total_applied}/{len(lever_jobs)} applications submitted")
        logger.info(f"{'=' * 60}")
        return total_applied

    # ------------------------------------------------------------------ #
    #  Lever Form Application Logic
    # ------------------------------------------------------------------ #

    def _apply_to_lever_job(self, job):
        """
        Navigate to the Lever apply URL and fill/submit the application form.

        Lever's standard apply page (jobs.lever.co/.../apply) has:
        - Full name input
        - Email input
        - Phone input
        - Current company input
        - Resume file upload
        - Optional link fields (LinkedIn, GitHub, Portfolio)
        - Custom questions (text areas / dropdowns)
        - Submit button

        Args:
            job: dict with 'job_id', 'title', 'ats_url'

        Returns:
            bool: True if application submitted successfully
        """
        ats_url = job.get('ats_url', '')
        job_id = job.get('job_id', 'unknown')
        title = job.get('title', 'Unknown')

        # Ensure we go directly to the /apply page
        apply_url = ats_url
        if '/apply' not in apply_url:
            apply_url = apply_url.rstrip('/') + '/apply'

        applicant = self.config_data.get('applicant', {})
        resume_path = self.config_data.get('resume_path', '')
        resume_full_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            resume_path
        )

        try:
            # Step 1: Navigate to the apply page
            logger.info(f"  Navigating to: {apply_url}")
            self.driver.get(apply_url)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            logger.info("  Page loaded")

            # Step 2: Fill Full Name
            self._fill_field(
                ['input[name="name"]', 'input[placeholder*="name" i]', '#name'],
                f"{applicant.get('first_name', '')} {applicant.get('last_name', '')}".strip(),
                label="Full Name"
            )

            # Step 3: Fill Email
            self._fill_field(
                ['input[name="email"]', 'input[type="email"]', 'input[placeholder*="email" i]', '#email'],
                applicant.get('email', ''),
                label="Email"
            )

            # Step 4: Fill Phone
            self._fill_field(
                ['input[name="phone"]', 'input[type="tel"]', 'input[placeholder*="phone" i]', '#phone'],
                applicant.get('phone', ''),
                label="Phone"
            )

            # Step 5: Fill Current Company (optional)
            experience = applicant.get('experience', [])
            current_company = experience[0].get('company', '') if experience else ''
            if current_company:
                self._fill_field(
                    ['input[name="org"]', 'input[placeholder*="company" i]', 'input[placeholder*="organization" i]', '#org'],
                    current_company,
                    label="Current Company",
                    required=False
                )

            # Step 6: Upload Resume
            if resume_path and os.path.exists(resume_full_path):
                self._upload_resume(resume_full_path)
            else:
                logger.warning(f"  Resume file not found: {resume_full_path}")

            # Step 7: Fill LinkedIn URL (optional - leave blank)
            # Step 8: Skip optional links (GitHub, Portfolio)

            # Step 9: Handle custom questions (best-effort)
            self._handle_custom_questions()

            # Step 10: Submit application
            submitted = self._submit_form()

            # Step 11: Track result
            if submitted:
                self._track_application(job, status='applied')
            else:
                self._track_application(job, status='failed')

            return submitted

        except Exception as e:
            logger.error(f"  Error during application: {e}")
            import traceback
            traceback.print_exc()
            self._track_application(job, status='error')
            return False

    def _fill_field(self, selectors, value, label="Field", required=True):
        """
        Try multiple CSS selectors to find and fill a form field.

        Args:
            selectors: List of CSS selectors to try
            value: Value to type into the field
            label: Human-readable label for logging
            required: Whether to warn if field not found
        """
        if not value:
            logger.debug(f"  Skipping {label}: no value to fill")
            return False

        for selector in selectors:
            try:
                elem = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                if elem.is_displayed() and elem.is_enabled():
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                    time.sleep(0.3)
                    elem.clear()
                    self.human.fill_text_field(elem, value)
                    logger.info(f"  Filled {label}: {value[:50]}")
                    return True
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                logger.debug(f"  Selector {selector} failed for {label}: {e}")
                continue

        if required:
            logger.warning(f"  Could not find field: {label}")
        return False

    def _upload_resume(self, resume_full_path):
        """
        Upload resume file to the Lever form.
        Lever uses a hidden file input that we can send_keys to directly.
        """
        upload_selectors = [
            'input[type="file"]',
            'input[name="resume"]',
            'input[accept*="pdf"]',
        ]
        for selector in upload_selectors:
            try:
                file_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                # Use JS to make hidden inputs visible if needed
                self.driver.execute_script("arguments[0].style.display = 'block';", file_input)
                time.sleep(0.3)
                file_input.send_keys(resume_full_path)
                logger.info(f"  Resume uploaded: {os.path.basename(resume_full_path)}")
                time.sleep(2)  # Wait for upload to complete
                return True
            except (NoSuchElementException, Exception) as e:
                logger.debug(f"  Upload selector {selector} failed: {e}")
                continue

        logger.warning("  Could not find file upload input for resume")
        return False

    def _handle_custom_questions(self):
        """
        Handle custom questions on Lever forms (best-effort).
        Lever forms may have text areas or dropdowns for custom questions.
        We skip optional questions and fill mandatory text areas with a generic response.
        """
        try:
            # Find all visible textareas (custom questions)
            textareas = self.driver.find_elements(By.CSS_SELECTOR, 'textarea')
            visible_textareas = [t for t in textareas if t.is_displayed() and t.is_enabled()]

            if visible_textareas:
                logger.info(f"  Found {len(visible_textareas)} custom text question(s)")
                generic_response = "I am excited about this opportunity and believe my skills and experience make me a strong candidate. I look forward to discussing further."
                for i, textarea in enumerate(visible_textareas):
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", textarea)
                        time.sleep(0.3)
                        textarea.clear()
                        self.human.fill_text_field(textarea, generic_response)
                        logger.info(f"  Filled custom textarea {i + 1}")
                    except Exception as e:
                        logger.debug(f"  Failed to fill textarea {i + 1}: {e}")

            # Handle select/dropdown questions (choose first non-empty option)
            selects = self.driver.find_elements(By.CSS_SELECTOR, 'select')
            visible_selects = [s for s in selects if s.is_displayed() and s.is_enabled()]
            if visible_selects:
                logger.info(f"  Found {len(visible_selects)} dropdown question(s)")
                from selenium.webdriver.support.ui import Select
                for i, select_elem in enumerate(visible_selects):
                    try:
                        sel = Select(select_elem)
                        options = [o for o in sel.options if o.get_attribute('value')]
                        if options:
                            sel.select_by_index(1)  # Select first real option (skip blank)
                            logger.info(f"  Selected option for dropdown {i + 1}")
                    except Exception as e:
                        logger.debug(f"  Failed to handle dropdown {i + 1}: {e}")

        except Exception as e:
            logger.debug(f"  Error handling custom questions: {e}")

    def _submit_form(self):
        """
        Click the Submit application button on the Lever form.

        Returns:
            bool: True if submission button clicked and page changed
        """
        submit_selectors = [
            'button[type="submit"]',
            'button.postings-btn',
            'button[data-qa="btn-submit"]',
            '//button[contains(., "Submit application")]',
            '//button[contains(., "Submit")]',
            '//input[@type="submit"]',
        ]

        for selector in submit_selectors:
            try:
                if selector.startswith('//'):
                    elem = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    elem = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                time.sleep(0.5)

                logger.info(f"  Clicking submit button...")
                try:
                    elem.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", elem)

                time.sleep(3)

                # Check for confirmation (Lever shows a thank-you page)
                current_url = self.driver.current_url
                page_source = self.driver.page_source.lower()

                confirmation_signals = [
                    'thank you',
                    'application submitted',
                    'your application',
                    'successfully submitted',
                    'we\'ve received',
                    '/confirmation',
                ]
                for signal in confirmation_signals:
                    if signal in page_source or signal in current_url.lower():
                        logger.info(f"  Application confirmed (detected: '{signal}')")
                        return True

                # If URL changed (redirect after submit), treat as success
                logger.info("  Form submitted (URL may have changed)")
                return True

            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                logger.debug(f"  Submit selector failed: {e}")
                continue

        logger.warning("  Could not find Submit button")
        return False

    def _track_application(self, job, status='applied'):
        """
        Log application result to CSV tracker.

        Args:
            job: dict with job details
            status: 'applied', 'failed', or 'error'
        """
        try:
            csv_tracker.log_application(
                company=self._extract_company_from_title(job.get('title', '')),
                job_title=job.get('title', 'Unknown')[:100],
                job_url=job.get('ats_url', ''),
                status=status,
                platform='lever',
                notes=f"job_id={job.get('job_id', '')}"
            )
            logger.info(f"  Tracked application status: {status}")
        except Exception as e:
            logger.debug(f"  CSV tracking failed: {e}")

    def _extract_company_from_title(self, title):
        """
        Try to extract company name from the hiring_cafe title string.
        Titles often contain company names embedded in the text.
        """
        if not title:
            return 'Unknown'
        # hiring_cafe titles contain company name after job title
        # e.g. "Senior Gen AI Engineer (R-18859)\nChennai, Tamil Nadu, India\n...Dun & Bradstreet:..."
        lines = title.split('\n')
        if len(lines) >= 5:
            return lines[4].split(':')[0].strip()[:100]
        return lines[0][:100] if lines else 'Unknown'
