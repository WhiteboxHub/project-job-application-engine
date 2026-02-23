"""
Scheduler Worker — JSON-Driven Automation Orchestration

Triggered by Windows Task Scheduler → run_scheduler.bat

Flow:
  1. Load candidate from parsed_resume.json + guest_form_data.json
  2. Query DuckDB for FULLY AUTOMATED sites (currently: LanceSoft only)
  3. For each site: launch strategy, skip already-applied jobs, log results

Usage:
    python scripts/scheduler_worker.py [--dry-run]
"""
import sys
import os
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import logger
from core.candidate_loader import CandidateLoader
from data.db_duckdb import db_duckdb
from config.settings import settings

# ----------------------------------------------------------------------------
# Fully automated sites config
# This replaces querying candidate_marketing / ats_platforms tables.
# Add more entries here when a new site is ready for full automation.
# ----------------------------------------------------------------------------
FULLY_AUTOMATED_SITES = [
    {
        "site_id": 2,
        "company_name": "LanceSoft",
        "domain": "lancesoft.com",
        "automation_level": "full",
        "class_handler": "strategies.custom.lancesoft.LanceSoftStrategy",
        "search_url_template": (
            "https://www2.jobdiva.com/portal/?a=3djdnw5yqdh8wl3frr5t6561tvvokq01affwpxt3lcutzo4f8yt1aeiy3msk02or"
            "&compid=0&SearchString="
        ),
    }
]


