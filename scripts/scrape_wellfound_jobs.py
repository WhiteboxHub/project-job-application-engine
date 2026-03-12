#!/usr/bin/env python3
"""
Scrape AI/ML job URLs from Wellfound and save to a JSON file.

Navigates up to 20 pages of Wellfound job listings, filters job URLs by
AI/ML-related keywords, deduplicates, and saves results to JSON.

Usage:
  python scripts/scrape_wellfound_jobs.py
  python scripts/scrape_wellfound_jobs.py --max-pages 5
  python scripts/scrape_wellfound_jobs.py --output data/my_jobs.json --headless
"""

import argparse
import json
import os
import sys
import time
import random
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.browser import browser_service
from core.logger import logger
from core.human_behavior import HumanBehavior
from config.settings import settings

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)

# ─── Configuration ─────────────────────────────────────────────────────────────

# Landing page (visited first to avoid anti-bot detection / cookie banner)
JOBS_HOME_URL = "https://wellfound.com/jobs"

# What to type into the search form
SEARCH_JOB_TITLE = "Artificial Intelligence Engineer (AI)"
SEARCH_LOCATION  = "United States"

# Keywords matched against the job URL path (case-insensitive).
# A job URL is kept if ANY of these substrings appears in it.
AIML_KEYWORDS = [
    "artificial-intelligence",
    "ai-engineer",
    "ai-ml",
    "aiml",
    "machine-learning",
    "ml-engineer",
    "deep-learning",
    "data-science",
    "nlp",
    "natural-language",
    "computer-vision",
    "llm",
    "generative-ai",
    "gen-ai",
    "genai",          # e.g. /jobs/123-genai-engineer
    # standalone "ai" — matched as a dash-bounded token to reduce false positives
    "-ai-",
    "-ai",
]

# Wellfound job card links look like /jobs/<id>-<slug>
JOB_LINK_PATTERN = "/jobs/"

PAGE_LOAD_WAIT = 15   # seconds to wait for job cards after navigation
SCROLL_PAUSE   = 1.5  # seconds to pause between scrolls


# ─── Helpers ───────────────────────────────────────────────────────────────────

def is_aiml_url(url: str) -> bool:
    """Return True if any AI/ML keyword appears in the job URL (case-insensitive)."""
    lower = url.lower()
    for kw in AIML_KEYWORDS:
        if kw in lower:
            return True
    return False

def handle_bot_check(driver):
    """
    Check if Wellfound's Cloudflare/DataDome 'unexpected activity' page is showing.
    If so, performs very slow, human-like scroll to bypass.
    """
    hm = HumanBehavior(driver)
    for _ in range(4):  # Check multiple times
        is_blocked = False
        try:
            # Check for DataDome 'Access is temporarily restricted'
            for el in driver.find_elements(By.XPATH, "//*[contains(text(), 'Access is temporarily restricted')]"):
                if el.is_displayed():
                    is_blocked = True
                    break
            
            if not is_blocked:
                # Check for Cloudflare 'Just a moment...'
                for el in driver.find_elements(By.XPATH, "//*[contains(text(), 'Just a moment...')]"):
                    if el.is_displayed():
                        is_blocked = True
                        break
            
            if not is_blocked:
                # Check for Cloudflare challenge div
                for el in driver.find_elements(By.ID, "challenge-running"):
                    if el.is_displayed():
                        is_blocked = True
                        break
        except Exception:
            pass

        if is_blocked:
            logger.info("🛡️ Bot challenge detected! Waiting and simulating human hesitation...")
            
            # Dump a screenshot so we know exactly what it's seeing
            try:
                driver.save_screenshot("data/bot_challenge_detected.png")
            except Exception:
                pass

            # DataDome tracks ultra-fast mouse movements as bots. 
            # We must wait, then scroll smoothly.
            time.sleep(random.uniform(3.0, 6.0))
            hm.scroll_page(direction='down', amount=200)
            time.sleep(random.uniform(2.0, 4.0))
            hm.scroll_page(direction='up', amount=100)
            hm.move_mouse_randomly()
            time.sleep(3)
        else:
            break

