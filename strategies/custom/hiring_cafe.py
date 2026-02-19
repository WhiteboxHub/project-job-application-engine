from strategies.base import BaseStrategy
from core.logger import logger
from core.human_behavior import HumanBehavior
from core.safe_actions import SafeActions
import json
import os
import re
import time
from datetime import datetime
from urllib.parse import quote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from models.config_models import JobListing

# Hiring Cafe job link: <a href="/viewjob/{job_id}">...</a>
JOB_LINK_SELECTOR = 'a[href^="/viewjob/"]'

# Apply now button on job page (opens ATS in new tab)
APPLY_NOW_BUTTON_XPATH = "//button[.//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply now')]]"

# URL host/path patterns -> ATS platform name (lowercase)
ATS_PLATFORM_PATTERNS = [
    (r"lever\.co|jobs\.lever\.", "lever"),
    (r"greenhouse\.io|boards\.greenhouse|jobs\.greenhouse", "greenhouse"),
    (r"sapsf\.com|successfactors\.com", "sapsf"),
    (r"workday\.com", "workday"),
    (r"ashhq\.by|ashhqby", "ashhqby"),
    (r"smartrecruiters\.com", "smartrecruiters"),
    (r"icims\.com", "icims"),
    (r"jobvite\.com", "jobvite"),
    (r"taleo\.net|taleocdn", "taleo"),
    (r"myworkdayjobs\.com", "workday"),
    (r"apply\.workable\.com|workable\.com", "workable"),
    (r"bamboohr\.com", "bamboohr"),
    (r"paycom\.com", "paycom"),
    (r"ultipro\.com", "ultipro"),
    (r"linkedin\.com/jobs", "linkedin"),
    (r"indeed\.com", "indeed"),
    (r"ashbyhq\.com", "ashby"),
    (r"recruitee\.com", "recruitee"),
    (r"teamtailor\.com", "teamtailor"),
    (r"personio\.com", "personio"),
]


def _job_id_from_href(href: str) -> str | None:
    """Extract job ID from href like '/viewjob/p16gu5rnyh9yhp7v'."""
    if not href:
        return None
    match = re.search(r"/viewjob/([a-zA-Z0-9_-]+)", href)
    return match.group(1) if match else None


