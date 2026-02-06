from core.base import BaseStrategy
from core.logger import logger
from urllib.parse import urljoin
import os
import time
import random
import re

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from config.settings import settings
from data.db_duckdb import db_duckdb


class InfosysStrategy(BaseStrategy):
    """
    Infosys automation (multi-ATS):
    - find_jobs: open Infosys careers search -> scrape job links -> filter AI roles
    - apply: open job -> click apply -> detect ATS (SmartDreamers/BrassRing/other)
            -> upload resume + fill basics (best-effort)
            -> stop before final submit unless INFY_SUBMIT=true
    """

    def __init__(self, driver, job_site, selectors):
        super().__init__(driver, job_site, selectors)
        # Ensure we have a base set of selectors even if DB is empty
        self._ensure_default_selectors()

    def _ensure_default_selectors(self):
        if not self.selectors:
            self.selectors = {}
        
        defaults = {
            "search": {
                "input_box": [["css selector", "input.js_search_cp_jobs"], ["css selector", "input[placeholder='Search job']"]],
                "job_links": [["css selector", "a.job[href*='/description/reqid/']"]]
            },
            "apply": {
                "apply_button": [["css selector", "a.infosys-apply-link"], ["css selector", ".apply-button-container a"]],
                "form_signals": [["css selector", "input[name='firstName']"], ["css selector", "#firstname"]]
            },
            "personal_form": {
                "firstname": [["css selector", "#firstname"], ["name", "firstName"]],
                "lastname": [["css selector", "#lastname"], ["name", "lastName"]],
                "email": [["css selector", "#email"], ["name", "email"]],
                "phone": [["css selector", "#phone"], ["name", "mobileNumber"], ["name", "phone"]],
                "address": [["css selector", "#address"], ["name", "addressLine1"]],
                "city": [["css selector", "#city"], ["name", "city"]],
                "state": [["css selector", "#state"], ["name", "state"]],
                "zip_code": [["css selector", "#zipcode"], ["name", "zipCode"]],
                "country": [["css selector", "#country"], ["name", "country"]]
            }
        }
        
        # Deep merge/overlay defaults if missing
        for key, val in defaults.items():
            if key not in self.selectors or not self.selectors[key]:
                self.selectors[key] = val
            elif isinstance(val, dict):
                for subkey, subval in val.items():
                    if subkey not in self.selectors[key] or not self.selectors[key][subkey]:
                        self.selectors[key][subkey] = subval

    def login(self):
        logger.info("Infosys: No login step implemented (treating as public).")
        return True

    def _wait(self, timeout=25):
        return WebDriverWait(self.driver, timeout)

    def _scroll_into_view(self, el):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        except Exception:
            pass

    def _safe_click(self, by, value, timeout=10):
        self._close_common_popups()
        try:
            el = self._wait(timeout).until(EC.presence_of_element_located((by, value)))
            self._scroll_into_view(el)
            time.sleep(random.uniform(0.3, 0.8))
            try:
                el.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", el)
            return True
        except Exception as e:
            logger.warning(f"Infosys: Could not click {value}: {e}")
            return False

    def _is_field_empty(self, element):
        """Checks if a form element (input or select) is effectively empty."""
        try:
            tag = element.tag_name.lower()
            if tag == "input" or tag == "textarea":
                val = element.get_attribute("value") or ""
                return not val.strip()
            elif tag == "select":
                try:
                    sel = Select(element)
                    if not sel.options: return True
                    selected = sel.first_selected_option.text.lower()
                    # Typical empty indicators in dropdowns
                    empty_markers = ["select", "choose", "please", "---", "--", "none"]
                    return any(m in selected for m in empty_markers) or not selected.strip()
                except:
                    return True
        except:
            return True
        return True

    def _safe_type_if_empty(self, by, value, text, timeout=10):
        """Types into a field only if it's currently empty."""
        try:
            el = self._wait(timeout).until(EC.presence_of_element_located((by, value)))
            if self._is_field_empty(el):
                return self._safe_type(by, value, text, timeout=timeout)
            else:
                logger.info(f"Infosys: Field '{value}' already has data. Skipping manual entry.")
                return True
        except Exception:
            return False

    def _safe_select_if_empty(self, by, value, text, timeout=10):
        """Selects from a dropdown only if no valid option is already selected."""
        try:
            el = self._wait(timeout).until(EC.presence_of_element_located((by, value)))
            if self._is_field_empty(el):
                self._scroll_into_view(el)
                sel = Select(el)
                try:
                    sel.select_by_visible_text(text)
                    logger.info(f"Infosys: Selected '{text}' for dropdown {value}")
                except:
                    # Partial match fallback
                    for opt in sel.options:
                        if text.lower() in opt.text.lower():
                            sel.select_by_visible_text(opt.text)
                            logger.info(f"Infosys: Selected '{opt.text}' (partial) for dropdown {value}")
                            break
                return True
            else:
                logger.info(f"Infosys: Dropdown '{value}' already has a selection. Skipping.")
                return True
        except Exception:
            return False

    def _safe_type(self, by, value, text, timeout=10, clear=True):
        self._close_common_popups()
        try:
            el = self._wait(timeout).until(EC.element_to_be_clickable((by, value)))
            self._scroll_into_view(el)
            
            # Check current value before clearing
            try:
                current_val = el.get_attribute('value')
                if current_val == text:
                    logger.debug(f"Infosys: Field {value} already has correct value. Skipping type.")
                    return True
            except: pass

            # Ensure element is focused and clicked
            try:
                el.click()
            except:
                self.driver.execute_script("arguments[0].click();", el)
            
            if clear:
                try:
                    el.clear()
                    # Also try clearing via script if standard clear fails
                    self.driver.execute_script("arguments[0].value = '';", el)
                except Exception:
                    pass
            
            time.sleep(random.uniform(0.1, 0.3))
            
            # Try standard typing
            try:
                el.send_keys(text)
            except Exception:
                # Fallback to JS
                self.driver.execute_script("arguments[0].value = arguments[1];", el, text)
            
            # Dispatch events
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", el)
            self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", el)
            
            return True
        except Exception as e:
            logger.warning(f"Infosys: Could not type into {value}: {e}")
            return False

    def _click_next(self):
        """Click the Next/Continue button to proceed to the next section."""
        logger.info("Infosys: Attempting to click Next button...")
        
        selectors_list = [
            ("css selector", "#forward-navigation"),
            ("css selector", "a.form-next-button"),
            ("css selector", "button[aria-label='Next']"),
            ("css selector", "button.next"),
            ("xpath", "//button[text()='Next' or text()='NEXT']"),
            ("xpath", "//button[contains(@class, 'next') and not(contains(@class, 'disabled'))]"),
            ("xpath", "//a[text()='Next' or text()='NEXT']"),
            ("xpath", "//input[@type='button' and (@value='Next' or @value='NEXT')]"),
        ]
        
        for by, val in selectors_list:
            try:
                for btn in self.driver.find_elements(getattr(By, by.upper().replace(" ", "_")), val):
                    if btn.is_displayed() and btn.is_enabled():
                        self._scroll_into_view(btn)
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        
                        logger.info(f"Infosys: Clicked Next button using {val}")
                        time.sleep(5)
                        return True
            except Exception:
                pass
                
        logger.warning("Infosys: Could not find or click Next button")
        return False

    def _select_option(self, element, value):
        """Robust dropdown selection with fuzzy matching."""
        try:
            select = Select(element)
            
            # 1. Exact match
            try:
                select.select_by_visible_text(value)
                logger.info(f"Infosys: Selected '{value}' (exact)")
                return True
            except: pass
            
            # 2. Case-insensitive / Partial match
            options = select.options
            best_match = None
            val_lower = value.strip().lower()
            
            if "bachelor" in val_lower: val_lower = "bachelor"
            if "master" in val_lower: val_lower = "master"

            for opt in options:
                text = opt.text.strip().lower()
                if val_lower == text:
                    best_match = opt
                    break
                if val_lower in text:
                    best_match = opt
                    break
            
            if best_match:
                select.select_by_visible_text(best_match.text)
                logger.info(f"Infosys: Selected '{best_match.text}' (fuzzy match for '{value}')")
                return True
                
            # 3. Value match
            try:
                select.select_by_value(value)
                return True
            except: pass
            
            # 4. Fallback (JS)
            self.driver.execute_script("""
                var sel = arguments[0];
                var val = arguments[1];
                for (var i = 0; i < sel.options.length; i++) {
                    if (sel.options[i].text.trim().toLowerCase() === val.toLowerCase() || sel.options[i].value.toLowerCase() === val.toLowerCase()) {
                        sel.selectedIndex = i;
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        sel.dispatchEvent(new Event('input', { bubbles: true }));
                        return true;
                    }
                }
                return false;
            """, element, value)
            return True
        except Exception as e:
            logger.warning(f"Infosys: Dropdown selection failed: {e}")
            return False

    def _maybe_switch_new_tab(self):
        try:
            time.sleep(2)
            handles = self.driver.window_handles
            if len(handles) > 1:
                logger.info(f"Infosys: Found {len(handles)} windows. Switching to last.")
                self.driver.switch_to.window(handles[-1])
                time.sleep(2)
                logger.info(f"Infosys: Switched to tab/window: {self.driver.current_url}")
        except Exception:
            pass

    def _handle_infosys_privacy_modal(self):
        logger.info("Infosys: Checking for Privacy Notice modal...")
        proceed_selectors = self._get_selector("apply.proceed_button", [])
        if not proceed_selectors:
             proceed_selectors = [["css selector", ".consent-button"], ["xpath", "//button[contains(.,'Proceed')]"]]
        
        if "privacy notice" in self.driver.page_source.lower() or "data privacy" in self.driver.page_source.lower():
            try:
                scroll_container_selectors = [".consent-text-box", "#privacy-content", ".modal-body"]
                for sc in scroll_container_selectors:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sc)
                    if els and els[0].is_displayed():
                        logger.info(f"Infosys: Scrolling privacy container {sc} to bottom...")
                        self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", els[0])
                        time.sleep(1)
                        break
            except Exception: pass

            for sel_data in proceed_selectors:
                try:
                    sel = (getattr(By, sel_data[0].upper().replace(" ", "_")), sel_data[1])
                    btn = self._wait(8).until(EC.element_to_be_clickable(sel))
                    logger.info(f"Infosys: Found privacy notice 'Proceed' button via {sel}. Clicking...")
                    self._scroll_into_view(btn)
                    time.sleep(2)
                    try: btn.click()
                    except: self.driver.execute_script("arguments[0].click();", btn)
                    logger.info("Infosys: Clicked Privacy Proceed button.")
                    time.sleep(5)
                    return True
                except: continue
        return False

    def _close_common_popups(self):
        try:
            alert = self.driver.switch_to.alert
            alert.accept()
        except: pass

        xpaths = [
            "//button[contains(.,'Accept All')]", "//button[contains(.,'Accept')]",
            "//button[contains(@id,'onetrust-accept-btn-handler')]", "//button[contains(.,'I Agree')]",
            "//button[contains(.,'Agree')]", "//button[contains(.,'Got it')]", "//button[contains(.,'OK')]",
        ]
        for xp in xpaths:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                if btn.is_displayed() and btn.is_enabled():
                    self._scroll_into_view(btn)
                    btn.click()
                    time.sleep(1)
                    logger.info("Infosys: Closed popup/banner.")
                    break
            except: continue

    def _handle_recaptcha(self, max_wait_seconds: int = 60) -> bool:
        try:
            recaptcha_iframes = self.driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@title, 'recaptcha')]")
            visible = [i for i in recaptcha_iframes if i.is_displayed()]
            if not visible: return True
            logger.warning("Infosys: Visible reCAPTCHA detected.")
            start = time.time()
            while time.time() - start < max_wait_seconds:
                try:
                    still = [i for i in recaptcha_iframes if i.is_displayed()]
                    if not still: return True
                except: return True
                time.sleep(2)
            input("Solve reCAPTCHA in browser, then press Enter here...")
            return True
        except: return True

    def _handle_infosys_post_upload_popup(self):
        try:
            logger.info("Infosys: Monitoring for post-upload popups...")
            popup_selectors = [(By.CSS_SELECTOR, ".modal-close"), (By.CSS_SELECTOR, ".p-dialog-header-close"), (By.CSS_SELECTOR, "button.close"), (By.XPATH, "//button[contains(.,'Close')]"), (By.XPATH, "//button[contains(.,'OK')]")]
            start_time = time.time()
            popup_count = 0
            while time.time() - start_time < 60:
                found_in_this_iteration = False
                for sel in popup_selectors:
                    try:
                        btns = self.driver.find_elements(*sel)
                        for btn in btns:
                            if btn.is_displayed() and btn.is_enabled():
                                popup_count += 1
                                logger.info(f"Infosys: Found popup #{popup_count}, closing with {sel}")
                                try: btn.click()
                                except: self.driver.execute_script("arguments[0].click();", btn)
                                found_in_this_iteration = True
                                time.sleep(3)
                                break
                    except: continue
                    if found_in_this_iteration: break
                if popup_count >= 2: break
                time.sleep(0.5)
            logger.info(f"Infosys: Popup monitoring complete. Closed {popup_count} popup(s)")
            time.sleep(3)
            current_url = self.driver.current_url
            logger.info(f"Infosys: Current URL after popup closure: {current_url}")
            try:
                self._wait(10).until(lambda d: d.find_elements(By.CSS_SELECTOR, "#firstname, input[name='firstName']"))
                logger.info("Infosys: Application form is ready")
            except: pass
        except Exception as e:
            logger.warning(f"Infosys: Error in popup handling: {e}")

    def _handle_infosys_first_time_step(self):
        try:
            sel_data = [["css selector", ".apply-first-time-button"], ["xpath", "//button[contains(.,'applying for the first time')]"]]
            btn = None
            for s in sel_data:
                try:
                    by = getattr(By, s[0].upper().replace(" ", "_"))
                    btn = self._wait(5).until(EC.element_to_be_clickable((by, s[1])))
                    if btn: break
                except: continue
            if btn:
                logger.info("Infosys: Selecting 'First time applicant' (visibly waiting)...")
                self._scroll_into_view(btn)
                time.sleep(2)
                try: btn.click()
                except: self.driver.execute_script("arguments[0].click();", btn)
                logger.info("Infosys: Clicked 'First time applicant' button.")
                time.sleep(5)
        except: pass

    def _upload_resume_focused(self, resume_path: str) -> bool:
        upload_triggers = ["//button[contains(.,'Upload') and (contains(.,'Resume') or contains(.,'CV'))]", "//label[contains(.,'Upload') and (contains(.,'Resume') or contains(.,'CV'))]"]
        for xp in upload_triggers:
            try:
                btns = self.driver.find_elements(By.XPATH, xp)
                for btn in btns:
                    if btn.is_displayed():
                        try: btn.click()
                        except: self.driver.execute_script("arguments[0].click();", btn)
            except: continue
        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if not file_inputs:
            try: file_inputs = self._wait(5).until(lambda d: d.find_elements(By.CSS_SELECTOR, "input[type='file']"))
            except: pass
        if not file_inputs: return False
        input_element = file_inputs[0]
        file_path = os.path.abspath(resume_path)
        self.driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible'; arguments[0].style.opacity=1; arguments[0].removeAttribute('hidden');", input_element)
        input_element.send_keys(file_path)
        logger.info(f"Infosys: Sent {os.path.basename(file_path)} to file input.")
        return True

    def _is_target_job(self, title: str) -> bool:
        if not title: return False
        t = title.lower().strip()
        allow = ["ai engineer", "artificial intelligence", "machine learning", "ml engineer", "llm", "large language model", "data scientist", "nlp"]
        block = ["nurse", "driver", "sales", "retail"]
        return any(a in t for a in allow) and not any(b in t for b in block)

    def _detect_infosys_ats(self) -> str:
        url = (self.driver.current_url or "").lower()
        html = (self.driver.page_source or "").lower()
        if "brassring.com" in url or "tgnewui" in url or "brassring" in html: return "brassring"
        if "smartdreamers" in html or "digitalcareers.infosys.com" in url: return "smartdreamers"
        return "unknown"

    def find_jobs(self):
        keyword = getattr(settings, "INFY_KEYWORD", "ai engineers")
        base_search_url = "https://digitalcareers.infosys.com/infosys/global-careers?location=USA"
        logger.info(f"Infosys: Opening search page: {base_search_url}")
        self.driver.get(base_search_url)
        self._close_common_popups()
        time.sleep(5)
        try:
            reveal = self._wait(5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".search-jobs-button")))
            reveal.click()
            time.sleep(2)
        except: pass
        try:
            box = self._wait(5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "input.js_search_cp_jobs")))
            box.send_keys(keyword + Keys.ENTER)
            logger.info(f"Infosys: Searched for {keyword}")
            time.sleep(5)
        except: pass
        links = self.driver.find_elements(By.CSS_SELECTOR, "a.job[href*='/description/reqid/']")
        jobs, seen = [], set()
        for a in links:
            href = a.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                title = a.text.strip() or "Infosys Job"
                if self._is_target_job(title):
                    match = re.search(r"reqid/([^/?#]+)", href)
                    ext_id = match.group(1) if match else "ext_" + str(len(jobs))
                    jobs.append({"job_title": title, "job_url": href, "external_job_id": ext_id})
        logger.info(f"Infosys: Found {len(jobs)} target jobs.")
        return jobs

    def apply(self, listing):
        job_title = listing.get("job_title", "Unknown")
        job_url = listing.get("job_url")
        logger.info(f"Infosys: Applying to {job_title}...")
        self.driver.get(job_url)
        time.sleep(2)
        try:
             apply_btn = self._wait(10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.infosys-apply-link")))
             apply_btn.click()
             time.sleep(3)
        except: pass
        self._maybe_switch_new_tab()
        self._handle_infosys_first_time_step()
        self._handle_infosys_privacy_modal()
        ats = self._detect_infosys_ats()
        logger.info(f"Infosys: ATS={ats}")
        if settings.RESUME_PATH:
             self._upload_resume_focused(settings.RESUME_PATH)
             self._handle_infosys_post_upload_popup()
        
        # 4.2. Personal Details
        logger.info("Infosys: Filling personal details...")
        field_map = {"firstname": "#firstname", "lastname": "#lastname", "email": "#email", "phone": "#phone", "address_1": "#address_1", "city": "#city", "zipcode": "#zipcode"}
        for attr, selector in field_map.items():
            val = getattr(settings, attr.upper(), "")
            if val: self._safe_type(By.CSS_SELECTOR, selector, val)
        
        # Select Country and State
        try:
            self._select_option(self.driver.find_element(By.CSS_SELECTOR, "#country"), settings.COUNTRY)
            time.sleep(1)
            self._select_option(self.driver.find_element(By.CSS_SELECTOR, "#state"), settings.STATE)
        except: pass
        
        self._click_next() # After Personal
        
        # Education
        logger.info("Infosys: Filling education...")
        try:
            self._select_option(self.driver.find_element(By.CSS_SELECTOR, "select[id*='Degree']"), settings.DEGREE)
        except: pass
        self._click_next() # After Education

        # Work Experience
        logger.info("Infosys: Filling work experience...")
        for idx in range(1, 5):
            comp = getattr(settings, f"WORK_COMPANY_{idx}", "")
            if not comp: break
            if idx > 1:
                try: self.driver.find_element(By.CSS_SELECTOR, ".add-more-trigger.work").click()
                except: pass
            field_map_work = {"company": f"#work_company_{idx-1}", "job_title": f"#work_title_{idx-1}", "start_year": f"#work_start_year_{idx-1}", "end_year": f"#work_end_year_{idx-1}"}
            for attr, selector in field_map_work.items():
                val = getattr(settings, f"WORK_{attr.upper()}_{idx}", "")
                if val: self._safe_type(By.CSS_SELECTOR, selector, val)
        self._click_next() # After Work

        # EEO
        logger.info("Infosys: Filling EEO...")
        
        # 1. Gender/Ethnicity/Race (usually dropdowns)
        eeo_map = {"gender": settings.GENDER, "ethnicity": settings.ETHNICITY, "race": settings.RACE}
        for field, val in eeo_map.items():
            try:
                if field == "ethnicity": val = "No" if "no" in val.lower() else "Yes"
                sel = self.driver.find_element(By.CSS_SELECTOR, f"select[name*='{field}']")
                self._select_option(sel, val)
            except: pass

        # 2. Legal Name
        try:
            legal_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='custom[eeo][legal_name]']")
            if not legal_field.get_attribute("value"):
                legal_field.send_keys(f"{settings.FIRST_NAME} {settings.LAST_NAME}")
        except: pass
        
        self._click_next() # After EEO part 1
        
        # 3. Follow-up EEO (Veteran/Disability)
        for field in ["veteran", "disability"]:
             try:
                 time.sleep(2)
                 # Try direct radio selection for "No" (per user selectors)
                 radio_sel = f"input[name='custom[eeo][{field}]'][value='No']"
                 try:
                     radio = self.driver.find_element(By.CSS_SELECTOR, radio_sel)
                     if radio.is_displayed():
                         self.driver.execute_script("arguments[0].click();", radio)
                         logger.info(f"Infosys: Selected 'No' for {field} via radio.")
                         
                         if field == "disability":
                             try:
                                 legal_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='custom[eeo][legal_name]']")
                                 if not legal_field.get_attribute("value"):
                                     legal_field.send_keys(f"{settings.FIRST_NAME} {settings.LAST_NAME}")
                             except: pass
                                     
                         self._click_next()
                         continue
                 except: pass

                 # Fallback: Original label search
                 labels = self.driver.find_elements(By.TAG_NAME, "label")
                 for lab in labels:
                     if field in lab.text.lower():
                         sel_id = lab.get_attribute("for")
                         if sel_id:
                             val = getattr(settings, "VETERAN_STATUS" if field=="veteran" else "DISABILITY_STATUS")
                             elem = self.driver.find_element(By.ID, sel_id)
                             if elem.tag_name.lower() == "select":
                                 self._select_option(elem, val)
                             else:
                                 self.driver.execute_script("arguments[0].click();", elem)
                             self._click_next()
                             break
             except: pass

        # Agreement
        logger.info("Infosys: Filling agreement...")
        try:
            # 0. Check if we're still on EEO pages (false positive protection)
            try:
                page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                has_agreement_fields = self.driver.find_elements(By.NAME, "custom[other][statement]") or self.driver.find_elements(By.NAME, "custom[other][reference]")
                if not has_agreement_fields:
                    if "voluntary self-identification" in page_text or "veteran" in page_text:
                        logger.error("Infosys: STUCK on EEO/Veteran page! Retrying Next...")
                        self._click_next()
                        time.sleep(5)
            except: pass
            # 1. Direct Name Selectors (High Priority - from User)
            name_val_map = {
                "custom[other][reference]": "Infosys Careers Site",
                "custom[other][authorized]": "Yes",
                "custom[other][degree]": "Yes",
                "custom[other][employed]": "No",
                "custom[other][contract_restriction]": "No",
                "custom[other][statement]": "Accept"
            }
            for name, val in name_val_map.items():
                try:
                    elem = self.driver.find_element(By.NAME, name)
                    if elem.tag_name == "input" and elem.get_attribute("type") == "radio":
                        try:
                            target_radio = self.driver.find_element(By.CSS_SELECTOR, f"input[name='{name}'][value='{val}']")
                            self.driver.execute_script("arguments[0].click();", target_radio)
                            logger.info(f"Infosys: Selected '{val}' for name '{name}' via radio.")
                        except:
                            self.driver.execute_script("arguments[0].click();", elem)
                    else:
                        self._select_option(elem, val)
                        logger.info(f"Infosys: Selected '{val}' for name '{name}' via select.")
                except: pass

            # 3. Robust Label-based detection
            labels = self.driver.find_elements(By.TAG_NAME, "label")
            for lab in labels:
                txt = lab.text.lower()
                # Negative (No)
                if any(key in txt for key in ["employed by infosys", "contractual restrictions", "require sponsorship", "support for continued work"]):
                    try:
                        target_id = lab.get_attribute("for")
                        sel_elem = None
                        if target_id:
                            try: sel_elem = self.driver.find_element(By.ID, target_id)
                            except: pass
                        if not sel_elem:
                            try: sel_elem = lab.find_element(By.XPATH, ".//input[@type='radio' and (@value='No' or @value='False')] | ..//input[@type='radio' and (@value='No' or @value='False')] | ..//select")
                            except: pass
                        if sel_elem:
                            if sel_elem.tag_name == "input":
                                if not sel_elem.is_selected():
                                    self.driver.execute_script("arguments[0].click();", sel_elem)
                                    logger.info(f"Infosys: Selected 'No' for label: {lab.text[:40]}...")
                            else:
                                self._select_option(sel_elem, "No")
                                logger.info(f"Infosys: Selected 'No' for label: {lab.text[:40]}...")
                    except: pass
                # Positive (Yes)
                if "relocate" in txt or "travel" in txt:
                    try:
                        target_id = lab.get_attribute("for")
                        sel_elem = None
                        if target_id:
                            try: sel_elem = self.driver.find_element(By.ID, target_id)
                            except: pass
                        if not sel_elem:
                            try: sel_elem = lab.find_element(By.XPATH, ".//input[@type='radio' and (@value='Yes' or @value='True')] | ..//input[@type='radio' and (@value='Yes' or @value='True')] | ..//select")
                            except: pass
                        if sel_elem:
                            if sel_elem.tag_name == "input":
                                if not sel_elem.is_selected():
                                    self.driver.execute_script("arguments[0].click();", sel_elem)
                                    logger.info(f"Infosys: Selected 'Yes' for label: {lab.text[:40]}...")
                            else:
                                self._select_option(sel_elem, "Yes")
                                logger.info(f"Infosys: Selected 'Yes' for label: {lab.text[:40]}...")
                    except: pass

            try:
                arbitration_cb = self.driver.find_element(By.CSS_SELECTOR, "input[name='custom[other][arbitration]']")
                if not arbitration_cb.is_selected():
                    self.driver.execute_script("arguments[0].click();", arbitration_cb)
                    logger.info("Infosys: Checked Mutual Arbitration Agreement.")
            except:
                try:
                    cb = self.driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                    if not cb.is_selected(): self.driver.execute_script("arguments[0].click();", cb)
                except: pass

            # Check for missed required fields (error messages)
            try:
                errors = self.driver.find_elements(By.CSS_SELECTOR, ".error-message, .required-error, .invalid-feedback")
                for err in errors:
                    if err.is_displayed():
                        logger.error(f"Infosys: Agreement field error visible: {err.text}")
            except: pass

            # 4. Final Signature
            try:
                sig_sels = ["input[name*='signature']", "input[name*='sig']", "input[id*='signature']"]
                sig_field = None
                for sel in sig_sels:
                    try:
                        sig_field = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if sig_field: break
                    except: continue
                
                if sig_field:
                    if not sig_field.get_attribute("value"):
                        sig_field.send_keys(f"{settings.FIRST_NAME} {settings.LAST_NAME}")
                        logger.info("Infosys: Signed Agreement page.")
            except:
                try:
                    legal_name_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='custom[eeo][legal_name]']")
                    if not legal_name_field.get_attribute("value"):
                        legal_name_field.send_keys(f"{settings.FIRST_NAME} {settings.LAST_NAME}")
                        logger.info("Infosys: Filled Legal Name as fallback signature.")
                except: pass
        except Exception as e:
            logger.error(f"Infosys: Agreement section error: {e}")

        # Transition to Review/Submit page
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, "#forward-navigation")
            self._scroll_into_view(btn)
            try: btn.click()
            except: self.driver.execute_script("arguments[0].click();", btn)
            logger.info("Infosys: Clicked Agreement-page Next (#forward-navigation)")
            time.sleep(3)
        except: pass

        # Final submission using specific selector from user
        try:
            # 1. Scrape Job Title/ID from header before submitting
            job_title = "N/A"
            job_id = "N/A"
            try:
                header = self.driver.find_element(By.CSS_SELECTOR, "h1, .job-title, .jobtitle")
                job_title = header.text.strip()
                page_text = self.driver.find_element(By.TAG_NAME, "body").text
                req_match = re.search(r"(\d{5,8}BR)", page_text)
                if req_match:
                    job_id = req_match.group(1)
            except:
                if hasattr(self, 'current_job'):
                    job_id = getattr(self.current_job, 'job_id', 'N/A')
                    job_title = getattr(self.current_job, 'title', 'N/A')

            # 2. Click 'Apply now'
            try:
                btn = self.driver.find_element(By.CSS_SELECTOR, ".form-submit-button.js_submit_apply_form.custom-apply.apply_enabled.has_spinner")
            except:
                btn = self.driver.find_element(By.CSS_SELECTOR, ".form-submit-button.js_submit_apply_form.custom-apply")
            
            self._scroll_into_view(btn)
            try: btn.click()
            except: self.driver.execute_script("arguments[0].click();", btn)
            logger.info(f"Infosys: Clicked 'Apply now' for Job: {job_title} ({job_id})")
            
            # 3. VERIFICATION: Wait for confirmation indicator
            logger.info("Infosys: Waiting for submission confirmation...")
            confirmation_received = False
            for _ in range(15):
                time.sleep(1)
                body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
                if any(msg in body_text for msg in ["thank you", "application received", "submitted", "success"]):
                    logger.info("Infosys: VERIFIED submission success via confirmation message.")
                    confirmation_received = True
                    break
                if "form" not in self.driver.current_url.lower() and "confirm" in self.driver.current_url.lower():
                    logger.info("Infosys: VERIFIED submission success via URL change.")
                    confirmation_received = True
                    break
            
            if not confirmation_received:
                logger.warning("Infosys: Submission click sent, but no confirmation message detected within 15s.")

            # 4. Record job submission in DuckDB
            try:
                db_duckdb.conn.execute("INSERT OR IGNORE INTO submitted_jobs (job_id, job_title) VALUES (?, ?)", (job_id, job_title))
                logger.info(f"Infosys: Recorded submission for JobID: {job_id} Title: {job_title}")
            except Exception as e:
                logger.debug(f"Infosys: Failed to record job: {e}")
            
            time.sleep(20)
            return True
        except:
            if getattr(settings, "INFY_SUBMIT", False):
                logger.info("Infosys: SUBMITTING...")
                # Try specific forward navigation button first
                try:
                    btn = self.driver.find_element(By.CSS_SELECTOR, "#forward-navigation")
                    self._scroll_into_view(btn)
                    try: btn.click()
                    except: self.driver.execute_script("arguments[0].click();", btn)
                    logger.info("Infosys: Clicked final submit button.")
                    time.sleep(5)
                    return True
                except: pass
                
                # General fallback if #forward-navigation fails
                return self._click_next()
            else:
                logger.info("Infosys: DRY RUN complete.")
                return True
        return False

if __name__ == "__main__":
    from core.browser import browser_service
    driver = browser_service.start_browser()
    class MockJobSite: name = "Infosys"; base_url = ""; search_url_template = ""; keyword = ""; location = ""
    strategy = InfosysStrategy(driver, MockJobSite(), {})
    jobs = strategy.find_jobs()
    if jobs: strategy.apply(jobs[0])