def fill_react_select(driver, placeholder: str, value: str):
    """
    Type a value into a react-select input identified by its placeholder text.
    Wellfound uses react-select for both the job title and location fields.
    After typing, waits for the dropdown, then picks the first suggestion or
    falls back to pressing Enter to trigger the search.
    """
    from selenium.webdriver.common.keys import Keys

    # react-select renders a sibling <div class="...-placeholder"> over the real
    # <input>. We locate by aria label or by the placeholder's parent container.
    input_el = None
    control_el = None

    # Strategy 1: look for an input whose container has a matching placeholder div
    try:
        # Find the placeholder div with matching text, then navigate to the input
        placeholders = driver.find_elements(
            By.XPATH,
            f"//div[contains(@class,'placeholder') and normalize-space(text())='{placeholder}']"
        )
        for ph in placeholders:
            try:
                # The real control container is the ancestor
                container = ph.find_element(By.XPATH, "./ancestor::div[contains(@class,'control')][1]")
                inp = container.find_element(By.TAG_NAME, "input")
                input_el = inp
                control_el = container
                break
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: match by aria-label on the input itself
    if input_el is None:
        try:
            input_el = driver.find_element(
                By.CSS_SELECTOR, f"input[aria-label='{placeholder}']"
            )
            control_el = input_el.find_element(By.XPATH, "./ancestor::div[contains(@class,'control')][1]")
        except Exception:
            pass

    # Strategy 3: fallback — any visible text input that isn't a search bar
    if input_el is None:
        try:
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[id^='react-select-']")
            if inputs:
                input_el = inputs[0] if placeholder.lower() in ("job title", "role") else (inputs[1] if len(inputs) > 1 else inputs[0])
                control_el = input_el.find_element(By.XPATH, "./ancestor::div[contains(@class,'control')][1]")
        except Exception:
            pass

    if input_el is None:
        logger.warning("⚠️  Could not locate react-select input for placeholder: '%s'", placeholder)
        return

    # Click the *container* to focus the React component (since input is only 2px wide)
    hm = HumanBehavior(driver)
    click_target = control_el if control_el else input_el
    hm.scroll_to_element(click_target)
    
    logger.info("  🖱️  Clicking '%s' field to focus...", placeholder)
    hm.human_click(click_target)
    time.sleep(0.5)
    
    logger.info("  ✏️  Human-typing '%s' into '%s' field...", value, placeholder)
    try:
        input_el.clear()
    except Exception:
        pass
    hm.human_type(input_el, value)

    # Wait for the react-select dropdown to appear and click the first option
    try:
        # Wait for any menu-like structure
        WebDriverWait(driver, 6).until(
            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, "[class$='-menu'], [class*='-menu '], div[id$='-listbox']"))
        )
        # Wait specifically for a clickable option
        option_selector = "[class$='-option'], [class*='-option '], [id*='-option-0']"
        first_option = WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, option_selector))
        )
        
        first_option.click()
        logger.info("  ✅ Selected first dropdown option for '%s'", placeholder)
        time.sleep(0.5)
    except (TimeoutException, NoSuchElementException, Exception) as e:
        # If menu or option doesn't appear or click fails, just press Enter
        logger.warning("  ⚠️ Dropdown interaction failed for '%s': %s. Falling back to Enter key.", placeholder, str(e))
        input_el.send_keys(Keys.ENTER)
        time.sleep(0.5)


