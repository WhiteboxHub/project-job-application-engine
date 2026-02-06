import os
import time
import fcntl
import undetected_chromedriver as uc
from config.settings import settings
from core.logger import logger
from core.proxy_manager import proxy_manager

class BrowserService:
    def __init__(self):
        self.driver = None
        self.lock_file = None
        
    def _acquire_lock(self):
        """Ensures only one instance touches the profile."""
        profile_path = settings.chrome_profile_path
        os.makedirs(profile_path, exist_ok=True)
        lock_path = os.path.join(profile_path, "profile.lock")
        
        self.lock_file = open(lock_path, 'w')
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Acquired lock on profile: {profile_path}")
        except IOError:
            logger.critical(f"Could not acquire lock on {lock_path}. Is another instance running?")
            raise RuntimeError("Browser profile is locked by another process.")

    def _release_lock(self):
        if self.lock_file:
            fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            self.lock_file.close()
            logger.info("Released profile lock.")

    def start_browser(self):
        self._acquire_lock()
        
        try:
            from selenium import webdriver
            from selenium_stealth import stealth
            
            options = webdriver.ChromeOptions()
            # Note: We skip user-data-dir in standard selenium for better stability unless needed
            # options.add_argument(f"--user-data-dir={settings.chrome_profile_path}")
            
            proxy_arg = proxy_manager.get_proxy_option()
            if proxy_arg:
                options.add_argument(proxy_arg)
                
            if settings.HEADLESS:
                options.add_argument("--headless=new")
                
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            self.driver = webdriver.Chrome(options=options)
            
            # Apply stealth
            stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            
            logger.info("Standard Selenium with Stealth started successfully.")
        except Exception as e:
            logger.error(f"Failed to start standard browser: {e}")
            self._release_lock()
            raise

        return self.driver


    def stop_browser(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error closing driver: {e}")
            finally:
                self.driver = None
        
        self._release_lock()

browser_service = BrowserService()