class SchedulerWorker:
    """Orchestrates automated job applications using JSON candidate data + DuckDB tracking"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.results = {
            "sites_processed": 0,
            "total_applications": 0,
            "successful": 0,
            "failed": 0,
            "errors": [],
        }

    # -------------------------------------------------------------------------
    # Site selection
    # -------------------------------------------------------------------------

    def get_fully_automated_sites(self):
        """Return list of fully automated site configs"""
        logger.info(f"📋 Fully automated sites configured: {len(FULLY_AUTOMATED_SITES)}")
        for s in FULLY_AUTOMATED_SITES:
            logger.info(f"   ✅ {s['company_name']} ({s['domain']})")
        return FULLY_AUTOMATED_SITES

    # -------------------------------------------------------------------------
    # Core automation runner
    # -------------------------------------------------------------------------

    def run_automation_for_site(self, candidate: dict, site: dict) -> dict:
        """
        Launch the strategy for one site and track results.

        Args:
            candidate: Unified dict from CandidateLoader.load()
            site:      Entry from FULLY_AUTOMATED_SITES

        Returns:
            dict with keys: status, applications, log_file
        """
        site_name = site["company_name"]
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 Processing: {candidate.get('first_name')} {candidate.get('last_name')} → {site_name}")
        logger.info(f"{'='*60}")

        # Resolve strategy class
        log_file = None
        try:
            # Set up per-run log file
            log_dir = Path("logs") / "automation" / datetime.now().strftime("%Y-%m-%d")
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%H%M%S")
            log_file = log_dir / f"{site_name}_{timestamp}.log"

            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.INFO)
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            logger.addHandler(file_handler)

            if self.dry_run:
                logger.info("🔍 DRY RUN — no applications will be submitted")
                settings.DRY_RUN = True

            # Dynamically import and instantiate the strategy
            module_path, class_name = site["class_handler"].rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            StrategyClass = getattr(module, class_name)

            # Boot browser
            from core.browser import BrowserService
            browser_svc = BrowserService()
            driver = browser_svc.start_browser()

            try:
                # Build a minimal job_site object the strategy expects
                job_site = _SiteConfig(site)

                # Instantiate strategy — passes candidate JSON as candidate_data
                strategy = StrategyClass(
                    driver=driver,
                    job_site=job_site,
                    selectors={},          # strategies load their own selectors
                    db_session=None,       # no DB session needed (DuckDB handles tracking)
                    candidate_data=candidate,
                )

                # Login / load portal
                logged_in = strategy.login()
                if not logged_in:
                    raise RuntimeError("Login/portal load failed")

                # Find + apply (single-phase for LanceSoft)
                if self.dry_run:
                    logger.info("🔍 DRY RUN — skipping actual applications")
                    apps_submitted = 0
                else:
                    apps_submitted = strategy.find_and_apply_jobs()

                logger.info(f"✅ {site_name} complete — {apps_submitted} applications submitted")

            finally:
                try:
                    if not settings.KEEP_BROWSER_OPEN:
                        browser_svc.stop_browser()
                except Exception:
                    pass

            # Log to DuckDB
            db_duckdb.log_scheduler_run(
                site=site_name,
                jobs_found=0,           # strategy doesn't return this separately
                jobs_applied=apps_submitted,
                status="completed",
            )

            logger.removeHandler(file_handler)
            file_handler.close()

            return {"status": "success", "applications": apps_submitted, "log_file": str(log_file)}

        except Exception as e:
            logger.error(f"❌ Error processing {site_name}: {e}")
            import traceback
            traceback.print_exc()

            db_duckdb.log_scheduler_run(
                site=site_name,
                jobs_found=0,
                jobs_applied=0,
                status="failed",
                error_message=str(e),
            )

            if log_file:
                try:
                    logger.removeHandler(file_handler)
                    file_handler.close()
                except Exception:
                    pass

            return {"status": "failed", "error": str(e)}

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    def run(self):
        """Main execution"""
        logger.info("=" * 70)
        logger.info("🚀 SCHEDULER WORKER STARTED")
        logger.info("=" * 70)
        logger.info(f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Dry Run   : {self.dry_run}")
        logger.info("")

        # Step 1 — Load candidate from JSON files
        logger.info("📄 Loading candidate data from JSON files...")
        candidate = CandidateLoader.load()
        if not candidate:
            logger.critical("❌ Could not load candidate data — aborting")
            return

        logger.info(
            f"👤 Candidate: {candidate.get('first_name')} {candidate.get('last_name')} "
            f"| {candidate.get('email')}"
        )
        logger.info("")

        # Step 2 — Get fully automated sites
        sites = self.get_fully_automated_sites()
        if not sites:
            logger.info("ℹ️  No fully automated sites configured")
            return

        logger.info(f"🌐 Running automation for {len(sites)} site(s)...\n")

        # Step 3 — Run each site
        for idx, site in enumerate(sites, 1):
            logger.info(f"[{idx}/{len(sites)}] {site['company_name']}")
            result = self.run_automation_for_site(candidate, site)

            self.results["sites_processed"] += 1
            if result["status"] == "success":
                self.results["successful"] += 1
                self.results["total_applications"] += result.get("applications", 0)
            else:
                self.results["failed"] += 1
                self.results["errors"].append({
                    "site": site["company_name"],
                    "error": result.get("error"),
                })

        self._print_summary()

    def _print_summary(self):
        logger.info("\n" + "=" * 70)
        logger.info("📊 EXECUTION SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Sites processed   : {self.results['sites_processed']}")
        logger.info(f"Total applications: {self.results['total_applications']}")
        logger.info(f"Successful        : {self.results['successful']}")
        logger.info(f"Failed            : {self.results['failed']}")

        if self.results["errors"]:
            logger.info("\n❌ Errors:")
            for err in self.results["errors"]:
                logger.info(f"   - {err['site']}: {err['error']}")

        logger.info("=" * 70)
        logger.info("✅ SCHEDULER WORKER COMPLETED")
        logger.info("=" * 70)


# ---------------------------------------------------------------------------
# Minimal site config object (duck-typed for strategies)
# ---------------------------------------------------------------------------

class _SiteConfig:
    """Lightweight object that mimics a SQLAlchemy JobSite row"""

    def __init__(self, site_dict: dict):
        self.id = site_dict.get("site_id", 0)
        self.company_name = site_dict.get("company_name", "")
        self.domain = site_dict.get("domain", "")
        self.search_url_template = site_dict.get("search_url_template", "")
        self.apply_url_template = site_dict.get("apply_url_template", "")
        self.automation_level = site_dict.get("automation_level", "full")
        self.is_active = True
        self.max_applications_per_run = site_dict.get("max_applications_per_run", 50)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scheduler Worker — Automated Job Applications")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without submitting applications")
    args = parser.parse_args()

    worker = SchedulerWorker(dry_run=args.dry_run)
    worker.run()


if __name__ == "__main__":
    main()
