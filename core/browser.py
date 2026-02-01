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
        
        options = uc.ChromeOptions()
        options.add_argument(f"--user-data-dir={settings.chrome_profile_path}")
        
        proxy_arg = proxy_manager.get_proxy_option()
        if proxy_arg:
            options.add_argument(proxy_arg)
            
        if settings.HEADLESS:
            options.add_argument("--headless=new")
            
        # Defense evasion
        options.add_argument("--no-first-run")
        options.add_argument("--no-service-autorun")
        options.add_argument("--password-store=basic")
        
        try:
            self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=144)
            logger.info("Browser started successfully.")
        except Exception as e:
            logger.error(f"Failed to start browser: {e}")
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
