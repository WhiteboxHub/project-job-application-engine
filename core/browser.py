import os
import re
import subprocess
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
            logger.info(
                "fcntl not available on this platform; skipping profile locking."
            )
            return

        self.lock_file = open(lock_path, "w")
        try:
            fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Acquired lock on profile: {profile_path}")
        except IOError:
            logger.critical(
                f"Could not acquire lock on {lock_path}. Is another instance running?"
            )
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

    @staticmethod
    def _get_chrome_major_version() -> int | None:
        """Read the installed Chrome major version from the Windows registry."""
        reg_keys = [
            r'HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon',
            r'HKEY_LOCAL_MACHINE\SOFTWARE\Google\Chrome\BLBeacon',
            r'HKEY_LOCAL_MACHINE\SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon',
        ]
        for key in reg_keys:
            try:
                out = subprocess.check_output(
                    f'reg query "{key}" /v version',
                    shell=True, stderr=subprocess.DEVNULL
                ).decode(errors="ignore")
                m = re.search(r'version\s+REG_SZ\s+(\d+)', out)
                if m:
                    version = int(m.group(1))
                    logger.info(f"Detected installed Chrome major version: {version}")
                    return version
            except Exception:
                continue
        logger.warning("Could not detect Chrome version from registry; uc will auto-detect.")
        return None

    def start_browser(self):
        self._acquire_lock()

        # Detect installed Chrome version once so both drivers use the same version
        chrome_version = self._get_chrome_major_version()

        # Try to import undetected_chromedriver here; if unavailable, we'll fall back to selenium webdriver
        try:
            import undetected_chromedriver as uc_local

            global uc
            uc = uc_local
        except ModuleNotFoundError as e:
            # If undetected_chromedriver can't be imported (e.g., distutils missing), log and continue to fallback
            logger.warning(
                f"undetected_chromedriver import failed: {e}. Falling back to selenium webdriver."
            )
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

        # Essential stability flags to prevent "DevToolsActivePort file doesn't exist" crashes in Task Scheduler
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if settings.HEADLESS:
            options.add_argument("--headless=new")

        # Defense evasion
        options.add_argument("--no-first-run")
        options.add_argument("--no-service-autorun")
        options.add_argument("--password-store=basic")

        # If undetected_chromedriver is available, prefer it
        if uc:
            try:
<<<<<<< HEAD
                # use_subprocess=True is required on Windows to prevent 'chrome not reachable'.
                # version_main is set to the detected Chrome major version to avoid ChromeDriver
                # version mismatches (e.g. uc ships driver 147 but Chrome is 146).
                self.driver = uc.Chrome(
                    options=options,
                    use_subprocess=True,
                    version_main=chrome_version,  # None = let uc auto-detect (safe fallback)
                )
                time.sleep(5)  # Give the window handle time to stabilize
                logger.info(
                    f"Browser started successfully (undetected-chromedriver, version={chrome_version})."
=======
                # version_main=146 pins ChromeDriver to match Chrome 146.0.x
                # Change this if you update Chrome to a newer major version
                self.driver = uc.Chrome(
                    options=options, use_subprocess=True, version_main=146
                )
                time.sleep(5)  # Give the window handle time to stabilize
                logger.info(
                    "Browser started successfully (undetected-chromedriver v146)."
>>>>>>> 3f314ca3d9809e6a903bc14e2efd88b06adbd4c9
                )
            except Exception as e:
                logger.warning(
                    f"uc.Chrome failed to start: {e}. Attempting fallback using webdriver-manager."
                )

        # Fallback: use webdriver-manager to install a matching chromedriver and start selenium Chrome
        if not self.driver:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service as ChromeService
                from webdriver_manager.chrome import ChromeDriverManager

                # Pin to detected Chrome version so webdriver-manager fetches the right driver
                driver_path = ChromeDriverManager(
                    driver_version=f"{chrome_version}" if chrome_version else None
                ).install()
                service = ChromeService(driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
                time.sleep(2)
                logger.info(
                    f"Browser started successfully (webdriver-manager fallback, version={chrome_version})."
                )
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
                raise RuntimeError(
                    "Started browser but session is unresponsive (zombie)."
                )

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
