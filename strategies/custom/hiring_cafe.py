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
    (r"sapsf\.com|successfactors\.com", "successfactors"),  # SAP SuccessFactors (sapsf = same ATS)
    (r"workday\.com", "workday"),
    (r"adp\.com|workforcenow\.adp\.com", "adp"),
    (r"ashhq\.by|ashhqby", "ashhqby"),
    (r"smartrecruiters\.com", "smartrecruiters"),
    (r"icims\.com", "icims"),
    (r"jobvite\.com", "jobvite"),
    (r"taleo\.net|taleocdn", "taleo"),
    (r"myworkdayjobs\.com", "workday"),
    (r"apply\.workable\.com|workable\.com", "workable"),
    (r"bamboohr\.com", "bamboohr"),
    (r"paycom\.com", "paycom"),
    (r"paychex\.com|myapps\.paychex\.com", "paychex"),
    (r"ultipro\.com", "ultipro"),
    (r"linkedin\.com/jobs", "linkedin"),
    (r"indeed\.com", "indeed"),
    (r"ashbyhq\.com", "ashby"),
    (r"recruitee\.com", "recruitee"),
    (r"teamtailor\.com", "teamtailor"),
    (r"personio\.com", "personio"),
    (r"oraclecloud\.com", "oraclecloud"),
    (r"applytojob\.com", "applytojob"),
    (r"brassring\.com", "brassring"),
    (r"rippling\.com", "rippling"),
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


# Date filter: dateFetchedPastNDays in searchState (default 2 = 24 hours)
DATE_FETCHED_PRESETS = {
    "24h": 2,   # 24 hours
    "3d": 4,    # 3 days
    "1w": 14,   # 1 week
    "2w": 21,   # 2 weeks
    "all": -1,  # All time
}


def _parse_date_fetched_past_n_days(value) -> int:
    """Parse config value to dateFetchedPastNDays. Presets: 24h=2, 3d=4, 1w=14, 2w=21, all=-1. Default 2 (24h)."""
    if value is None:
        return 2
    if isinstance(value, int):
        return value
    s = str(value).strip().lower()
    if s in DATE_FETCHED_PRESETS:
        return DATE_FETCHED_PRESETS[s]
    try:
        return int(value)
    except (TypeError, ValueError):
        return 2


def _normalize_search_keyword(keyword: str) -> str:
    """Use + for spaces in searchQuery (e.g. 'AI Engineer' -> 'AI+Engineer'). Hiring.cafe expects AI+Engineer (encoded as AI%2BEngineer in URL)."""
    if not keyword:
        return keyword
    s = keyword.strip()
    if " " in s and "+" not in s:
        s = s.replace(" ", "+")
    return s


def _build_search_url(
    keyword: str,
    base_url: str = "https://hiring.cafe",
    date_fetched_past_n_days: int = 2,
) -> str:
    """Build hiring.cafe search URL. searchState = {"searchQuery": "AI+Engineer", "dateFetchedPastNDays": N}; + is encoded as %2B."""
    search_query = _normalize_search_keyword(keyword)
    search_state = json.dumps({
        "searchQuery": search_query,
        "dateFetchedPastNDays": date_fetched_past_n_days,
    })
    encoded = quote(search_state, safe="")
    return f"{base_url}/?searchState={encoded}"


def detect_ats_platform(url: str) -> str | None:
    """
    Detect ATS platform from URL (e.g. lever, greenhouse, successfactors, workday, ashhqby).
    Returns platform name or None if unknown.
    """
    if not url:
        return None
    url_lower = url.lower()
    for pattern, platform in ATS_PLATFORM_PATTERNS:
        if re.search(pattern, url_lower):
            return platform
    return None


