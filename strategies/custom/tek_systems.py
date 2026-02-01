from strategies.base import BaseStrategy
from core.logger import logger
from urllib.parse import urljoin
import os
import time
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from config.settings import settings


class TekSystemsStrategy(BaseStrategy):
    """
    TEKsystems automation:
    - find_jobs: scrape job links (FILTERED: only AI Engineer roles)
    - apply: click Apply -> load form -> upload resume -> fill fields -> continue -> optional submit
    """

    # -------------------------
    # Core helpers
    # -------------------------
    def login(self):
        logger.info("TEKsystems: No login step implemented (treating as public).")
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
            time.sleep(random.uniform(0.3, 0.8))  # Human-like delay
            try:
                el.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", el)
            return True
        except Exception as e:
            logger.warning(f"TEKsystems: Could not click {value}: {e}")
            return False

    def _safe_type(self, by, value, text, timeout=10, clear=True):
        self._close_common_popups()
        try:
            el = self._wait(timeout).until(EC.presence_of_element_located((by, value)))
            self._scroll_into_view(el)
            if clear:
                try:
                    el.clear()
                except Exception:
                    pass
            time.sleep(random.uniform(0.2, 0.5))  # Human-like delay before typing
            try:
                # Type with slight delay for more human-like behavior
                for char in text:
                    el.send_keys(char)
                    if random.random() < 0.1:  # 10% chance of tiny pause
                        time.sleep(random.uniform(0.05, 0.15))
            except Exception:
                # JS fallback
                self.driver.execute_script("arguments[0].value = arguments[1];", el, text)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change', { bubbles: true }));", el)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", el)
            return True
        except Exception as e:
            logger.warning(f"TEKsystems: Could not type into {value}: {e}")
            return False

    def _xpath_literal(self, s: str) -> str:
        if "'" not in s:
            return f"'{s}'"
        if '"' not in s:
            return f'"{s}"'
        parts = s.split("'")
        return "concat(" + ",\"'\",".join([f"'{p}'" for p in parts]) + ")"

    def _maybe_switch_new_tab(self):
        try:
            handles = self.driver.window_handles
            if len(handles) > 1:
                logger.info(f"TEKsystems: Found {len(handles)} windows. Switching to last.")
                self.driver.switch_to.window(handles[-1])
                time.sleep(1)
                logger.info(f"TEKsystems: Switched to new tab/window: {self.driver.current_url}")
        except Exception as e:
            logger.warning(f"TEKsystems: Error during window switch: {e}")

    def _debug_dump(self, tag="debug"):
        """Save screenshot + html into /tmp for debugging stuck pages."""
        try:
            ts = int(time.time())
            screenshot_path = f"/tmp/teks_{tag}_{ts}.png"
            html_path = f"/tmp/teks_{tag}_{ts}.html"

            self.driver.save_screenshot(screenshot_path)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)

            logger.info(f"DEBUG DUMP screenshot: {screenshot_path}")
            logger.info(f"DEBUG DUMP html: {html_path}")
            logger.info(f"DEBUG URL: {self.driver.current_url}")
            logger.info(f"DEBUG TITLE: {self.driver.title}")
        except Exception as e:
            logger.warning(f"DEBUG DUMP failed: {e}")

    def _close_common_popups(self):
        """Close cookie/consent popups and handle unexpected alerts."""
        # 1. Handle Alert
        try:
            alert = self.driver.switch_to.alert
            txt = alert.text
            logger.warning(f"TEKsystems: Handling alert: {txt}")
            alert.accept()
        except Exception:
            pass

        # 2. Existing popup logic
        xpaths = [
            "//button[contains(.,'Accept')]",
            "//button[contains(.,'I Agree')]",
            "//button[contains(.,'Agree')]",
            "//button[contains(.,'Got it')]",
            "//button[contains(.,'OK')]",
        ]
        for xp in xpaths:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                if btn.is_displayed() and btn.is_enabled():
                    self._scroll_into_view(btn)
                    btn.click()
                    time.sleep(1)
                    logger.info("TEKsystems: Closed popup/banner.")
                    break
            except Exception:
                continue

    def _handle_recaptcha(self, max_wait_seconds: int = 60) -> bool:
        """Detect and handle reCAPTCHA challenges.
        
        Args:
            max_wait_seconds: Maximum time to wait for CAPTCHA completion
            
        Returns:
            True if CAPTCHA was handled or not present, False if failed
        """
        try:
            # Check for reCAPTCHA iframe
            recaptcha_iframes = self.driver.find_elements(By.XPATH, "//iframe[contains(@src, 'recaptcha') or contains(@title, 'recaptcha')]")
            
            if recaptcha_iframes:
                logger.warning("TEKsystems: reCAPTCHA detected on page")
                logger.info(f"TEKsystems: Waiting up to {max_wait_seconds}s for CAPTCHA completion...")
                
                # Wait for CAPTCHA to be solved (either automatically or manually)
                start_time = time.time()
                while time.time() - start_time < max_wait_seconds:
                    try:
                        # Check if CAPTCHA iframe is still present and visible
                        visible_captchas = [iframe for iframe in recaptcha_iframes if iframe.is_displayed()]
                        if not visible_captchas:
                            logger.info("TEKsystems: reCAPTCHA appears to be completed")
                            time.sleep(2)  # Wait a bit for any post-CAPTCHA processing
                            return True
                    except Exception:
                        # CAPTCHA might have been removed from DOM
                        logger.info("TEKsystems: reCAPTCHA no longer in DOM")
                        return True
                    
                    time.sleep(2)
                
                logger.warning(f"TEKsystems: reCAPTCHA still present after {max_wait_seconds}s")
                return False
            
            # No CAPTCHA detected
            return True
            
        except Exception as e:
            logger.warning(f"TEKsystems: Error checking for reCAPTCHA: {e}")
            return True  # Assume no CAPTCHA if detection fails

    # -------------------------
    # AI Engineer ONLY filter
    # -------------------------
    def _is_target_job(self, title: str) -> bool:
        """
        Returns True ONLY if the job title matches AI Engineer-type roles.
        Adjust allow/block lists to your preference.
        """
        if not title:
            return False
        t = title.lower().strip()

        allow = [
            "ai engineer",
            "artificial intelligence engineer",
            "machine learning",
            "ml engineer",
            "llm",
            "large language model",
            "data scientist",
            "data science",
            "nlp engineer",
            "natural language processing",
        ]

        block = [
            # Only block very unrelated sectors if needed
            "nurse", "driver", "sales", "retail",
        ]

        if any(a in t for a in allow):
            return True

        if any(b in t for b in block):
            return False
        return False

    # -------------------------
    # find_jobs (search + filter)
    # -------------------------
    def find_jobs(self):
        if not getattr(self.job_site, "search_url_template", None):
            logger.warning("TEKsystems: search_url_template missing in job_site config.")
            return []

        # Default to AI Engineer as core focus
        keyword = (getattr(self.job_site, "keyword", None) or "AI Engineer").strip()
        location = getattr(self.job_site, "location", None) or ""

        # Navigate to base search page (not pre-filled)
        base_search_url = "https://careers.teksystems.com/us/en/search-results"
        logger.info(f"TEKsystems: Navigating to search page: {base_search_url}")
        self.driver.get(base_search_url)
        self._close_common_popups()

        # Find and interact with search input to trigger autocomplete
        search_input_selectors = [
            (By.CSS_SELECTOR, "input[placeholder*='Search']"),
            (By.CSS_SELECTOR, "input[type='search']"),
            (By.CSS_SELECTOR, "input[aria-label*='Search']"),
            (By.XPATH, "//input[contains(@placeholder, 'keyword') or contains(@placeholder, 'search')]"),
        ]

        search_input = None
        for sel in search_input_selectors:
            try:
                search_input = self._wait(10).until(EC.presence_of_element_located(sel))
                logger.info(f"TEKsystems: Found search input using {sel}")
                break
            except Exception:
                continue

        if not search_input:
            logger.warning("TEKsystems: Could not find search input field")
            self._debug_dump("no_search_input")
            return []

        # Type keyword to trigger autocomplete
        try:
            self._scroll_into_view(search_input)
            search_input.clear()
            search_input.send_keys(keyword)
            logger.info(f"TEKsystems: Typed '{keyword}' into search box")
            time.sleep(3)  # Wait for autocomplete dropdown to appear
        except Exception as e:
            logger.warning(f"TEKsystems: Could not type into search input: {e}")
            return []

        # Capture autocomplete suggestions
        autocomplete_selectors = [
            (By.CSS_SELECTOR, "ul.autocomplete-results a"),
            (By.CSS_SELECTOR, ".autocomplete-dropdown a"),
            (By.CSS_SELECTOR, "[role='listbox'] a"),
            (By.XPATH, "//ul[contains(@class, 'autocomplete')]//a"),
            (By.XPATH, "//div[contains(@class, 'suggestions')]//a"),
        ]

        links = []
        for sel in autocomplete_selectors:
            try:
                self._wait(5).until(EC.presence_of_all_elements_located(sel))
                found = self.driver.find_elements(*sel)
                if found:
                    links = found
                    logger.info(f"TEKsystems: Found {len(links)} autocomplete suggestions using {sel}")
                    break
            except Exception:
                continue

        # If no autocomplete, try pressing Enter to search and get results
        if not links:
            logger.info("TEKsystems: No autocomplete results, trying Enter key search")
            try:
                search_input.send_keys(Keys.RETURN)
                time.sleep(3)
                
                # Now try to find job links on results page
                card_link_selectors = [
                    (By.CSS_SELECTOR, "a[href*='/en/job/']"),
                    (By.CSS_SELECTOR, "a[href*='/job/']"),
                    (By.CSS_SELECTOR, "a.au-target[href*='/job/']"),
                ]

                for sel in card_link_selectors:
                    try:
                        self._wait(15).until(EC.presence_of_all_elements_located(sel))
                        found = self.driver.find_elements(*sel)
                        if found:
                            links = found
                            logger.info(f"TEKsystems: Found {len(links)} job links using {sel}")
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"TEKsystems: Enter key search failed: {e}")

        if not links:
            logger.warning("TEKsystems: No job links found via autocomplete or search.")
            logger.info(f"TEKsystems: Current URL: {self.driver.current_url}")
            self._debug_dump("no_job_links")
            return []

        base_url = getattr(self.job_site, "base_url", None) or "https://www.teksystems.com"
        jobs, seen = [], set()

        for a in links:
            try:
                href = a.get_attribute("href")
                title = (a.text or "").strip()
                if not href:
                    continue

                full_url = href if href.startswith("http") else urljoin(base_url, href)
                if full_url in seen:
                    continue
                seen.add(full_url)

                if "/job/" not in full_url and "/en/job/" not in full_url:
                    continue

                if not title:
                    title = "TEKsystems Job"

                # ✅ FILTER: Only include AI Engineer-target roles
                if not self._is_target_job(title):
                    logger.info(f"TEKsystems: Skipping non-target job: {title}")
                    continue

                jobs.append({"job_title": title, "job_url": full_url})
            except Exception:
                continue

        logger.info(f"TEKsystems: Parsed {len(jobs)} AI-target job listings.")
        return jobs

    # -------------------------
    # After Apply: wait for form
    # -------------------------
    def _wait_for_application_form(self, old_url: str, pause_on_lock: bool = True) -> bool:
        time.sleep(1)
        self._close_common_popups()

        # Wait for URL change loosely
        try:
            logger.info("TEKsystems: Waiting for redirection/tab switch...")
            time.sleep(5)
            self._maybe_switch_new_tab()
            logger.info(f"TEKsystems: Post-Apply URL: {self.driver.current_url}")
        except Exception as e:
            logger.warning(f"TEKsystems: Could not access current_url/handles after Apply: {e}")

        # Signals that form exists
        form_signals = [
            (By.CSS_SELECTOR, "input[type='file']"),  # resume upload input
            (By.XPATH, "//input[@placeholder='First Name' or @aria-label='First Name']"),
            (By.XPATH, "//input[@placeholder='Email Address' or @type='email']"),
            (By.XPATH, "//input[@placeholder='Phone Number' or contains(@aria-label,'Phone')]"),
        ]

        for sel in form_signals:
            try:
                self._wait(12).until(EC.presence_of_element_located(sel))
                logger.info(f"TEKsystems: Form detected using: {sel}")
                return True
            except Exception:
                continue

        # Bot protection detection (manual only)
        if pause_on_lock:
            try:
                html = self.driver.page_source.lower()
                if any(x in html for x in ["captcha", "verify you are human", "challenge", "blocked"]):
                    logger.warning("TEKsystems: Bot protection detected. Complete it manually.")
                    input("Complete verification in browser, then press Enter to continue...")

                    for sel in form_signals:
                        try:
                            self._wait(15).until(EC.presence_of_element_located(sel))
                            logger.info(f"TEKsystems: Form detected after verification: {sel}")
                            return True
                        except Exception:
                            continue
            except Exception:
                pass

        # iframe try
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"TEKsystems: Found {len(iframes)} iframes after Apply.")
            if iframes:
                self.driver.switch_to.frame(iframes[0])
                logger.info("TEKsystems: Switched into first iframe; retrying detection...")

                for sel in form_signals:
                    try:
                        self._wait(10).until(EC.presence_of_element_located(sel))
                        logger.info(f"TEKsystems: Form detected inside iframe using: {sel}")
                        return True
                    except Exception:
                        continue
        except Exception:
            pass

        logger.warning("TEKsystems: Form not detected after Apply.")
        self._debug_dump("stuck_after_apply")
        return False

    # -------------------------
    # STRONG resume upload (key fix)
    # -------------------------
    def _upload_resume_strong(self, resume_path: str) -> bool:
        """
        Upload resume by sending file path to input[type=file].
        Does NOT rely on OS file picker.
        """
        resume_path = os.path.abspath(resume_path)
        if not os.path.exists(resume_path):
            raise FileNotFoundError(f"Resume not found: {resume_path}")

        # Sometimes upload button needs to be clicked to reveal input.
        upload_triggers = [
            "//button[contains(.,'Upload') and (contains(.,'Resume') or contains(.,'CV'))]",
            "//a[contains(.,'Upload') and (contains(.,'Resume') or contains(.,'CV'))]",
            "//*[contains(.,'Upload resume')]/ancestor::button[1]",
        ]
        for xp in upload_triggers:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                if btn.is_displayed() and btn.is_enabled():
                    self._scroll_into_view(btn)
                    try:
                        btn.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    break
            except Exception:
                continue

        # Find all file inputs
        file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        if not file_inputs:
            file_inputs = self._wait(10).until(lambda d: d.find_elements(By.CSS_SELECTOR, "input[type='file']"))

        chosen = None
        for fi in file_inputs:
            try:
                # Make usable if hidden
                self.driver.execute_script(
                    "arguments[0].style.display='block';"
                    "arguments[0].style.visibility='visible';"
                    "arguments[0].style.opacity=1;"
                    "arguments[0].removeAttribute('hidden');",
                    fi
                )
                chosen = fi
                break
            except Exception:
                continue

        if not chosen:
            logger.warning("TEKsystems: Found file inputs but couldn't use any.")
            self._debug_dump("file_input_unusable")
            return False

        self._scroll_into_view(chosen)
        chosen.send_keys(resume_path)
        logger.info(f"TEKsystems: Resume path sent to file input: {resume_path}")

        # Wait until Continue/Next becomes clickable (best signal upload succeeded)
        try:
            self._wait(25).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[normalize-space(.)='Continue' or normalize-space(.)='Next']")
                )
            )
            logger.info("TEKsystems: Continue/Next clickable after resume upload.")
            return True
        except Exception:
            pass

        # fallback: detect filename or success text
        basename = os.path.basename(resume_path)
        signals = [
            (By.XPATH, f"//*[contains(.,'{basename}')]"),
            (By.XPATH, "//*[contains(.,'Uploaded') or contains(.,'Success') or contains(.,'Complete')]"),
        ]
        for sel in signals:
            try:
                self._wait(10).until(EC.presence_of_element_located(sel))
                logger.info(f"TEKsystems: Upload signal detected: {sel}")
                return True
            except Exception:
                continue

        logger.warning("TEKsystems: Resume upload may not be complete (no signals found).")
        self._debug_dump("resume_upload_failed")
        return False

    # -------------------------
    # Form selection helpers
    # -------------------------
    def _click_yes_no_question(self, question_contains: str, answer_yes: bool):
        """Enhanced yes/no question handler with multiple fallback strategies."""
        target = "Yes" if answer_yes else "No"
        target_value = "true" if answer_yes else "false"
        q = self._xpath_literal(question_contains)
        
        # Strategy 1: Label-based selection (original approach)
        candidates = [
            f"//*[contains(normalize-space(.), {q})]/following::label[normalize-space(.)='{target}'][1]",
            f"//*[contains(normalize-space(.), {q})]/following::span[normalize-space(.)='{target}']/ancestor::label[1]",
            f"//*[contains(normalize-space(.), {q})]/following::label[contains(normalize-space(.), '{target}')][1]",
        ]
        
        for xp in candidates:
            try:
                if self._safe_click(By.XPATH, xp, timeout=6):
                    logger.info(f"TEKsystems: Clicked {target} for question: {question_contains}")
                    return True
            except Exception:
                continue
        
        # Strategy 2: Direct radio input selection by value
        try:
            radio_inputs = self.driver.find_elements(By.XPATH, f"//*[contains(normalize-space(.), {q})]/following::input[@type='radio']")
            for radio in radio_inputs[:4]:  # Check first 4 radio buttons after question
                try:
                    value = radio.get_attribute("value")
                    if value and (value.lower() == target.lower() or value.lower() == target_value):
                        self._scroll_into_view(radio)
                        time.sleep(0.3)
                        try:
                            radio.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", radio)
                        logger.info(f"TEKsystems: Clicked {target} radio for question: {question_contains}")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        
        # Strategy 3: Search by ID pattern (common patterns like "question.answer.True")
        try:
            id_patterns = [
                f"//input[@type='radio' and contains(@id, 'True')]",
                f"//input[@type='radio' and contains(@id, 'False')]",
            ]
            target_pattern = id_patterns[0] if answer_yes else id_patterns[1]
            
            radios = self.driver.find_elements(By.XPATH, target_pattern)
            for radio in radios:
                try:
                    # Check if this radio is near our question text
                    parent = radio.find_element(By.XPATH, "./ancestor::*[contains(., " + q + ")][1]")
                    if parent:
                        self._scroll_into_view(radio)
                        time.sleep(0.3)
                        try:
                            radio.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", radio)
                        logger.info(f"TEKsystems: Clicked {target} radio by ID pattern for question: {question_contains}")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        
        logger.warning(f"TEKsystems: Could not click {target} for question: {question_contains}")
        self._debug_dump(f"yes_no_question_failed_{target}")
        return False

    def _pick_radio_option(self, question_contains: str, option_text: str):
        """Enhanced radio option picker with multiple fallback strategies."""
        qc = self._xpath_literal(question_contains)
        ot = self._xpath_literal(option_text)
        
        # Strategy 1: Label-based selection
        candidates = [
            f"//*[contains(normalize-space(.), {qc})]/following::label[.//span[normalize-space(.)={ot}] or normalize-space(.)={ot}][1]",
            f"//*[contains(normalize-space(.), {qc})]/following::span[normalize-space(.)={ot}]/ancestor::label[1]",
            f"//*[contains(normalize-space(.), {qc})]/following::label[contains(normalize-space(.), {ot})][1]",
        ]
        
        for xp in candidates:
            try:
                if self._safe_click(By.XPATH, xp, timeout=8):
                    logger.info(f"TEKsystems: Selected '{option_text}' for question: {question_contains}")
                    return True
            except Exception:
                continue
        
        # Strategy 2: Direct radio input selection with partial value matching
        try:
            radio_inputs = self.driver.find_elements(By.XPATH, f"//*[contains(normalize-space(.), {qc})]/following::input[@type='radio']")
            for radio in radio_inputs[:10]:  # Check first 10 radio buttons
                try:
                    # Check value attribute or associated label text
                    value = radio.get_attribute("value") or ""
                    radio_id = radio.get_attribute("id") or ""
                    
                    # Try to find associated label
                    label_text = ""
                    if radio_id:
                        try:
                            label = self.driver.find_element(By.XPATH, f"//label[@for='{radio_id}']")
                            label_text = label.text.strip()
                        except Exception:
                            pass
                    
                    # Check if this radio matches our option
                    if (option_text.lower() in value.lower() or 
                        option_text.lower() in label_text.lower() or
                        option_text.lower() in radio_id.lower()):
                        self._scroll_into_view(radio)
                        time.sleep(0.3)
                        try:
                            radio.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", radio)
                        logger.info(f"TEKsystems: Selected '{option_text}' radio for question: {question_contains}")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        
        logger.warning(f"TEKsystems: Could not pick option '{option_text}' for question '{question_contains}'")
        self._debug_dump(f"radio_option_failed")
        return False

    def _click_checkbox(self, label_text: str):
        """Enhanced checkbox clicker with multiple fallback strategies."""
        lt = self._xpath_literal(label_text)
        
        # Strategy 1: Label-based selection
        candidates = [
            f"//label[.//span[normalize-space(.)={lt}] or normalize-space(.)={lt}]",
            f"//span[normalize-space(.)={lt}]/ancestor::label[1]",
            f"//label[contains(normalize-space(.), {lt})]",
            f"//label[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{label_text.lower()}')]",
        ]
        
        for xp in candidates:
            try:
                if self._safe_click(By.XPATH, xp, timeout=6):
                    logger.info(f"TEKsystems: Clicked checkbox: {label_text}")
                    return True
            except Exception:
                continue
        
        # Strategy 2: Direct checkbox input selection
        try:
            checkboxes = self.driver.find_elements(By.XPATH, "//input[@type='checkbox']")
            for checkbox in checkboxes:
                try:
                    checkbox_id = checkbox.get_attribute("id") or ""
                    checkbox_value = checkbox.get_attribute("value") or ""
                    checkbox_name = checkbox.get_attribute("name") or ""
                    
                    # Try to find associated label
                    label_elem_text = ""
                    if checkbox_id:
                        try:
                            label = self.driver.find_element(By.XPATH, f"//label[@for='{checkbox_id}']")
                            label_elem_text = label.text.strip()
                        except Exception:
                            pass
                    
                    # Check if this checkbox matches our label text
                    if (label_text.lower() in label_elem_text.lower() or
                        label_text.lower() in checkbox_value.lower() or
                        label_text.lower() in checkbox_id.lower() or
                        label_text.lower() in checkbox_name.lower()):
                        self._scroll_into_view(checkbox)
                        time.sleep(0.3)
                        try:
                            checkbox.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", checkbox)
                        logger.info(f"TEKsystems: Clicked checkbox by input: {label_text}")
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        
        logger.warning(f"TEKsystems: Could not click checkbox: {label_text}")
        return False

    def _select_native_dropdown(self, label_text: str, option_text: str):
        """Select from native HTML <select> element by visible text."""
        lab = self._xpath_literal(label_text)
        
        # Find the select element near the label
        select_targets = [
            f"//label[contains(normalize-space(.), {lab})]/following::select[1]",
            f"//*[contains(normalize-space(.), {lab})]/following::select[1]",
            f"//select[@aria-label='{label_text}' or contains(@aria-label, '{label_text}')]",
        ]
        
        for xp in select_targets:
            try:
                select_element = self._wait(8).until(EC.presence_of_element_located((By.XPATH, xp)))
                self._scroll_into_view(select_element)
                time.sleep(0.3)
                
                # Use Selenium's Select class for native dropdowns
                select = Select(select_element)
                
                # Try to select by visible text
                try:
                    select.select_by_visible_text(option_text)
                    logger.info(f"TEKsystems: Selected {label_text} = {option_text} (native select)")
                    time.sleep(0.5)  # Wait for any onChange handlers
                    return True
                except Exception as e:
                    # Try partial match if exact match fails
                    logger.debug(f"TEKsystems: Exact match failed, trying partial match: {e}")
                    for option in select.options:
                        if option_text.lower() in option.text.lower():
                            select.select_by_visible_text(option.text)
                            logger.info(f"TEKsystems: Selected {label_text} = {option.text} (native select, partial match)")
                            time.sleep(0.5)
                            return True
                    raise
            except Exception as e:
                logger.debug(f"TEKsystems: Native select attempt failed with {xp}: {e}")
                continue
        
        logger.warning(f"TEKsystems: Could not find native select for label: {label_text}")
        return False

    def _select_custom_dropdown(self, label_text: str, option_text: str):
        """Best-effort dropdown select: click near label -> type -> Enter."""
        lab = self._xpath_literal(label_text)
        click_targets = [
            f"//label[contains(normalize-space(.), {lab})]/following::*[@role='combobox'][1]",
            f"//*[contains(normalize-space(.), {lab})]/following::*[@role='combobox'][1]",
            f"//label[contains(normalize-space(.), {lab})]/following::button[1]",
            f"//*[contains(normalize-space(.), {lab})]/following::button[1]",
            f"//label[contains(normalize-space(.), {lab})]/following::div[1]",
            f"//*[contains(normalize-space(.), {lab})]/following::div[1]",
            f"//label[contains(normalize-space(.), {lab})]/following::input[not(@type='hidden')][1]",
        ]

        clicked = False
        for xp in click_targets:
            try:
                el = self._wait(6).until(EC.element_to_be_clickable((By.XPATH, xp)))
                self._scroll_into_view(el)
                time.sleep(0.3)
                try:
                    el.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", el)
                clicked = True
                logger.info(f"TEKsystems: Clicked dropdown trigger for {label_text}")
                time.sleep(0.5)
                break
            except Exception:
                continue
        if not clicked:
            logger.warning(f"TEKsystems: Could not click dropdown for label: {label_text}")
            return False

        inputs = [
            (By.XPATH, "//input[@aria-autocomplete='list' and not(@type='hidden')]"),
            (By.XPATH, "//div[@role='combobox']//input[not(@type='hidden')]"),
            (By.XPATH, "//input[@role='combobox' and not(@type='hidden')]"),
            (By.XPATH, "//input[not(@type='hidden') and @aria-expanded]"),
            (By.XPATH, "//input[not(@type='hidden')][last()]"),
        ]
        for by, val in inputs:
            try:
                inp = self._wait(5).until(EC.presence_of_element_located((by, val)))
                self._scroll_into_view(inp)
                time.sleep(0.2)
                try:
                    inp.clear()
                except Exception:
                    pass
                inp.send_keys(Keys.CONTROL + "a")
                time.sleep(0.1)
                inp.send_keys(option_text)
                time.sleep(0.5)
                inp.send_keys(Keys.ENTER)
                logger.info(f"TEKsystems: Selected {label_text} = {option_text}")
                time.sleep(0.3)
                return True
            except Exception:
                continue

        # fallback: active element
        try:
            ae = self.driver.switch_to.active_element
            ae.send_keys(Keys.CONTROL + "a")
            time.sleep(0.1)
            ae.send_keys(option_text)
            time.sleep(0.5)
            ae.send_keys(Keys.ENTER)
            logger.info(f"TEKsystems: Selected {label_text} = {option_text} (active element)")
            time.sleep(0.3)
            return True
        except Exception as e:
            logger.warning(f"TEKsystems: Dropdown select failed for {label_text}: {e}")
            return False

    def _click_flow_buttons(self, actually_submit: bool):
        """Click Continue/Next/Submit buttons with enhanced detection."""
        safe_buttons = ["Continue", "Next", "Review", "Save and Continue", "Proceed"]
        submit_buttons = ["Submit", "Submit Application", "Finish", "Complete", "Apply Now"]

        def click_by_text(txt):
            self._close_common_popups()
            t = self._xpath_literal(txt)
            
            # Multiple selector strategies
            selectors = [
                (By.XPATH, f"//button[normalize-space(.)={t}]"),
                (By.XPATH, f"//a[normalize-space(.)={t}]"),
                (By.XPATH, f"//button[contains(normalize-space(.), {t})]"),
                (By.XPATH, f"//a[contains(normalize-space(.), {t})]"),
                (By.XPATH, f"//input[@type='submit' and contains(@value, '{txt}')]"),
                (By.XPATH, f"//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{txt.lower()}')]"),
            ]
            
            for by, selector in selectors:
                try:
                    el = self._wait(8).until(EC.presence_of_element_located((by, selector)))
                    
                    # Wait for element to be clickable
                    try:
                        self._wait(5).until(EC.element_to_be_clickable((by, selector)))
                    except Exception:
                        pass  # Try clicking anyway
                    
                    self._scroll_into_view(el)
                    time.sleep(0.5)
                    try:
                        el.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", el)
                    time.sleep(2)
                    return True
                except Exception:
                    continue
            return False

        # Attempt safe transitions (Continue, Next, etc.)
        for txt in safe_buttons:
            if click_by_text(txt):
                logger.info(f"TEKsystems: Clicked transition button: {txt}")
                time.sleep(1)
                # Check for and handle any reCAPTCHA after clicking
                self._handle_recaptcha(max_wait_seconds=30)
                if not actually_submit:
                    return True
                break

        if actually_submit:
            # Scroll to bottom to ensure submit button is visible
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
            except Exception:
                pass
            
            for txt in submit_buttons:
                if click_by_text(txt):
                    logger.info(f"TEKsystems: Clicked submit-like button: {txt}")
                    return True

            # Last resort: search for any button containing 'submit' (case-insensitive)
            try:
                self._close_common_popups()
                btn = self._wait(8).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//button[contains(translate(normalize-space(.),'SUBMIT','submit'),'submit')]")
                    )
                )
                self._scroll_into_view(btn)
                time.sleep(0.5)
                try:
                    btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", btn)
                time.sleep(2)
                logger.info("TEKsystems: Clicked submit fallback button.")
                return True
            except Exception:
                logger.warning("TEKsystems: Submit button not found.")
                self._debug_dump("submit_button_not_found")
        else:
            logger.info("TEKsystems: DRY RUN mode (not clicking Submit). Set TEK_SUBMIT=true to submit.")

        return True

    # -------------------------
    # apply
    # -------------------------
    def _fill_eeo_fields(self):
        """Fill Veteran, Disability, and Full Name fields on the second page."""
        logger.info("TEKsystems: Handling EEO/Veteran/Disability page...")
        
        vet_status = settings.VETERAN_STATUS
        dis_status = settings.DISABILITY_STATUS
        full_name = f"{settings.FIRST_NAME} {settings.LAST_NAME}"

        # 1. Protected Veteran Status
        # Try finding the label first to ensure page loaded
        try:
            self._wait(10).until(lambda d: d.find_element(By.XPATH, "//*[contains(translate(., 'VETERAN', 'veteran'), 'veteran')]"))
            logger.info("TEKsystems: Detected Veteran status question.")
        except Exception:
            logger.warning("TEKsystems: Veteran status section not detected (might be single page or already filled).")
        
        # Try native dropdown
        if not self._select_native_dropdown("Protected Veteran", vet_status):
            # Try custom/other selectors
            if not self._select_custom_dropdown("Protected Veteran", vet_status):
                 # Try clicking the option directly if it's a radio/list
                 self._pick_radio_option("Protected Veteran", vet_status)

        # 2. Disability Status
        # Try native dropdown
        if not self._select_native_dropdown("Disability", dis_status):
            if not self._select_custom_dropdown("Disability", dis_status):
                self._pick_radio_option("Disability", dis_status)

        # 3. Full Name / Signature
        # Keywords: Full Name, Signature, Name
        name_inputs = [
            "//input[contains(@aria-label, 'Full Name')]",
            "//input[contains(@placeholder, 'Full Name')]",
            "//label[contains(., 'Full Name')]/following::input[1]",
            "//input[contains(@aria-label, 'Signature')]",
            "//input[contains(@placeholder, 'Signature')]",
            "//label[contains(., 'Signature')]/following::input[1]",
             "//label[contains(., 'My name is')]/following::input[1]"
        ]
        
        typed_name = False
        for xpath in name_inputs:
            if self._safe_type(By.XPATH, xpath, full_name):
                logger.info(f"TEKsystems: Filled Full Name/Signature: {full_name}")
                typed_name = True
                break
        
        if not typed_name:
             logger.warning("TEKsystems: Could not find Full Name/Signature field.")
             self._debug_dump("eeo_name_fail")

    def apply(self, listing):
        job_title = listing.get("job_title", "Unknown")

        # ✅ HARD BLOCK: never apply unless it's AI Engineer
        if not self._is_target_job(job_title):
            logger.info(f"TEKsystems: Not an AI Engineer role. Skipping apply: {job_title}")
            return False

        job_url = listing.get("job_url")

        ACTUALLY_SUBMIT = settings.TEK_SUBMIT
        PAUSE_ON_LOCK = settings.TEK_PAUSE_ON_LOCK
        PAUSE_BEFORE_SUBMIT = settings.TEK_PAUSE_BEFORE_SUBMIT

        resume_path = settings.RESUME_PATH
        first_name = settings.FIRST_NAME
        last_name = settings.LAST_NAME
        phone = settings.PHONE_NUMBER
        email = settings.EMAIL
        street = settings.STREET_ADDRESS
        city = settings.CITY
        zip_code = settings.ZIP_CODE
        country = settings.COUNTRY
        state = settings.STATE
        current_title = settings.CURRENT_TITLE
        desired_salary = settings.DESIRED_SALARY

        # Eligibility
        authorized_us = settings.AUTHORIZED_US
        visa_required = settings.VISA_SPONSORSHIP

        # Preferences
        years_opt = settings.TEK_YEARS_OPTION
        work_hybrid = settings.WORK_HYBRID
        work_remote = settings.WORK_REMOTE
        work_onsite = settings.WORK_ONSITE
        sms_opt_in = settings.SMS_OPT_IN

        logger.info(f"TEKsystems: Opening job: {job_title} -> {job_url}")
        self.driver.get(job_url)
        self._close_common_popups()

        # Click Apply
        old_url = self.driver.current_url
        apply_selectors = [
            (By.XPATH, "//a[contains(., 'Apply') and @href]"),
            (By.XPATH, "//button[contains(., 'Apply')]"),
            (By.CSS_SELECTOR, "a[href*='apply']"),
        ]

        clicked = False
        for sel in apply_selectors:
            try:
                btn = self._wait(10).until(EC.element_to_be_clickable(sel))
                self._scroll_into_view(btn)
                try:
                    btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", btn)
                logger.info(f"TEKsystems: Clicked Apply using {sel}")
                clicked = True
                time.sleep(2)
                break
            except Exception:
                continue

        if not clicked:
            logger.warning("TEKsystems: Apply button not clickable.")
            self._debug_dump("apply_not_clickable")
            return False

        # Wait for application form
        if not self._wait_for_application_form(old_url=old_url, pause_on_lock=PAUSE_ON_LOCK):
            return False

        # Upload resume (critical)
        if not resume_path:
            logger.warning("TEKsystems: RESUME_PATH not set; cannot upload resume.")
            self._debug_dump("resume_path_missing")
            return False

        logger.info("TEKsystems: Uploading resume (strong method)...")
        if not self._upload_resume_strong(resume_path):
            logger.warning("TEKsystems: Resume upload failed; cannot proceed.")
            return False

        # Fill contact fields (best-effort)
        if first_name:
            self._safe_type(By.XPATH, "//input[@placeholder='First Name' or @aria-label='First Name']", first_name)
        if last_name:
            self._safe_type(By.XPATH, "//input[@placeholder='Last Name' or @aria-label='Last Name']", last_name)
        if phone:
            self._safe_type(By.XPATH, "//input[@placeholder='Phone Number' or contains(@aria-label,'Phone')]", phone)
        if email:
            self._safe_type(By.XPATH, "//input[@placeholder='Email Address' or @type='email']", email)


        if street:
            self._safe_type(By.XPATH, "//input[@placeholder='123 Main St.' or contains(@aria-label,'Street')]", street)
        if city:
            self._safe_type(By.XPATH, "//input[@placeholder='Beverly Hills' or contains(@aria-label,'City')]", city)
        if zip_code:
            self._safe_type(By.XPATH, "//input[@placeholder='90210' or contains(@aria-label,'Zip') or contains(@aria-label,'Postal')]", zip_code)

        # Country/State dropdowns (native HTML select elements)
        if country:
            self._select_native_dropdown("Country", country)
        if state:
            self._select_native_dropdown("State", state)
        
        # Desired Salary
        if desired_salary:
            self._safe_type(By.XPATH, "//input[contains(@aria-label,'Desired Salary') or contains(@placeholder,'Salary') or contains(@aria-label,'salary')]", desired_salary)

        # Eligibility questions
        self._click_yes_no_question('Are you authorized to work in "U.S."', authorized_us)
        self._click_yes_no_question("require visa sponsorship", visa_required)

        # Current title (best-effort)
        try:
            if current_title:
                self._safe_type(
                    By.XPATH,
                    "//*[contains(.,'current or most recent job title')]/following::input[1]",
                    current_title
                )
        except Exception:
            logger.warning("TEKsystems: current title input not found; skipping.")

        # Years of experience
        if years_opt:
            self._pick_radio_option("How many years of work experience", years_opt)

        # Work type checkboxes
        if work_hybrid:
            self._click_checkbox("Hybrid")
        if work_remote:
            self._click_checkbox("Remote")
        if work_onsite:
            self._click_checkbox("On-site")

        # SMS preference - use direct element IDs for reliable clicking
        try:
            if sms_opt_in:
                # Click "I agree to receive text messages" using direct ID
                opt_in_radio = self._wait(8).until(
                    EC.element_to_be_clickable((By.ID, "agreementemail.TextSms11.True"))
                )
                self._scroll_into_view(opt_in_radio)
                time.sleep(0.3)
                opt_in_radio.click()
                logger.info("TEKsystems: Selected SMS opt-in: I agree to receive text messages")
            else:
                # Click "I do not want to receive text messages" using direct ID
                opt_out_radio = self._wait(8).until(
                    EC.element_to_be_clickable((By.ID, "agreementemail.TextSms11.False"))
                )
                self._scroll_into_view(opt_out_radio)
                time.sleep(0.3)
                opt_out_radio.click()
                logger.info("TEKsystems: Selected SMS opt-out: I do not want to receive text messages")
        except Exception as e:
            logger.warning(f"TEKsystems: Could not select SMS preference: {e}")

        if PAUSE_BEFORE_SUBMIT:
            input("Paused before clicking flow buttons. Press Enter to continue...")

        # Continue to EEO page
        logger.info("TEKsystems: Clicking Next to proceed to EEO step...")
        self._click_flow_buttons(actually_submit=False)
        
        # Fill EEO fields
        self._fill_eeo_fields()

        if PAUSE_BEFORE_SUBMIT:
            input("Paused before Final Submit. Press Enter to continue...")

        # Final Submit
        logger.info("TEKsystems: Clicking Final Submit...")
        self._click_flow_buttons(actually_submit=ACTUALLY_SUBMIT)

        return True