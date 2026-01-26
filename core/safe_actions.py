import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, ElementClickInterceptedException
from core.logger import logger

class SafeActions:
    def __init__(self, driver):
        self.driver = driver
        
    def _random_sleep(self, min_s=2.1, max_s=4.5):
        time.sleep(random.uniform(min_s, max_s))

    def _micro_move(self, element):
        """Moves mouse slightly offset from center before clicking."""
        try:
            action = ActionChains(self.driver)
            # Standard move to element
            action.move_to_element(element)
            # Add small random offset
            x_offset = random.randint(1, 10)
            y_offset = random.randint(1, 10)
            action.move_by_offset(x_offset, y_offset)
            action.perform()
        except Exception:
            # Fallback if move fails (e.g. element hidden?), just ignore
            pass

    def safe_click(self, selector, by=By.CSS_SELECTOR, timeout=10, retries=3):
        """
        Attempts to find and click an element with retries on Stale/Intercepted exceptions.
        """
        attempt = 0
        while attempt < retries:
            try:
                element = self.driver.find_element(by, selector)
                self._micro_move(element)
                self._random_sleep(0.5, 1.5)
                element.click()
                logger.debug(f"Clicked element: {selector}")
                return True
            except (StaleElementReferenceException, ElementClickInterceptedException) as e:
                logger.warning(f"Click failed ({type(e).__name__}) on {selector}, retrying ({attempt+1}/{retries})")
                time.sleep(2)
                attempt += 1
            except NoSuchElementException:
                logger.error(f"Element not found: {selector}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error clicking {selector}: {e}")
                return False
        return False

    def safe_type(self, selector, text, by=By.CSS_SELECTOR, retries=3):
        attempt = 0
        while attempt < retries:
            try:
                element = self.driver.find_element(by, selector)
                element.clear()
                self._random_sleep(0.3, 0.7)
                for char in text:
                    element.send_keys(char)
                    time.sleep(random.uniform(0.05, 0.2)) # Typing speed variation
                return True
            except StaleElementReferenceException:
                time.sleep(1)
                attempt += 1
            except Exception as e:
                logger.error(f"Error typing in {selector}: {e}")
                return False
        return False

    def check_exists(self, selector, by=By.CSS_SELECTOR):
        try:
            self.driver.find_element(by, selector)
            return True
        except NoSuchElementException:
            return False
