import os
import re
import subprocess
import time
from pathlib import Path
import sys

# --- Python 3.12 distutils shim ---
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

    def _get_chrome_binary(self):
        """Return the first installed Chrome binary we can find."""
        candidates = [
            os.environ.get("CHROME_BINARY"),
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                "Google",
                "Chrome",
                "Application",
                "chrome.exe",
            ),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def _get_chrome_version(self, chrome_binary):
        """Best-effort full version detection for the installed Chrome binary."""
        if not chrome_binary:
            return None

        try:
            import subprocess

            output = subprocess.check_output(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-Item '{chrome_binary}').VersionInfo.ProductVersion",
                ],
                text=True,
            ).strip()
            return output or None
        except Exception:
            return None

    def _get_chrome_major_version(self, chrome_binary):
        """Return Chrome's major version as an int when available."""
        version = self._get_chrome_version(chrome_binary)
        if not version:
            return None

        match = re.match(r"(\d+)", version)
        if not match:
            return None

        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _find_local_chromedriver(self, chrome_major_version=None):
        """
        Look for an already-downloaded chromedriver before attempting any
        network-based installer.
        """
        explicit_path = os.environ.get("CHROMEDRIVER_PATH")
        if explicit_path and os.path.exists(explicit_path):
            return explicit_path

        home = Path.home()
        search_roots = [
            Path.cwd() / "drivers",
            Path.cwd() / "bin",
            home / ".cache" / "selenium",
            home / ".wdm",
        ]

        candidates = []
        for root in search_roots:
            if not root.exists():
                continue
            try:
                candidates.extend(root.rglob("chromedriver.exe"))
                # Also check for non-.exe if on non-Windows (though user is on Windows)
                candidates.extend(root.rglob("chromedriver"))
            except Exception:
                continue

        if not candidates:
            # Fallback to manual cached driver search
            return self._find_cached_driver()

        def version_key(path_obj):
            version_text = ""
            for part in path_obj.parts:
                match = re.search(r"\d+(?:\.\d+)+", part)
                if match:
                    version_text = match.group(0)
            if not version_text:
                return [0]
            return [int(piece) for piece in version_text.split(".")]

        matching_candidates = []
        if chrome_major_version is not None:
            for candidate in candidates:
                parsed_version = version_key(candidate)
                if parsed_version and parsed_version[0] == chrome_major_version:
                    matching_candidates.append(candidate)

        target_candidates = matching_candidates or candidates
        target_candidates.sort(key=version_key, reverse=True)
        return str(target_candidates[0])

    def _find_cached_driver(self):
        """Manually search for a cached chromedriver in the .wdm directory to bypass network blocks."""
        import glob
        # Try both the home directory and the workspace-relative path if applicable
        paths = [
            os.path.expanduser("~/.wdm/drivers/chromedriver/mac64"),
            os.path.join(os.getcwd(), ".wdm/drivers/chromedriver/mac64"),
            # Added common Windows wdm paths since user is on Windows
            os.path.expanduser("~/.wdm/drivers/chromedriver/win64"),
            os.path.join(os.getcwd(), ".wdm/drivers/chromedriver/win64")
        ]
        
        for base_path in paths:
            if not os.path.exists(base_path):
                continue
            
            # Look for executable chromedriver files in subdirectories
            search_pattern = os.path.join(base_path, "**/chromedriver*")
            driver_binaries = glob.glob(search_pattern, recursive=True)
            
            if driver_binaries:
                # Sort by mtime (most recent first)
                driver_binaries.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                for binary in driver_binaries:
                    # On Windows, check for .exe; on Mac/Linux check for executable bit
                    if binary.endswith(".exe") or os.access(binary, os.X_OK):
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

    @staticmethod
    def _get_installed_chrome_major_version_registry() -> int | None:
        """Read the installed Chrome major version from the Windows registry."""
        reg_keys = [
            r"HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon",
            r"HKEY_LOCAL_MACHINE\SOFTWARE\Google\Chrome\BLBeacon",
            r"HKEY_LOCAL_MACHINE\SOFTWARE\Wow6432Node\Google\Chrome\BLBeacon",
        ]
        for key in reg_keys:
            try:
                out = subprocess.check_output(
                    f'reg query "{key}" /v version',
                    shell=True, stderr=subprocess.DEVNULL
                ).decode(errors="ignore")
                m = re.search(r"version\s+REG_SZ\s+(\d+)", out)
                if m:
                    version = int(m.group(1))
                    logger.info(f"Detected installed Chrome major version: {version}")
                    return version
            except Exception:
                continue
        logger.warning("Could not detect Chrome version from registry; uc will auto-detect.")
        return None

    def _cleanup_orphans(self):
        """Clean up orphaned chromedriver processes on Windows."""
        if os.name == "nt":
            try:
                # Use taskkill to cleanly remove orphaned drivers
                subprocess.run(
                    "taskkill /F /IM chromedriver.exe /T",
                    shell=True,
                    capture_output=True,
                    check=False
                )
                logger.info("Cleaned up orphaned chromedriver processes.")
            except Exception as e:
                logger.debug(f"Process cleanup warning: {e}")

    def start_browser(self):
        self._cleanup_orphans()
        self._acquire_lock()

        # Detect installed Chrome version once so both drivers use the same version
        chrome_major_version = self._get_installed_chrome_major_version_registry()
        
        explicit_driver_path = os.environ.get("CHROMEDRIVER_PATH")
        explicit_driver_exists = explicit_driver_path and os.path.exists(explicit_driver_path)

        # Try to import undetected_chromedriver here; if unavailable, we'll fall back to selenium webdriver
        if explicit_driver_path and not explicit_driver_exists:
            logger.warning(
                f"CHROMEDRIVER_PATH was set but the file does not exist: {explicit_driver_path}"
            )

        if explicit_driver_exists:
            logger.info(
                "CHROMEDRIVER_PATH detected; skipping undetected_chromedriver and using the explicit local driver."
            )
            global uc
            uc = None
        else:
            try:
                import undetected_chromedriver as uc_local

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

        chrome_binary = self._get_chrome_binary()
        chrome_major_version = self._get_chrome_major_version(chrome_binary)
        if chrome_binary:
            options.binary_location = chrome_binary

        proxy_arg = proxy_manager.get_proxy_option()
        if proxy_arg:
            options.add_argument(proxy_arg)

        # Essential stability flags to prevent "DevToolsActivePort file doesn't exist" crashes in Task Scheduler
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=0")  # Let OS pick free port
        
        # Prevent Chrome on Windows from freezing page loads when running in background
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")

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

                # use_subprocess=True is required on Windows to prevent 'chrome not reachable'.
                # version_main is set to the detected Chrome major version to avoid ChromeDriver
                # version mismatches (e.g. uc ships driver 147 but Chrome is 146).
                self.driver = uc.Chrome(
                    options=options,
                    use_subprocess=True,
                    version_main=chrome_major_version,  # None = let uc auto-detect (safe fallback)
                )
                time.sleep(5)  # Give the window handle time to stabilize

                # Immediate check: Is the session actually alive?
                _ = self.driver.current_url
                logger.info(
                    f"Browser started successfully (undetected-chromedriver, version={chrome_major_version})."
                )
            except Exception as e:
                logger.warning(
                    f"uc.Chrome failed or produced a zombie session: {e}. Attempting fallback using webdriver-manager."
                )
                if self.driver:
                    self.stop_browser()
                    self.driver = None

        # Fallback: use webdriver-manager or local cache to start selenium Chrome
        if not self.driver:
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service as ChromeService
                from webdriver_manager.chrome import ChromeDriverManager

                # Prefer any already-cached local chromedriver before downloading one.
                driver_path = (
                    explicit_driver_path
                    if explicit_driver_exists
                    else self._find_local_chromedriver(chrome_major_version)
                )
                if driver_path:
                    logger.info(f"Using local chromedriver: {driver_path}")
                else:
                    logger.info(
                        "No local chromedriver found; attempting webdriver-manager download."
                    )
                    manager_kwargs = {}
                    if chrome_major_version is not None:
                        manager_kwargs["driver_version"] = str(chrome_major_version)
                    driver_path = ChromeDriverManager(**manager_kwargs).install()

                # Pin to detected Chrome version so webdriver-manager fetches the right driver
                service = ChromeService(driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
                time.sleep(2)
                logger.info(
                    f"Browser started successfully (webdriver-manager fallback, version={chrome_major_version})."
                )
            except Exception as e2:
                chrome_version = self._get_chrome_version(chrome_binary)
                logger.error(f"Failed to start browser with fallback: {e2}")
                self._release_lock()
                raise RuntimeError(
                    "Unable to start Chrome. "
                    f"Detected Chrome at '{chrome_binary or 'not found'}'"
                    + (f" (version {chrome_version})" if chrome_version else "")
                    + ". Install a matching chromedriver locally or allow network access so webdriver-manager can download it."
                ) from e2

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
                logger.error(f"Browser health check failed during final validation: {e}")
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
