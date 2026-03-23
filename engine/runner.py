"""
Engine Runner - Main Orchestration Logic
Coordinates the entire automation workflow.
Uses raw DuckDB queries (no SQLAlchemy ORM session needed).
"""

import json
from datetime import datetime

from core.browser import browser_service
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


class EngineRunner:
    """Main orchestrator for the job application engine"""

    def __init__(self):
        self.browser = None

    def run(self, site_filter=None, candidate_data=None):
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
            # 1. Start Browser
            logger.info("Initializing browser...")
            self.browser = browser_service.start_browser()
            logger.info("Browser started successfully")

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
                    WHERE LOWER(js.company_name) LIKE LOWER(?)
                """
                params.append(f"%{site_filter}%")
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

            # 3. Load candidate data (from JSON if not passed directly)
            if not candidate_data:
                candidate_data = CandidateLoader.load()
                
            execution_tracker.initialize(run_parameters=candidate_data)

            # 4. Process each site
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

                # Generate output.json and dispatch email
                try:
                    output_path = execution_tracker.generate_report("data/output.json")
                    logger.info(f"Saved run report to {output_path}")
                    
                    from core.email_reporter import email_reporter
                    email_reporter.send_report(output_path)
                except Exception as out_err:
                    logger.error(f"Failed to generate output.json or send email report: {out_err}")

            except Exception as re:
                logger.debug(f"Could not print final report: {re}")

            if self.browser:
                try:
                    from config.settings import settings

                    if getattr(settings, "KEEP_BROWSER_OPEN", False):
                        logger.info(
                            "\nKEEP_BROWSER_OPEN is True - leaving browser open for inspection"
                        )
                    else:
                        logger.info("\nStopping browser...")
                        browser_service.stop_browser()
                        logger.info("Browser closed")
                except Exception:
                    browser_service.stop_browser()

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
                        logger.error(
                            f"[FATAL] Browser session lost before applying: {se}"
                        )
                        break

                    try:
                        # Pre-check: skip already applied
                        job_url = job.get("job_url", "")
                        job_title = job.get("job_title", "Unknown")
                        status_info = csv_tracker.get_job_status(
                            site.company_name.lower(), job_url
                        )
                        if status_info and status_info.get("status") == "applied":
                            logger.info(f"Skipping already applied job: {job_title}")
                            continue

                        logger.info(f"\nApplying to: {job_title}")
                        success = strategy.apply(job)
                        if success:
                            # Verify if it was actually applied or just skipped (e.g. already applied detection)
                            # We check the tracker again. If it's 'applied', and it wasn't 'applied' before,
                            # we count it. If the strategy itself handles the quota, even better.
                            guards.increment_counter()
                            applied_count += 1
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
