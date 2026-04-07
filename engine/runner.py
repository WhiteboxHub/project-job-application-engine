"""
Engine Runner - Main Orchestration Logic
Coordinates the entire automation workflow.
Uses raw DuckDB queries (no SQLAlchemy ORM session needed).
"""

import json
from datetime import datetime

from core.browser import browser_service
from core.backend_client import backend_client
from core.candidate_loader import CandidateLoader
from core.logger import logger
from core.execution_logger import execution_tracker
from data.csv_tracker import tracker as csv_tracker
from data.db_connection import db
from engine.factory import strategy_factory
from engine.guards import guards


class _SiteRow:
    """Duck-typed JobSite object built from a raw DuckDB row"""

    def __init__(self, row):
        # row columns: id, company_name, domain, search_url_template,
        #              apply_url_template, max_applications_per_run,
        #              class_handler, automation_level
        self.id = row[0]
        self.company_name = row[1]
        self.domain = row[2]
        self.search_url_template = row[3]
        self.apply_url_template = row[4]
        self.max_applications_per_run = row[5]
        self.is_active = True
        # Simulate platform relationship
        self.platform = _PlatformRow(row[6], row[7])


class _PlatformRow:
    def __init__(self, class_handler, automation_level):
        self.class_handler = class_handler
        self.automation_level = automation_level or "manual"


def _log_status_from_report(report_status: str) -> str:
    """Map output.json status to automation_workflow_logs.status enum."""
    if report_status == "success":
        return "success"
    if report_status == "completed_with_errors":
        return "partial_success"
    return "failed"


