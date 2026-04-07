"""
DuckDB Manager — Job tracking, dedup, and scheduler audit log.
All job application history lives here (no MySQL needed).
"""

import json
from datetime import datetime

from core.logger import logger


class DuckDBManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DuckDBManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # Reuse the single connection managed by DuckDBConnection (db_connection.py).
        # This avoids opening a second file handle to the same .duckdb file which
        # would cause "file already in use" errors on Windows.
        from data.db_connection import db as _db_conn

        self.conn = _db_conn.get_connection()
        self._create_schema()
        logger.info(f"DuckDB initialized (shared connection)")

    def _create_schema(self):
        """Create all tables if they don't exist"""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS site_selectors (
                id INTEGER PRIMARY KEY,
                ats_platform_id INTEGER,
                job_site_id INTEGER,
                config_json JSON,
                updated_at TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS submitted_jobs (
                job_id VARCHAR PRIMARY KEY,
                job_title VARCHAR,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Dedup table — check before applying to any job
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS applied_jobs (
                job_id    VARCHAR NOT NULL,
                site      VARCHAR NOT NULL,
                candidate_id VARCHAR NOT NULL DEFAULT 'default',
                job_title VARCHAR,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (job_id, site, candidate_id)
            )
        """)

        # Migration: Add candidate_id if missing from an older schema
        try:
            cols = self.conn.execute("PRAGMA table_info('applied_jobs')").fetchall()
            col_names = [c[1] for c in cols]
            if col_names and "candidate_id" not in col_names:
                logger.info("Migrating applied_jobs table to include candidate_id...")
                self.conn.execute("ALTER TABLE applied_jobs RENAME TO applied_jobs_old")
                self.conn.execute("""
                    CREATE TABLE applied_jobs (
                        job_id    VARCHAR NOT NULL,
                        site      VARCHAR NOT NULL,
                        candidate_id VARCHAR NOT NULL DEFAULT 'unknown',
                        job_title VARCHAR,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (job_id, site, candidate_id)
                    )
                """)
                self.conn.execute("""
                    INSERT INTO applied_jobs (job_id, site, job_title, applied_at)
                    SELECT job_id, site, job_title, applied_at FROM applied_jobs_old
                """)
                self.conn.execute("DROP TABLE applied_jobs_old")
        except Exception as e:
            logger.warning(f"DuckDB Migration failed (non-critical): {e}")

        # Audit log — one row per scheduler run per site
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_runs (
                id            INTEGER PRIMARY KEY,
                run_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                site          VARCHAR,
                jobs_found    INTEGER DEFAULT 0,
                jobs_applied  INTEGER DEFAULT 0,
                status        VARCHAR DEFAULT 'completed',
                error_message VARCHAR
            )
        """)

        # Auto-increment sequence for scheduler_runs
        self.conn.execute("""
            CREATE SEQUENCE IF NOT EXISTS scheduler_runs_seq START 1
        """)

        logger.info("DuckDB schema verified.")

    # -------------------------------------------------------------------------
    # Dedup helpers
    # -------------------------------------------------------------------------

    def is_already_applied(self, job_id: str, site: str, candidate_id: str = "default") -> bool:
        """Return True if this specific candidate already applied to this job on this site"""
        # Ensure candidate_id is a string and handle None
        cid = str(candidate_id) if candidate_id else "default"
        result = self.conn.execute(
            "SELECT 1 FROM applied_jobs WHERE job_id = ? AND site = ? AND candidate_id = ?",
            [str(job_id), site, cid],
        ).fetchone()
        return result is not None

    def mark_applied(self, job_id: str, site: str, job_title: str = "", candidate_id: str = "default"):
        """Record a successful application for dedup"""
        try:
            cid = str(candidate_id) if candidate_id else "default"
            self.conn.execute(
                """
                INSERT OR IGNORE INTO applied_jobs (job_id, site, candidate_id, job_title, applied_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [str(job_id), site, cid, job_title, datetime.now()],
            )
            logger.debug(f"Marked as applied: {job_id} @ {site} for candidate {cid}")
        except Exception as e:
            logger.error(f"Failed to mark job as applied: {e}")

    # -------------------------------------------------------------------------
    # Scheduler audit log
    # -------------------------------------------------------------------------

    def log_scheduler_run(
        self,
        site: str,
        jobs_found: int,
        jobs_applied: int,
        status: str = "completed",
        error_message: str = None,
    ):
        """Write one audit row per scheduler run"""
        try:
            self.conn.execute(
                """
                INSERT INTO scheduler_runs
                    (id, run_at, site, jobs_found, jobs_applied, status, error_message)
                VALUES
                    (nextval('scheduler_runs_seq'), ?, ?, ?, ?, ?, ?)
                """,
                [datetime.now(), site, jobs_found, jobs_applied, status, error_message],
            )
            logger.info(f"Scheduler run logged: {site} — {jobs_applied} applied")
        except Exception as e:
            logger.error(f"Failed to log scheduler run: {e}")

    # -------------------------------------------------------------------------
    # Selector helpers (used by existing config_manager)
    # -------------------------------------------------------------------------

    def get_selectors(self, job_site_id=None, ats_platform_id=None):
        """Fetch merged selectors for a site/platform"""
        conditions = []
        params = []

        if job_site_id is not None:
            conditions.append("job_site_id = ?")
            params.append(job_site_id)
        if ats_platform_id is not None:
            conditions.append("ats_platform_id = ?")
            params.append(ats_platform_id)

        if not conditions:
            return {}

        query = "SELECT config_json FROM site_selectors WHERE " + " OR ".join(
            conditions
        )
        rows = self.conn.execute(query, params).fetchall()

        merged = {}
        for (cfg_json,) in rows:
            if isinstance(cfg_json, str):
                merged.update(json.loads(cfg_json))
            elif isinstance(cfg_json, dict):
                merged.update(cfg_json)

        return merged


class _LazyDuckDBManager:
    """
    Lazy proxy for DuckDBManager.
    Prevents multiprocessing spawn subprocesses from opening the locked
    .duckdb file during module import on Windows.
    """

    _mgr = None

    def _get(self):
        if self._mgr is None:
            self._mgr = DuckDBManager()
        return self._mgr

    def is_already_applied(self, job_id: str, site: str, candidate_id: str = "default") -> bool:
        return self._get().is_already_applied(job_id, site, candidate_id)

    def mark_applied(self, job_id: str, site: str, job_title: str = "", candidate_id: str = "default"):
        return self._get().mark_applied(job_id, site, job_title, candidate_id)

    def log_scheduler_run(
        self,
        site: str,
        jobs_found: int,
        jobs_applied: int,
        status: str = "completed",
        error_message: str = None,
    ):
        return self._get().log_scheduler_run(
            site, jobs_found, jobs_applied, status, error_message
        )

    def get_selectors(self, job_site_id=None, ats_platform_id=None):
        return self._get().get_selectors(job_site_id, ats_platform_id)


# Lazy singleton — safe to import from worker/subprocess contexts
db_duckdb = _LazyDuckDBManager()
