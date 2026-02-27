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



#!/usr/bin/env python3
"""
Step 2 — Extract ATS URLs from hiring.cafe job pages.

CHECKPOINT / RESUME
───────────────────
Progress is saved to the JSON file after EVERY single job.
If execution is interrupted (Ctrl-C, crash, power cut, etc.):
  • All data extracted so far is already in the JSON file.
  • Simply re-run the EXACT SAME command — already-processed jobs
    are detected and skipped automatically.
  • You will never lose extracted data or have to start over.

Usage
─────
  # Normal run (all jobs)
  python scripts/hiring_cafe_step2_extract_ats_urls.py

  # Test with first 20 jobs only
  python scripts/hiring_cafe_step2_extract_ats_urls.py --limit 20

  # Resume after interrupt (same command, skips done jobs automatically)
  python scripts/hiring_cafe_step2_extract_ats_urls.py
"""

import argparse
import json
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

# Allow running from project root
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.browser import browser_service
from core.logger import logger
from strategies.custom.hiring_cafe import HiringCafeStrategy


# ── graceful shutdown flag ───────────────────────────────────────────────────
_shutdown_requested = False

def _handle_signal(sig, frame):
    global _shutdown_requested
    _shutdown_requested = True
    logger.warning("⚠️  Signal received — finishing current job then saving...")


def _load_jobs(path: str) -> tuple[dict, list[dict]]:
    """Load JSON and return (metadata_dict, jobs_list)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {}, data
    jobs = data.get("jobs", [])
    meta = {k: v for k, v in data.items() if k != "jobs"}
    return meta, jobs


def _save_jobs(path: str, meta: dict, jobs: list[dict]) -> None:
    """Atomically write jobs to file using a temp file to avoid corruption."""
    tmp = path + ".tmp"
    payload = {
        **meta,
        "step": 2,
        "updated": datetime.now().isoformat(),
        "count": len(jobs),
        "jobs": jobs,
    }
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    # Atomic rename — if this crashes mid-write the original is still intact
    os.replace(tmp, path)


def _resume_stats(jobs: list[dict], limit: int | None) -> tuple[int, int]:
    """Return (already_done, remaining) counts."""
    to_process = jobs[:limit] if limit else jobs
    done = sum(1 for j in to_process if "ats_url" in j)
    return done, len(to_process) - done


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Step 2: Extract ATS URLs (checkpoint/resume supported)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", default="hiring_cafe_jobs.json",
        help="Input JSON from Step 1 (default: hiring_cafe_jobs.json)",
    )
    parser.add_argument(
        "--output", default=None,
        help="Output file (default: overwrite --input in place)",
    )
    parser.add_argument(
        "--limit", type=int, default=None, metavar="N",
        help="Only process first N jobs (useful for testing)",
    )
    args = parser.parse_args()

    input_path  = args.input
    output_path = args.output or args.input  # overwrite in place by default

    # ── Validate input ───────────────────────────────────────────────────────
    if not os.path.isfile(input_path):
        print(f"❌ Input file not found: {input_path}", file=sys.stderr)
        return 1

    meta, jobs = _load_jobs(input_path)

    if not jobs:
        print("❌ No jobs found in input file.", file=sys.stderr)
        return 1

    # ── Ensure all jobs have job_id + hiring_cafe_url ────────────────────────
    for j in jobs:
        jid = j.get("job_id") or j.get("external_id")
        url = j.get("hiring_cafe_url") or j.get("url")
        if not jid and url and "viewjob/" in str(url):
            jid = str(url).rstrip("/").split("viewjob/")[-1].split("?")[0]
        if not url and jid:
            url = f"https://hiring.cafe/viewjob/{jid}"
        if jid:
            j["job_id"] = jid
        if url:
            j["hiring_cafe_url"] = url
            j.setdefault("url", url)

    # ── Resume stats ─────────────────────────────────────────────────────────
    already_done, remaining = _resume_stats(jobs, args.limit)

    print()
    print("=" * 60)
    print(f"📋 Total jobs loaded : {len(jobs)}")
    print(f"⏭️  Already processed : {already_done}  (will be skipped)")
    print(f"🔄 To process now    : {remaining}")
    print(f"💾 Saving to         : {output_path}  (after every job)")
    print("=" * 60)
    print()

    if remaining == 0:
        print("✅ All jobs already processed! Nothing to do.")
        print("   Run Step 3 to build the by_ats file.")
        return 0

    # ── Register signal handlers for graceful shutdown ───────────────────────
    signal.signal(signal.SIGINT,  _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # ── Monkey-patch strategy to check shutdown flag between jobs ────────────
    # We wrap _write_jobs_payload so it uses our atomic save
    driver = None
    exit_code = 0

    try:
        driver = browser_service.start_browser()
        strategy = HiringCafeStrategy(driver)

        # Override _write_jobs_payload to use our atomic save
        original_write = strategy._write_jobs_payload
        def _atomic_write(path, job_list):
            _save_jobs(path, meta, job_list)
        strategy._write_jobs_payload = _atomic_write

        # Run enrichment — saves after every job via output_file param
        strategy.enrich_jobs_with_ats_links(
            jobs,
            limit=args.limit,
            output_file=output_path,
        )

    except KeyboardInterrupt:
        logger.warning("⚠️  KeyboardInterrupt caught.")
        exit_code = 1

    except Exception as e:
        logger.critical("❌ Fatal error: %s", e)
        import traceback
        traceback.print_exc()
        exit_code = 1

    finally:
        # ── Always save before exiting ───────────────────────────────────────
        try:
            _save_jobs(output_path, meta, jobs)
            done_now, _ = _resume_stats(jobs, args.limit)
            logger.info("💾 Final save: %d/%d jobs processed → %s", done_now, len(jobs), output_path)
        except Exception as save_err:
            logger.critical("❌ Could not save final state: %s", save_err)

        if driver:
            try:
                browser_service.stop_browser()
                logger.info("🧹 Browser closed.")
            except Exception:
                pass

    # ── Summary ──────────────────────────────────────────────────────────────
    done_total, left = _resume_stats(jobs, args.limit)
    has_ats = sum(1 for j in jobs if j.get("ats_url"))

    print()
    print("=" * 60)
    if exit_code == 0:
        print(f"✅ Step 2 complete!")
    else:
        print(f"⚠️  Step 2 interrupted — progress saved. Re-run to resume.")
    print(f"   Jobs with ATS URL : {has_ats}")
    print(f"   Jobs processed    : {done_total}/{len(jobs)}")
    if left > 0:
        print(f"   Remaining         : {left}  ← re-run to continue")
    print(f"   Saved to          : {output_path}")
    if exit_code == 0:
        print()
        print("   ➡️  Run Step 3 next:")
        print("       python scripts/hiring_cafe_step3_combine_by_ats.py")
    print("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())


