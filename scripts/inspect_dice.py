
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def inspect_dice():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Add a common user agent to avoid basic bot detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    log_file = open("dice_inspection_log.txt", "w", encoding="utf-8")
    def log(msg):
        print(msg)
        log_file.write(msg + "\n")

    try:
        log("Navigating to Dice.com...")
        driver.get("https://www.dice.com/")
        time.sleep(15) 
        
        # Helper to recursively find elements in shadow roots
        def find_in_shadows(tag_name, text_filter=None, selector=None):
            script = """
                function findNested(root, tag, text, sel) {
                    let results = [];
                    let elements = sel ? root.querySelectorAll(sel) : root.querySelectorAll(tag);
                    for (let el of elements) {
                        if (!text || el.textContent.includes(text)) {
                            results.push(el);
                        }
                    }
                    let all = root.querySelectorAll('*');
                    for (let el of all) {
                        if (el.shadowRoot) {
                            results = results.concat(findNested(el.shadowRoot, tag, text, sel));
                        }
                    }
                    return results;
                }
                return findNested(document, arguments[0], arguments[1], arguments[2]);
            """
            return driver.execute_script(script, tag_name, text_filter, selector)

        log("Searching for 'Job Search' span in all Shadow Roots...")
        spans = find_in_shadows("span", "Job Search")
        if spans:
            log(f"Found {len(spans)} potential 'Job Search' spans")
            span_to_click = spans[0]
            
            log("Clicking 'Job Search' span via JS...")
            driver.execute_script("arguments[0].click();", span_to_click)
            time.sleep(5) 
            
            # Find inputs
            kw_input = find_in_shadows("input", selector="input[name='q']")
            loc_input = find_in_shadows("input", selector="input[name='location']")
            search_btn = find_in_shadows("button", selector="button[data-testid='job-search-search-bar-search-button']")
            
            if not search_btn:
                search_btn = find_in_shadows("button", text_filter="Search")

            if kw_input and loc_input and search_btn:
                log("Filling inputs and clicking Search...")
                driver.execute_script("arguments[0].value = 'AI Engineer';", kw_input[0] if isinstance(kw_input, list) else kw_input)
                driver.execute_script("arguments[0].value = 'USA';", loc_input[0] if isinstance(loc_input, list) else loc_input)
                time.sleep(1)
                driver.execute_script("arguments[0].click();", search_btn[0] if isinstance(search_btn, list) else search_btn)
                log("Search clicked, waiting for results...")
                time.sleep(15)
                
                log(f"Current URL after search: {driver.current_url}")
                
                # Save page source of results
                with open("dice_results_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                log("Saved dice_results_page.html")
                
                # Inspect results page for cards
                log("Searching for cards in results page Shadow DOM...")
                cards = find_in_shadows("dices-search-results-card")
                if not cards:
                    cards = find_in_shadows("div", selector=".card")
                if not cards:
                    cards = find_in_shadows("dhi-search-card")
                
                if cards:
                    log(f"Found {len(cards)} cards on results page")
                    for i, card in enumerate(cards[:5]):
                        html = driver.execute_script("return arguments[0].outerHTML", card)
                        log(f"Card {i} HTML snippet: {html[:300]}...") 
                else:
                    log("No cards found in Shadow DOM on results page.")
                    # Try standard results tags
                    std_links = driver.find_elements(By.TAG_NAME, "a")
                    log(f"Total links on page: {len(std_links)}")
                    # Look for links that might be job links
                    job_links = [l for l in std_links if "/job-detail/" in (l.get_attribute("href") or "")]
                    log(f"Found {len(job_links)} potential job detail links")
                    for i, l in enumerate(job_links[:3]):
                        log(f"Job Link {i}: {l.get_attribute('href')}")
            else:
                log("Failed to find inputs/button for search execution.")
        else:
            log("No 'Job Search' spans found.")

    except Exception as e:
        log(f"Error: {e}")
    finally:
        driver.quit()
        log_file.close()

if __name__ == "__main__":
    inspect_dice()