def categorize_jobs_by_ats(jobs: list[dict]) -> dict[str, list[dict]]:
    """
    Group jobs by ATS platform. Each group is a list of entries with
    job_id, title, job_posting_url, ats: { url, platform }. Keys are platform names; "unknown" for null/missing.
    """
    by_platform = {}
    for j in jobs:
        ats_obj = j.get("ats")
        if isinstance(ats_obj, dict):
            platform = (ats_obj.get("platform") or "unknown").strip() or "unknown"
            ats_url = ats_obj.get("url")
        else:
            platform = (j.get("ats_platform") or "unknown").strip() or "unknown"
            ats_url = j.get("ats_url")
        job_posting_url = j.get("url") or j.get("job_posting_url") or j.get("hiring_cafe_url")
        entry = {
            "job_id": j.get("job_id"),
            "title": j.get("title"),
            "job_posting_url": job_posting_url,
            "ats": {"url": ats_url, "platform": platform},
        }
        if platform not in by_platform:
            by_platform[platform] = []
        by_platform[platform].append(entry)
    return by_platform


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
        # Support multiple keywords: search_keywords (list) or search_keyword (single) or env
        env_kw = os.environ.get("HIRING_CAFE_SEARCH_KEYWORD", "").strip()
        if env_kw:
            keywords = [env_kw]
        elif config.get("search_keywords"):
            keywords = [str(k).strip() for k in config["search_keywords"] if str(k).strip()]
        elif config.get("search_keyword"):
            keywords = [str(config["search_keyword"]).strip()]
        else:
            keywords = ["AI"]
        self._search_keywords = keywords if keywords else ["AI"]
        self._date_fetched_past_n_days = _parse_date_fetched_past_n_days(
            config.get("date_fetched_past_n_days") or config.get("date_filter") or 2
        )
        base_url = "https://hiring.cafe"
        search_url = _build_search_url(
            self._search_keywords[0], base_url, self._date_fetched_past_n_days
        )

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

        logger.info(
            "✅ HiringCafeStrategy initialized (keywords=%s, date_fetched_past_n_days=%s)",
            self._search_keywords,
            self._date_fetched_past_n_days,
        )
    
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

    def enrich_jobs_with_ats_links_batched(
        self,
        jobs: list[dict],
        batch_size: int = 100,
        output_file: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Enrich jobs in batches of batch_size (default 100), ordered per keyword.
        After each batch, updates jobs in place and writes output_file if given.
        """
        ordered = self._jobs_ordered_per_keyword(jobs)
        if limit is not None:
            ordered = ordered[:limit]
        total = len(ordered)
        logger.info("🔗 Enriching %d jobs in batches of %d (per-keyword order)", total, batch_size)
        for start in range(0, total, batch_size):
            batch = ordered[start : start + batch_size]
            batch_num = start // batch_size + 1
            max_batch = (total + batch_size - 1) // batch_size
            logger.info("📦 Batch %d/%d: jobs %d–%d", batch_num, max_batch, start + 1, start + len(batch))
            try:
                for i, job in enumerate(batch):
                    jid = job.get("job_id") or job.get("external_id")
                    if not jid:
                        continue
                    ats = self._get_ats_link_from_job_page(jid)
                    job["ats_url"] = ats["ats_url"] if ats else None
                    job["ats_platform"] = ats["ats_platform"] if ats else None
                    if ats:
                        logger.info("  -> %s: %s...", ats["ats_platform"], (ats["ats_url"] or "")[:60])
                    self.human.random_delay(1, 2)
                if output_file:
                    self._write_jobs_payload(output_file, jobs)
            except BaseException:
                logger.warning("⚠️ Batch %d interrupted; saving current state.", batch_num)
                if output_file:
                    self._write_jobs_payload(output_file, jobs)
                raise
        return jobs
    
    def find_jobs_for_keyword(self, keyword: str) -> list[dict]:
        """
        Run search for one keyword: navigate, scroll to end, extract jobs.
        Returns list of job dicts (job_id, title, url, ...).
        """
        search_url = _build_search_url(
            keyword, self.base_url, self._date_fetched_past_n_days
        )
        try:
            logger.info("🌐 Keyword %r -> %s", keyword, search_url)
            self.driver.get(search_url)
            time.sleep(3)
            self.human.random_delay(2, 4)
            if "hiring.cafe" not in self.driver.current_url.lower():
                logger.warning("⚠️ Unexpected URL: %s", self.driver.current_url)
            initial_count = self._get_current_job_count()
            if initial_count == 0:
                self._debug_page_structure()
            self._scroll_until_end(max_scrolls=100, scroll_delay=2)
            jobs = self._extract_job_listings()
            logger.info("✅ Keyword %r: %d jobs", keyword, len(jobs))
            return jobs
        except Exception as e:
            logger.error("❌ Error for keyword %r: %s", keyword, e)
            import traceback
            traceback.print_exc()
            return []

    def _merge_jobs_unique(self, keyword_job_lists: list[tuple[str, list[dict]]]) -> list[dict]:
        """
        Merge (keyword, jobs) pairs into one unique list by job_id.
        Each job gets source_keywords: list of keywords that found it.
        """
        by_id = {}
        for keyword, lst in keyword_job_lists:
            for j in lst:
                jid = j.get("job_id") or j.get("external_id")
                if not jid:
                    continue
                if jid not in by_id:
                    by_id[jid] = {**j, "source_keywords": [keyword]}
                else:
                    if keyword not in by_id[jid].get("source_keywords", []):
                        by_id[jid].setdefault("source_keywords", []).append(keyword)
        return list(by_id.values())

    def _jobs_ordered_per_keyword(self, jobs: list[dict]) -> list[dict]:
        """Order jobs so we process by keyword: all from first keyword, then second, etc. Each job once."""
        order = []
        seen_ids = set()
        for keyword in self._search_keywords:
            for j in jobs:
                jid = j.get("job_id") or j.get("external_id")
                if not jid or jid in seen_ids:
                    continue
                if keyword in (j.get("source_keywords") or []):
                    order.append(j)
                    seen_ids.add(jid)
        # Any job not in any keyword (shouldn't happen) append at end
        for j in jobs:
            jid = j.get("job_id") or j.get("external_id")
            if jid and jid not in seen_ids:
                order.append(j)
                seen_ids.add(jid)
        return order

    def find_jobs(self) -> list[dict]:
        """
        Phase 1: Infinite scroll per keyword, collect all jobs into a unique set (by job_id).
        Each job has source_keywords listing which keyword(s) found it.
        Returns list of job dicts (deduplicated).
        """
        if len(self._search_keywords) == 1:
            kw = self._search_keywords[0]
            jobs = self.find_jobs_for_keyword(kw)
            for j in jobs:
                j["source_keywords"] = [kw]
            return jobs
        keyword_job_lists = []
        for keyword in self._search_keywords:
            jobs = self.find_jobs_for_keyword(keyword)
            keyword_job_lists.append((keyword, jobs))
            self.human.random_delay(1, 2)
        merged = self._merge_jobs_unique(keyword_job_lists)
        logger.info("✅ Unique jobs across all keywords: %d", len(merged))
        return merged
    
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

    def _write_jobs_payload(self, output_file: str, jobs: list) -> None:
        """Write current jobs to JSON file (used for normal save and on unexpected exit)."""
        if not jobs:
            return
        try:
            payload = {
                "source": "hiring.cafe",
                "updated": datetime.now().isoformat(),
                "count": len(jobs),
                "jobs": [
                    {
                        "job_id": j.get("job_id"),
                        "title": j.get("title"),
                        "job_posting_url": j.get("url"),
                        "ats": {
                            "url": j.get("ats_url"),
                            "platform": j.get("ats_platform"),
                        },
                        "source_keywords": j.get("source_keywords"),
                        "scraped_at": j.get("scraped_at"),
                    }
                    for j in jobs
                ],
            }
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            logger.info("💾 Saved %d jobs to %s", len(jobs), output_file)
        except Exception as e:
            logger.error("❌ Error saving to file: %s", e)
    
    def scrape_and_save(
        self,
        output_file=None,
        enrich_ats: bool = False,
        enrich_ats_limit: int | None = None,
        job_limit: int | None = None,
        ats_batch_size: int = 100,
    ):
        """
        Phase 1: Infinite scroll per keyword, collect unique jobs (set by job_id) with source_keywords.
        Phase 2: Enrich in batches of ats_batch_size (default 100), ordered per keyword; write after each batch.
        Phase 3: Combine and categorize by ATS at end (caller writes hiring_cafe_by_ats.json).
        """
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"hiring_cafe_jobs_{timestamp}.json"
        
        logger.info("🚀 Phase 1: Infinite scroll per keyword, collect unique jobs...")
        if job_limit is not None:
            logger.info("🧪 Test mode: limiting to %d jobs", job_limit)
        
        jobs = self.find_jobs()
        
        if job_limit is not None and jobs:
            jobs = jobs[:job_limit]
            logger.info("📋 Using first %d jobs (test limit)", len(jobs))
        
        self._write_jobs_payload(output_file, jobs)
        
        if enrich_ats and jobs:
            logger.info("🔗 Phase 2: Enrich in batches of %d (per-keyword order)...", ats_batch_size)
            try:
                self.enrich_jobs_with_ats_links_batched(
                    jobs,
                    batch_size=ats_batch_size,
                    output_file=output_file,
                    limit=enrich_ats_limit,
                )
                self._write_jobs_payload(output_file, jobs)
            except BaseException:
                logger.warning("⚠️ Enrichment interrupted; current state saved to JSON.")
                self._write_jobs_payload(output_file, jobs)
                raise
        
        if not jobs:
            logger.warning("⚠️ No jobs found to save")
        return jobs

