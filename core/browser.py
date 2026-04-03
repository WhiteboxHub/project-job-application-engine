import os
import time
import sys

# --- Python 3.12 distutils shim ---
import sys
from types import ModuleType

def shim_distutils():
    # If distutils is already present and working, don't interfere
    try:
        from distutils.version import LooseVersion
        return
    except ImportError:
        pass

    try:
        # Many versions of setuptools bundle a functional distutils
        import setuptools
        try:
            import distutils
            sys.modules['distutils'] = distutils
            from distutils.version import LooseVersion
            return
        except ImportError:
            pass
    except ImportError:
        pass

    # If all else fails, provide a minimal compatible structure for UC
    d = ModuleType('distutils')
    d.__path__ = []
    d.__version__ = '3.12.0'
    sys.modules['distutils'] = d
    
    dv = ModuleType('distutils.version')
    # Minimal LooseVersion implementation to satisfy UC
    class LooseVersion:
        def __init__(self, version_str):
            import re
            self.vstring = str(version_str)
            # Split into parts like the real LooseVersion
            self.version = [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', self.vstring) if x]
        def __str__(self): return self.vstring
        def __repr__(self): return f"LooseVersion('{self.vstring}')"
        def __lt__(self, other): return self.version < (LooseVersion(other).version if isinstance(other, str) else getattr(other, 'version', []))
        def __le__(self, other): return self.version <= (LooseVersion(other).version if isinstance(other, str) else getattr(other, 'version', []))
        def __gt__(self, other): return self.version > (LooseVersion(other).version if isinstance(other, str) else getattr(other, 'version', []))
        def __ge__(self, other): return self.version >= (LooseVersion(other).version if isinstance(other, str) else getattr(other, 'version', []))
    
    dv.LooseVersion = LooseVersion
    sys.modules['distutils.version'] = dv
    sys.modules['distutils.spawn'] = ModuleType('distutils.spawn')

shim_distutils()
# -----------------------------------

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

    def _find_cached_driver(self):
        """Manually search for a cached chromedriver in the .wdm directory to bypass network blocks."""
        import glob
        # Try both the home directory and the workspace-relative path if applicable
        paths = [
            os.path.expanduser("~/.wdm/drivers/chromedriver/mac64"),
            os.path.join(os.getcwd(), ".wdm/drivers/chromedriver/mac64")
        ]
        
        for base_path in paths:
            if not os.path.exists(base_path):
                continue
            
            # Look for executable chromedriver files in subdirectories
            # Pattern: ~/.wdm/drivers/chromedriver/mac64/*/chromedriver-mac-arm64/chromedriver
            driver_binaries = glob.glob(os.path.join(base_path, "**/chromedriver"), recursive=True)
            
            if driver_binaries:
                # Sort by mtime (most recent first)
                driver_binaries.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                for binary in driver_binaries:
                    if os.access(binary, os.X_OK):
                        logger.info(f"Found cached driver via manual discovery: {binary}")
                        return binary
        return None

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

    def _get_chrome_version(self):
        """Detect local Chrome version on macOS."""
        import subprocess
        try:
            cmd = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"]
            output = subprocess.check_output(cmd).decode("utf-8")
            # Expected: "Google Chrome 146.0.7680.178"
            version = output.strip().split()[-1]
            main_version = int(version.split(".")[0])
            logger.info(f"Detected local Chrome version: {version} (main: {main_version})")
            return main_version
        except Exception as e:
            logger.warning(f"Could not detect local Chrome version: {e}")
            return None

    def start_browser(self):
        self._acquire_lock()
        
        chrome_main_version = self._get_chrome_version()

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
        
        # User-Agent Spoofing
        user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        options.add_argument(f"--user-agent={user_agent}")
        
        # Stability and bypassing some local DNS/Proxy blocks
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--dns-prefetch-disable")
        options.add_argument("--ignore-certificate-errors")

        # If undetected_chromedriver is available, prefer it
        if uc:
            try:
                # use_subprocess=True can sometimes cause NoSuchWindowException on macOS if Chrome
                # takes too long to bind. We'll try it, but increase the stabilization wait.
                self.driver = uc.Chrome(
                    options=options, 
                    use_subprocess=True,
                    version_main=chrome_main_version
                )
                
                # Wait for at least one window handle to appear
                for _ in range(10):
                    if self.driver.window_handles:
                        break
                    time.sleep(1)
                
                logger.info(
                    f"Browser started successfully (undetected-chromedriver, version_main={chrome_main_version})."
                )
            except Exception as e:
                logger.warning(
                    f"uc.Chrome failed to start (version_main={chrome_main_version}): {e}. Attempting fallback using webdriver-manager."
                )

        # Fallback: use webdriver-manager or local cache to start selenium Chrome
        if not self.driver:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service as ChromeService
                
                driver_path = None
                try:
                    from webdriver_manager.chrome import ChromeDriverManager
                    # Auto-detect driver version based on local Chrome installation
                    # Install() often fails if it can't check the latest version online
                    if chrome_main_version:
                        driver_path = ChromeDriverManager(driver_version=str(chrome_main_version)).install()
                    else:
                        driver_path = ChromeDriverManager().install()
                except Exception as wdm_err:
                    logger.warning(f"webdriver-manager failed: {wdm_err}. Trying manual cache lookup.")
                    driver_path = self._find_cached_driver()

                if not driver_path:
                    raise RuntimeError("No chromedriver found in cache and network download failed.")

                service = ChromeService(driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
                time.sleep(2)
                logger.info(
                    f"Browser started successfully (manual/cache fallback: {driver_path})."
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
                # Re-verify window handles before checking URL
                if not self.driver.window_handles:
                    raise RuntimeError("No window handles available after startup.")
                    
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
