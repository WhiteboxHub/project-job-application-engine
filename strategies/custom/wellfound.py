import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from core.logger import logger
from core.human_behavior import HumanBehavior
from strategies.base import BaseStrategy
from config.settings import settings

class WellfoundStrategy(BaseStrategy):
    """
    Strategy for scraping and interacting with Wellfound (wellfound.com).
    """

    def __init__(self, driver, job_site, selectors, db_session=None, candidate_data=None):
        super().__init__(driver, job_site, selectors, db_session, candidate_data)
        self.hb = HumanBehavior(driver)
        # We use a custom full_config selector type from DuckDB
        self.config = selectors.get('full_config', {})
        self.aiml_keywords = [
            "artificial-intelligence", "ai-engineer", "ai-ml", "aiml",
            "machine-learning", "ml-engineer", "deep-learning", "data-science",
            "nlp", "natural-language", "computer-vision", "llm",
            "generative-ai", "gen-ai", "genai", "-ai-", "-ai"
        ]

    def login(self):
        """
        Wellfound discovery doesn't strictly require login, but we land on /jobs
        and handle bot checks/cookies.
        """
        logger.info(f"🌐 Navigating to {self.job_site.search_url_template}")
        self.driver.get(self.job_site.search_url_template)
        
        # Initial hesitation
        time.sleep(random.uniform(5.0, 8.0))
        self._handle_bot_check()
        self._dismiss_cookie_banner()
        return True

    def find_jobs(self):
        """
        Perform search and extract AI/ML job listings.
        """
        # 1. Search via UI
        self._perform_search()

        # 2. Extract Jobs
        all_jobs = []
        max_pages = getattr(settings, 'WELLFOUND_MAX_PAGES', 3)
        
        for page_num in range(1, max_pages + 1):
            logger.info(f"📄 Scraping Wellfound page {page_num}...")
            
            # Simple bot check & scroll
            self._handle_bot_check()
            self._scroll_to_load_all()
            
            # Extract links
            page_urls = self._extract_job_urls()
            for url in page_urls:
                all_jobs.append({
                    "job_url": url,
                    "job_title": url.split('/')[-1].replace('-', ' ').title(),
                    "external_id": url.split('/')[-1]
                })

            if page_num < max_pages:
                if not self._click_next():
                    break
        
        return all_jobs

    def apply(self, listing):
        """
        Placeholder for application logic. Currently focused on discovery.
        """
        logger.info(f"Application logic for Wellfound is currently manual. URL: {listing.get('job_url')}")
        return False

    # ─── Internal Helpers ──────────────────────────────────────────────────────

    def _handle_bot_check(self):
        for _ in range(3):
            is_blocked = False
            try:
                if "Access is temporarily restricted" in self.driver.page_source or "Just a moment..." in self.driver.page_source:
                    is_blocked = True
            except: pass
            
            if is_blocked:
                logger.info("🛡️ Bot challenge detected! Simulating human hesitation...")
                time.sleep(random.uniform(5.0, 10.0))
                self.hb.move_mouse_randomly()
                self.hb.scroll_page(direction='down', amount=200)
                time.sleep(3)
            else:
                break

    def _dismiss_cookie_banner(self):
        try:
            for tag in ("button", "a"):
                elems = self.driver.find_elements(By.TAG_NAME, tag)
                for el in elems:
                    text = (el.text or "").strip().lower()
                    if any(w in text for w in ("agree", "accept", "got it")):
                        el.click()
                        logger.info("🍪 Cookie banner dismissed.")
                        return
        except: pass

    def _perform_search(self):
        search_config = self.config.get('search', {})
        title = "Artificial Intelligence Engineer (AI)"
        location = "United States"

        logger.info(f"🔍 Searching for '{title}' in '{location}'")
        self._fill_react_select(search_config.get('job_title_placeholder', "Job title"), title)
        time.sleep(1)
        self._fill_react_select(search_config.get('location_placeholder', "Location"), location)
        
        btn_sel = search_config.get('search_button', "button[type='button'][class*='bg-black']")
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, btn_sel)
            self.hb.human_click(btn)
            time.sleep(5)
        except:
            logger.warning("Could not click search button, trying Enter key.")
            from selenium.webdriver.common.keys import Keys
            self.driver.switch_to.active_element.send_keys(Keys.ENTER)
            time.sleep(5)

    def _fill_react_select(self, placeholder, value):
        from selenium.webdriver.common.keys import Keys
        try:
            input_el = self.driver.find_element(By.XPATH, f"//input[@aria-label='{placeholder}']")
        except:
            try:
                input_el = self.driver.find_element(By.XPATH, f"//div[contains(text(),'{placeholder}')]/following-sibling::div//input")
            except:
                logger.warning(f"Could not find input for {placeholder}")
                return

        self.hb.human_click(input_el)
        time.sleep(0.5)
        self.hb.human_type(input_el, value)
        time.sleep(2)
        input_el.send_keys(Keys.ENTER)

    def _scroll_to_load_all(self):
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        self.driver.execute_script("window.scrollTo(0, 0);")

    def _extract_job_urls(self):
        card_sel = self.config.get('listing', {}).get('card_link', "a[href*='/jobs/']")
        found = set()
        anchors = self.driver.find_elements(By.CSS_SELECTOR, card_sel)
        for a in anchors:
            href = a.get_attribute("href") or ""
            href = href.split('?')[0].rstrip('/')
            if "/jobs/" in href and any(kw in href.lower() for kw in self.aiml_keywords):
                found.add(href)
        return found

    def _click_next(self):
        next_sel = self.config.get('pagination', {}).get('next_button', "a[aria-label='Next page']")
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, next_sel)
            if btn.is_displayed():
                self.hb.human_click(btn)
                time.sleep(random.uniform(5.0, 8.0))
                return True
        except: pass
        return False
