import os
import sys

# Add project root to sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from core.webdriver_manager import WebDriverManager
from data.db_duckdb import get_db

def test_wipro_session():
    # Setup paths
    os.makedirs('data', exist_ok=True)
    db_path = 'data/job_engine.duckdb'
    
    # Initialize DB
    conn = get_db(db_path)
    
    # Init WebDriver
    print("Starting WebDriver...")
    browser = WebDriverManager(headless=False, user_data_dir=None)
    driver = browser.get_driver()
    
    try:
        print("Driver active:", driver.session_id)
        print("Navigating to Wipro...")
        driver.get("https://careers.wipro.com/job/AI-Engineer/132892-en_US")
        
        # Test tab stability after page load
        print("Waiting 10 seconds to see if session drops...")
        import time
        for i in range(10):
            print(f"  Sec {i} - Session ID: {driver.session_id}, Title: {driver.title}")
            time.sleep(1)
            
    except Exception as e:
        print(f"Exception caught: {e}")
    finally:
        print("Closing browser...")
        browser.close()

if __name__ == "__main__":
    test_wipro_session()
