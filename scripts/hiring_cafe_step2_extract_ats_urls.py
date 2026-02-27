#!/usr/bin/env python3
"""
Step 2: Extract ATS URLs for jobs from a Step 1 JSON.

Reads jobs from input file (job_id / hiring_cafe_url), opens each job page,
resolves Apply link (ATS URL), and writes updated JSON with ats_url and ats_platform.

Usage:
  python scripts/hiring_cafe_step2_extract_ats_urls.py [--input FILE] [--output FILE] [--limit N]
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.browser import browser_service
from core.logger import logger
from strategies.custom.hiring_cafe import HiringCafeStrategy
from config.settings import settings


def _normalize_job(j):
    """Ensure job has job_id and hiring_cafe_url for step 2."""
    jid = j.get("job_id") or j.get("external_id")
    url = j.get("hiring_cafe_url") or j.get("url") or j.get("job_posting_url")
    if not jid and url and "viewjob/" in url:
        jid = url.rstrip("/").split("viewjob/")[-1].split("?")[0]
    if jid and not url:
        url = f"https://hiring.cafe/viewjob/{jid}"
    return jid, url


def main():
    parser = argparse.ArgumentParser(
        description="Step 2: Extract ATS URLs for jobs from Step 1 JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/hiring_cafe_step2_extract_ats_urls.py --input hiring_cafe_jobs.json
  python scripts/hiring_cafe_step2_extract_ats_urls.py --input hiring_cafe_jobs.json --output enriched.json --limit 20
        """,
    )
    parser.add_argument(
        "--input",
        type=str,
        default="hiring_cafe_jobs.json",
        help="Input JSON from Step 1 (default: hiring_cafe_jobs.json)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON (default: overwrite --input)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        metavar="N",
        default=None,
        help="Only enrich first N jobs (default: all)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode",
    )
    args = parser.parse_args()
    output_path = args.output or args.input

    if not os.path.isfile(args.input):
        print(f"Error: input file not found: {args.input}", file=sys.stderr)
        return 1

    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    jobs = data.get("jobs") if isinstance(data, dict) else data
    if not jobs:
        print("No jobs in input.", file=sys.stderr)
        return 1

    # Normalize: ensure job_id and hiring_cafe_url
    for j in jobs:
        jid, url = _normalize_job(j)
        if not jid:
            continue
        j["job_id"] = jid
        j["hiring_cafe_url"] = url
        if "url" not in j:
            j["url"] = url

    to_process = jobs[: args.limit] if args.limit else jobs
    logger.info("🔗 Step 2: Extracting ATS URLs for %d jobs...", len(to_process))

    if args.headless:
        settings.HEADLESS = True
        logger.info("👻 Running in HEADLESS mode")

    driver = None
    try:
        driver = browser_service.start_browser()
        strategy = HiringCafeStrategy(driver)
        enriched = strategy.enrich_jobs_with_ats_links(jobs, limit=args.limit)

        payload = {
            "source": "hiring.cafe",
            "step": 2,
            "updated": datetime.now().isoformat(),
            "count": len(enriched),
            "jobs": [
                {
                    "job_id": j.get("job_id"),
                    "title": j.get("title"),
                    "hiring_cafe_url": j.get("hiring_cafe_url") or j.get("url"),
                    "ats_url": j.get("ats_url"),
                    "ats_platform": j.get("ats_platform"),
                    "source_keywords": j.get("source_keywords"),
                    "scraped_at": j.get("scraped_at"),
                }
                for j in enriched
            ],
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 60)
        print(f"✅ Step 2 complete: ATS URLs written to {output_path}")
        print("   Run step 3 to combine into by_ats file.")
        print("=" * 60)
        return 0

    except KeyboardInterrupt:
        logger.info("\n⚠️ Interrupted by user")
        return 1
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        if driver:
            logger.info("🧹 Closing browser...")
            browser_service.stop_browser()


if __name__ == "__main__":
    sys.exit(main())
