# import time

# from selenium.webdriver.common.by import By
# from selenium.webdriver.support.ui import WebDriverWait
# from selenium.webdriver.support import expected_conditions as EC

# from core.logger import logger
# from strategies.base import BaseStrategy
# from core.human_behavior import HumanBehavior

# class AETalentsStrategy(BaseStrategy):
#     """AE Talents job application automation strategy."""

#     def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
#         super().__init__(driver, job_site, selectors, db_session, candidate_data)
#         self.portal_url = getattr(job_site, "search_url_template", "https://aetalentsgroup.com/careers.php")
#         # runner._load_selectors returns {"listing": {...}, "application": {...}}
#         # Merge both dicts into a flat config so .get("key") works for all phases
#         self.selectors_config = {
#             **((selectors or {}).get("listing", {})),
#             **((selectors or {}).get("application", {})),
#         }
#         self.human = HumanBehavior(driver)

#     def login(self):
#         """No login required for AE Talents."""
#         logger.info("AETalents: Checking login requirements... (No login required)")
#         return True

#     def find_jobs(self):
#         """Search for jobs."""
#         if not self.candidate_data:
#             logger.error("No candidate data provided")
#             return []

#         search_config = self.candidate_data.get("search", {})
#         keyword = search_config.get("keyword", "")
#         if not keyword and search_config.get("keywords"):
#              keyword = search_config.get("keywords")[0]
#         location = search_config.get("location", "")

#         logger.info(f"Navigating to {self.portal_url}")
#         self.driver.get(self.portal_url)
#         time.sleep(3)

#         search_input_sel = self.selectors_config.get("search_input", "")
#         # Fill search keyword
#         if keyword:
#             try:
#                 search_input = WebDriverWait(self.driver, 10).until(
#                     EC.presence_of_element_located((By.CSS_SELECTOR, search_input_sel))
#                 )
#                 self.human.fill_text_field(search_input, keyword)
#                 logger.info(f"Entered search keyword: {keyword}")
#             except Exception as e:
#                 logger.warning(f"Could not find search input: {e}")

#         # Fill location (Temporarily commented out due to site issues)
#         # location_input_sel = self.selectors_config.get("location_input", "")
#         # if location:
#         #     try:
#         #         loc_input = WebDriverWait(self.driver, 5).until(
#         #             EC.presence_of_element_located((By.CSS_SELECTOR, location_input_sel))
#         #         )
#         #         self.human.fill_text_field(loc_input, location)
#         #         logger.info(f"Entered location: {location}")
#         #     except Exception as e:
#         #         logger.warning(f"Could not find location input: {e}")

#         search_btn_sel = self.selectors_config.get("search_button", "")
#         # Click search
#         try:
#             search_btn = WebDriverWait(self.driver, 5).until(
#                 EC.element_to_be_clickable((By.CSS_SELECTOR, search_btn_sel))
#             )
#             self.human.human_click(search_btn)
#             logger.info("Clicked search button")
#             time.sleep(3) # Wait for page reload
#         except Exception as e:
#             logger.warning(f"Could not click search button: {e}")

#         job_card_sel = self.selectors_config.get("job_card_link", "")
#         # Extract job cards
#         jobs = []
#         try:
#             # Check for "No positions found" message first
#             no_results_elements = self.driver.find_elements(By.XPATH, "//h3[contains(text(), 'No positions found')]")
#             if no_results_elements:
#                 logger.info("No positions found for this search. Returning empty list.")
#                 return []

#             # Look for <a> tags linking to the detail page
#             WebDriverWait(self.driver, 10).until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, job_card_sel))
#             )
#             job_links = self.driver.find_elements(By.CSS_SELECTOR, job_card_sel)
            
#             seen = set()
#             for link in job_links:
#                 url = link.get_attribute("href")
#                 title = link.text.strip()
                
#                 # Strict AI/ML check
#                 title_lower = title.lower()
#                 ai_keywords = ['ai', 'ml', 'artificial intelligence', 'machine learning', 'data scientist', 'llm', 'genai']
#                 is_ai_ml = any(kw in title_lower for kw in ai_keywords)
                
#                 # Ignore empty titles or generic "View Details" text
#                 if url not in seen and title and "View Details" not in title and is_ai_ml:
#                     seen.add(url)
#                     jobs.append({
#                         "job_title": title,
#                         "job_url": url,
#                         "external_id": url.split("id=")[-1] if "id=" in url else ""
#                     })
#             logger.info(f"Found {len(jobs)} jobs matching criteria")
#         except Exception as e:
#             logger.warning(f"No job cards found or error parsing them: {e}")

