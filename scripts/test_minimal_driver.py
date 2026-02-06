import undetected_chromedriver as uc
import time
import os

def test_browser():
    options = uc.ChromeOptions()
    # options.add_argument(f"--user-data-dir={os.path.abspath('./chrome_profile_test')}")
    
    print("Starting browser...")
    try:
        driver = uc.Chrome(options=options)
        print("Browser started. Navigating to Google...")
        driver.get("https://www.google.com")
        print(f"Title: {driver.title}")
        time.sleep(10)
        driver.quit()
        print("Success!")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_browser()
