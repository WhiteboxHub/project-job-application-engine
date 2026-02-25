from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
import time
import os
from selenium.webdriver.common.by import By
from config.settings import settings

class AshbyStrategy(BaseStrategy):
    """
    Ashby (jobs.ashbyhq.com) Automation Strategy
    """
    
    def __init__(self, driver, job_site, selectors, db_session=None):
        super().__init__(driver, job_site, selectors)
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.safe_actions = SafeActions(driver)
        self._load_applicant_data()

    def _load_applicant_data(self):
        """Loads applicant info from guest_form_data.json"""
        import json
        try:
            path = os.path.join("data", "guest_form_data.json")
            if os.path.exists(path):
                with open(path, "r") as f:
                    self.applicant_data = json.load(f)
                    logger.info(f"ASHBY: Loaded applicant data for {self.applicant_data.get('applicant', {}).get('first_name')}")
            else:
                self.applicant_data = {}
        except Exception as e:
            logger.error(f"ASHBY: Error loading applicant data: {e}")
            self.applicant_data = {}

    def login(self):
        """Ashby job boards do not require login to search."""
        logger.info("ASHBY: Login not required.")
        return True

    def find_jobs(self):
        """
        Search for jobs on an Ashby board.
        """
        logger.info("ASHBY: Starting job discovery...")
        
        try:
            keywords = ["AI", "Python"]
            all_jobs = []

            for keyword in keywords:
                base_url = "https://jobs.ashbyhq.com/"
                self.driver.get(base_url)
                time.sleep(4)

                logger.info(f"ASHBY: Looking for search input to filter by '{keyword}'")
                
                search_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='search'], input[placeholder*='Search' i], input[placeholder*='Filter' i]")
                if search_inputs:
                    search_input = search_inputs[0]
                    search_input.clear()
                    self.human.human_type(search_input, keyword)
                    time.sleep(3)
                else:
                    logger.warning("ASHBY: Search input not found, parsing all visible jobs instead.")

                try:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/job/'], .job-posting a, a.job-link")
                    logger.info(f"ASHBY: Found {len(cards)} elements for '{keyword}'")
                    
                    for card in cards:
                        try:
                            title = card.text.strip() or "Ashby Job"
                            url = card.get_attribute("href")
                            
                            if url and keyword.lower() in title.lower():
                                if not any(j.get('job_url') == url for j in all_jobs):
                                    all_jobs.append({
                                        "title": title,
                                        "job_url": url,
                                        "site": "ASHBY"
                                    })
                        except Exception as e:
                            logger.debug(f"ASHBY: Skipping card error: {e}")
                except Exception as e:
                    logger.error(f"ASHBY: Error scraping cards: {e}")
                    
            logger.info(f"ASHBY: Total jobs found: {len(all_jobs)}")
            return all_jobs

        except Exception as e:
            logger.error(f"ASHBY: Job search failed: {e}")
            return []

    def apply(self, listing):
        """
        Applies to an Ashby job listing.
        Fills all mandatory fields and pauses for user input on unknown ones.
        """
        logger.info(f"ASHBY: Processing application for {listing.get('title')}...")
        
        try:
            self.driver.get(listing.get('job_url'))
            time.sleep(3)
            
            # Click "Apply" button if form isn't already visible
            apply_btns = self.driver.find_elements(By.XPATH,
                "//*[self::a or self::button][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]")
            
            # Check for form fields broadly (Ashby React app may not use <form> tags)
            form_fields = self.driver.find_elements(By.CSS_SELECTOR, "input, textarea, select")
            visible_form_fields = [f for f in form_fields if f.is_displayed()]
            
            if not visible_form_fields and apply_btns:
                logger.info("ASHBY: Clicking 'Apply' button to reach form.")
                try:
                    self.driver.execute_script("arguments[0].click();", apply_btns[0])
                    time.sleep(5)  # Give React more time to render the form
                except:
                    pass
            else:
                logger.info(f"ASHBY: Form already visible with {len(visible_form_fields)} field(s).")
            
            # Build applicant data mapping
            applicant = self.applicant_data.get("applicant", {})
            first_name = applicant.get("first_name", "Ghazal")
            last_name = applicant.get("last_name", "Sultan")
            email = applicant.get("email", "ghazal.sultan1616@gmail.com")
            phone = applicant.get("phone", "")
            city = applicant.get("city", "")
            state = applicant.get("state", "")
            country = applicant.get("country", "")
            zipcode = applicant.get("zipcode", "")
            full_name = f"{first_name} {last_name}"
            location = f"{city}, {state}, {country}" if city else ""
            
            # Keyword-to-value mapping for auto-filling
            field_map = {
                "name": full_name,
                "full name": full_name,
                "first name": first_name,
                "first_name": first_name,
                "last name": last_name,
                "last_name": last_name,
                "email": email,
                "e-mail": email,
                "phone": phone,
                "mobile": phone,
                "telephone": phone,
                "phone number": phone,
                "city": city,
                "location": location,
                "address": f"{city}, {state} {zipcode}",
                "state": state,
                "country": country,
                "zip": zipcode,
                "zipcode": zipcode,
                "postal": zipcode,
                "linkedin": applicant.get("linkedin", ""),
                "website": applicant.get("website", ""),
                "portfolio": applicant.get("portfolio", ""),
                # Common open-ended required fields
                "how did you hear": "Online job board (Hiring.cafe)",
                "hear about": "Online job board (Hiring.cafe)",
                "referral": "Online job board (Hiring.cafe)",
                "source": "Online job board (Hiring.cafe)",
                "how did you find": "Online job board (Hiring.cafe)",
                "cover letter": f"I am excited to apply for this position. I am a highly motivated professional with a strong background in technology. Please find my resume attached.",
                "cover": f"I am excited to apply for this position. My skills and experience align well with this role.",
                "salary": applicant.get("salary_expectation", "Open to discussion"),
                "expected salary": applicant.get("salary_expectation", "Open to discussion"),
                "sponsor": "No",
                "authorization": "Yes",
                "authorized": "Yes",
                "legally authorized": "Yes",
                "require sponsorship": "No",
            }
            
            logger.info(f"ASHBY: Preparing to fill form as {full_name} ({email})")
            
            # Upload resume FIRST
            resume_path = self.applicant_data.get("resume_path")
            logger.info(f"ASHBY: Resume path from config: {resume_path}")
            if resume_path and os.path.exists(resume_path):
                logger.info(f"ASHBY: Resume file found at {resume_path}")
                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if not file_inputs:
                    self.driver.execute_script("""
                        var inputs = document.querySelectorAll('input[type="file"]');
                        inputs.forEach(function(el) { el.style.display = 'block'; el.style.opacity = '1'; });
                    """)
                    time.sleep(1)
                    file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                if file_inputs:
                    logger.info(f"ASHBY: Found {len(file_inputs)} file input(s). Uploading resume...")
                    try:
                        file_inputs[0].send_keys(os.path.abspath(resume_path))
                        time.sleep(3)
                        logger.info("ASHBY: Resume uploaded successfully.")
                    except Exception as upload_err:
                        logger.error(f"ASHBY: Resume upload failed: {upload_err}")
                else:
                    logger.warning("ASHBY: No file input found on page. Resume not uploaded.")
            else:
                logger.warning(f"ASHBY: Resume file not found or path not set. Path: {resume_path}")
            
            # Scan ALL visible fields on the page — Ashby React app doesn't always use <form> tags
            all_inputs = self.driver.find_elements(By.CSS_SELECTOR,
                "input:not([type='hidden']):not([type='file']):not([type='submit']):not([type='checkbox']):not([type='radio']), "
                "textarea, select")
            all_inputs = [f for f in all_inputs if f.is_displayed()]
            logger.info(f"ASHBY: Found {len(all_inputs)} visible fillable field(s) on page.")
            
            unfilled_required = []
            
            for field in all_inputs:
                try:
                    field_type = field.tag_name.lower()
                    input_type = field.get_attribute("type") or "text"
                    field_name = (field.get_attribute("name") or "").lower()
                    field_id = (field.get_attribute("id") or "").lower()
                    placeholder = (field.get_attribute("placeholder") or "").lower()
                    aria_label = (field.get_attribute("aria-label") or "").lower()
                    required = field.get_attribute("required") is not None or field.get_attribute("aria-required") == "true"
                    
                    # Try to get label text
                    label_text = ""
                    if field_id:
                        labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{field_id}']")
                        if labels:
                            label_text = labels[0].text.strip().lower()
                    
                    # Skip if already filled
                    current_value = field.get_attribute("value") or ""
                    if current_value.strip():
                        logger.info(f"ASHBY: Field '{label_text or field_name or placeholder}' already has value, skipping.")
                        continue
                    
                    # Combine all hints to match against field_map
                    hints = [field_name, field_id, placeholder, aria_label, label_text]
                    matched_value = None
                    
                    for hint in hints:
                        if not hint:
                            continue
                        for key, value in field_map.items():
                            if key in hint and value:
                                matched_value = value
                                break
                        if matched_value:
                            break
                    
                    if matched_value and field_type in ["input", "textarea"]:
                        logger.info(f"ASHBY: Auto-filling '{label_text or field_name or placeholder}' with '{matched_value}'")
                        field.clear()
                        self.human.human_type(field, matched_value)
                        time.sleep(0.5)
                    elif field_type == "select" and matched_value:
                        from selenium.webdriver.support.ui import Select
                        try:
                            sel = Select(field)
                            for option in sel.options:
                                if matched_value.lower() in option.text.lower():
                                    sel.select_by_visible_text(option.text)
                                    logger.info(f"ASHBY: Selected '{option.text}' for '{label_text or field_name}'")
                                    break
                        except:
                            pass
                    elif required or "required" in (label_text + placeholder):
                        field_label = label_text or field_name or placeholder or aria_label or "unknown"
                        unfilled_required.append(field_label)
                        logger.warning(f"ASHBY: ⚠️ Required field '{field_label}' could not be auto-filled.")
                except Exception as field_err:
                    logger.warning(f"ASHBY: Error processing a form field: {field_err}")
            
            # Handle checkboxes (consent/agreement) — also outside form tags
            checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            for cb in checkboxes:
                try:
                    if cb.is_displayed() and not cb.is_selected():
                        self.driver.execute_script("arguments[0].click();", cb)
                        logger.info("ASHBY: Checked a checkbox (consent/agreement).")
                        time.sleep(0.3)
                except Exception as e:
                    logger.debug(f"ASHBY: Could not click checkbox: {e}")
            
            # If there are unfilled required fields:
            # In DRY RUN — just log and continue (don't block)
            # In LIVE mode — pause for user to fill manually
            if unfilled_required:
                logger.warning(f"ASHBY: ⚠️ {len(unfilled_required)} required field(s) could not be auto-filled: {', '.join(unfilled_required)}")
                if settings.DRY_RUN:
                    logger.info("ASHBY: [DRY RUN] Skipping manual pause. Would have required user input for above fields.")
                else:
                    logger.info("ASHBY: ⏸️ PAUSING - Please fill the remaining required fields in the browser...")
                    print("\n" + "=" * 60)
                    print(f"⚠️  MANUAL INPUT NEEDED for {len(unfilled_required)} field(s):")
                    for f in unfilled_required:
                        print(f"   • {f}")
                    print("=" * 60)
                    print("👉 Fill these fields in the browser window, then press ENTER to submit...")
                    input()  # Blocks until user presses Enter
                    logger.info("ASHBY: User confirmed manual fields filled. Proceeding to submit.")

            
            # Find and click Submit button
            submit_btn = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            if not submit_btn:
                submit_btn = self.driver.find_elements(By.XPATH,
                    "//*[self::button or self::input[@type='submit']][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]")
                
            if submit_btn:
                if settings.DRY_RUN:
                    logger.info(f"ASHBY: [DRY RUN] Simulation complete. Would have clicked '{submit_btn[0].text.strip()}'. skipping submission.")
                    return True
                    
                logger.info(f"ASHBY: Clicking submit button: '{submit_btn[0].text.strip()}'")
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", submit_btn[0])
                    time.sleep(1)
                    self.driver.execute_script("arguments[0].click();", submit_btn[0])
                    time.sleep(5)
                    logger.info("ASHBY: ✅ Submit button clicked successfully.")
                except Exception as click_err:
                    logger.warning(f"ASHBY: JS click failed, trying native click: {click_err}")
                    submit_btn[0].click()
                    time.sleep(5)
            else:
                logger.warning("ASHBY: No submit button found on the page.")
            
            return True

        except Exception as e:
            logger.error(f"ASHBY: Error during application: {e}")
            return False