class EngineRunner:
    """Main orchestrator for the job application engine"""

    def __init__(self):
        self.browser = None

    def run(self, site_filter=None, candidate_data=None, workflow_log_id=None):
        """
        Main execution workflow:
        1. Initialize Browser
        2. Fetch Active Sites from DuckDB
        3. For each site: load strategy, run find_and_apply
        4. Cleanup and report

        Args:
            site_filter (str, optional): Company name to filter (case-insensitive)
            candidate_data (dict, optional): Candidate data override
        """
        logger.info("=" * 60)
        logger.info("Starting Job Application Engine...")
        logger.info("=" * 60)

        started_at = datetime.utcnow().isoformat()

        try:
            if not candidate_data:
                candidate_data = CandidateLoader.load()

            execution_tracker.initialize(
                run_parameters=candidate_data, workflow_log_id=workflow_log_id
            )

            # 2. Get Active Sites from DuckDB
            conn = db.get_connection()

            # When --site is given explicitly, bypass is_active so inactive sites
            # can still be run on-demand (e.g. KForce, Capgemini set is_active=false)
            params = []
            if site_filter:
                sql = """
                    SELECT
                        js.id,
                        js.company_name,
                        js.domain,
                        js.search_url_template,
                        js.apply_url_template,
                        js.max_applications_per_run,
                        ap.class_handler,
                        ap.automation_level
                    FROM job_sites js
                    JOIN ats_platforms ap ON js.ats_platform_id = ap.id
                    WHERE (
                        LOWER(REPLACE(js.company_name, ' ', '')) LIKE LOWER(REPLACE(?, ' ', ''))
                        OR LOWER(js.domain) LIKE LOWER(?)
                    )
                """
                search_term = f"%{site_filter}%"
                params.extend([search_term, search_term])
                logger.info(f"[SEARCH] Filtering for site: {site_filter}")
            else:
                sql = """
                    SELECT
                        js.id,
                        js.company_name,
                        js.domain,
                        js.search_url_template,
                        js.apply_url_template,
                        js.max_applications_per_run,
                        ap.class_handler,
                        ap.automation_level
                    FROM job_sites js
                    JOIN ats_platforms ap ON js.ats_platform_id = ap.id
                    WHERE js.is_active = true AND ap.automation_level = 'full'
                """

            rows = conn.execute(sql, params).fetchall()
            active_sites = [_SiteRow(r) for r in rows]

            if not active_sites:
                if site_filter:
                    logger.warning(
                        f"[WARNING] No active job site found matching '{site_filter}'"
                    )
                    logger.info(
                        "Tip: check job_sites table in DuckDB or run scripts/init_db.py"
                    )
                else:
                    logger.warning("[WARNING] No active job sites found in DuckDB.")
                return

            logger.info(f"\n[LIST] Found {len(active_sites)} active job site(s):")
            for site in active_sites:
                logger.info(
                    f"   - {site.company_name} ({site.domain}) [{site.platform.automation_level}]"
                )

            # 3. Process each site (candidate_data / tracker already initialized)
            for site in active_sites:
                if not guards.can_apply():
                    logger.warning("Application limit reached. Stopping.")
                    break
                self._process_site(conn, site, candidate_data)

        except KeyboardInterrupt:
            logger.warning("\n[STOP] Script stopped by user (Ctrl+C).")
        except Exception as e:
            logger.critical(f"[ERROR] Engine crashed: {e}")
            import traceback

            traceback.print_exc()

        finally:
            # --- Final report (Always show) ---
            try:
                stats = guards.get_stats()
                logger.info("\n" + "=" * 60)
                logger.info("ENGINE RUN SUMMARY")
                logger.info("=" * 60)
                logger.info(
                    f"Applications submitted: {stats['applications_submitted']}/{stats['max_applications']}"
                )
                logger.info(f"Dry run mode: {stats['dry_run_mode']}")
                logger.info("=" * 60)

                # Generate output.json, sync execution_metadata to backend (same contract as
                # hiring-cafe-engine: PUT /api/orchestrator/logs/{id}), then email — isolated
                # so SMTP failures cannot mask a successful metadata sync.
                try:
                    output_path, _ = execution_tracker.generate_report("data/output.json")
                    logger.info(f"Saved run report to {output_path}")

                    # Same JSON as output.json — load from disk so execution_metadata matches the file byte-for-byte intent.
                    with open(output_path, encoding="utf-8") as f:
                        report_payload = json.load(f)

                    _es = report_payload.get("execution_summary") or {}
                    logger.info(
                        "[RUN_SUMMARY] runner_completed: "
                        f"attempted={_es.get('total_applications_attempted', 0)}, "
                        f"successful={_es.get('total_applications_successful', 0)}, "
                        f"failed={_es.get('total_applications_failed', 0)}"
                    )

                    lid = execution_tracker.workflow_log_id
                    if lid:
                        summary = report_payload.get("execution_summary") or {}
                        log_content = ""
                        try:
                            with open("logs/scheduler_run.log", "r", encoding="utf-8", errors="ignore") as f:
                                log_content = f.read()
                        except Exception:
                            pass

                        ok = backend_client.update_workflow_log(
                            lid,
                            _log_status_from_report(report_payload.get("status", "failed")),
                            records_processed=int(
                                summary.get("total_applications_successful", 0)
                            ),
                            records_failed=int(summary.get("total_applications_failed", 0)),
                            execution_metadata=report_payload,
                            logfile=log_content,
                        )
                        if not ok:
                            logger.error(
                                f"[WORKFLOW_LOG] PUT failed for log id={lid}; check ERROR line above."
                            )
                        else:
                            logger.info(
                                f"[WORKFLOW_LOG] execution_metadata synced for log id={lid}"
                            )

                        # --- Sync schedule last_run / next_run to Workflows Scheduler UI ---
                        schedule_id = execution_tracker.run_parameters.get("schedule_id") if hasattr(execution_tracker, "run_parameters") else None
                        if not schedule_id:
                            schedule_id = report_payload.get("schedule_id")
                        if schedule_id:
                            from datetime import timedelta
                            now_utc = datetime.utcnow()
                            # Next week at 9:30 AM local time
                            now_local = datetime.now()
                            next_week_local = now_local + timedelta(days=7)
                            next_run_local = next_week_local.replace(hour=9, minute=30, second=0, microsecond=0)
                            # Convert local 9:30 AM to UTC for the backend
                            local_offset = now_local - now_utc
                            next_run_utc = next_run_local - local_offset
                            
                            backend_client.update_schedule(
                                int(schedule_id),
                                last_run_at=now_utc.strftime("%Y-%m-%d %H:%M:%S"),
                                next_run_at=next_run_utc.strftime("%Y-%m-%d %H:%M:%S"),
                            )
                        else:
                            logger.warning("[SCHEDULE] No schedule_id found — skipping schedule sync.")
                    else:
                        logger.warning(
                            "[WORKFLOW_LOG] No workflow_log_id on this run — automation_workflow_logs "
                            "was not created at start (see main.py warnings) or create_log failed."
                        )

                    try:
                        from core.email_reporter import email_reporter

                        email_reporter.send_report(output_path)
                    except Exception as email_err:
                        logger.error(
                            f"[EMAIL] Report email failed (run report and workflow log already saved): {email_err}"
                        )

                except Exception as out_err:
                    logger.error(
                        f"Failed to generate output.json or sync workflow log: {out_err}"
                    )
                    lid = execution_tracker.workflow_log_id
                    if lid:
                        log_content = ""
                        try:
                            with open("logs/scheduler_run.log", "r", encoding="utf-8", errors="ignore") as f:
                                log_content = f.read()
                        except Exception:
                            pass
                            
                        backend_client.update_workflow_log(
                            lid,
                            "failed",
                            error_summary=str(out_err)[:255],
                            logfile=log_content,
                        )

            except Exception as re:
                logger.debug(f"Could not print final report: {re}")

            # Close DuckDB connection so WAL is flushed to disk
            try:
                db.get_connection().close()
                logger.info("DuckDB connection closed cleanly")
            except Exception:
                pass

    def _process_site(self, conn, site: _SiteRow, candidate_data=None):
        """
        Process a single job site.

        Args:
            conn: DuckDB connection
            site:  _SiteRow instance
            candidate_data: Candidate profile dict
        """
        logger.info("\n" + "-" * 60)
        logger.info(f"Processing: {site.company_name}")
        logger.info("-" * 60)

        try:
            # Start fresh browser for THIS site specifically
            logger.info("Initializing fresh browser session for site...")
            self.browser = browser_service.start_browser()
            
            # Load selectors from DuckDB
            selectors = self._load_selectors(conn, site)

            # Get strategy class path
            strategy_path = site.platform.class_handler

            logger.info(f"Strategy: {strategy_path}")

            # Instantiate strategy via factory
            try:
                strategy = strategy_factory.get_strategy(
                    strategy_path,
                    self.browser,
                    site,
                    selectors,
                    None,  # db_session not needed  DuckDB singleton handles tracking
                    candidate_data,
                )
            except Exception as e:
                logger.error(
                    f"[ERROR] Failed to load strategy for {site.company_name}: {e}"
                )
                return

            # Login / portal load
            logger.info("Attempting login...")
            if not strategy.login():
                logger.error(f"Login failed for {site.company_name}")
                return
            logger.info("Login successful (or not required)")

            # Find + apply
            if getattr(strategy, "use_single_phase", False):
                logger.info(f"\nFinding and applying to jobs (Single-Phase)...")
                applied_count = strategy.find_and_apply_jobs()
                logger.info(
                    f"Completed {site.company_name}: {applied_count} applications submitted"
                )
                return

            # Traditional two-phase approach for other sites
            logger.info("Discovering jobs...")
            jobs = strategy.find_jobs()
            logger.info(f"Found {len(jobs)} job(s)")
            execution_tracker.add_jobs_found(len(jobs))

            if jobs:
                # Save discovered jobs to tracker
                try:
                    new_count = csv_tracker.add_discovered_jobs(
                        site.company_name.lower(), jobs
                    )
                    logger.info(
                        f"Added {new_count} new job(s) to tracker for {site.company_name}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to save discovered jobs to CSV: {e}")

                logger.info("\n[APPLY] Starting application process...")
                applied_count = 0

                for job in jobs:
                    if not guards.can_apply():
                        logger.warning("[WARNING] Application limit reached")
                        break

                    # 4a. SESSION HEALTH CHECK: Before applying, ensure browser is still alive
                    try:
                        _ = self.browser.current_url
                    except Exception as se:
                        logger.warning(
                            f"[SESSION] Browser session lost before applying: {se}"
                        )
                        # --- Recovery: restart browser and re-mount strategy ---
                        logger.info("[SESSION] Attempting browser session recovery...")
                        try:
                            browser_service.stop_browser()
                        except Exception:
                            pass
                        try:
                            self.browser = browser_service.start_browser()
                            selectors = self._load_selectors(conn, site)
                            strategy = strategy_factory.get_strategy(
                                site.platform.class_handler,
                                self.browser,
                                site,
                                selectors,
                                None,
                                candidate_data,
                            )
                            if not strategy.login():
                                logger.error("[SESSION] Re-login failed after recovery. Stopping site.")
                                break
                            logger.info("[SESSION] Browser session recovered. Resuming applications.")
                        except Exception as re_err:
                            logger.error(f"[SESSION] Recovery failed: {re_err}. Stopping site.")
                            break

                    try:
                        # Pre-check: skip already applied FOR THIS CANDIDATE
                        job_url = job.get("job_url", "")
                        job_title = job.get("job_title", "Unknown")
                        candidate_email = candidate_data.get("applicant", {}).get("email", "default_candidate@example.com")
                        
                        if csv_tracker.is_done_by_candidate(site.company_name.lower(), job_url, candidate_email):
                            logger.info(f"Skipping already processed job (applied/failed) for {candidate_email}: {job_title}")
                            continue

                        logger.info(f"\nApplying to: {job_title}")
                        success = strategy.apply(job)
                        if success:
                            # Verify if it was actually applied or just skipped (e.g. already applied detection)
                            # We check the tracker again. If it's 'applied', and it wasn't 'applied' before,
                            # we count it. If the strategy itself handles the quota, even better.
                            guards.increment_counter()
                            applied_count += 1
                            csv_tracker.mark_applied_for_candidate(site.company_name.lower(), job_url, candidate_email, "applied")

                            execution_tracker.record_success(
                                site.company_name, 
                                job.get("external_id", job.get("job_url", "")), 
                                job_title, 
                                job_url
                            )
                            logger.info(f"Application #{applied_count} successful")
                        else:
                            execution_tracker.record_error(
                                site.company_name, 
                                job.get("external_id", job.get("job_url", "")), 
                                job_title, 
                                job_url, 
                                "Application logic returned False"
                            )
                            logger.warning("Application failed")
                            # Mark as failed so same job is skipped on next keyword iteration
                            csv_tracker.mark_applied_for_candidate(
                                site.company_name.lower(), job_url, candidate_email, "failed"
                            )
                    except Exception as e:
                        logger.error(f"[ERROR] Error applying to job: {e}")
                        execution_tracker.record_error(
                            site.company_name, 
                            job.get("external_id", job.get("job_url", "")), 
                            job.get("job_title", "Unknown"), 
                            job.get("job_url", ""), 
                            str(e)
                        )
                        if any(
                            msg in str(e).lower()
                            for msg in [
                                "no such window",
                                "disconnected",
                                "invalid session id",
                            ]
                        ):
                            logger.error("[FATAL] Browser session lost. Stopping.")
                            break
                        continue

                logger.info(
                    f"\n[OK] Completed {site.company_name}: {applied_count} applications"
                )
            else:
                logger.info("[INFO] No jobs found to apply to")

        except Exception as e:
            logger.error(f"[ERROR] Error processing {site.company_name}: {e}")
            import traceback

            traceback.print_exc()

        finally:
            if self.browser:
                try:
                    from config.settings import settings

                    if getattr(settings, "KEEP_BROWSER_OPEN", False):
                        logger.info(
                            "\nKEEP_BROWSER_OPEN is True - leaving browser open for inspection"
                        )
                    else:
                        logger.info("\nStopping browser for site cleanup...")
                        browser_service.stop_browser()
                        logger.info("Browser closed")
                except Exception:
                    browser_service.stop_browser()
                self.browser = None

    def _load_selectors(self, conn, site: _SiteRow) -> dict:
        """
        Load selectors for a site from DuckDB.

        Returns:
            dict with 'listing' and 'application' keys
        """
        selectors = {}
        try:
            rows = conn.execute(
                "SELECT type, config_json FROM site_selectors WHERE job_site_id = ?",
                [site.id],
            ).fetchall()

            for sel_type, config_json in rows:
                if isinstance(config_json, str):
                    selectors[sel_type] = json.loads(config_json)
                else:
                    selectors[sel_type] = config_json

            logger.info(f"Loaded {len(selectors)} selector configuration(s)")
        except Exception as e:
            logger.warning(f"Could not load selectors for {site.company_name}: {e}")

        return selectors