def search_wellfound(driver):
    """
    Fills in the job title and location search fields via the UI and clicks the Search button.
    Assumes the browser is already on wellfound.com/jobs and has passed initial checks.
    Waits until job result cards appear before returning.
    """
    from selenium.webdriver.common.keys import Keys
    hm = HumanBehavior(driver)

    # Wait for the search form to be ready - increased timeout in case it loads slowly
    try:
        logger.info("⏳ Waiting up to 30s for the search form inputs to appear...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[id^='react-select-']"))
        )
    except TimeoutException:
        logger.warning("⚠️  Search form inputs did not appear in time. Taking screenshot.")
        try:
            driver.save_screenshot("data/search_inputs_timeout.png")
        except Exception:
            pass

    logger.info("🔍 Filling search form: title='%s', location='%s'", SEARCH_JOB_TITLE, SEARCH_LOCATION)

    # Fill job title
    fill_react_select(driver, "Job title", SEARCH_JOB_TITLE)
    time.sleep(1.2)

    # Fill location
    fill_react_select(driver, "Location", SEARCH_LOCATION)
    time.sleep(1.2)

    # Dynamic strategy to click the Search button
    search_clicked = False
    logger.info("  🔎 Clicking Search button...")
    
    # Array of dynamic selectors, from most robust structure to fallback text
    search_selectors = [
        (By.CSS_SELECTOR, "button[type='button'][class*='bg-black']"),
        (By.CSS_SELECTOR, "button.bg-black"),
        (By.XPATH, "//button[translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='search']"),
        (By.CSS_SELECTOR, "button[class*='hover:bg-gray-800']"),
        (By.CSS_SELECTOR, "form button[type='submit']")
    ]
    
    for by, sel in search_selectors:
        try:
            btn = driver.find_element(by, sel)
            if btn.is_displayed() and btn.is_enabled():
                hm.human_click(btn)
                search_clicked = True
                logger.info("  ✅ Clicked Search button using dynamic selector: %s", sel)
                break
        except Exception:
            continue

    if not search_clicked:
        logger.warning("  ⚠️ Could not find Search button dynamically, trying fallback Enter key.")
        try:
            active = driver.switch_to.active_element
            active.send_keys(Keys.ENTER)
        except Exception:
            pass
        
    time.sleep(3)

    # Wait for search results (job cards) to appear
    logger.info("⏳ Waiting for search results to load...")
    try:
        WebDriverWait(driver, PAGE_LOAD_WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f"a[href*='{JOB_LINK_PATTERN}']"))
        )
        logger.info("✅ Search results loaded. Current URL: %s", driver.current_url)
    except TimeoutException:
        logger.warning("⚠️  Search results did not load in time — will try to scrape anyway.")

    # Ensure we use the proper bot check after results load
    handle_bot_check(driver)





def dismiss_cookie_banner(driver):
    """Try to dismiss Wellfound's cookie consent banner if it appears."""
    cookie_selectors = [
        "button[id*='onetrust-accept']",
        "button[id*='accept']",
        "button[aria-label*='Agree']",
        "button[aria-label*='Accept']",
    ]
    for sel in cookie_selectors:
        try:
            btn = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
            btn.click()
            logger.info("🍪 Cookie banner dismissed.")
            time.sleep(1)
            return
        except TimeoutException:
            continue
        except Exception:
            continue

    # Generic text-based approach
    try:
        for tag in ("button", "a"):
            elems = driver.find_elements(By.TAG_NAME, tag)
            for el in elems:
                try:
                    text = (el.text or "").strip().lower()
                    if any(w in text for w in ("agree", "accept", "got it", "proceed")):
                        if el.is_displayed() and el.is_enabled():
                            el.click()
                            logger.info("🍪 Cookie banner dismissed via text match.")
                            time.sleep(1)
                            return
                except Exception:
                    continue
    except Exception:
        pass

    logger.debug("No cookie banner found (or already dismissed).")