#         return jobs

#     def apply(self, listing):
#         """Phase 2: Apply to the job"""
#         url = listing.get("job_url", "")
#         title = listing.get("job_title", "Unknown")

#         logger.info(f"\n[APPLY] Applying to: {title}")
#         logger.info(f"URL: {url}")

#         try:
#             self.driver.get(url)
#             time.sleep(3)

#             # Step 1: Click "Apply Now" button to load the application form
#             apply_now_sel = self.selectors_config.get("apply_now_button", "a.btn-secondary")
#             try:
#                 apply_btn = WebDriverWait(self.driver, 10).until(
#                     EC.element_to_be_clickable((By.CSS_SELECTOR, apply_now_sel))
#                 )
#                 self.human.human_click(apply_btn)
#                 logger.info("Clicked 'Apply Now' button on job detail page")
#                 time.sleep(3)
#             except Exception as e:
#                 logger.error(f"Could not find or click 'Apply Now' button: {e}")
#                 return False

#             # Application form logic
#             logger.info("Application form loaded. Filling in candidate details...")

#             applicant = self.candidate_data.get("applicant", {})

#             first_name_sel = self.selectors_config.get("first_name", "")
#             first_name_input = WebDriverWait(self.driver, 10).until(
#                 EC.presence_of_element_located((By.CSS_SELECTOR, first_name_sel))
#             )
#             self.human.fill_text_field(first_name_input, applicant.get("first_name", ""))

#             last_name_sel = self.selectors_config.get("last_name", "")
#             last_name_input = self.driver.find_element(By.CSS_SELECTOR, last_name_sel)
#             self.human.fill_text_field(last_name_input, applicant.get("last_name", ""))

#             email_sel = self.selectors_config.get("email", "")
#             email_input = self.driver.find_element(By.CSS_SELECTOR, email_sel)
#             self.human.fill_text_field(email_input, applicant.get("email", ""))

#             visa_status = (
#                 applicant.get("workstatus")
#                 or applicant.get("work_authorization", {}).get("visa_status", "")
#                 or "Other"
#             )
#             if visa_status:
#                 visa_sel = self.selectors_config.get("visa_status", "")
#                 try:
#                     from selenium.webdriver.support.ui import Select
#                     visa_element = self.driver.find_element(By.CSS_SELECTOR, visa_sel)
#                     select = Select(visa_element)
#                     matched = False
#                     for option in select.options:
#                         if visa_status.lower() in option.text.lower():
#                             select.select_by_visible_text(option.text)
#                             matched = True
#                             break
#                     if not matched:
#                         select.select_by_value("Other")
#                     time.sleep(1)
#                 except Exception as e:
#                     logger.warning(f"Could not set visa status: {e}")

#             resume_path = self.get_resume_path()
#             if resume_path:
#                 try:
#                     resume_sel = self.selectors_config.get("resume", "")
#                     resume_input = self.driver.find_element(By.CSS_SELECTOR, resume_sel)
#                     resume_input.send_keys(resume_path)
#                     logger.info("Uploaded resume")
#                     time.sleep(2)
#                 except Exception as e:
#                     logger.warning(f"Failed to upload resume: {e}")

#             submit_sel = self.selectors_config.get("submit_button", "")
#             submit_btn = self.driver.find_element(By.CSS_SELECTOR, submit_sel)
            
#             from config.settings import settings
#             if getattr(settings, "DRY_RUN", False):
#                 logger.info("[DRY RUN] Skipping actual submission click.")
#                 logger.info("Dry run successful!")
#                 return True

#             self.human.human_click(submit_btn)
#             logger.info("Clicked submit application button, waiting for confirmation...")
#             time.sleep(4)

#             # Validate success
#             try:
#                 success_sel = self.selectors_config.get("success_message", "")
#                 if success_sel:
#                     WebDriverWait(self.driver, 10).until(
#                         EC.presence_of_element_located((By.CSS_SELECTOR, success_sel))
#                     )
#                     logger.info("Explicit success element detected!")
#                 else:
#                     # Fallback generic validation
#                     WebDriverWait(self.driver, 10).until(
#                         lambda d: any(
#                             phrase in d.page_source.lower() 
#                             for phrase in ["success", "thank you", "application submitted", "received"]
#                         )
#                     )
#                     logger.info("Generic success text detected on the page!")
#                 return True
#             except Exception as e:
#                 logger.error(f"Could not verify application success confirmation: {e}")
#                 return False

