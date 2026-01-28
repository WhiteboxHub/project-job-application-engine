import os
import time
import portalocker
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
            portalocker.lock(self.lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
            logger.info(f"Acquired lock on profile: {profile_path}")
        except portalocker.LockException:
            logger.critical(f"Could not acquire lock on {lock_path}. Is another instance running?")
            raise RuntimeError("Browser profile is locked by another process.")

    def _release_lock(self):
        if self.lock_file:
            portalocker.unlock(self.lock_file)
            self.lock_file.close()
            logger.info("Released profile lock.")

    def start_browser(self):
        self._acquire_lock()
        
        # Determine standard options first
        from selenium.webdriver.chrome.options import Options as SeleniumOptions
        sel_options = SeleniumOptions()
        sel_options.add_argument(f"--user-data-dir={os.path.abspath(settings.chrome_profile_path)}")
        
        proxy_arg = proxy_manager.get_proxy_option()
        if proxy_arg:
            sel_options.add_argument(proxy_arg)
            
        if settings.HEADLESS:
            sel_options.add_argument("--headless=new")
            
        sel_options.add_argument("--no-first-run")
        sel_options.add_argument("--no-service-autorun")
        sel_options.add_argument("--password-store=basic")
        sel_options.add_argument("--no-sandbox")
        sel_options.add_argument("--disable-dev-shm-usage")

        if settings.USE_UC:
            try:
                logger.info("Attempting to start undetected-chromedriver...")
                options = uc.ChromeOptions()
                for arg in sel_options.arguments:
                    options.add_argument(arg)
                
                self.driver = uc.Chrome(options=options)
                logger.info("Browser started successfully (undetected-chromedriver).")
                return self.driver
            except Exception as e:
                logger.warning(f"Failed to start undetected-chromedriver: {e}. Falling back to standard Selenium.")

        try:
            from selenium import webdriver
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            
            logger.info("Initializing standard Selenium with ChromeDriverManager...")
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=sel_options)
            logger.info("Browser started successfully (Standard Selenium).")
        except Exception as e:
            logger.error(f"Failed to start standard Selenium: {e}")
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