def scroll_to_load_all(driver):
    """
    Scroll down incrementally so lazy-loaded job cards finish rendering.
    Stops when the page height stops growing.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    for _ in range(15):  # max 15 scroll steps per page
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    # Scroll back to top so the pagination buttons (at the bottom/top) are reachable
    driver.execute_script("window.scrollTo(0, 0);")


def extract_job_urls(driver) -> set:
    """
    Extract all unique job page URLs visible on the current page.
    Returns a set of absolute URLs that pass the AI/ML keyword filter.
    """
    found = set()
    try:
        # Wait until at least one job link is present
        WebDriverWait(driver, PAGE_LOAD_WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f"a[href*='{JOB_LINK_PATTERN}']"))
        )
        # Scroll to trigger lazy loading before reading all links
        scroll_to_load_all(driver)

        anchors = driver.find_elements(By.CSS_SELECTOR, f"a[href*='{JOB_LINK_PATTERN}']")
        for a in anchors:
            try:
                href = a.get_attribute("href") or ""
                text = (a.text or "").strip()
                
                # Strip query params, fragments, and trailing slash for clean dedup
                href = href.strip().split("?")[0].split("#")[0].rstrip("/")
                
                # Robust check: must have /jobs/ in URL and have a visible title (text)
                if href and JOB_LINK_PATTERN in href and text:
                    if is_aiml_url(href) or is_aiml_url(text):
                        if href not in found:
                            logger.info(f"    ✨ Found AI/ML Job: '{text}' -> {href}")
                            found.add(href)
                    else:
                        logger.debug(f"  ⏭  Skipped (no AI/ML keyword in title/URL): {text} ({href})")
            except StaleElementReferenceException:
                continue
    except TimeoutException:
        logger.warning("  ⚠️  No job links found on this page (timeout).")
    return found


def click_next_and_wait(driver) -> bool:
    """
    Find and click the Next page button, then wait dynamically until new job
    cards appear (URL change OR fresh job links detected). Returns True on
    success, False if no Next button exists or the click had no effect.
    """
    hm = HumanBehavior(driver)
    # Selectors tried in priority order (from live page inspection)
    next_selectors = [
        "a[aria-label='Next page']",
        "a[aria-label='Next Page']",
        "button[aria-label='Next page']",
        "button[aria-label='Next Page']",
        "a[data-test='Pagination-next']",
        "a.pagination-next",
        "button.pagination-next",
    ]

    btn = None
    for sel in next_selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed() and el.is_enabled():
                btn = el
                logger.info("  🔍 Found Next button via selector: %s", sel)
                break
        except (NoSuchElementException, StaleElementReferenceException):
            continue

    # Fallback: scan all <a>/<button> for visible Next text
    if btn is None:
        for tag in ("a", "button"):
            try:
                for el in driver.find_elements(By.TAG_NAME, tag):
                    try:
                        text = (el.text or "").strip().lower()
                        if text in ("next", "next page", "›", "»") and el.is_displayed() and el.is_enabled():
                            btn = el
                            logger.info("  🔍 Found Next button via text: '%s'", el.text.strip())
                            break
                    except StaleElementReferenceException:
                        continue
                if btn:
                    break
            except Exception:
                continue

    if btn is None:
        logger.info("  🛑 No Next button found — end of pagination.")
        return False

    # Snapshot current URL and a stale marker before clicking
    url_before = driver.current_url

    # Scroll button into view and click
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    time.sleep(random.uniform(0.6, 1.5))
    
    # Use human-like click
    hm.human_click(btn)
    logger.info("  🖱️  Clicked Next Page — waiting for content to refresh...")

    # Significant wait after click: Wellfound can be slow, 
    # and "fast clicks" are a strong bot signature.
    time.sleep(random.uniform(6.0, 9.0))

    try:
        # Wait until URL changes OR new cards appear
        WebDriverWait(driver, PAGE_LOAD_WAIT).until(
            lambda d: d.current_url != url_before or 
                     len(d.find_elements(By.CSS_SELECTOR, f"a[href*='{JOB_LINK_PATTERN}']")) > 0
        )
        # Final bit of human hesitation after load
        time.sleep(random.uniform(1.0, 4.0))
        return True
    except TimeoutException:
        logger.warning("  ⚠️  Timed out waiting for new page content after clicking Next.")
        return False

def load_existing_output(output_path: str) -> set:
    """If output JSON already exists, load its URLs for cross-run deduplication."""
    if not os.path.exists(output_path):
        return set()
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        existing = set(data.get("job_urls", []))
        logger.info("📂 Loaded %d existing URLs from %s", len(existing), output_path)
        return existing
    except Exception as e:
        logger.warning("Could not load existing output (%s) — starting fresh.", e)
        return set()


def save_output(output_path: str, job_urls: set, pages_scraped: int):
    """Save the collected job URLs to a JSON file (written after every page)."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    payload = {
        "source": "wellfound.com",
        "search_query": f"{SEARCH_JOB_TITLE} in {SEARCH_LOCATION}",
        "home_url": JOBS_HOME_URL,
        "keywords_filter": AIML_KEYWORDS,
        "pages_scraped": pages_scraped,
        "updated": datetime.now().isoformat(),
        "count": len(job_urls),
        "job_urls": sorted(job_urls),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info("💾 Saved %d unique job URLs to %s", len(job_urls), output_path)


