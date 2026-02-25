import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

def simple_inspect():
    print("Starting Simple TCS Inspection...")
    try:
        options = Options()
        # options.add_argument("--headless=new") # Run headless if preferred, but maybe headful is better for debugging
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        url = "https://www.tcs.com/careers"
        print(f"Navigating to {url}...")
        driver.get(url)
        time.sleep(10) # ample time to load
        
        title = driver.title
        print(f"Page Title: {title}")
        
        with open("tcs_simple_source.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("Saved source to tcs_simple_source.html")
        
        driver.quit()
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_inspect()