def _load_hiring_cafe_config() -> dict:
    """Load Hiring Cafe config from config/hiring_cafe.json. Returns {} if missing."""
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config",
            "hiring_cafe.json",
        )
        if os.path.isfile(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load hiring_cafe config: {e}")
    return {}


def _build_search_url(keyword: str, base_url: str = "https://hiring.cafe") -> str:
    """Build hiring.cafe search URL from keyword. searchState is URL-encoded JSON {"searchQuery": keyword}."""
    search_state = json.dumps({"searchQuery": keyword})
    encoded = quote(search_state, safe="")
    return f"{base_url}/?searchState={encoded}"


def detect_ats_platform(url: str) -> str | None:
    """
    Detect ATS platform from URL (e.g. lever, greenhouse, sapsf, workday, ashhqby).
    Returns platform name or None if unknown.
    """
    if not url:
        return None
    url_lower = url.lower()
    for pattern, platform in ATS_PLATFORM_PATTERNS:
        if re.search(pattern, url_lower):
            return platform
    return None


class HiringCafeStrategy(BaseStrategy):
    """
    Hiring Cafe scraper strategy.
    
    Features:
    - Infinite scroll to load all job positions
    - Extracts job listings from the search results
    - Can be run standalone for scraping only
    """
    
    def __init__(self, driver, job_site=None, selectors=None, db_session=None):
        config = _load_hiring_cafe_config()
        # Env override: HIRING_CAFE_SEARCH_KEYWORD; else config file; else "AI"
        keyword = (
            os.environ.get("HIRING_CAFE_SEARCH_KEYWORD")
            or config.get("search_keyword")
            or "AI"
        ).strip()
        self._search_keyword = keyword
        base_url = "https://hiring.cafe"
        search_url = _build_search_url(keyword, base_url)

        # Allow initialization without job_site for standalone use
        if job_site is None:
            class MinimalJobSite:
                def __init__(self, url_template):
                    self.company_name = "Hiring Cafe"
                    self.search_url_template = url_template
            job_site = MinimalJobSite(search_url)

        super().__init__(driver, job_site, selectors or {})
        self.db_session = db_session
        self.human = HumanBehavior(driver)
        self.base_url = base_url
        self.search_url = search_url

        logger.info("✅ HiringCafeStrategy initialized (search_keyword=%s)", keyword)
    
    def login(self):
        """
        Hiring Cafe doesn't require login for viewing jobs.
        Returns True to indicate success.
        """
        logger.info("ℹ️ No login required for Hiring Cafe")
        return True
    
    def _scroll_to_bottom(self):
        """Scroll to the bottom of the page"""
        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)  # Wait for content to load
    
    def _get_viewjob_links(self):
        """Find all visible 'Job Posting' links with href /viewjob/{id}."""
        try:
            links = self.driver.find_elements(By.CSS_SELECTOR, JOB_LINK_SELECTOR)
            return [el for el in links if el.is_displayed()]
        except Exception as e:
            logger.warning(f"Error finding viewjob links: {e}")
            return []

    def _get_unique_job_ids(self) -> set[str]:
        """Return set of unique job IDs currently visible on the page."""
        ids = set()
        for link in self._get_viewjob_links():
            href = link.get_attribute("href") or ""
            job_id = _job_id_from_href(href)
            if job_id:
                ids.add(job_id)
        return ids

    def _get_current_job_count(self) -> int:
        """
        Count unique job listings via a[href^="/viewjob/"] links.
        """
        return len(self._get_unique_job_ids())
    
    def _debug_page_structure(self):
        """
        Debug method to print page structure for troubleshooting.
        Useful when selectors don't match the actual page structure.
        """
        logger.info("🔍 Analyzing page structure for debugging...")
        try:
            # Get page source length
            page_source_length = len(self.driver.page_source)
            logger.info(f"Page source length: {page_source_length} characters")
            
            # Count common elements
            element_counts = {}
            test_selectors = [
                ("articles", "article"),
                ("divs", "div"),
                ("links", "a"),
                ("cards", "[class*='card']"),
                ("jobs", "[class*='job']"),
                ("listings", "[class*='listing']"),
            ]
            
            for name, selector in test_selectors:
                try:
                    count = len(self.driver.find_elements(By.CSS_SELECTOR, selector))
                    element_counts[name] = count
                except Exception:
                    element_counts[name] = 0
            
            logger.info(f"Element counts: {element_counts}")
            
            # Try to find any links with job-related text
            try:
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                job_related_links = [
                    link for link in all_links 
                    if link.is_displayed() and any(
                        keyword in link.text.lower() or keyword in link.get_attribute("href", "").lower()
                        for keyword in ["job", "position", "career", "apply", "hiring"]
                    )
                ]
                logger.info(f"Found {len(job_related_links)} links with job-related keywords")
                
                if job_related_links:
                    logger.info("Sample link texts:")
                    for link in job_related_links[:5]:
                        logger.info(f"  - {link.text[:50]} | {link.get_attribute('href')[:80]}")
            except Exception as e:
                logger.debug(f"Error analyzing links: {e}")
                
        except Exception as e:
            logger.warning(f"Error in debug_page_structure: {e}")
    
    def _scroll_until_end(self, max_scrolls=100, scroll_delay=2):
        """
        Scroll until no more jobs are loading.
        
        Args:
            max_scrolls: Maximum number of scroll attempts
            scroll_delay: Delay between scrolls in seconds
            
        Returns:
            True if scrolling completed, False if max scrolls reached
        """
        logger.info("🔄 Starting infinite scroll to load all positions...")
        
        previous_count = 0
        no_change_count = 0
        scroll_attempts = 0
        
        while scroll_attempts < max_scrolls:
            # Get current job count
            current_count = self._get_current_job_count()
            logger.info(f"📊 Current job count: {current_count} (scroll attempt {scroll_attempts + 1}/{max_scrolls})")
            
            # If count hasn't changed after multiple scrolls, we're done
            if current_count == previous_count:
                no_change_count += 1
                if no_change_count >= 3:  # No change for 3 consecutive scrolls
                    logger.info(f"✅ No new jobs loaded after {no_change_count} scrolls. Reached end.")
                    return True
            else:
                no_change_count = 0  # Reset counter when new jobs appear
            
            previous_count = current_count
            
            # Scroll down
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            self._scroll_to_bottom()
            
            # Wait for new content to potentially load
            time.sleep(scroll_delay)
            
            # Check if page height changed (new content loaded)
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                # Try scrolling a bit more to trigger lazy loading
                self.driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(1)
            
            scroll_attempts += 1
            
            # Human-like delay
            self.human.random_delay(0.5, 1.5)
        
        logger.warning(f"⚠️ Reached maximum scroll attempts ({max_scrolls}). Stopping.")
        return False
    
    def extract_all_job_ids(self) -> list[str]:
        """
        Extract all unique job IDs from the current page (a[href^="/viewjob/"]).
        Call after scrolling to end to get the full list.
        """
        return sorted(self._get_unique_job_ids())

    def _extract_job_listings(self):
        """
        Extract job listings using a[href^="/viewjob/"] links.
        Each link gives job_id from href; url is base_url + href.
        """
        jobs = []
        logger.info("🔍 Extracting job listings via viewjob links...")
        
        try:
            seen_ids = set()
            for link in self._get_viewjob_links():
                try:
                    href = link.get_attribute("href") or ""
                    job_id = _job_id_from_href(href)
                    if not job_id or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)
                    
                    url = href if href.startswith("http") else (self.base_url + (href if href.startswith("/") else "/" + href))
                    
                    # Optional: try to get title from parent container
                    title = None
                    try:
                        parent = link.find_element(By.XPATH, "./ancestor::*[self::article or self::div][position()<=3]")
                        raw = (parent.text or "").strip()
                        if raw and "Job Posting" in raw:
                            title = raw.replace("Job Posting", "").strip()[:200] or None
                    except Exception:
                        pass
                    if not title:
                        title = f"Job {job_id}"
                    
                    job_data = {
                        "job_id": job_id,
                        "external_id": job_id,
                        "title": title,
                        "url": url,
                        "company": None,
                        "location": None,
                        "scraped_at": datetime.now().isoformat(),
                    }
                    jobs.append(job_data)
                except Exception as e:
                    logger.warning(f"Error extracting from link: {e}")
                    continue
            
            logger.info(f"✅ Extracted {len(jobs)} unique job listings (job IDs)")
            return jobs
            
        except Exception as e:
            logger.error(f"❌ Error extracting job listings: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _get_ats_link_from_job_page(self, job_id: str) -> dict | None:
        """
        Open job page, click Apply now, capture ATS URL from new tab, close tab.
        Returns {"ats_url": str, "ats_platform": str} or None if failed.
        """
        job_url = f"{self.base_url}/viewjob/{job_id}"
        try:
            self.driver.get(job_url)
            time.sleep(2)
            self.human.random_delay(1, 2)

            main_handle = self.driver.current_window_handle

            # Find and click "Apply now" button
            try:
                btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, APPLY_NOW_BUTTON_XPATH))
                )
                self.actions.safe_click_element(btn)
            except (TimeoutException, NoSuchElementException) as e:
                logger.warning(f"Apply now button not found on {job_id}: {e}")
                return None

            time.sleep(2)
            self.human.random_delay(1, 2)

            handles = self.driver.window_handles
            new_handles = [h for h in handles if h != main_handle]
            if not new_handles:
                # Same-tab redirect
                current = self.driver.current_url
                if "hiring.cafe" not in current.lower():
                    platform = detect_ats_platform(current) or "unknown"
                    return {"ats_url": current, "ats_platform": platform}
                logger.warning(f"No new tab opened for job {job_id}")
                return None

            self.driver.switch_to.window(new_handles[0])
            ats_url = self.driver.current_url
            ats_platform = detect_ats_platform(ats_url) or "unknown"
            self.driver.close()
            self.driver.switch_to.window(main_handle)
            return {"ats_url": ats_url, "ats_platform": ats_platform}
        except Exception as e:
            logger.warning(f"Error getting ATS link for job {job_id}: {e}")
            try:
                if len(self.driver.window_handles) > 1:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except Exception:
                pass
            return None

    def enrich_jobs_with_ats_links(
        self, jobs: list[dict], limit: int | None = None
    ) -> list[dict]:
        """
        For each job (with job_id or external_id), open job page, click Apply now,
        capture ATS URL and platform from new tab. Adds ats_url and ats_platform to each job.
        If limit is set, only process that many jobs.
        """
        out = []
        to_process = jobs[:limit] if limit is not None else jobs
        for i, job in enumerate(to_process):
            jid = job.get("job_id") or job.get("external_id")
            if not jid:
                out.append({**job, "ats_url": None, "ats_platform": None})
                continue
            logger.info(f"Enriching job {i+1}/{len(to_process)}: {jid}")
            ats = self._get_ats_link_from_job_page(jid)
            enriched = {**job, "ats_url": None, "ats_platform": None}
            if ats:
                enriched["ats_url"] = ats["ats_url"]
                enriched["ats_platform"] = ats["ats_platform"]
                logger.info(f"  -> {ats['ats_platform']}: {ats['ats_url'][:80]}...")
            out.append(enriched)
            self.human.random_delay(1, 2)
        if limit is not None and len(jobs) > limit:
            for j in jobs[limit:]:
                out.append({**j, "ats_url": j.get("ats_url"), "ats_platform": j.get("ats_platform")})
        return out
    
    def find_jobs(self):
        """
        Navigates to the search URL, scrolls until the end, and scrapes job listings.
        
        Returns:
            List of dictionaries with job details (external_id, title, url).
        """
        try:
            logger.info(f"🌐 Navigating to: {self.search_url}")
            self.driver.get(self.search_url)
            
            # Wait for page to load
            time.sleep(3)
            self.human.random_delay(2, 4)
            
            # Check if page loaded successfully
            if "hiring.cafe" not in self.driver.current_url.lower():
                logger.warning(f"⚠️ Unexpected URL after navigation: {self.driver.current_url}")
            
            # Debug page structure if no jobs found initially
            initial_count = self._get_current_job_count()
            if initial_count == 0:
                logger.warning("⚠️ No jobs found initially. Running page structure analysis...")
                self._debug_page_structure()
            
            # Scroll until the end
            self._scroll_until_end(max_scrolls=100, scroll_delay=2)
            
            # Extract all job listings
            jobs = self._extract_job_listings()
            
            logger.info(f"✅ Found {len(jobs)} total job listings")
            return jobs
            
        except Exception as e:
            logger.error(f"❌ Error in find_jobs: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def apply(self, listing: JobListing):
        """
        Placeholder for apply functionality.
        Hiring Cafe application process not implemented yet.
        
        Args:
            listing: JobListing object
            
        Returns:
            False (not implemented)
        """
        logger.warning("⚠️ Apply functionality not implemented for Hiring Cafe")
        return False
    
    def scrape_and_save(
        self,
        output_file=None,
        enrich_ats: bool = False,
        enrich_ats_limit: int | None = None,
        job_limit: int | None = None,
    ):
        """
        Standalone method to scrape jobs and save to JSON file.
        
        Args:
            output_file: Path to output JSON file (default: hiring_cafe_jobs_TIMESTAMP.json)
            enrich_ats: If True, open each job page, click Apply now, capture ATS URL and platform
            enrich_ats_limit: Max number of jobs to enrich (None = all)
            job_limit: Max number of jobs to process/save (None = all). Use for test runs.
            
        Returns:
            List of scraped jobs (with ats_url, ats_platform if enrich_ats=True)
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"hiring_cafe_jobs_{timestamp}.json"
        
        logger.info("🚀 Starting Hiring Cafe scraper...")
        if job_limit is not None:
            logger.info("🧪 Test mode: limiting to %d jobs", job_limit)
        
        jobs = self.find_jobs()
        
        if job_limit is not None and jobs:
            jobs = jobs[:job_limit]
            logger.info("📋 Using first %d jobs (test limit)", len(jobs))
        
        if enrich_ats and jobs:
            logger.info("🔗 Enriching jobs with ATS links (Apply now -> new tab)...")
            jobs = self.enrich_jobs_with_ats_links(jobs, limit=enrich_ats_limit)
        
        if jobs:
            try:
                # Single maintained output: hiring cafe link + corresponding ATS link per job
                payload = {
                    "source": "hiring.cafe",
                    "updated": datetime.now().isoformat(),
                    "count": len(jobs),
                    "jobs": [
                        {
                            "job_id": j.get("job_id"),
                            "title": j.get("title"),
                            "hiring_cafe_url": j.get("url"),
                            "ats_url": j.get("ats_url"),
                            "ats_platform": j.get("ats_platform"),
                            "scraped_at": j.get("scraped_at"),
                        }
                        for j in jobs
                    ],
                }
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2, ensure_ascii=False)
                logger.info(f"💾 Saved {len(jobs)} jobs to {output_file}")
            except Exception as e:
                logger.error(f"❌ Error saving to file: {e}")
        else:
            logger.warning("⚠️ No jobs found to save")
        
        return jobs

