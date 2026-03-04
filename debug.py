import sys
import os
import time
from selenium.webdriver.common.by import By

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.browser import browser_service

driver = browser_service.start_browser()
driver.get("https://hiring.cafe/?searchState=%7B%22searchQuery%22%3A%20%22MLOps%22%2C%20%22dateFetchedPastNDays%22%3A%202%7D")
time.sleep(5)

links = driver.find_elements(By.CSS_SELECTOR, 'a[href^="/viewjob/"]')
print(f"Total links present in DOM: {len(links)}")
displayed = [el for el in links if el.is_displayed()]
print(f"Total links displayed: {len(displayed)}")

for i, l in enumerate(links[:5]):
    print(f"Link {i}: text='{l.text[:30]}', displayed={l.is_displayed()}, location={l.location}, size={l.size}")

browser_service.stop_browser()
