"""
inspect_wipro_selectors.py
Navigates to Wipro search results and prints the actual CSS selectors for job containers.
Run with: python scripts/inspect_wipro_selectors.py
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.browser import BrowserManager

def inspect():
    mgr = BrowserManager()
    driver = mgr.start_browser(headless=False)
    
    url = "https://careers.wipro.com/search/?q=AI+Engineer&locationsearch=United+States"
    print(f"\nNavigating to: {url}")
    driver.get(url)
    time.sleep(8)  # give JS time to render
    
    # SAP SuccessFactors known selectors to try
    candidates = [
        "a.jobTitle",
        "a[class*='jobTitle']",
        "li.job-list-item",
        "div[class*='job-list']",
        "div.jobListItem",
        "table.joblisting tr",
        "div.joblisting",
        "span.jobTitle",
        "h2.jobTitle",
        "a[data-ph-at-id='job-link']",
        "div[data-ph-at-id='job-list-item']",
    ]
    
    print("\n=== Checking selectors ===")
    for sel in candidates:
        try:
            els = driver.find_elements("css selector", sel)
            if els:
                sample_text = els[0].text[:60] if els[0].text else "(no text)"
                sample_href = els[0].get_attribute('href') or ''
                print(f"  ✅ '{sel}' → {len(els)} elements  |  text: '{sample_text}'  |  href: {sample_href[:80]}")
            else:
                print(f"  ❌ '{sel}' → 0 elements")
        except Exception as e:
            print(f"  ❌ '{sel}' → error: {e}")
    
    # Also dump unique classes on any <a> tags in main content
    print("\n=== Looking at all <a> tags with 'job' in class/href ===")
    try:
        links = driver.find_elements("css selector", "a[href*='/job/'], a[href*='/jobs/'], a[class*='job']")
        for link in links[:10]:
            print(f"  href={link.get_attribute('href')}  class={link.get_attribute('class')}  text={link.text[:50]}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n=== Page title ===", driver.title)
    print("\nBrowser staying open - inspect manually then Ctrl+C")
    
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    
    driver.quit()

if __name__ == '__main__':
    inspect()
