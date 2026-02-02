import logging
import time
from core.browser import browser_service
from strategies.custom.insight_global import InsightGlobalStrategy
from config.settings import settings
from data.csv_tracker import tracker

logging.basicConfig(level=logging.INFO)

# Force safe test settings
settings.HEADLESS = True
settings.DRY_RUN = True

print("Starting test run: HEADLESS=True, DRY_RUN=True")

driver = None
try:
    driver = browser_service.start_browser()
    strat = InsightGlobalStrategy(driver, job_site=None, selectors=None)
    applied = strat.run_search_and_apply()
    print(f"Test run complete. Applications attempted (DRY_RUN): {applied}")
    jobs = tracker.get_jobs('insight_global')
    print(f"CSV tracker contains {len(jobs)} rows (showing up to 5):")
    for r in jobs[:5]:
        print(r)

except Exception as e:
    print(f"Test run failed: {e}")
finally:
    try:
        if driver:
            browser_service.stop_browser()
    except Exception:
        pass

print("Done.")