# ─── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scrape AI/ML job URLs from Wellfound (up to N pages).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/scrape_wellfound_jobs.py
  python scripts/scrape_wellfound_jobs.py --max-pages 5
  python scripts/scrape_wellfound_jobs.py --output data/my_jobs.json --headless
        """,
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=settings.WELLFOUND_MAX_PAGES,
        metavar="N",
        help=f"Maximum number of pages to scrape (default: {settings.WELLFOUND_MAX_PAGES})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "wellfound_aiml_jobs.json",
        ),
        help="Output JSON file path (default: data/wellfound_aiml_jobs.json)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="Start fresh — do NOT merge with existing output file",
    )
    args = parser.parse_args()

    if args.headless:
        settings.HEADLESS = True
        logger.info("👻 Running in HEADLESS mode")

    # ── Start ───────────────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("🚀 Wellfound AI/ML Job URL Scraper")
    logger.info("   Search    : '%s' in '%s'", SEARCH_JOB_TITLE, SEARCH_LOCATION)
    logger.info("   Max pages : %d", args.max_pages)
    logger.info("   Output    : %s", args.output)
    logger.info("=" * 60)

    # Load previously scraped URLs for cross-run deduplication
    all_urls: set = set() if args.no_merge else load_existing_output(args.output)
    urls_before = len(all_urls)

    driver = None
    pages_scraped = 0

    try:
        driver = browser_service.start_browser()

        # ── Warm-up: land on /jobs first to allow cookie consent ─────────────
        logger.info("🌐 Warm-up: navigating to %s", JOBS_HOME_URL)
        driver.get(JOBS_HOME_URL)
        
        # Give DataDome/Cloudflare JS time to execute on the fresh profile
        # without immediately triggering aggressive navigation
        logger.info("⏳ Hesitating on landing page to pass passive bot checks...")
        time.sleep(random.uniform(6.0, 9.0))
        
        handle_bot_check(driver)
        dismiss_cookie_banner(driver)
        time.sleep(2)

        # ── Search via form ───────────────────────────────────────────────────
        search_wellfound(driver)

        # ── Page 1: results are now loaded from the search ────────────────────
        logger.info("─" * 50)
        logger.info("📄 Scraping page 1 / %d", args.max_pages)

        # ── Page loop (page 1 already loaded, pages 2-N via Next button) ──────
        for page_num in range(1, args.max_pages + 1):
            if page_num > 1:
                logger.info("─" * 50)
                logger.info("📄 Scraping page %d / %d", page_num, args.max_pages)

            # Sanity check — bail on error pages
            current_url = driver.current_url
            if "error" in current_url.lower() or "404" in current_url:
                logger.warning("  ⚠️  Error page detected — stopping at page %d.", page_num)
                break

            logger.info("   URL: %s", current_url)

            # Extract and filter job URLs from this page
            page_urls = extract_job_urls(driver)
            if not page_urls:
                logger.info("  🛑 No AI/ML job URLs on page %d — end of results.", page_num)
                break

            new_this_page = page_urls - all_urls
            all_urls.update(page_urls)
            pages_scraped = page_num

            logger.info(
                "   AI/ML URLs this page : %d  |  New (not seen before) : %d",
                len(page_urls),
                len(new_this_page),
            )
            logger.info("   Running total unique AI/ML URLs : %d", len(all_urls))

            # Save incrementally after every page
            save_output(args.output, all_urls, pages_scraped)

            if page_num >= args.max_pages:
                logger.info("   🏁 Reached max pages limit (%d). Done.", args.max_pages)
                break

            # ── Navigate to next page by clicking the Next button ─────────────
            if not click_next_and_wait(driver):
                logger.info("   🏁 No more pages after page %d.", page_num)
                break

    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user — saving collected URLs so far...")
        if all_urls:
            save_output(args.output, all_urls, pages_scraped)
        return 1

    except Exception as e:
        logger.critical("❌ Fatal error: %s", e)
        import traceback
        traceback.print_exc()
        if all_urls:
            logger.info("💾 Saving %d URLs collected before crash...", len(all_urls))
            save_output(args.output, all_urls, pages_scraped)
        return 1

    finally:
        if driver:
            logger.info("🧹 Closing browser...")
            browser_service.stop_browser()

    # ── Summary ─────────────────────────────────────────────────────────────────
    new_total = len(all_urls) - urls_before
    print("\n" + "=" * 60)
    print(f"✅  Wellfound scrape complete!")
    print(f"   Pages scraped  : {pages_scraped}")
    print(f"   Unique AI/ML   : {len(all_urls)} job URLs")
    print(f"   New this run   : {new_total}")
    print(f"   Output file    : {args.output}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
