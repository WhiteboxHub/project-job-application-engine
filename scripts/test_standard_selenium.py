
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time

def test_standard_driver():
    print("Starting standard Selenium driver test...")
    try:
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=options)
        print("Driver started successfully!")
        driver.get("https://www.google.com")
        print(f"Title: {driver.title}")
        driver.quit()
        print("Driver closed successfully.")
    except Exception as e:
        print(f"Standard driver test failed: {e}")

if __name__ == "__main__":
    test_standard_driver()
