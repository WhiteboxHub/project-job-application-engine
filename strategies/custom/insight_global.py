from strategies.base import BaseStrategy
from core.logger import logger
import time
import os
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from data.csv_tracker import tracker as csv_tracker


class InsightGlobalStrategy(BaseStrategy):
    """
    Simplified Insight Global strategy that:
    1. Loads search params from JSON
    2. Searches for jobs
    3. Applies as guest with minimal form fields
    """
    
    def __init__(self, driver, db_session, config):
        super().__init__(driver, db_session, config)
        self.config_data = self._load_config()
    
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
    
    def _verify_upload_success(self):
        """
        Verify that resume upload was successful by checking for upload indicators.
        Returns True if upload appears successful, False otherwise.
        """
        try:
            # Method 1: Check for uploaded file name in DOM (most reliable for Dropzone)
            try:
                uploaded_file = self.driver.find_element(By.CSS_SELECTOR, "div.dz-filename span, .dz-filename, div.dz-details span.dz-filename")
                if uploaded_file and uploaded_file.text:
                    logger.info(f"✅ Upload verification: Found filename '{uploaded_file.text}' in UI")
                    return True
            except Exception:
                pass
            
            # Method 2: Check for Dropzone success class (visible indicators)
            try:
                success_elements = self.driver.find_elements(By.CSS_SELECTOR, ".dz-success, .dz-complete, .dz-processing")
                if success_elements:
                    logger.info(f"✅ Upload verification: Found {len(success_elements)} Dropzone status indicator(s)")
                    return True
            except Exception:
                pass
            
            # Method 3: Check for preview thumbnails or file preview
            try:
                preview = self.driver.find_element(By.CSS_SELECTOR, ".dz-preview, .dz-image-preview, .dz-file-preview")
                if preview and preview.is_displayed():
                    logger.info(f"✅ Upload verification: Found visible preview element")
                    return True
            except Exception:
                pass
            
            # Method 4: Check if the dropzone message disappeared (means file was added)
            try:
                # If the "Drop file here" message is gone, it means a file was added
                dropzone_msg = self.driver.find_elements(By.CSS_SELECTOR, "div.dz-message")
                if dropzone_msg:
                    # Check if it's hidden or display:none
                    is_hidden = self.driver.execute_script("""
                        var msg = arguments[0];
                        var style = window.getComputedStyle(msg);
                        return style.display === 'none' || style.visibility === 'hidden' || !msg.offsetParent;
                    """, dropzone_msg[0])
                    
                    if is_hidden:
                        logger.info(f"✅ Upload verification: Dropzone message hidden (file uploaded)")
                        return True
            except Exception:
                pass
            
            # Method 5: Check if file input has files (fallback, less reliable)
            try:
                js_check = """
                var input = document.querySelector('input[type="file"]');
                if (input && input.files && input.files.length > 0) {
                    return input.files[0].name;
                }
                return null;
                """
                filename = self.driver.execute_script(js_check)
                if filename:
                    logger.info(f"ℹ️ Upload verification: File input contains '{filename}' (but UI may not show it)")
                    # Don't return True here - we want visual confirmation
                    pass
            except Exception:
                pass
            
            logger.warning("⚠️ Upload verification: No visual upload indicators found in UI")
            return False
            
        except Exception as e:
            logger.debug(f"Upload verification error: {e}")
            return False
    
    def _attempt_recaptcha_click(self):
        """
        Attempt to automatically click the reCAPTCHA checkbox.
        
        IMPORTANT: This will likely not work for modern reCAPTCHA v2/v3 because:
        - Google detects automation/Selenium
        - Will show image challenge even if checkbox is clicked
        
        Returns:
            - True if reCAPTCHA appears to be solved (green checkmark)
            - False if image challenge appears or clicking fails
        """
        try:
            logger.info("🔄 Attempting to automatically click reCAPTCHA checkbox...")
            logger.info("   Note: Modern reCAPTCHA detects bots - this may not work")
            
            # Wait for reCAPTCHA iframe to load
            time.sleep(2)
            
            # Find the reCAPTCHA iframe
            recaptcha_iframe = None
            iframe_selectors = [
                "iframe[src*='recaptcha/api2/anchor']",
                "iframe[title*='reCAPTCHA']",
                "iframe[name*='recaptcha']"
            ]
            
            for selector in iframe_selectors:
                try:
                    recaptcha_iframe = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if recaptcha_iframe:
                        logger.info(f"✅ Found reCAPTCHA iframe with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not recaptcha_iframe:
                logger.warning("❌ Could not find reCAPTCHA iframe")
                return False
            
            # Switch to the iframe
            self.driver.switch_to.frame(recaptcha_iframe)
            logger.info("🔄 Switched to reCAPTCHA iframe")
            
            # Wait for checkbox to be present
            time.sleep(1)
            
            # Find and click the checkbox
            checkbox_selectors = [
                "div.recaptcha-checkbox-border",
                "div.recaptcha-checkbox-checkmark",
                "#recaptcha-anchor",
                "div[role='checkbox']"
            ]
            
            checkbox_clicked = False
            for selector in checkbox_selectors:
                try:
                    checkbox = self.driver.find_element(By.CSS_SELECTOR, selector)
                    
                    # Try to click
                    try:
                        checkbox.click()
                    except:
                        # Fallback to JavaScript click
                        self.driver.execute_script("arguments[0].click();", checkbox)
                    
                    logger.info(f"✅ Clicked reCAPTCHA checkbox using: {selector}")
                    checkbox_clicked = True
                    break
                except Exception as e:
                    logger.debug(f"Checkbox selector {selector} failed: {e}")
                    continue
            
            if not checkbox_clicked:
                logger.warning("❌ Could not find or click reCAPTCHA checkbox")
                self.driver.switch_to.default_content()
                return False
            
            # Wait for reCAPTCHA to process (3-5 seconds)
            logger.info("⏳ Waiting for reCAPTCHA to process...")
            time.sleep(4)
            
            # Check if we got the green checkmark (success) or image challenge (failed)
            try:
                # Look for the green checkmark indicator
                checkmark = self.driver.find_element(By.CSS_SELECTOR, "span.recaptcha-checkbox-checked")
                if checkmark:
                    logger.info("✅ SUCCESS! reCAPTCHA checkbox is checked (green checkmark)")
                    self.driver.switch_to.default_content()
                    return True
            except Exception:
                pass
            
            # Switch back to check if image challenge appeared
            self.driver.switch_to.default_content()
            
            # Check for image challenge iframe
            try:
                challenge_iframe = self.driver.find_element(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/bframe']")
                if challenge_iframe and challenge_iframe.is_displayed():
                    logger.warning("⚠️ reCAPTCHA image challenge detected")
                    logger.warning("   Google detected automation - showing image puzzle")
                    logger.warning("   Cannot solve image challenges without 2Captcha API")
                    return False
            except Exception:
                pass
            
            # If we're here, status is unclear - switch back and return False
            self.driver.switch_to.default_content()
            logger.warning("⚠️ reCAPTCHA click attempted but status unclear")
            return False
            
        except Exception as e:
            logger.error(f"reCAPTCHA click attempt failed: {e}")
            try:
                self.driver.switch_to.default_content()
            except:
                pass
            return False
    
    def login(self):
        """No login required for guest applications"""
        logger.info("InsightGlobal: No login required (guest mode).")
        return True
    
    def _search_jobs(self, keyword, location, distance):
        """
        Perform a single search with given parameters
        Returns list of job URLs found
        """
        url = "https://insightglobal.com/jobs/"
        logger.info(f"Opening Insight Global: {url}")
        self.driver.get(url)
        
        try:
            # Wait for search form to load
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Title'], input#textinput"))
            )
            logger.info("Search page loaded successfully")
        except Exception as e:
            logger.error(f"Search page failed to load: {e}")
            return []
        
        time.sleep(1)
        
        # Fill keyword
        try:
            keyword_input = self.driver.find_element(By.CSS_SELECTOR, "#textinput")
            keyword_input.clear()
            keyword_input.send_keys(keyword)
            logger.info(f"Entered keyword: {keyword}")
        except Exception as e:
            logger.error(f"Failed to enter keyword: {e}")
            return []
        
        # Fill location
        try:
            location_input = self.driver.find_element(By.CSS_SELECTOR, "#locationinput")
            location_input.clear()
            location_input.send_keys(location)
            logger.info(f"Entered location: {location}")
        except Exception as e:
            logger.error(f"Failed to enter location: {e}")
            return []
        
        # Set distance
        try:
            dropdown_btn = self.driver.find_element(By.ID, 'dropdownMenu1')
            dropdown_btn.click()
            time.sleep(0.5)
            
            # Try to select distance option
            try:
                distance_option = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    f"div.distance-input ul.dropdown-menu li[data-value='{distance}'] a"
                )
                distance_option.click()
                logger.info(f"Set distance: {distance} miles")
            except Exception:
                logger.debug("Distance dropdown selection failed (non-critical)")
        except Exception:
            logger.debug("Distance dropdown not found (non-critical)")
        
        # Click search button
        try:
            search_btn = self.driver.find_element(By.CSS_SELECTOR, "#homesearch")
            search_btn.click()
            logger.info("Clicked search button")
        except Exception as e:
            logger.error(f"Failed to click search button: {e}")
            return []
        
        # Wait for results
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.result"))
            )
            time.sleep(2)  # Additional wait for JS to render results
        except Exception:
            logger.warning("No results found or timeout waiting for results")
            return []
        
        # Extract job URLs
        job_urls = []
        try:
            result_rows = self.driver.find_elements(By.CSS_SELECTOR, "div.result")
            logger.info(f"Found {len(result_rows)} job results")
            
            for row in result_rows:
                try:
                    # Find job title link
                    link = row.find_element(By.CSS_SELECTOR, "div.job-title a")
                    href = link.get_attribute('href')
                    title = link.text.strip()
                    
                    if href and href not in job_urls:
                        job_urls.append(href)
                        logger.info(f"Found job: {title}")
                        
                        # Track in CSV
                        csv_tracker.add_discovered_jobs('insight_global', [{
                            'external_id': href.split('/')[-2] if '/' in href else href,
                            'job_title': title,
                            'job_url': href
                        }])
                        
                except Exception as e:
                    logger.debug(f"Error extracting job from result row: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error parsing results: {e}")
        
        logger.info(f"Extracted {len(job_urls)} unique job URLs")
        return job_urls
    
    def _apply_to_job(self, job_url):
        """
        Apply to a single job:
        1. Navigate to job detail page
        2. Click Apply button
        3. Click Apply as Guest
        4. Fill form with JSON data
        5. Upload resume
        6. Submit
        """
        from engine.guards import guards
        from config.settings import settings as _settings
        
        if not guards.can_apply():
            logger.info("Application limit reached - stopping")
            return False
        
        # Check if already applied
        try:
            status = csv_tracker.get_job_status('insight_global', job_url)
            if status and status.get('status') == 'applied':
                logger.info(f"Already applied to this job, skipping: {job_url}")
                return False
        except Exception:
            pass
        
        logger.info(f"=" * 60)
        logger.info(f"Applying to job: {job_url}")
        logger.info(f"=" * 60)
        
        try:
            # Navigate to job detail page
            self.driver.get(job_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
            # Find and click Apply button
            apply_selectors = [
                "#ContentPlaceHolder1_lblApplyLink",
                "a.btn.btn-primary",
                "a.result-action-button.quick-apply",
                "button[contains(text(), 'Apply')]",
                "a[contains(text(), 'Apply')]"
            ]
            
            apply_clicked = False
            for selector in apply_selectors:
                try:
                    # Try CSS selector first
                    if '#' in selector or '.' in selector:
                        apply_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    else:
                        # Skip XPath-style selectors for now
                        continue
                    
                    try:
                        apply_btn.click()
                    except Exception:
                        # Use JavaScript click as fallback
                        self.driver.execute_script("arguments[0].click();", apply_btn)
                    
                    logger.info(f"Clicked Apply button using selector: {selector}")
                    apply_clicked = True
                    break
                except Exception:
                    continue
            
            if not apply_clicked:
                # Try XPath as last resort
                try:
                    apply_btn = self.driver.find_element(
                        By.XPATH,
                        "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]"
                    )
                    apply_btn.click()
                    logger.info("Clicked Apply button using XPath")
                    apply_clicked = True
                except Exception:
                    pass
            
            if not apply_clicked:
                logger.error("Could not find Apply button on job detail page")
                csv_tracker.update_job_status('insight_global', job_url, 'failed', 
                                            attempts_inc=1, last_error='No Apply button')
                return False
            
            time.sleep(2)
            
            # Find and click "Apply as Guest" link
            guest_link_found = False
            guest_url = None
            
            try:
                # Try direct ID selector
                guest_link = self.driver.find_element(By.CSS_SELECTOR, "#ContentPlaceHolder1_guestLogin4")
                guest_url = guest_link.get_attribute('href')
                logger.info(f"Found guest application link: {guest_url}")
                guest_link_found = True
            except Exception:
                # Try finding by href pattern
                try:
                    guest_link = self.driver.find_element(
                        By.XPATH,
                        "//a[contains(@href, 'jobapplynoaccount.aspx')]"
                    )
                    guest_url = guest_link.get_attribute('href')
                    logger.info(f"Found guest application link (fallback): {guest_url}")
                    guest_link_found = True
                except Exception:
                    pass
            
            if not guest_link_found or not guest_url:
                logger.error("Could not find 'Apply as Guest' link")
                csv_tracker.update_job_status('insight_global', job_url, 'failed',
                                            attempts_inc=1, last_error='No guest link')
                return False
            
            # Navigate to guest application form
            logger.info("Navigating to guest application form...")
            self.driver.get(guest_url)
            
            # Wait for form to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "txtFirstName"))
                )
                logger.info("Guest application form loaded")
            except Exception as e:
                logger.error(f"Guest form failed to load: {e}")
                csv_tracker.update_job_status('insight_global', job_url, 'failed',
                                            attempts_inc=1, last_error='Form load timeout')
                return False
            
            time.sleep(1)
            
            # Fill form fields from JSON
            applicant = self.config_data.get('applicant', {})
            
            try:
                # First Name
                first_name_input = self.driver.find_element(By.CSS_SELECTOR, "#txtFirstName")
                first_name_input.clear()
                first_name_input.send_keys(applicant.get('first_name', ''))
                logger.info(f"Filled first name: {applicant.get('first_name')}")
                
                # Last Name
                last_name_input = self.driver.find_element(By.CSS_SELECTOR, "#txtLastName")
                last_name_input.clear()
                last_name_input.send_keys(applicant.get('last_name', ''))
                logger.info(f"Filled last name: {applicant.get('last_name')}")
                
                # Email
                email_input = self.driver.find_element(By.CSS_SELECTOR, "#txtEmail")
                email_input.clear()
                email_input.send_keys(applicant.get('email', ''))
                logger.info(f"Filled email: {applicant.get('email')}")
                
                # Phone
                phone_input = self.driver.find_element(By.CSS_SELECTOR, "#txtPhone")
                phone_input.clear()
                phone_input.send_keys(applicant.get('phone', ''))
                logger.info(f"Filled phone: {applicant.get('phone')}")
                
                # Click "Yes" on minimum requirements radio button
                try:
                    time.sleep(0.5)
                    min_req_yes = self.driver.find_element(By.CSS_SELECTOR, "#ContentPlaceHolder1_chkMinReq_0")
                    # Scroll into view
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", min_req_yes)
                    time.sleep(0.3)
                    
                    # Click the radio button
                    try:
                        min_req_yes.click()
                    except Exception:
                        # Use JavaScript click if regular click fails
                        self.driver.execute_script("arguments[0].click();", min_req_yes)
                    
                    logger.info("✅ Selected 'Yes' for minimum requirements")
                except Exception as e:
                    logger.warning(f"Could not click minimum requirements (may not exist on this form): {e}")
                
            except Exception as e:
                logger.error(f"Failed to fill form fields: {e}")
                csv_tracker.update_job_status('insight_global', job_url, 'failed',
                                            attempts_inc=1, last_error=f'Form fill error: {e}')
                return False
            
            # Upload resume - ENHANCED MULTI-METHOD APPROACH
            resume_path = self.config_data.get('resume_path', '')
            if resume_path:
                try:
                    # Build absolute path
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                    resume_full_path = os.path.join(project_root, resume_path)
                    
                    # Get absolute normalized path for Windows - normalize separators
                    resume_full_path = os.path.abspath(resume_full_path)
                    resume_full_path = resume_full_path.replace('\\', '/')  # Convert to forward slashes for Selenium
                    
                    logger.info(f"=" * 60)
                    logger.info(f"📎 RESUME UPLOAD STARTING")
                    logger.info(f"File path: {resume_full_path}")
                    
                    # Validate file exists and get info
                    if not os.path.exists(resume_full_path):
                        logger.error(f"❌ Resume file not found at: {resume_full_path}")
                        logger.error(f"Please verify the file exists and the path is correct")
                        return False
                    
                    file_size = os.path.getsize(resume_full_path)
                    logger.info(f"File size: {file_size / 1024:.2f} KB")
                    logger.info(f"File exists: ✅")
                    logger.info(f"=" * 60)
                    
                    # Wait for page to fully stabilize
                    logger.info("⏳ Waiting for page to fully load...")
                    time.sleep(3)  # Increased wait time for JavaScript to fully initialize
                    
                    # Scroll to resume section with retry
                    for attempt in range(3):
                        try:
                            resume_section = self.driver.find_element(By.CSS_SELECTOR, "#pnlResumeDrop")
                            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", resume_section)
                            time.sleep(1.5)
                            logger.info("✅ Scrolled to resume section")
                            break
                        except Exception as e:
                            if attempt == 2:
                                logger.warning(f"Could not scroll to resume section after 3 attempts: {e}")
                            time.sleep(1)
                    
                    upload_success = False
                    upload_method = None
                    
                    # METHOD 1: Direct file input with Dropzone event triggering
                    if not upload_success:
                        try:
                            logger.info("\n🔍 METHOD 1: Direct file input with Dropzone triggers...")
                            
                            # Wait explicitly for file input to be present
                            file_input = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                            )
                            
                            logger.info(f"Found file input element")
                            logger.info(f"  - Tag: {file_input.tag_name}")
                            logger.info(f"  - Displayed: {file_input.is_displayed()}")
                            logger.info(f"  - Enabled: {file_input.is_enabled()}")
                            
                            # Send the file path
                            file_input.send_keys(resume_full_path)
                            logger.info("✅ File path sent to input element")
                            
                            # CRITICAL: Trigger Dropzone events to make it process the file
                            try:
                                logger.info("🔄 Triggering Dropzone events...")
                                trigger_script = """
                                var fileInput = arguments[0];
                                
                                // Trigger the change event
                                var changeEvent = new Event('change', { bubbles: true });
                                fileInput.dispatchEvent(changeEvent);
                                
                                // Also trigger input event
                                var inputEvent = new Event('input', { bubbles: true });
                                fileInput.dispatchEvent(inputEvent);
                                
                                // Try to trigger Dropzone's addedfile event if Dropzone exists
                                try {
                                    var dropzoneElement = fileInput.closest('.dropzone');
                                    if (dropzoneElement && dropzoneElement.dropzone) {
                                        var files = fileInput.files;
                                        if (files.length > 0) {
                                            // Manually trigger Dropzone to process the file
                                            dropzoneElement.dropzone.addFile(files[0]);
                                            return 'Dropzone.addFile called';
                                        }
                                    }
                                } catch (e) {
                                    console.log('Dropzone API not available:', e);
                                }
                                
                                return 'Events triggered';
                                """
                                
                                result = self.driver.execute_script(trigger_script, file_input)
                                logger.info(f"Event trigger result: {result}")
                            except Exception as e:
                                logger.warning(f"Could not trigger Dropzone events: {e}")
                            
                            # Wait for upload to process
                            time.sleep(3)
                            
                            # Verify upload by checking for success indicators
                            upload_success = self._verify_upload_success()
                            if upload_success:
                                upload_method = "Method 1: Direct file input with Dropzone triggers"
                                logger.info(f"✅ {upload_method} - SUCCESS")
                            
                        except Exception as e:
                            logger.warning(f"❌ Method 1 failed: {e}")

                    
                    # METHOD 2: Make file input visible then interact
                    if not upload_success:
                        try:
                            logger.info("\n🔍 METHOD 2: Visible file input approach...")
                            
                            # Find all file inputs and make them visible
                            js_make_visible = """
                            var inputs = document.querySelectorAll('input[type="file"]');
                            if (inputs.length > 0) {
                                inputs.forEach(function(input) {
                                    input.style.cssText = 'display: block !important; visibility: visible !important; opacity: 1 !important; position: absolute !important; z-index: 9999 !important; width: 200px !important; height: 50px !important;';
                                });
                                return inputs.length;
                            }
                            return 0;
                            """
                            
                            count = self.driver.execute_script(js_make_visible)
                            logger.info(f"Made {count} file input(s) visible")
                            
                            if count > 0:
                                time.sleep(1)
                                file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                                
                                for idx, file_input in enumerate(file_inputs):
                                    try:
                                        logger.info(f"Trying file input #{idx + 1}/{len(file_inputs)}")
                                        file_input.send_keys(resume_full_path)
                                        time.sleep(2)
                                        
                                        if self._verify_upload_success():
                                            upload_success = True
                                            upload_method = f"Method 2: Visible file input #{idx + 1}"
                                            logger.info(f"✅ {upload_method} - SUCCESS")
                                            break
                                    except Exception as e:
                                        logger.debug(f"File input #{idx + 1} failed: {e}")
                                        continue
                        except Exception as e:
                            logger.warning(f"❌ Method 2 failed: {e}")
                    
                    # METHOD 3: Click dropzone then send keys
                    if not upload_success:
                        try:
                            logger.info("\n🔍 METHOD 3: Click dropzone approach...")
                            
                            # Find dropzone clickable area
                            dropzone_selectors = [
                                "#pnlResumeDrop div.dropzone",
                                "#pnlResumeDrop",
                                "div.dropzone.needsclick.dz-clickable",
                                "div.dz-message",
                                "div[class*='dropzone']"
                            ]
                            
                            for selector in dropzone_selectors:
                                try:
                                    dropzone = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    logger.info(f"Found dropzone with selector: {selector}")
                                    
                                    # Click to activate
                                    try:
                                        dropzone.click()
                                    except:
                                        self.driver.execute_script("arguments[0].click();", dropzone)
                                    
                                    time.sleep(0.5)
                                    
                                    # Now find and fill file input
                                    file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                                    file_input.send_keys(resume_full_path)
                                    time.sleep(2)
                                    
                                    if self._verify_upload_success():
                                        upload_success = True
                                        upload_method = f"Method 3: Click dropzone ({selector})"
                                        logger.info(f"✅ {upload_method} - SUCCESS")
                                        break
                                except Exception as e:
                                    logger.debug(f"Dropzone selector {selector} failed: {e}")
                                    continue
                                    
                        except Exception as e:
                            logger.warning(f"❌ Method 3 failed: {e}")
                    
                    # METHOD 4: Direct JavaScript file manipulation
                    if not upload_success:
                        try:
                            logger.info("\n🔍 METHOD 4: JavaScript file manipulation...")
                            
                            # Try to trigger Dropzone's file handling directly
                            js_upload = """
                            var input = document.querySelector('input[type="file"]');
                            if (input) {
                                // Make sure it's interactable
                                input.style.display = 'block';
                                input.style.opacity = '1';
                                input.style.position = 'relative';
                                
                                // Trigger change event after setting value
                                var event = new Event('change', { bubbles: true });
                                input.dispatchEvent(event);
                                
                                return true;
                            }
                            return false;
                            """
                            
                            if self.driver.execute_script(js_upload):
                                time.sleep(0.5)
                                file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                                file_input.send_keys(resume_full_path)
                                time.sleep(2)
                                
                                if self._verify_upload_success():
                                    upload_success = True
                                    upload_method = "Method 4: JavaScript manipulation"
                                    logger.info(f"✅ {upload_method} - SUCCESS")
                                    
                        except Exception as e:
                            logger.warning(f"❌ Method 4 failed: {e}")
                    
                    # METHOD 5: Find file input within dropzone container
                    if not upload_success:
                        try:
                            logger.info("\n🔍 METHOD 5: Nested file input search...")
                            
                            # Find dropzone container then locate file input within it
                            resume_panel = self.driver.find_element(By.CSS_SELECTOR, "#pnlResumeDrop")
                            file_input = resume_panel.find_element(By.CSS_SELECTOR, "input[type='file']")
                            
                            logger.info("Found file input within resume panel")
                            
                            # Use JavaScript to make it absolutely positioned and visible
                            self.driver.execute_script("""
                                arguments[0].style.cssText = 'position: absolute; top: 0; left: 0; display: block; opacity: 1; width: 200px; height: 50px; z-index: 10000;';
                            """, file_input)
                            
                            time.sleep(0.5)
                            file_input.send_keys(resume_full_path)
                            time.sleep(2)
                            
                            if self._verify_upload_success():
                                upload_success = True
                                upload_method = "Method 5: Nested file input"
                                logger.info(f"✅ {upload_method} - SUCCESS")
                                
                        except Exception as e:
                            logger.warning(f"❌ Method 5 failed: {e}")
                    
                    # METHOD 6: Simulate user clicking the dropzone (most realistic)
                    if not upload_success:
                        try:
                            logger.info("\n🔍 METHOD 6: Simulating user click on dropzone...")
                            
                            # Find and click the dropzone area to simulate user interaction
                            dropzone_selectors = [
                                "#pnlResumeDrop div.dropzone.needsclick.dz-clickable",
                                "#pnlResumeDrop div.dropzone",
                                "#pnlResumeDrop",
                                "div.dropzone.dz-clickable"
                            ]
                            
                            for selector in dropzone_selectors:
                                try:
                                    dropzone = self.driver.find_element(By.CSS_SELECTOR, selector)
                                    logger.info(f"Found dropzone to click: {selector}")
                                    
                                    # Scroll it into view first
                                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", dropzone)
                                    time.sleep(0.5)
                                    
                                    # Try normal click first
                                    try:
                                        dropzone.click()
                                        logger.info("Clicked dropzone (normal click)")
                                    except:
                                        # Fallback to JavaScript click
                                        self.driver.execute_script("arguments[0].click();", dropzone)
                                        logger.info("Clicked dropzone (JavaScript click)")
                                    
                                    time.sleep(1)
                                    
                                    # Now the file input should be activated, try uploading
                                    file_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                                    file_input.send_keys(resume_full_path)
                                    logger.info("✅ File sent after clicking dropzone")
                                    
                                    # Trigger events
                                    self.driver.execute_script("""
                                        var input = arguments[0];
                                        var changeEvent = new Event('change', {bubbles: true});
                                        input.dispatchEvent(changeEvent);
                                        
                                        // Try Dropzone API if available
                                        var dzElement = input.closest('.dropzone');
                                        if (dzElement && dzElement.dropzone && input.files.length > 0) {
                                            dzElement.dropzone.emit('addedfile', input.files[0]);
                                            dzElement.dropzone.emit('complete', input.files[0]);
                                        }
                                    """, file_input)
                                    
                                    time.sleep(3)
                                    
                                    if self._verify_upload_success():
                                        upload_success = True
                                        upload_method = f"Method 6: User click simulation ({selector})"
                                        logger.info(f"✅ {upload_method} - SUCCESS")
                                        break
                                    
                                except Exception as e:
                                    logger.debug(f"Dropzone selector {selector} failed: {e}")
                                    continue
                                    
                        except Exception as e:
                            logger.warning(f"❌ Method 6 failed: {e}")
                    
                    # Final result
                    logger.info(f"\n{'=' * 60}")
                    if upload_success:
                        logger.info(f"✅ RESUME UPLOAD SUCCESSFUL!")
                        logger.info(f"Method used: {upload_method}")
                        logger.info(f"{'=' * 60}\n")
                        time.sleep(2)  # Wait for upload to fully process
                    else:
                        logger.error(f"❌ RESUME UPLOAD FAILED!")
                        logger.error(f"All 6 upload methods failed")
                        logger.error(f"The application will continue WITHOUT the resume")
                        logger.error(f"{'=' * 60}\n")
                        
                except Exception as e:
                    logger.error(f"Resume upload exception: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            
            # Handle reCAPTCHA if present
            try:
                logger.info("Checking for reCAPTCHA...")
                recaptcha_frame = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha']")
                
                if recaptcha_frame:
                    logger.info("⚠️ reCAPTCHA detected on this form")
                    
                    # ATTEMPT 1: Try automatic clicking (user's preferred method)
                    logger.info("\n" + "=" * 60)
                    logger.info("ATTEMPTING AUTOMATIC reCAPTCHA SOLVING")
                    logger.info("=" * 60)
                    
                    recaptcha_solved = self._attempt_recaptcha_click()
                    
                    if recaptcha_solved:
                        logger.info("=" * 60)
                        logger.info("✅ reCAPTCHA SOLVED AUTOMATICALLY!")
                        logger.info("=" * 60 + "\n")
                    else:
                        logger.warning("=" * 60)
                        logger.warning("❌ AUTOMATIC reCAPTCHA SOLVING FAILED")
                        logger.warning("=" * 60 + "\n")
                        
                        # In dry-run mode, just notify the user
                        if _settings.DRY_RUN:
                            logger.warning("🔵 DRY RUN: Auto-click failed")
                            logger.info("   In live mode, would attempt 2Captcha API as fallback")
                        else:
                            # ATTEMPT 2: Fall back to 2Captcha API if configured
                            captcha_api_key = os.getenv('TWOCAPTCHA_API_KEY', '')  
                            
                            if captcha_api_key:
                                logger.info("Attempting 2Captcha API as fallback...")
                                try:
                                    # Get the sitekey
                                    site_key = "6Lc73fMaAAAAAP06JY9D89xVxygVw9a_gOlvSUZA"
                                    page_url = self.driver.current_url
                                    
                                    # Import 2captcha library if available
                                    try:
                                        from twocaptcha import TwoCaptcha
                                        solver = TwoCaptcha(captcha_api_key)
                                        result = solver.recaptcha(sitekey=site_key, url=page_url)
                                        
                                        # Inject the solution
                                        response_token = result['code']
                                        js_inject = f"""
                                        document.getElementById('g-recaptcha-response').innerHTML = '{response_token}';
                                        """
                                        self.driver.execute_script(js_inject)
                                        logger.info("✅ reCAPTCHA solved using 2Captcha API")
                                        time.sleep(1)
                                    except ImportError:
                                        logger.error("2captcha-python library not installed. Run: pip install 2captcha-python")
                                        logger.warning("⚠️ Continuing without solving reCAPTCHA - submission may fail")
                                    except Exception as e:
                                        logger.error(f"Failed to solve reCAPTCHA with 2Captcha: {e}")
                                        logger.warning("⚠️ Continuing without solving reCAPTCHA - submission may fail")
                                except Exception as e:
                                    logger.error(f"reCAPTCHA 2Captcha fallback error: {e}")
                            else:
                                logger.warning("⚠️ Auto-click failed and no TWOCAPTCHA_API_KEY configured")
                                logger.info("Options:")
                                logger.info("1. Manually solve the reCAPTCHA in the browser")
                                logger.info("2. Configure 2Captcha API: https://2captcha.com")
                                logger.warning("⚠️ Continuing without solving - submission will likely fail")
                else:
                    logger.info("✅ No reCAPTCHA detected - proceeding to submit")
            except Exception as e:
                logger.debug(f"reCAPTCHA check error: {e}")
            
            # Submit form
            if _settings.DRY_RUN:
                logger.info("=" * 80)
                logger.info("🔵 DRY RUN MODE: Form filled but NOT submitting")
                logger.info("📋 REVIEW THE BROWSER NOW - You have 30 seconds to inspect the form!")
                logger.info("   Check: First Name, Last Name, Email, Phone, Resume attached")
                logger.info("=" * 80)
                csv_tracker.update_job_status('insight_global', job_url, 'dry_run',
                                            attempts_inc=1, last_error='')
                time.sleep(30)  # Give 30 seconds to review the filled form
                return True
            else:
                try:
                    logger.info("\n" + "=" * 60)
                    logger.info("ATTEMPTING TO SUBMIT APPLICATION")
                    logger.info("=" * 60)
                    
                    # Try multiple submit button selectors (input and button types)
                    submit_selectors = [
                        "#ContentPlaceHolder1_cmdApply",  # Specific ID for Insight Global
                        "input[type='submit']",
                        "button[type='submit']",
                        "input[value*='Apply']",
                        "button[value*='Apply']"
                    ]
                    
                    submit_btn = None
                    for selector in submit_selectors:
                        try:
                            submit_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                            if submit_btn:
                                logger.info(f"✅ Found submit button with selector: {selector}")
                                break
                        except Exception:
                            continue
                    
                    if not submit_btn:
                        logger.error("❌ Could not find submit button with any selector")
                        csv_tracker.update_job_status('insight_global', job_url, 'failed',
                                                    attempts_inc=1, last_error='Submit button not found')
                        return False
                    
                    # Scroll button into view
                    logger.info("🔄 Scrolling submit button into view...")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", submit_btn)
                    time.sleep(1)
                    
                    # Wait for button to be clickable (in case it's disabled)
                    logger.info("⏳ Waiting for button to be enabled...")
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, submit_selectors[0]))
                        )
                        logger.info("✅ Button is enabled and clickable")
                    except Exception as e:
                        logger.warning(f"⚠️ Timeout waiting for button to be clickable: {e}")
                        logger.info("Attempting to click anyway...")
                    
                    # Try multiple click methods
                    clicked = False
                    
                    # Method 1: Normal Selenium click
                    try:
                        logger.info("🔄 Attempting normal click...")
                        submit_btn.click()
                        clicked = True
                        logger.info("✅ Normal click successful")
                    except Exception as e:
                        logger.warning(f"⚠️ Normal click failed: {e}")
                    
                    # Method 2: JavaScript click
                    if not clicked:
                        try:
                            logger.info("🔄 Attempting JavaScript click...")
                            self.driver.execute_script("arguments[0].click();", submit_btn)
                            clicked = True
                            logger.info("✅ JavaScript click successful")
                        except Exception as e:
                            logger.warning(f"⚠️ JavaScript click failed: {e}")
                    
                    # Method 3: Submit the form directly
                    if not clicked:
                        try:
                            logger.info("🔄 Attempting to submit form directly...")
                            self.driver.execute_script("arguments[0].form.submit();", submit_btn)
                            clicked = True
                            logger.info("✅ Form submitted directly")
                        except Exception as e:
                            logger.warning(f"⚠️ Direct form submit failed: {e}")
                    
                    if not clicked:
                        logger.error("❌ All click methods failed!")
                        csv_tracker.update_job_status('insight_global', job_url, 'failed',
                                                    attempts_inc=1, last_error='Failed to click submit button')
                        return False
                    
                    logger.info("=" * 60)
                    logger.info("✅ SUBMITTED APPLICATION!")
                    logger.info("=" * 60 + "\n")
                    
                    csv_tracker.update_job_status('insight_global', job_url, 'applied',
                                                attempts_inc=1, last_error='')
                    guards.increment_counter()
                    time.sleep(2)
                    return True
                    
                except Exception as e:
                    logger.error(f"❌ Failed to submit form: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    csv_tracker.update_job_status('insight_global', job_url, 'failed',
                                                attempts_inc=1, last_error=f'Submit failed: {e}')
                    return False
                    
        except Exception as e:
            logger.error(f"Error during application process: {e}")
            csv_tracker.update_job_status('insight_global', job_url, 'failed',
                                        attempts_inc=1, last_error=str(e))
            return False
    
    def find_jobs(self):
        """Search for jobs using JSON configuration"""
        if not self.config_data:
            logger.error("No configuration data available")
            return []
        
        search = self.config_data.get('search', {})
        keyword = search.get('keyword', 'aiml')
        location = search.get('location', 'chicago')
        distance = search.get('distance', 50)
        
        logger.info(f"Starting job search with: keyword='{keyword}', location='{location}', distance={distance}")
        
        job_urls = self._search_jobs(keyword, location, distance)
        return [{'job_url': url} for url in job_urls]
    
    def apply(self, listing):
        """Apply to a single job listing"""
        job_url = listing.get('job_url') if isinstance(listing, dict) else getattr(listing, 'job_url', None)
        
        if not job_url:
            logger.error("No job URL provided")
            return False
        
        return self._apply_to_job(job_url)
    
    def run_search_and_apply(self):
        """
        Main entry point:
        1. Search for jobs
        2. Apply to each one
        """
        from config.settings import settings as _settings
        
        logger.info("=" * 80)
        logger.info("STARTING JOB APPLICATION ENGINE")
        logger.info("=" * 80)
        
        if _settings.DRY_RUN:
            logger.info("🔵 MODE: DRY RUN (forms will be filled but NOT submitted)")
        else:
            logger.info("🟢 MODE: LIVE (applications WILL be submitted)")
        
        # Search for jobs
        jobs = self.find_jobs()
        
        if not jobs:
            logger.info("No jobs found")
            return 0
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"Found {len(jobs)} jobs - starting application process")
        logger.info(f"{'=' * 80}\n")
        
        # Apply to each job
        applied_count = 0
        for i, job in enumerate(jobs, 1):
            logger.info(f"\n--- Processing job {i}/{len(jobs)} ---")
            
            success = self.apply(job)
            if success:
                applied_count += 1
            
            # Cooldown between applications
            if i < len(jobs):
                cooldown = _settings.SUBMISSION_COOLDOWN_SECONDS
                logger.info(f"Waiting {cooldown} seconds before next job...")
                time.sleep(cooldown)
        
        logger.info(f"\n{'=' * 80}")
        logger.info(f"APPLICATION RUN COMPLETE")
        logger.info(f"Successfully processed: {applied_count}/{len(jobs)} jobs")
        logger.info(f"{'=' * 80}\n")
        
        return applied_count
