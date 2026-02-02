import sys
import os
# Ensure project root is on sys.path so package-style imports work when running this script directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import time
from core.browser import browser_service
from strategies.custom.insight_global import InsightGlobalStrategy
from config.settings import settings


def main(apply: bool):
    # Ensure DRY RUN by default for safety
    settings.DRY_RUN = True

    # Optionally run headless by setting HEADLESS env var or editing .env
    driver = browser_service.start_browser()
    try:
        strat = InsightGlobalStrategy(driver, job_site=None, selectors=None)

        jobs = strat.find_jobs()
        print(f"Discovered {len(jobs)} jobs.")
        for j in jobs[:20]:
            print('-', j.get('job_title'), j.get('job_url'))

        if apply:
            print("Running apply loop (DRY RUN mode)")
            applied = strat.run_search_and_apply()
            print(f"Applied (DRY RUN count): {applied}")
    finally:
        time.sleep(1)
        browser_service.stop_browser()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Attempt to apply to discovered jobs (keeps DRY_RUN true unless you change env)')
    args = p.parse_args()
    main(args.apply)