#         except Exception as e:
#             logger.error(f"Error during application for {title}: {e}")
#             return False



import time
import random

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

from core.logger import logger
from strategies.base import BaseStrategy
from core.human_behavior import HumanBehavior

class AETalentsStrategy(BaseStrategy):
    """AE Talents job application automation strategy."""

    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.portal_url = getattr(job_site, "search_url_template", "https://aetalentsgroup.com/careers.php")
        # runner._load_selectors returns {"listing": {...}, "application": {...}}
        # Merge both dicts into a flat config so .get("key") works for all phases
        self.selectors_config = {
            **((selectors or {}).get("listing", {})),
            **((selectors or {}).get("application", {})),
        }
        self.human = HumanBehavior(driver)

    def login(self):
        """No login required for AE Talents."""
        logger.info("AETalents: Checking login requirements... (No login required)")
        return True

    def find_jobs(self):
        """Search for jobs."""
        if not self.candidate_data:
            logger.error("No candidate data provided")
            return []

        search_config = self.candidate_data.get("search", {})
<<<<<<< HEAD
        keyword = search_config.get("keyword", "")
        if not keyword and search_config.get("keywords"):
             keyword = search_config.get("keywords")[0]
=======
        keywords = search_config.get("keywords", [])
        if not keywords and search_config.get("keyword"):
            keywords = [search_config.get("keyword")]
        
        location = search_config.get("location", "")
>>>>>>> 24ab8d27e45ab74e9887e6c0d08ccf088a3b05d0

        all_jobs = []
        seen_urls = set()

<<<<<<< HEAD
        search_input_sel = self.selectors_config.get("search_input", "")
        if keyword:
=======
        for keyword in keywords:
            logger.info(f"\n[SEARCH] Searching AE Talents for: '{keyword}'")
            self.driver.get(self.portal_url)
            time.sleep(5) # Slow down to avoid triggering cloudflare rate limits

            # Fill search keyword
            search_input_sel = self.selectors_config.get("search_input", "#job_search")
            if search_input_sel:
                try:
                    search_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, search_input_sel))
                    )
                    self.human.fill_text_field(search_input, keyword)
                except Exception as e:
                    logger.warning(f"Could function search input for keyword '{keyword}': {e}")
                    continue

            # Click search
            search_btn_sel = self.selectors_config.get("search_button", "button.btn-primary")
>>>>>>> 24ab8d27e45ab74e9887e6c0d08ccf088a3b05d0
            try:
                search_btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, search_btn_sel))
                )
                try:
                    self.human.human_click(search_btn)
                except:
                    logger.warning(f"Regular search click failed for '{keyword}', trying JS click")
                    self.driver.execute_script("arguments[0].click();", search_btn)
                time.sleep(3) # Wait for page reload
            except Exception as e:
                logger.warning(f"Could not click search button for keyword '{keyword}': {e}")
                continue

<<<<<<< HEAD
        search_btn_sel = self.selectors_config.get("search_button", "")
        try:
            search_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, search_btn_sel))
            )
            self.human.human_click(search_btn)
            logger.info("Clicked search button")
            time.sleep(3)
        except Exception as e:
            logger.warning(f"Could not click search button: {e}")

        jobs = []
        try:
            # Check for "No positions found" message first
            no_results = self.driver.find_elements(
                By.XPATH, "//h3[contains(text(), 'No positions found')]"
            )
            if no_results:
                logger.info("No positions found for this search.")
                return []

            # Wait for at least one job detail link to appear
            job_card_sel = self.selectors_config.get("job_card_link", "a[href*='p=detail']")
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, job_card_sel))
                )
            except Exception:
                logger.warning(f"No job cards matched selector '{job_card_sel}'")
                return []

            # Get all detail-page links
            job_links = self.driver.find_elements(By.CSS_SELECTOR, job_card_sel)
            logger.info(f"[DEBUG] Found {len(job_links)} job link(s) on page")

            seen = set()
            for link in job_links:
                url = link.get_attribute("href")
                if not url or url in seen:
                    continue

                # --- Title extraction: walk UP the DOM to find the card container,
                #     then look for a heading tag inside it (same approach as KForce) ---
                title = ""
                try:
                    # Walk up 1-3 levels to find a container with a heading
                    node = link
                    for _ in range(4):
                        node = node.find_element(By.XPATH, "..")
                        # Try common heading selectors inside the container
                        for heading_sel in ("h2", "h3", "h4", ".job-title", ".position-title"):
                            try:
                                heading = node.find_element(By.CSS_SELECTOR, heading_sel)
                                candidate = heading.text.strip()
                                # Accept first non-trivial, non-navigation text
                                if candidate and len(candidate) > 3 and candidate.lower() not in (
                                    "view details", "apply", "careers", "home"
                                ):
                                    title = candidate
                                    break
                            except Exception:
                                continue
                        if title:
                            break
                except Exception:
                    pass

                # Absolute fallback: read the link's own text (may still be empty)
                if not title:
                    title = link.text.strip()

                logger.info(f"[DEBUG] Job found: title='{title}' | url='{url}'")

                if not title:
                    logger.warning(f"[DEBUG] Could not extract title for {url} — skipping")
                    continue

                # Broad AI/ML keyword filter
                title_lower = title.lower()
                ai_keywords = [
                    'ai', 'ml', 'artificial intelligence', 'machine learning',
                    'data scientist', 'llm', 'genai', 'generative', 'nlp',
                    'deep learning', 'computer vision', 'data engineer',
                ]
                is_ai_ml = any(kw in title_lower for kw in ai_keywords)

                if is_ai_ml and "View Details" not in title:
                    seen.add(url)
                    jobs.append({
                        "job_title": title,
                        "job_url": url,
                        "external_id": url.split("id=")[-1] if "id=" in url else ""
                    })
                else:
                    logger.info(f"[DEBUG] '{title}' skipped — did not match AI/ML filter")

            logger.info(f"Found {len(jobs)} jobs matching criteria")

        except Exception as e:
            logger.warning(f"Error during job discovery: {e}")

        return jobs
