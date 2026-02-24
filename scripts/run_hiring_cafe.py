"""
Hiring Cafe Scraper Runner
Runs the HiringCafeStrategy to discover jobs and save them to hiring_cafe_output.json.
"""

import os
import sys
import argparse
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import logger
from core.browser import browser_service
from strategies.custom.hiring_cafe import HiringCafeStrategy

def main():
    parser = argparse.ArgumentParser(description="Run Hiring Cafe Scraper")
    parser.add_argument("--output", default="hiring_cafe_output.json", help="Output filename")
    parser.add_argument("--limit", type=int, help="Limit number of jobs to scrape")
    parser.add_argument("--enrich", action="store_true", help="Enrich jobs with ATS links (clicks each job)")
    parser.add_argument("--enrich-limit", type=int, help="Limit number of jobs to enrich")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    
    args = parser.parse_args()
    
    # Set headless mode if requested
    if args.headless:
        from config.settings import settings
        settings.HEADLESS = True

    driver = None
    try:
        logger.info("Starting browser...")
        driver = browser_service.start_browser()
        
        strategy = HiringCafeStrategy(driver=driver)
        
        logger.info(f"Starting scrape. Output will be saved to: {args.output}")
        jobs = strategy.scrape_and_save(
            output_file=args.output,
            enrich_ats=args.enrich,
            enrich_ats_limit=args.enrich_limit,
            job_limit=args.limit
        )
        
        if jobs:
            logger.info(f"✅ Successfully scraped and saved {len(jobs)} jobs to {args.output}")
        else:
            logger.warning("No jobs were found.")
            
    except Exception as e:
        logger.error(f"Error during scrape: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if driver:
            browser_service.stop_browser()

if __name__ == "__main__":
    main()
