"""
Engine Runner - Main Orchestration Logic
Coordinates the entire automation workflow.
Uses raw DuckDB queries (no SQLAlchemy ORM session needed).
"""

import time
import importlib
import json
from data.db_connection import db
from data.db_duckdb import db_duckdb
from engine.factory import strategy_factory
from engine.guards import guards
from core.browser import browser_service
from core.logger import logger
from core.candidate_loader import CandidateLoader


class _SiteRow:
    """Duck-typed JobSite object built from a raw DuckDB row"""
    def __init__(self, row):
        # row columns: id, company_name, domain, search_url_template,
        #              apply_url_template, max_applications_per_run,
        #              class_handler, automation_level
        self.id                      = row[0]
        self.company_name            = row[1]
        self.domain                  = row[2]
        self.search_url_template     = row[3]
        self.apply_url_template      = row[4]
        self.max_applications_per_run = row[5]
        self.is_active               = True
        # Simulate platform relationship
        self.platform                = _PlatformRow(row[6], row[7])


class _PlatformRow:
    def __init__(self, class_handler, automation_level):
        self.class_handler    = class_handler
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

        try:
            # 1. Start Browser
            logger.info("Initializing browser...")
            self.browser = browser_service.start_browser()
            logger.info("Browser started successfully")

            # 2. Get Active Sites from DuckDB
            conn = db.get_connection()
            try:
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
                        WHERE js.is_active = true
                    """

                rows = conn.execute(sql, params).fetchall()
                active_sites = [_SiteRow(r) for r in rows]

                if not active_sites:
                    if site_filter:
                        logger.warning(f"[WARNING] No active job site found matching '{site_filter}'")
                        logger.info("Tip: check job_sites table in DuckDB or run scripts/init_db.py")
                    else:
                        logger.warning("[WARNING] No active job sites found in DuckDB.")
                    return

                logger.info(f"\n[LIST] Found {len(active_sites)} active job site(s):")
                for site in active_sites:
                    logger.info(f"   - {site.company_name} ({site.domain}) [{site.platform.automation_level}]")

                # 3. Load candidate data (from JSON if not passed directly)
                if not candidate_data:
                    candidate_data = CandidateLoader.load()

                # 4. Process each site
                for site in active_sites:
                    if not guards.can_apply():
                        logger.warning("Application limit reached. Stopping.")
                        break
                    self._process_site(conn, site, candidate_data)

                # 5. Final report
                stats = guards.get_stats()
                logger.info("\n" + "=" * 60)
                logger.info("ENGINE RUN COMPLETE")
                logger.info("=" * 60)
                logger.info(f"Applications submitted: {stats['applications_submitted']}/{stats['max_applications']}")
                logger.info(f"Dry run mode: {stats['dry_run_mode']}")
                logger.info("=" * 60)

            finally:
                # DuckDB connection is a singleton — no need to close
                pass

        except Exception as e:
            logger.critical(f"[ERROR] Engine crashed: {e}")
            import traceback
            traceback.print_exc()

        finally:
            if self.browser:
                try:
                    from config.settings import settings
                    if getattr(settings, 'KEEP_BROWSER_OPEN', False):
                        logger.info("\nKEEP_BROWSER_OPEN is True - leaving browser open for inspection")
                    else:
                        logger.info("\nStopping browser...")
                        browser_service.stop_browser()
                        logger.info("Browser closed")
                except Exception:
                    browser_service.stop_browser()

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
                    None,            # db_session not needed — DuckDB singleton handles tracking
                    candidate_data
                )
            except Exception as e:
                logger.error(f"[ERROR] Failed to load strategy for {site.company_name}: {e}")
                return

            # Login / portal load
            logger.info("Attempting login...")
            if not strategy.login():
                logger.error(f"Login failed for {site.company_name}")
                return
            logger.info("Login successful (or not required)")

            # Find + apply
            if getattr(strategy, 'use_single_phase', False):
                logger.info(f"\nFinding and applying to jobs (Single-Phase)...")
                applied_count = strategy.find_and_apply_jobs()
                logger.info(f"Completed {site.company_name}: {applied_count} applications submitted")
                return

            # Traditional two-phase approach for other sites
            logger.info("Discovering jobs...")
            jobs = strategy.find_jobs()
            logger.info(f"Found {len(jobs)} job(s)")

            if jobs:
                logger.info("\n[APPLY] Starting application process...")
                applied_count = 0

                for job in jobs:
                    if not guards.can_apply():
                        logger.warning("[WARNING] Application limit reached")
                        break
                    try:
                        logger.info(f"\nApplying to: {job.get('job_title', 'Unknown Title')}")
                        success = strategy.apply(job)
                        if success:
                            guards.increment_counter()
                            applied_count += 1
                            logger.info(f"Application #{applied_count} successful")
                        else:
                            logger.warning("Application failed")
                    except Exception as e:
                        logger.error(f"[ERROR] Error applying to job: {e}")
                        if any(msg in str(e).lower() for msg in ["no such window", "disconnected", "invalid session id"]):
                            logger.error("[FATAL] Browser session lost. Stopping.")
                            break
                        continue

                logger.info(f"\n[OK] Completed {site.company_name}: {applied_count} applications")
            else:
                logger.info("ℹ️ No jobs found to apply to")

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
                [site.id]
            ).fetchall()

            for (sel_type, config_json) in rows:
                if isinstance(config_json, str):
                    selectors[sel_type] = json.loads(config_json)
                else:
                    selectors[sel_type] = config_json

            logger.info(f"Loaded {len(selectors)} selector configuration(s)")
        except Exception as e:
            logger.warning(f"Could not load selectors for {site.company_name}: {e}")

        return selectors
