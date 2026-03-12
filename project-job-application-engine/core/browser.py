import os
import time
try:
    import fcntl
    _HAS_FCNTL = True
except Exception:
    _HAS_FCNTL = False
uc = None
from config.settings import settings
from core.logger import logger
from core.proxy_manager import proxy_manager

class BrowserService:
    def __init__(self):
        self.driver = None
        self.lock_file = None
        
    def _acquire_lock(self):
        """Ensures only one instance touches the profile. On Windows (no fcntl) locking is skipped."""
        profile_path = settings.chrome_profile_path
        os.makedirs(profile_path, exist_ok=True)
        lock_path = os.path.join(profile_path, "profile.lock")

        self.lock_file = None
        if not _HAS_FCNTL:
            logger.info("fcntl not available on this platform; skipping profile locking.")
            return

        self.lock_file = open(lock_path, 'w')
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Acquired lock on profile: {profile_path}")
        except IOError:
            logger.critical(f"Could not acquire lock on {lock_path}. Is another instance running?")
            raise RuntimeError("Browser profile is locked by another process.")

    def _release_lock(self):
        if not _HAS_FCNTL:
            return
        if self.lock_file:
            try:
                fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            except Exception:
                pass
            self.lock_file.close()
            logger.info("Released profile lock.")

    def start_browser(self):
        self._acquire_lock()
        # Try to import undetected_chromedriver here; if unavailable, we'll fall back to selenium webdriver
        try:
            import undetected_chromedriver as uc_local
            global uc
            uc = uc_local
        except ModuleNotFoundError as e:
            # If undetected_chromedriver can't be imported (e.g., distutils missing), log and continue to fallback
            logger.warning(f"undetected_chromedriver import failed: {e}. Falling back to selenium webdriver.")
            uc = None

        if uc:
            options = uc.ChromeOptions()
        else:
            from selenium.webdriver import ChromeOptions
            options = ChromeOptions()
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
        
        # If undetected_chromedriver is available, prefer it
        if uc:
            try:
                # User is on version 145; explicitly set it to avoid v146 mismatch
                # use_subprocess=False fixes 'blank chrome' / 'window not found' on some Windows setups
                self.driver = uc.Chrome(
                    options=options, 
                    use_subprocess=False,
                    version_main=145
                )
                time.sleep(5) # Give the window handle time to stabilize
                logger.info("Browser started successfully (undetected-chromedriver v145).")
            except Exception as e:
                logger.warning(f"uc.Chrome failed to start: {e}. Attempting fallback using webdriver-manager.")

        # Fallback: use webdriver-manager to install a matching chromedriver and start selenium Chrome
        if not self.driver:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service as ChromeService
                from webdriver_manager.chrome import ChromeDriverManager

                # Force version 145 in fallback as well
                driver_path = ChromeDriverManager(driver_version="145.0.7632.117").install()
                service = ChromeService(driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
                time.sleep(2)
                logger.info("Browser started successfully (webdriver-manager fallback v145).")
            except Exception as e2:
                logger.error(f"Failed to start browser with fallback: {e2}")
                self._release_lock()
                raise

        if self.driver and not settings.HEADLESS:
            try:
                # Re-check if window still exists before maximizing
                if self.driver.window_handles:
                    self.driver.maximize_window()
            except Exception as e:
                logger.warning(f"Could not maximize window (non-fatal): {e}")

        # Final health check - verify session is actually responsive
        if self.driver:
            try:
                # Simple call to verify session is active
                _ = self.driver.current_url
                logger.info("Browser health check passed.")
            except Exception as e:
                logger.error(f"Browser health check failed: {e}")
                self.stop_browser()
                raise RuntimeError("Started browser but session is unresponsive (zombie).")

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
