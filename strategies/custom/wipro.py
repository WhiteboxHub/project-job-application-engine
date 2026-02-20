from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.captcha_handler import CaptchaHandler
from core.safe_actions import SafeActions
import time
import os
import json
import random
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from data.csv_tracker import tracker as csv_tracker
from models.config_models import JobListing
from models.history_models import Application


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
    
    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors)
        self.db_session = db_session
        self.job_site = job_site
        self.config_data = self._load_config()
        self.human = HumanBehavior(driver)
        self.captcha_handler = CaptchaHandler(driver, timeout=120)
        self.safe_actions = SafeActions(driver)
        
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
        """Helper to save a screenshot with a standardized name"""
        filename = name if name.endswith(".png") else f"{name}.png"
        try:
            self.driver.save_screenshot(filename)
            logger.info(f"  [DEBUG] Saved screenshot: {filename}")
        except Exception as e:
            logger.debug(f"Failed to save screenshot {filename}: {e}")
    
    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'data',
                'guest_form_data.json'
            )
            with open(config_path, 'r') as f:
                data = json.load(f)
            logger.info(f"Loaded configuration from {config_path}")
            return data
        except Exception as e:
            logger.error(f"Failed to load config JSON: {e}")
            return None
    
    # _load_selectors method removed - selectors are now loaded from database

    
    def login(self):
        """
        Check if login is required for Wipro portal.
        Most career portals allow guest applications.
        """
        logger.info("Wipro: Checking login requirements...")
        
        try:
            # Navigate to portal
            logger.info(f"Opening Wipro careers portal: {self.portal_url}")
            self.driver.get(self.portal_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
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
        search = self.config_data.get('search', {})
        keyword = search.get('keyword', 'AI Engineer')
        location = search.get('location', '')
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[SEARCH] Searching Wipro Jobs: '{keyword}' in '{location}'")
        logger.info(f"{'='*60}")
        
        all_jobs = []
        seen_urls = set()
        
        try:
            # Navigate to portal
            self.driver.get(self.portal_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
            # Fill search form
            try:
                # Enter keyword
                keyword_selectors = self.selectors_config['keyword_input'].split(', ')
                keyword_input = None
                
                for selector in keyword_selectors:
                    try:
                        keyword_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except:
                        continue
                
                if keyword_input:
                    keyword_input.clear()
                    self.human.fill_text_field(keyword_input, keyword)
                    logger.info(f"  [+] Entered keyword: {keyword}")
                else:
                    logger.warning("  [!] Could not find keyword input field")
                
                # Enter location (if provided)
                if location:
                    location_selectors = self.selectors_config['location_input'].split(', ')
                    location_input = None
                    
                    for selector in location_selectors:
                        try:
                            location_input = self.driver.find_element(By.CSS_SELECTOR, selector)
                            break
                        except:
                            continue
                    
                    if location_input:
                        location_input.clear()
                        self.human.fill_text_field(location_input, location)
                        logger.info(f"  [+] Entered location: {location}")
                
                # Click search button
                search_btn_selectors = self.selectors_config['search_button'].split(', ')
                search_btn = None
                
                for selector in search_btn_selectors:
                    try:
                        search_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except:
                        continue
                
                if search_btn:
                    try:
                        search_btn.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", search_btn)
                    logger.info("  [+] Clicked search button")
                    time.sleep(6)  # Wait for results to load
                
            except Exception as e:
                logger.error(f"Error filling search form: {e}")
                return []
            
            # Extract job listings (with pagination support)
            page_num = 1
            MAX_PAGES = 20
            
            while page_num <= MAX_PAGES:
                logger.info(f"\n[PAGE] Processing page {page_num}...")
                
                # Find all job containers
                # Find all job containers on current page
                job_containers = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    self.selectors_config['job_container'].split(',')[0].strip()
                )
                
                if not job_containers:
                    logger.warning(f"  No job containers found on page {page_num}")
                    # Debug: Save screenshot and page source
                    try:
                        self.save_screenshot("debug_wipro_no_jobs")
                        with open("debug_wipro_source.html", "w", encoding="utf-8") as f:
                            f.write(self.driver.page_source)
                        logger.info("  [INFO] Saved debug_wipro_no_jobs.png and debug_wipro_source.html")
                    except Exception as e:
                        logger.error(f"  Failed to save debug info: {e}")
                    break
                    
                logger.info(f"  Found {len(job_containers)} jobs on page {page_num}")
                
                # Extract job details
                # Extract job details from each container
                for idx, job_elem in enumerate(job_containers):
                    try:
                        # Get job title from anchor element
                        title_elem = self._find_element_within_parent(
                            job_elem, self.selectors_config['job_title']
                        )
                        title = title_elem.text.strip() if title_elem else None
                        
                        # Get job URL (same element as title, it's an anchor)
                        link_elem = self._find_element_within_parent(
                            job_elem, self.selectors_config['job_link']
                        )
                        job_url = link_elem.get_attribute('href') if link_elem else None
                        
                        # Build full URL if it's relative
                        if job_url and job_url.startswith('/'):
                            # Wipro URLs are relative: /job/TITLE/ID-en_US
                            base_url = self.portal_url.split('/careers-home')[0]
                            job_url = base_url + job_url
                        
                        # Get job ID from first footer value span
                        job_id = None
                        id_elem = self._find_element_within_parent(
                            job_elem, self.selectors_config['job_id']
                        )
                        job_id = id_elem.text.strip() if id_elem else None
                        
                        # Fallback: extract ID from URL if footer value not found
                        if not job_id and job_url:
                            # URL format: /job/TITLE/125816-en_US
                            try:
                                url_parts = job_url.split('/')
                                id_part = url_parts[-1]  # "125816-en_US"
                                job_id = id_part.split('-')[0]  # "125816"
                            except:
                                job_id = str(hash(job_url))[:8]
                        
                        if title and job_url and job_id:
                            if job_url in seen_urls:
                                continue
                            
                            seen_urls.add(job_url)
                            job_data = {
                                'job_title': title,
                                'external_id': job_id,
                                'job_url': job_url
                            }
                            all_jobs.append(job_data)
                            logger.info(f"  [+] [{idx+1}] {title} (ID: {job_id})")
                            
                            # Save to database and CSV
                            csv_tracker.add_discovered_jobs('wipro', [job_data])
                            
                            if self.db_session and self.job_site:
                                self._save_job_to_db(job_data)
                        
                    except Exception as e:
                        logger.debug(f"  Error extracting job: {e}")
                        continue
                
                # Try to go to next page
                try:
                    next_btn = self._find_element_by_selectors(
                        self.selectors_config['next_page'],
                        timeout=3
                    )
                    
                    if next_btn and next_btn.is_displayed() and next_btn.is_enabled():
                        self.human.human_click(next_btn)
                        logger.info(f"  > Navigating to page {page_num + 1}...")
                        time.sleep(3)  # Wait for new results to load
                        page_num += 1
                    else:
                        logger.info("  - No more pages")
                        break
                        
                except Exception:
                    logger.info("  - Pagination complete")
                    break
            
            logger.info(f"\n{'='*60}")
            logger.info(f"[OK] Job Discovery Complete: {len(all_jobs)} jobs found")
            logger.info(f"{'='*60}\n")
            
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
        from engine.guards import guards
        from config.settings import settings
        from types import SimpleNamespace
        
        # Normalize listing to handle both JobListing object and dictionary
        if isinstance(listing, dict):
            listing = SimpleNamespace(**listing)
        
        # Check if we can apply
        if not guards.can_apply():
            logger.info("Application limit reached - stopping")
            return False
        
        # Check if already applied
        try:
            status = csv_tracker.get_job_status('wipro', listing.job_url)
            if status and status.get('status') == 'applied':
                logger.info(f"Already applied to this job, skipping: {listing.job_url}")
                return False
        except Exception:
            pass
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[APPLY] Applying to: {listing.job_title}")
        logger.info(f"URL: {listing.job_url}")
        logger.info(f"{'='*60}")
        
        try:
            # Navigate to job posting
            self.driver.get(listing.job_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
            # Click Apply button (TWO-STEP PROCESS for Wipro)
            # Step 1: Click the dropdown button to open menu
            apply_dropdown_btn = self._find_element_by_selectors(
                self.selectors_config['apply_button_dropdown'],
                wait_for_visible=True
            )
            
            if not apply_dropdown_btn:
                logger.error("Could not find Apply dropdown button")
                csv_tracker.update_job_status('wipro', listing.job_url, 'failed',
                                            attempts_inc=1, last_error='No Apply dropdown button')
                return False
            
            self.human.human_click(apply_dropdown_btn)
            logger.info("  [+] Clicked Apply dropdown button")
            time.sleep(1.5)  # Wait for dropdown menu to appear
            
            # Step 2: Click "Apply Now" menu item in dropdown
            apply_menu_item = self._find_element_by_selectors(
                self.selectors_config['apply_button_menu_item'],
                wait_for_visible=True,
                timeout=5
            )
            
            if not apply_menu_item:
                logger.error("Could not find Apply Now menu item in dropdown")
                csv_tracker.update_job_status('wipro', listing.job_url, 'failed',
                                            attempts_inc=1, last_error='No Apply Now menu item')
                return False
            
            self.human.human_click(apply_menu_item)
            logger.info("  [+] Clicked Apply Now menu item")
            time.sleep(3)  # Wait for page to load
            
            # Handle login page if it appears
            try:
                logger.info("Checking for login page...")
                login_email = self._find_element_by_selectors(
                    self.selectors_config['login_email_input'],
                    timeout=5
                )
                
                if login_email:
                    logger.info("Login page detected - signing in...")
                    
                    # Get credentials from config
                    wipro_creds = self.config_data.get('wipro_credentials', {})
                    email = wipro_creds.get('email', '')
                    password = wipro_creds.get('password', '')
                    
                    if not email or not password:
                        logger.error("Wipro credentials not found in config! Please add 'wipro_credentials' with 'email' and 'password'")
                        csv_tracker.update_job_status('wipro', listing.job_url, 'failed',
                                                    attempts_inc=1, last_error='Missing Wipro credentials')
                        return False
                    
                    # Fill email
                    self.human.fill_text_field(login_email, email)
                    logger.info(f"  [+] Filled email: {email}")
                    time.sleep(1)
                    
                    # Fill password
                    login_password = self._find_element_by_selectors(
                        self.selectors_config['login_password_input']
                    )
                    if login_password:
                        self.human.fill_text_field(login_password, password)
                        logger.info("  [+] Filled password")
                        time.sleep(1)
                    
                    # Click Sign In button
                    sign_in_btn = self._find_element_by_selectors(
                        self.selectors_config['login_submit_button'],
                        wait_for_visible=True
                    )
                    if sign_in_btn:
                        self.human.human_click(sign_in_btn)
                        logger.info("  [+] Clicked Sign In button")
                        time.sleep(8)  # Increased wait for login to complete and form to load
                        
                        # Check for "Already Applied" message right after login
                        if self._check_already_applied(listing.job_url):
                            return False
                        
                        # Wait for form sections to appear
                        logger.info("Waiting for application form sections to render...")
                        try:
                            WebDriverWait(self.driver, 20).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, ".rcmFormSection, .rcmFormSectionTopBar"))
                            )
                            logger.info("[OK] Form sections detected")
                        except Exception as e:
                            logger.warning(f"Timeout waiting for form sections: {e}")
                    else:
                        logger.error("Could not find Sign In button")
                        csv_tracker.update_job_status('wipro', listing.job_url, 'failed',
                                                    attempts_inc=1, last_error='No Sign In button')
                        return False
                else:
                    logger.info("No login page detected - proceeding to application form")
                    
            except Exception as e:
                logger.warning(f"Login page check failed (may be already logged in): {e}")
            
            # Click "Expand all sections" if present
            try:
                expand_btn = self._find_element_by_selectors(
                    self.selectors_config['expand_all_sections'],
                    timeout=10
                )
                if expand_btn:
                    btn_text = expand_btn.text.lower()
                    if 'collapse' in btn_text:
                        logger.info("Sections already expanded ('Collapse' text detected) - skipping expand all click")
                    else:
                        logger.info("Found 'Expand all sections' button - clicking...")
                        self.human.human_click(expand_btn)
                        time.sleep(2)
            except Exception:
                pass

            # DEBUG: Save page source after expansion
            try:
                with open("debug_application_form.html", "w", encoding="utf-8") as f:
                    f.write(self.driver.page_source)
                logger.info("  [DEBUG] Saved application form source to debug_application_form.html")
            except Exception as e:
                logger.warning(f"  [DEBUG] Failed to save page source: {e}")

            # Debug: List sections found
            try:
                section_headers = self.driver.find_elements(By.CSS_SELECTOR, ".rcmFormSectionTopBar span, .rcmFormSection h2, .rcmFormSection h3, .rcmFormSection h4, span.rcmFormSectionTopBar")
                logger.info(f"  [DEBUG] Found {len(section_headers)} section headers:")
                for header in section_headers:
                    h_text = header.text.strip()
                    if h_text:
                        h_tag = header.tag_name
                        h_class = header.get_attribute('class')
                        logger.info(f"    - '{h_text}' (Tag: {h_tag}, Class: {h_class})")
            except:
                pass
                
            # Fill application form
            applicant = self.config_data.get('applicant', {})
            search_config = self.config_data.get('search', {})
            
            # --- Form Initialization (Resume Upload First) ---
            # We upload the resume first because it often triggers a form reset or page refresh.
            resume_path = self.config_data.get('resume_path', '')
            if resume_path:
                success = self._upload_resume(resume_path)
                if not success:
                    logger.warning("[WARNING] Resume upload may have failed, but continuing...")
                else:
                    logger.info("  [+] Resume uploaded successfully at start of process")
                    time.sleep(2) # Stabilize after upload

            # --- Profile Information Section ---
            # 1. First Name (Mandatory)
            self._fill_field('first_name_input', applicant.get('first_name', ''))
            
            # 2. Last Name (Mandatory)
            self._fill_field('last_name_input', applicant.get('last_name', ''))
            
            # 3. Email (Mandatory)
            self._fill_field('email_input', applicant.get('email', ''))
            
            # 4. Phone (Mandatory)
            self._fill_field('phone_input', applicant.get('phone', ''))
            
            # 4a. Preferred Name and Social URL (Optional)
            self._fill_field('preferred_name_input', applicant.get('preferred_name', ''))
            self._fill_field('social_account_url_input', applicant.get('social_account_url', ''))
            
            # 4b. Country Code (Dropdown)
            country_code = applicant.get('countrycode', '')
            self._handle_dropdown('country_code_select', country_code)
            
            # 4b. Gender (Dropdown)
            gender = applicant.get('gender', '')
            self._handle_dropdown('gender_select', gender)
            
            # 4c. Disability Assistance (Optional)
            disability_assist = applicant.get('disability_assistance', 'No')
            self._handle_dropdown('disability_assistance_select', disability_assist)
            if disability_assist.lower() == 'yes':
                self._fill_field('disability_assistance_explain_input', applicant.get('disability_assistance_explain', ''))

            # --- Dropdowns FIRST to avoid AJAX resetting inputs ---
            # 8. Country (Mandatory - Dropdown)
            country = applicant.get('country', '')
            self._handle_dropdown('country_select', country)
            
            # 9. State (Mandatory - Dropdown)
            state = applicant.get('state', '')
            self._handle_dropdown('state_select', state)

            # 10. Employment Question (Mandatory)
            employed_before = applicant.get('employed_before_wipro', '')
            self._handle_dropdown('employed_before_select', employed_before)

            # --- Inputs AFTER Dropdowns ---
            # 5. Address (Mandatory)
            address = applicant.get('address', '')
            self._fill_field('address_input', address)
            
            # 6. City (Mandatory)
            city = applicant.get('city', '')
            self._fill_field('city_input', city)
            
            # 7. Postal Code (Mandatory)
            zip_code = applicant.get('zip_code', '')
            self._fill_field('zip_input', zip_code)
            
            # Employee ID Logic
            emp_id = applicant.get('wipro_employee_id', '')
            self._fill_field('employee_id_input', emp_id if emp_id else 'NA')

            
            # --- Professional Experience Section ---
            self._ensure_section_expanded('experience_section_trigger')
            
            # Remove any auto-populated experience rows from resume parsing
            self._remove_extra_experience_rows()
            
            try:
                # Fill latest experience if available
                experience = applicant.get('experience', [])
                if experience:
                    latest_job = experience[0]
                    
                    # Fill Title
                    self._fill_field('job_title_input', latest_job.get('title', ''))
                    
                    # Fill Company
                    self._fill_field('company_input', latest_job.get('company', ''))
                    
                    # Fill Dates
                    self._fill_field('start_date_input', latest_job.get('start_date', ''))
                    self._fill_field('end_date_input', latest_job.get('end_date', ''))
                    
                    # Fill Country/Region for Experience
                    exp_country = latest_job.get('country', '')
                    self._handle_dropdown('exp_country_select', exp_country)
                    
                    # Fill State for Experience
                    exp_state = latest_job.get('state', '')
                    self._handle_dropdown('exp_state_select', exp_state)

                    # Fill City for Experience
                    exp_city = latest_job.get('city', '')
                    self._fill_field('exp_city_input', exp_city)
                    
                    # Debug screenshot
                    self.save_screenshot("debug_exp_section")
                    
                    logger.info("  [+] Filled Professional Experience section")
            except Exception as e:
                logger.warning(f"Failed to fill experience section: {e}")
            
            # --- Education Section ---
            self._ensure_section_expanded('education_section_trigger')
            try:
                education = applicant.get('education', [])
                if education:
                    latest_edu = education[0]
                    
                    # Fill Education Type
                    edu_type = latest_edu.get('education_type', '')
                    self._handle_dropdown('edu_type_select', edu_type)

                    # Fill Degree
                    degree = latest_edu.get('degree', '')
                    self._handle_dropdown('edu_degree_select', degree)
                    
                    # Fill School/University
                    # Using case-insensitive get to support both 'school' and 'university' from JSON
                    school_val = latest_edu.get('university') or latest_edu.get('school', '')
                    self._fill_field('edu_school_input', school_val)
                    
                    # Fill Major (if present in selectors)
                    major = latest_edu.get('major', '')
                    if major:
                        self._handle_dropdown('edu_major_select', major)
                    
                    # Fill Dates
                    self._fill_field('edu_start_date', latest_edu.get('start_date', ''))
                    self._fill_field('edu_end_date', latest_edu.get('end_date', ''))
                    
                    # Fill Year of Passing
                    grad_date = latest_edu.get('year_of_passing', '')
                    self._fill_field('edu_grad_date', grad_date)
                    
                    # Fill Country/Region for Education
                    edu_country = latest_edu.get('country', '')
                    self._handle_dropdown('edu_country_select', edu_country)
                    
                    # Fill State for Education
                    edu_state = latest_edu.get('state', '')
                    self._handle_dropdown('edu_state_select', edu_state)

                    # Fill City for Education
                    edu_city = latest_edu.get('city', '')
                    self._fill_field('edu_city_input', edu_city)
                    
                    # Debug screenshot (moved to end of section)
                    self.save_screenshot("debug_edu_section")
                    
                    logger.info("  [+] Filled Education section")
            except Exception as e:
                logger.warning(f"Failed to fill education section: {e}")
            
            # --- Job Specific Information & Voluntary Self-ID ---
            try:
                # Work Authorization
                auth_val = applicant.get('auth_country_select', '')
                self._handle_dropdown('auth_country_select', auth_val)
                
                auth_work_country = applicant.get('auth_work_country', '')
                self._handle_dropdown('auth_work_country_select', auth_work_country)
                
                visa_status = applicant.get('visa_status', '')
                self._handle_dropdown('visa_status_select', visa_status)
                
                sponsorship = applicant.get('sponsorship_future', '')
                self._handle_dropdown('sponsorship_future_select', sponsorship)
                
                citizenship = applicant.get('citizenship', '')
                self._handle_dropdown('citizenship_select', citizenship)
                
                govt_employed = applicant.get('govt_employed', '')
                self._handle_dropdown('govt_employed_select', govt_employed)
                
                # Compliance / Self-ID
                race = applicant.get('race', '')
                self._handle_dropdown('race_select', race)
                
                veteran = applicant.get('veteran', '')
                self._handle_dropdown('veteran_select', veteran)
                
                disability = applicant.get('disability', '')
                self._handle_dropdown('disability_select', disability)
                
                logger.info("  [+] Filled Job Specific & Compliance sections")
            except Exception as e:
                logger.warning(f"Failed to fill job specific section: {e}")
            
            # Check for terms/consent checkbox
            try:
                terms_checkbox = self._find_element_by_selectors(
                    self.selectors_config['terms_checkbox'].split(', ')
                )
                if terms_checkbox and not terms_checkbox.is_selected():
                    self.human.human_click(terms_checkbox)
                    logger.info("  [+] Accepted terms and conditions")
            except Exception:
                logger.debug("No terms checkbox found (optional)")
            
            # Check for reCAPTCHA
            if self.captcha_handler.detect_recaptcha():
                logger.warning("[WARNING] reCAPTCHA detected - waiting for manual solve...")
                self.captcha_handler.wait_for_manual_solve()
            
            # Save application (Disabled as it may clear fields)
            # try:
            #     save_btn = self._find_element_by_selectors(
            #         self.selectors_config['save_draft_button'].split(', ')
            #     )
            #     if save_btn:
            #         self.human.human_click(save_btn)
            #         logger.info("  [+] Saved application draft")
            #         time.sleep(10) # Wait for save
            # except Exception as e:
            #     logger.debug(f"Save draft failed (optional): {e}")
            
            # Perform validation before potential submission (helpful for dry runs too)
            validation_passed = self._validate_form()
            
            # Submit application (skip if dry-run mode)
            if settings.DRY_RUN:
                logger.info(f"[SEARCH] DRY RUN MODE - Skipping submission. Validation Passed: {validation_passed}")
                csv_tracker.update_job_status('wipro', listing.job_url, 'skipped (dry-run)')
                return validation_passed
            
            if not validation_passed:
                logger.error("[VALIDATION] Form has errors before submission. Aborting.")
                return False
            
            # Find and click submit button
            submit_btn = self._find_element_by_selectors(
                self.selectors_config['submit_button'].split(', ')
            )
            
            
            if submit_btn:
                self.human.human_click(submit_btn)
                logger.info("  [+] Clicked Submit button")
                
                logger.info("  [*] Waiting 15s for submission results / validation errors...")
                time.sleep(15)
                
                # Validate form AFTER submitting (errors appear now)
                if not self._validate_form():
                    logger.error("[VALIDATION] Submission failed - validation errors detected")
                    csv_tracker.update_job_status('wipro', listing.job_url, 'failed',
                                                attempts_inc=1, last_error='Validation failed after submit')
                    return False
                
                # Check for success message explicitly
                if self._check_submission_success():
                    # Mark as applied
                    csv_tracker.update_job_status('wipro', listing.job_url, 'applied')
                    logger.info("  [SUCCESS] Application submitted successfully!")
                    return True
                else:
                    logger.error("  [!] Submitted but could not confirm success message 'Your application has been sent'")
                    # Take screenshot for debugging missing success message
                    self.save_screenshot("failed_success_message")
                    csv_tracker.update_job_status('wipro', listing.job_url, 'failed',
                                                attempts_inc=1, last_error='Submitted but no confirmation message')
                    return False
            else:
                logger.error("Could not find Submit button")
                csv_tracker.update_job_status('wipro', listing.job_url, 'failed',
                                            attempts_inc=1, last_error='No Submit button')
                return False
            
        except Exception as e:
            logger.error(f"Application failed: {e}")
            self.save_screenshot("application_error")
            return False
    def _check_already_applied(self, listing_url):
        """Check for the 'You already applied for this position' message."""
        try:
            from data.csv_tracker import tracker as csv_tracker
            # Check for the specific SuccessFactors error message container
            exception_msg = self.driver.find_elements(By.CSS_SELECTOR, ".rcmJobApplyExceptionMsg")
            if exception_msg:
                msg_text = exception_msg[0].text.strip()
                if "already applied" in msg_text.lower():
                    logger.info(f"  [!] Detected 'Already Applied' message: {msg_text}")
                    # Update tracker so we don't try this job again
                    csv_tracker.update_job_status('wipro', listing_url, 'applied')
                    return True
        except Exception as e:
            logger.debug(f"Error checking 'already applied' message: {e}")
        return False


    def _check_submission_success(self):
        """Checks if the application success message is present on the page."""
        try:
            logger.info("  [*] Checking for submission success message...")
            success_msg_selectors = [
                "#applyConfirmMsg",
                "//div[@id='applyConfirmMsg'][contains(text(), 'Your application has been sent')]",
                "#rcmJobApplicationCtr",
                ".msgContent"
            ]
            success_element = self._find_element_by_selectors(success_msg_selectors, timeout=10)
            if success_element:
                text = success_element.text.strip()
                if "Your application has been sent" in text:
                    logger.info(f"  [SUCCESS] Confirmation message found: '{text[:60]}...'")
                    return True
                
            # Final fallback check for the entire container text
            container = self.driver.find_elements(By.ID, "rcmJobApplicationCtr")
            if container and "Your application has been sent" in container[0].text:
                logger.info("  [SUCCESS] Confirmation found in container text.")
                return True
                
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
            section_headers = self.driver.find_elements(By.CSS_SELECTOR, ".rcmFormSectionTopBar")
            
            has_errors = False
            for header in section_headers:
                try:
                    # check for text to identify section
                    section_name = header.text.strip().split('\n')[0] 
                    
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
                            logger.warning(f"  [!] Validation Error in section: '{section_name}'")
                            has_errors = True
                except Exception as e:
                    continue
            
            # Also check for any global error messages or standard required field errors
            # Common pattern: .fieldError, .error, etc.
            visible_field_errors = self.driver.find_elements(By.CSS_SELECTOR, ".fieldError, .errorContent, .validatorStatusError")
            visible_field_errors = [e for e in visible_field_errors if e.is_displayed()]
            
            if visible_field_errors:
                logger.warning(f"  [!] Found {len(visible_field_errors)} visible field errors")
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
            logger.info("  [*] Checking for auto-populated experience rows to remove...")
            
            # Find all remove buttons in the Professional Experience section
            # Based on HTML: div[role="button"][title="Delete Row"] with class "iconHolder"
            remove_buttons = self.driver.find_elements(
                By.CSS_SELECTOR, 
                'div[role="button"][title="Delete Row"] .delete_icon'
            )
            
            if remove_buttons:
                logger.info(f"  [*] Found {len(remove_buttons)} experience row(s) to remove")
                
                # Click each remove button (iterate in reverse to avoid stale elements)
                for i in range(len(remove_buttons) - 1, -1, -1):
                    try:
                        # Re-find buttons each iteration to avoid stale element issues
                        current_buttons = self.driver.find_elements(
                            By.CSS_SELECTOR, 
                            'div[role="button"][title="Delete Row"]'
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
            if selector_key == 'edu_start_date' and ('ui5-date-picker' in str(selector) or not selector):
                selector = "//div[contains(@class, 'rcmFormSection')][.//*[contains(text(), 'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='Start Date']"
            elif selector_key == 'edu_end_date' and ('ui5-date-picker' in str(selector) or not selector):
                selector = "//div[contains(@class, 'rcmFormSection')][.//*[contains(text(), 'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='End Date']"
            elif selector_key == 'edu_grad_date' and ('ui5-date-picker' in str(selector) or not selector):
                selector = "//div[contains(@class, 'rcmFormSection')][.//*[contains(text(), 'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='Year Of Passing']"
            
            field = self._find_element_by_selectors(
                selector,
                timeout=5,
                wait_for_visible=True
            )
            if field:
                # Check current value to see if it already matches target
                current_val = field.get_attribute('value') or ""
                if current_val.strip().lower() == str(value).strip().lower():
                    logger.info(f"  [+] Field {selector_key} already has correct value, skipping...")
                    return True

                # Handle ui5-date-picker widgets and date fields specially
                is_date_field = field.tag_name == 'ui5-date-picker-xweb-calendar-widget' or \
                              '_date' in selector_key.lower() or \
                              'date_input' in selector_key.lower() or \
                              'grad_date' in selector_key.lower()
                
                if is_date_field:
                    logger.debug(f"  [>] Special handling for date field {selector_key} (tag: {field.tag_name})")
                    # More robust event sequence for UI5/SuccessFactors
                    # Specifically for ui5-date-picker, we must ensure the 'value' property is set and 'change' is fired on the widget
                    self.driver.execute_script("""
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
                    """, field, value)
                elif 'city' in selector_key.lower() or 'VFLD' in str(field.get_attribute('name')):
                    logger.debug(f"  [>] Special handling for autocomplete/text field {selector_key}")
                    self.human.fill_text_field(field, value)
                    self.driver.execute_script("""
                        var element = arguments[0];
                        element.dispatchEvent(new Event('input', { bubbles: true }));
                        element.dispatchEvent(new Event('change', { bubbles: true }));
                        element.dispatchEvent(new Event('blur', { bubbles: true }));
                    """, field)
                else:
                    self.human.fill_text_field(field, value)
                
                logger.info(f"  [+] Filled {selector_key}")
                HumanBehavior.random_delay(0.2, 0.5)
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
                wait_for_visible=True
            )
            
            if not input_element:
                return False
                
            logger.info(f"  [*] Attempting to select '{value}' for {selector_key}")
            
            # Scroll and click to open dropdown
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_element)
            time.sleep(0.5)
            
            try:
                # Check current value before clicking
                current_val = input_element.get_attribute('value') or ""
                if current_val.strip().lower() == str(value).strip().lower():
                    logger.info(f"  [+] Dropdown {selector_key} already has correct value, skipping...")
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
            time.sleep(2.5) # Wait for results to filter
            
            # SuccessFactors often uses a list box that appears
            # 1. Try to find the exact option with multiple selectors
            option_selectors = [
                f"li[role='option']:contains('{value}')",
                f"div.sapMListBoxItem:contains('{value}')",
                f"//li[@role='option'][contains(text(), '{value}')]",
                f"//div[contains(@class, 'sapMListBoxItem')][contains(text(), '{value}')]"
            ]
            
            matching_option = self._find_element_by_selectors(option_selectors, timeout=3)
            
            if matching_option:
                try:
                    self.human.human_click(matching_option)
                    logger.info(f"  [+] Selected option: {value} (exact match)")
                    time.sleep(1)
                    return True
                except:
                    self.driver.execute_script("arguments[0].click();", matching_option)
                    return True

            # 2. Fallback: Find ALL options and filter in Python (case-insensitive)
            logger.info(f"  [!] Exact match not found, searching all options for '{value}'...")
            all_options = self.driver.find_elements(By.CSS_SELECTOR, "li[role='option'], div.sapMListBoxItem, span.sapMText")
            
            # Step 2a: Strict case-insensitive equality
            for opt in all_options:
                try:
                    opt_text = opt.text.strip()
                    if value.lower() == opt_text.lower():
                        logger.info(f"  [+] Found exact case-insensitive match: '{opt_text}'")
                        self.human.human_click(opt)
                        time.sleep(1)
                        return True
                except:
                    continue
                    
            # Step 2b: Partial match with guards
            for opt in all_options:
                try:
                    opt_text = opt.text.strip()
                    if value.lower() in opt_text.lower() or opt_text.lower() in value.lower():
                        # Guard: 'Male' should not match 'Female'
                        if value.lower() == 'male' and 'female' in opt_text.lower():
                            continue
                        logger.info(f"  [+] Found partial match: '{opt_text}'")
                        self.human.human_click(opt)
                        time.sleep(1)
                        return True
                except:
                    continue

            # 3. Final Fallback: Arrow Down + Enter
            logger.info(f"  [+] Using keyboard fallback (ARROW_DOWN + ENTER) for {selector_key}")
            input_element.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.5)
            input_element.send_keys(Keys.ENTER)
            time.sleep(1.5)
            return True
                
        except Exception as e:
            logger.warning(f"Failed to handle dropdown {selector_key}: {e}")
            
        return False

    def _ensure_section_expanded(self, selector_key):
        """Verify if a section is expanded (via aria-expanded) and click header if closed."""
        try:
            trigger = self._find_element_by_selectors(
                self.selectors_config.get(selector_key),
                timeout=5,
                wait_for_visible=True
            )
            
            if trigger:
                # SuccessFactors often puts aria-expanded on the button OR a parent/child
                expanded = trigger.get_attribute('aria-expanded')
                
                # If we can't find aria-expanded, check if it's on a child span or parent button
                if expanded is None:
                    try:
                        parent = trigger.find_element(By.XPATH, "./..")
                        expanded = parent.get_attribute('aria-expanded')
                    except:
                        pass
                
                if expanded == 'false':
                    logger.info(f"  [*] Section {selector_key} is collapsed (aria-expanded=false) - Expanding...")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
                    time.sleep(0.5)
                    self.human.human_click(trigger)
                    time.sleep(2)
                else:
                    logger.info(f"  [OK] Section {selector_key} already expanded or state unknown (aria-expanded={expanded})")
                    
        except Exception as e:
            logger.warning(f"Failed to ensure section {selector_key} is expanded: {e}")

    def _find_element_by_selectors(self, selectors, timeout=10, wait_for_visible=False):
        """
        Try multiple selectors to find an element with XPath/CSS auto-detection.
        
        Args:
            selectors: String of comma-separated selectors or list of selectors
            timeout: Max wait time per selector in seconds (default: 10)
            wait_for_visible: If True, wait for element to be visible (default: False)
        
        Returns:
            WebElement or None
        """
        # Convert string to list if needed
        if isinstance(selectors, str):
            # If it's a single XPath starting with // or (, don't split by commas
            if selectors.startswith('//') or selectors.startswith('(//'):
                selector_list = [selectors]
            else:
                selector_list = [s.strip() for s in selectors.split(',')]
        else:
            selector_list = selectors if isinstance(selectors, list) else [selectors]
        
        for selector in selector_list:
            if not selector:  # Skip empty selectors
                continue
            
            try:
                # Auto-detect XPath vs CSS
                if selector.startswith('//') or selector.startswith('(//'):
                    by_type = By.XPATH
                else:
                    by_type = By.CSS_SELECTOR
                
                # Choose wait condition based on visibility requirement
                if wait_for_visible:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.visibility_of_element_located((by_type, selector))
                    )
                else:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((by_type, selector))
                    )
                
                logger.debug(f"Found element with selector: {selector} (type: {by_type})")
                return element
                
            except Exception as e:
                logger.debug(f"Selector failed: {selector} - {type(e).__name__}")
                continue
        
        logger.warning(f"No element found with any of the selectors: {selector_list[:3]}...")
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
            if selectors.startswith('//') or selectors.startswith('(//'):
                selector_list = [selectors]
            else:
                selector_list = [s.strip() for s in selectors.split(',')]
        else:
            selector_list = selectors if isinstance(selectors, list) else [selectors]
        
        for selector in selector_list:
            if not selector:
                continue
            
            try:
                # Auto-detect XPath vs CSS
                if selector.startswith('//') or selector.startswith('(//'):
                    by_type = By.XPATH
                    # For XPath within parent, need to add ./ prefix
                    if not selector.startswith('.'):
                        selector = '.' + selector
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
                project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
                resume_path = os.path.join(project_root, resume_path)
            
            if not os.path.exists(resume_path):
                logger.error(f" Resume file not found: {resume_path}")
                return False
                
            logger.info(f" Uploading resume from: {resume_path}")
            
            # 1. Check for file input directly first
            file_input = self._find_element_by_selectors(
                self.selectors_config.get('resume_upload_input'),
                timeout=2
            )
            
            # 2. If not found, click the trigger button
            if not file_input:
                logger.info("  File input not found immediately - checking for trigger button...")
                trigger = self._find_element_by_selectors(
                    self.selectors_config.get('resume_upload_trigger'),
                    timeout=3,
                    wait_for_visible=True
                )
                
                if trigger:
                    logger.info("   Found resume upload trigger - clicking...")
                    # Scroll to trigger to ensure visibility
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
                    time.sleep(0.5)
                    try:
                        trigger.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", trigger)
                    
                    time.sleep(2) # Wait for dialog/input to appear
                    
                    # Try to find input again
                    file_input = self._find_element_by_selectors(
                        self.selectors_config.get('resume_upload_input'),
                        timeout=5
                    )
            
            if file_input:
                # Unhide if necessary (common in modern UIs)
                self.driver.execute_script(
                    "arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", 
                    file_input
                )
                
                file_input.send_keys(resume_path)
                logger.info("   Sent file path to input element")
                time.sleep(2)
                
                # Verify success (optional)
                success_indicator = self._find_element_by_selectors(
                    self.selectors_config.get('upload_success_indicator'),
                    timeout=5
                )
                if success_indicator:
                    logger.info("   Upload success indicator detected")
                
                return True
            else:
                logger.error(" Could not find file input element even after clicking trigger")
                return False
                
        except Exception as e:
            logger.error(f"Resume upload error: {e}")
            return False
    
    def _save_job_to_db(self, job_data):
        """Save job to database"""
        try:
            if not self.db_session or not self.job_site:
                return
            
            # Check if already exists
            existing = self.db_session.query(JobListing).filter(
                JobListing.job_site_id == self.job_site.id,
                JobListing.job_url == job_data['job_url']
            ).first()
            
            if not existing:
                job_listing = JobListing(
                    job_site_id=self.job_site.id,
                    external_job_id=job_data['external_id'],
                    job_title=job_data['job_title'],
                    job_url=job_data['job_url'],
                    status='discovered'
                )
                self.db_session.add(job_listing)
                self.db_session.commit()
                logger.debug(f"   Saved to database: {job_data['job_title']}")
        except Exception as e:
            logger.warning(f"   Database save failed: {e}")
            if self.db_session:
                self.db_session.rollback()
    
    def _update_job_status(self, job_id, status):
        """Update job status in database"""
        try:
            if not self.db_session or not self.job_site:
                return
            
            job = self.db_session.query(JobListing).filter(
                JobListing.job_site_id == self.job_site.id,
                JobListing.external_job_id == job_id
            ).first()
            
            if job:
                job.status = status
                self.db_session.commit()
                logger.debug(f"  Updated job status to: {status}")
        except Exception as e:
            logger.warning(f"   Status update failed: {e}")
            if self.db_session:
                self.db_session.rollback()
