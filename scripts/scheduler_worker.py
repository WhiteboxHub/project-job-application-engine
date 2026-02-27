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
    },
    {
        "site_id": 5,
        "company_name": "KForce",
        "domain": "kforce.com",
        "automation_level": "full",
        "class_handler": "strategies.custom.kforce.KForceStrategy",
        "search_url_template": "https://www.kforce.com/find-work/search-jobs/?keyword=",
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
    # Backend API Interactions
    # -------------------------------------------------------------------------

    def _fetch_eligible_candidates(self) -> list:
        """Fetch candidates from backend with run_weekly_flow=1"""
        url = f"{settings.BACKEND_URL}/api/weekly-workflow/eligible-candidates"
        try:
            logger.info(f"Fetching eligible candidates from {url}")
            import requests # Lazy load
            resp = requests.get(url, headers={"X-Internal-Secret": "super-secret-weekly-workflow-key"}, timeout=10)
            resp.raise_for_status()
            candidates = resp.json()
            logger.info(f"Found {len(candidates)} candidate(s) ready for automation")
            return candidates
        except Exception as e:
            logger.error(f"Failed to fetch candidates: {e}")
            return []

    def _reset_candidate_flag(self, candidate_id: int):
        """Reset run_weekly_flow flag on the backend"""
        if self.dry_run:
            logger.info(f"DRY RUN — Skipping reset for candidate {candidate_id}")
            return
        
        url = f"{settings.BACKEND_URL}/api/weekly-workflow/reset/{candidate_id}"
        try:
            import requests
            resp = requests.post(url, headers={"X-Internal-Secret": "super-secret-weekly-workflow-key"}, timeout=10)
            resp.raise_for_status()
            logger.info(f"Reset workflow flag for candidate {candidate_id}")
        except Exception as e:
            logger.error(f"Failed to reset flag for candidate {candidate_id}: {e}")

    def _get_workflow_id(self) -> int:
        """Fetch workflow ID by key"""
        url = f"{settings.BACKEND_URL}/api/automation-workflow/by-key/{self.workflow_key}"
        try:
            import requests
            resp = requests.get(url, headers={"X-Internal-Secret": "super-secret-weekly-workflow-key"}, timeout=10)
            if resp.status_code == 404:
                return 0
            resp.raise_for_status()
            return resp.json().get("id", 0)
        except Exception as e:
            logger.error(f"Failed to fetch workflow id: {e}")
            return 0

    def _get_schedule_id(self, workflow_id: int) -> int:
        """Find a schedule for the given workflow"""
        if workflow_id == 0:
            return 0
        url = f"{settings.BACKEND_URL}/api/automation-workflow-schedule/"
        try:
            import requests
            resp = requests.get(url, headers={"X-Internal-Secret": "super-secret-weekly-workflow-key"}, timeout=10)
            resp.raise_for_status()
            schedules = resp.json()
            for s in schedules:
                if s.get("automation_workflow_id") == workflow_id:
                    return s.get("id", 0)
            return 0
        except Exception as e:
            return 0

    def _update_schedule(self, schedule_id: int, run_parameters: dict, is_running: bool):
        """Update schedule run parameters and status"""
        if schedule_id == 0 or self.dry_run:
            return
        url = f"{settings.BACKEND_URL}/api/automation-workflow-schedule/{schedule_id}"
        payload = {
            "run_parameters": run_parameters,
            "is_running": is_running,
            "last_run_at": datetime.now().isoformat()
        }
        try:
            import requests
            requests.put(url, headers={"X-Internal-Secret": "super-secret-weekly-workflow-key"}, json=payload, timeout=10).raise_for_status()
        except Exception as e:
            logger.error(f"Failed to update schedule {schedule_id}: {e}")

    def _create_log_entry(self, workflow_id: int, schedule_id: int, run_id: str, parameters: dict):
        """Create a starting log entry"""
        if workflow_id == 0 or self.dry_run:
            return
        url = f"{settings.BACKEND_URL}/api/automation-workflow-log/"
        payload = {
            "workflow_id": workflow_id,
            "schedule_id": schedule_id if schedule_id > 0 else None,
            "run_id": run_id,
            "status": "running",
            "parameters_used": parameters,
            "started_at": datetime.now().isoformat()
        }
        try:
            import requests
            requests.post(url, headers={"X-Internal-Secret": "super-secret-weekly-workflow-key"}, json=payload, timeout=10).raise_for_status()
        except Exception:
            pass

    def _update_log_entry(self, run_id: str, status: str, metadata: dict, processed: int, failed: int, error: str = None):
        """Update log entry upon completion"""
        if self.dry_run:
            return
        url = f"{settings.BACKEND_URL}/api/automation-workflow-log/by-run-id/{run_id}"
        payload = {
            "status": status,
            "execution_metadata": metadata,
            "records_processed": processed,
            "records_failed": failed,
            "error_summary": error[:255] if error else None,
            "finished_at": datetime.now().isoformat()
        }
        try:
            import requests
            requests.patch(url, headers={"X-Internal-Secret": "super-secret-weekly-workflow-key"}, json=payload, timeout=10).raise_for_status()
        except Exception as e:
            logger.error(f"Failed to update log entry for run {run_id}: {e}")

    # -------------------------------------------------------------------------
    # Main entry point
    # -------------------------------------------------------------------------

    def run(self):
        """Main execution"""
        logger.info("=" * 70)
        logger.info("SCHEDULER WORKER STARTED")
        logger.info("=" * 70)
        logger.info(f"Timestamp : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Dry Run   : {self.dry_run}")
        logger.info("")

        self.workflow_key = "weekly_automation_application_engine"
        self.results["candidates_found"] = 0

        # Step 1 — Fetch candidates from backend
        all_candidates = self._fetch_eligible_candidates()
        
        # If no candidates on backend, fallback to local JSON for one-off testing
        if not all_candidates:
            logger.warning("No candidates found on backend — attempting fallback to local JSON files")
            local_candidate = CandidateLoader.load()
            if local_candidate:
                all_candidates = [{"candidate_id": 0, "candidate_json": local_candidate}]
            else:
                logger.critical("No candidates found anywhere — aborting")
                return

        self.results["candidates_found"] = len(all_candidates)

        # Step 2 — Fetch workflow and schedule context
        workflow_id = self._get_workflow_id()
        schedule_id = self._get_schedule_id(workflow_id)

        # Step 3 — Get fully automated sites
        sites = self.get_fully_automated_sites()
        if not sites:
            logger.info("No fully automated sites configured")
            return

        logger.info(f"Running automation for {len(all_candidates)} candidate(s) across {len(sites)} site(s)...\n")

        # Step 4 — Process each candidate
        import uuid # dynamic import to avoid altering top of file
        for c_idx, cand_record in enumerate(all_candidates, 1):
            cand_id = cand_record.get("candidate_id", 0)
            cand_data_raw = cand_record.get("candidate_json")
            if isinstance(cand_data_raw, str):
                try:
                    cand_data = json.loads(cand_data_raw)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON for candidate {cand_id}")
                    continue
            else:
                cand_data = cand_data_raw if cand_data_raw else {}

            # Inject top-level fields from the record into cand_data if they are missing
            for field in ["resume_url", "email", "phone", "first_name", "last_name"]:
                if field in cand_record and field not in cand_data:
                    cand_data[field] = cand_record[field]

            # Workflow Setup for this Candidate
            run_id = str(uuid.uuid4())
            if workflow_id > 0:
                self._update_schedule(schedule_id, cand_data, True)
                self._create_log_entry(workflow_id, schedule_id, run_id, cand_data)

            # Load into unified format via CandidateLoader
            candidate = CandidateLoader.load(cand_data)
            
            fullname = f"{candidate.get('first_name')} {candidate.get('last_name')}"
            logger.info(f"[{c_idx}/{len(all_candidates)}] Processing Candidate: {fullname} (ID: {cand_id})")

            # Process each site for this candidate
            cand_results = []
            cand_success_count = 0
            cand_fail_count = 0
            
            for s_idx, site in enumerate(sites, 1):
                logger.info(f"   [{s_idx}/{len(sites)}] Site: {site['company_name']}")
                result = self.run_automation_for_site(candidate, site)

                self.results["sites_processed"] += 1
                if result["status"] == "success":
                    self.results["successful"] += 1
                    self.results["total_applications"] += result.get("applications", 0)
                    cand_success_count += 1
                    cand_results.append({"site": site['company_name'], "status": "success", "apps": result.get("applications")})
                else:
                    cand_fail_count += 1
                    self.results["failed"] += 1
                    self.results["errors"].append({
                        "candidate": fullname,
                        "site": site["company_name"],
                        "error": result.get("error"),
                    })
                    cand_results.append({"site": site['company_name'], "status": "failed", "error": result.get("error")})

            # Teardown / Log results for this Candidate
            if workflow_id > 0:
                status = "success" if cand_fail_count == 0 else "partial_success" if cand_success_count > 0 else "failed"
                self._update_log_entry(run_id, status, {"detailed_results": cand_results}, cand_success_count, cand_fail_count)
                self._update_schedule(schedule_id, {}, False)

            # Reset flag on backend if everything finished
            if cand_id > 0:
                self._reset_candidate_flag(cand_id)

            # Cleanup: Delete downloaded resume if it's in the downloads folder
            resume_path = candidate.get("resume_path")
            if resume_path and "downloads" in resume_path and os.path.exists(resume_path):
                try:
                    os.remove(resume_path)
                except Exception:
                    pass

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