=======
            # Extract job cards
            job_card_sel = self.selectors_config.get("job_card_link", ".job-card a")
            try:
                # Check for "No positions found" message
                no_results = self.driver.find_elements(By.XPATH, "//h3[contains(text(), 'No positions found')]")
                if no_results:
                    logger.info(f"No results for keyword: {keyword}")
                    continue

                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, job_card_sel))
                )
                job_links = self.driver.find_elements(By.CSS_SELECTOR, job_card_sel)
                
                keyword_jobs_count = 0
                for link in job_links:
                    url = link.get_attribute("href")
                    title = link.text.strip()
                    
                    if not url or not title or "View Details" in title:
                        continue
                        
                    if url in seen_urls:
                        continue
>>>>>>> 24ab8d27e45ab74e9887e6c0d08ccf088a3b05d0

                    # Broadened AI/ML/Data check for filtering
                    title_lower = title.lower()
                    ai_keywords = [
                        'ai', 'ml', 'artificial intelligence', 'machine learning', 
                        'data scientist', 'llm', 'genai', 'generative ai', 
                        'python', 'mlops', 'data science'
                    ]
                    is_match = any(kw in title_lower for kw in ai_keywords)
                    
                    if is_match:
                        seen_urls.add(url)
                        all_jobs.append({
                            "job_title": title,
                            "job_url": url,
                            "external_id": url.split("id=")[-1] if "id=" in url else ""
                        })
                        keyword_jobs_count += 1
                
                logger.info(f"Collected {keyword_jobs_count} new unique jobs for keyword '{keyword}'")

            except Exception as e:
                logger.warning(f"Error parsing jobs for keyword '{keyword}': {e}")

        logger.info(f"\n[SUMMARY] Total unique jobs collected across all keywords: {len(all_jobs)}")
        return all_jobs

    def apply(self, listing):
        """Phase 2: Apply to the job"""
        url = listing.get("job_url", "")
        title = listing.get("job_title", "Unknown")

        logger.info(f"\n[APPLY] Applying to: {title}")
        logger.info(f"URL: {url}")

        try:
            self.driver.get(url)
            time.sleep(4)

            # Step 1: Click "Apply Now" button to load the application form
            apply_now_selectors = [
                "a.btn-secondary",
                "a.btn-primary[href*='apply']",
                "//a[contains(translate(text(), 'APPLY NOW', 'apply now'), 'apply now')]",
                "//a[contains(text(), 'Apply Now')]"
            ]
            
            apply_btn = None
            for sel in apply_now_selectors:
                try:
                    if sel.startswith("//"):
                        apply_btn = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, sel))
                        )
                    else:
                        apply_btn = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                        )
                    if apply_btn:
                        logger.info(f"Found 'Apply Now' button using selector: {sel}")
                        break
                except:
                    continue

            if not apply_btn:
                logger.error(f"Could not find 'Apply Now' button for job {title}")
                return False

            apply_url = apply_btn.get_attribute("href")
            if apply_url:
                logger.info(f"Navigating directly to application form URL: {apply_url}")
                self.driver.get(apply_url)
                time.sleep(3)
            else:
                try:
                    # Scroll to it and click as a fallback if it has no href
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
                    time.sleep(1)
                    self.human.human_click(apply_btn)
                except:
                    # Fallback to JS click if blocked by header/overlay
                    logger.warning("Regular click failed, trying JS click for 'Apply Now' button")
                    self.driver.execute_script("arguments[0].click();", apply_btn)
                    
                logger.info("Clicked 'Apply Now' button successfully")
                time.sleep(4)

            # Application form logic
            logger.info("Application form loaded. Filling in candidate details...")
            
            with open("debug_application_form.html", "w", encoding="utf-8") as f:
                f.write(self.driver.page_source)
            logger.info(f"Saved application form source. URL: {self.driver.current_url}. Windows: {len(self.driver.window_handles)}")
            
            applicant = self.candidate_data.get("applicant", {})

            # Verified selectors from browser inspection
            first_name_sel = self.selectors_config.get("first_name", "")
            last_name_sel = self.selectors_config.get("last_name", "")
            email_sel = self.selectors_config.get("email", "")
            phone_sel = self.selectors_config.get("phone", "")
            visa_sel = self.selectors_config.get("visa_status", "")
            linkedin_sel = self.selectors_config.get("linkedin_url", "")
            resume_sel = self.selectors_config.get("resume", "")
            submit_sel = self.selectors_config.get("submit_button", "")

            first_name_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, first_name_sel))
            )
            self.human.fill_text_field(first_name_input, applicant.get("first_name", ""))

            last_name_input = self.driver.find_element(By.CSS_SELECTOR, last_name_sel)
            self.human.fill_text_field(last_name_input, applicant.get("last_name", ""))

            email_input = self.driver.find_element(By.CSS_SELECTOR, email_sel)
            self.human.fill_text_field(email_input, applicant.get("email", ""))

            phone_input = self.driver.find_elements(By.CSS_SELECTOR, phone_sel)
            if phone_input:
                self.human.fill_text_field(phone_input[0], applicant.get("phone", ""))

            linkedin_input = self.driver.find_elements(By.CSS_SELECTOR, linkedin_sel)
            if linkedin_input:
                self.human.fill_text_field(linkedin_input[0], applicant.get("linkedin", ""))

            visa_status = (
                applicant.get("workstatus")
                or applicant.get("work_authorization", {}).get("visa_status", "")
                or "Other"
            )
            if visa_status:
                try:
                    from selenium.webdriver.support.ui import Select
                    visa_element = self.driver.find_element(By.CSS_SELECTOR, visa_sel)
                    select = Select(visa_element)
                    matched = False
                    for option in select.options:
                        if visa_status.lower() in option.text.lower():
                            select.select_by_visible_text(option.text)
                            matched = True
                            break
                    if not matched:
                        select.select_by_value("Other")
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Could not set visa status: {e}")

            resume_path = self.get_resume_path()
            if resume_path:
                try:
                    resume_input = self.driver.find_element(By.CSS_SELECTOR, resume_sel)
                    # For hidden file inputs, sometimes we need to make them visible or send keys directly
                    try:
                        self.driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", resume_input)
                    except:
                        pass
                    resume_input.send_keys(resume_path)
                    logger.info("Uploaded resume")
                    time.sleep(2)
                except Exception as e:
                    logger.warning(f"Failed to upload resume: {e}")

            submit_btn = self.driver.find_element(By.CSS_SELECTOR, submit_sel)
            
            from config.settings import settings
            if getattr(settings, "DRY_RUN", False):
                logger.info("[DRY RUN] Skipping actual submission click.")
                logger.info("Dry run successful!")
                return True

            self.human.human_click(submit_btn)
            logger.info("Clicked submit application button, waiting for confirmation...")
            time.sleep(4)

            # Validate success
            try:
                success_sel = self.selectors_config.get("success_message", ".alert-success")
                if success_sel:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, success_sel))
                    )
                    logger.info("Explicit success element detected!")
                else:
                    # Fallback generic validation
                    WebDriverWait(self.driver, 10).until(
                        lambda d: any(
                            phrase in d.page_source.lower() 
                            for phrase in ["success", "thank you", "application submitted", "received"]
                        )
                    )
                    logger.info("Generic success text detected on the page!")
                return True
            except Exception as e:
                logger.error(f"Could not verify application success confirmation: {e}")
                return False

        except Exception as e:
            logger.error(f"Error during application for {title}: {e}")
            return False

