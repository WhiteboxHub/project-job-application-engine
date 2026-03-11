"""
DBTracker — DuckDB-backed job tracker.

Replaces the old CSV-based CSVTracker. Stores all discovered/applied/failed
job data in the `job_listings` table instead of per-site CSV files.

Public API is identical to the old CSVTracker so no callers need to change:
  - add_discovered_jobs(site_name, jobs)  -> int
  - update_job_status(site_name, job_url, status, attempts_inc, last_error)  -> bool
  - get_jobs(site_name, status)  -> list[dict]
  - get_job_status(site_name, job_url)  -> dict | None
  - ensure_file(site_name)  -> no-op (kept for API compat)
"""

from datetime import datetime
from core.logger import logger


class DBTracker:
    """
    DuckDB-backed job tracker.
    Uses the job_listings table keyed on (job_site_id, job_url).
    """

    # ---------------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------------

    def _conn(self):
        """Return the shared DuckDB connection."""
        from data.db_connection import db
        return db.get_connection()

    def _site_id(self, site_name: str) -> int | None:
        """Resolve company name → job_sites.id (case-insensitive)."""
        conn = self._conn()
        row = conn.execute(
            "SELECT id FROM job_sites WHERE LOWER(company_name) = LOWER(?)",
            [site_name]
        ).fetchone()
        return row[0] if row else None

    def _normalize_url(self, url: str) -> str:
        """Strip query strings and trailing slashes for comparison."""
        if not url:
            return ""
        return url.split("?")[0].split("#")[0].rstrip("/")

    def _row_to_dict(self, row, columns) -> dict:
        """Convert a raw DuckDB row tuple to a dict using the column list."""
        return dict(zip(columns, row))

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def ensure_file(self, site_name: str):
        """No-op — kept for API compatibility with old CSV tracker."""
        pass

    def add_discovered_jobs(self, site_name: str, jobs: list) -> int:
        """
        Insert jobs that haven't been seen before.
        Returns the number of new rows added.
        """
        from hashlib import md5

        site_id = self._site_id(site_name)
        if site_id is None:
            logger.warning(f"[DBTracker] Unknown site '{site_name}' — cannot add jobs")
            return 0

        conn = self._conn()
        now = datetime.utcnow()

        # Pre-fetch existing URLs to correctly count new insertions
        # (INSERT OR IGNORE is silent for duplicates — doesn't raise an exception)
        existing_urls = {
            row[0] for row in conn.execute(
                "SELECT job_url FROM job_listings WHERE job_site_id = ?",
                [site_id]
            ).fetchall()
        }
        added = 0

        for job in jobs:
            url = job.get("job_url", "")
            if not url or url in existing_urls:
                continue

            # Use external_id if provided; otherwise derive one from the URL
            ext_id = job.get("external_id") or md5(url.encode()).hexdigest()[:20]

            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO job_listings
                        (job_site_id, external_job_id, job_title, job_url,
                         location, job_type, salary, description, requirements,
                         posted_date, company, industry,
                         status, attempts, last_error, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', 0, '', ?, ?)
                    """,
                    [
                        site_id,
                        ext_id,
                        job.get("job_title", ""),
                        url,
                        job.get("location", ""),
                        job.get("job_type", ""),
                        job.get("salary", ""),
                        job.get("description", ""),
                        job.get("requirements", ""),
                        job.get("posted_date", ""),
                        job.get("company", ""),
                        job.get("industry", ""),
                        now,
                        now,
                    ],
                )
                existing_urls.add(url)  # prevent re-adding same URL twice in one batch
                added += 1
            except Exception as e:
                logger.warning(f"[DBTracker] Failed to insert job '{url}': {e}")

        logger.debug(f"[DBTracker] add_discovered_jobs: {added} new row(s) for '{site_name}'")
        return added

    def update_job_status(
        self,
        site_name: str,
        job_url: str,
        status: str,
        attempts_inc: int = 0,
        last_error: str | None = None,
    ) -> bool:
        """
        Update the status (and optionally error) of a job by URL.
        Returns True if a row was found and updated.
        """
        site_id = self._site_id(site_name)
        if site_id is None:
            logger.warning(f"[DBTracker] Unknown site '{site_name}' — cannot update status")
            return False

        # Normalize URL on the Python side — avoids REGEXP_REPLACE in SQL
        # which conflicts with DuckDB's ? parameter placeholder syntax
        norm_url = self._normalize_url(job_url)
        conn = self._conn()
        now = datetime.utcnow()

        # Match on the raw URL first, then fall back to the normalized form
        row = conn.execute(
            """
            SELECT id, attempts FROM job_listings
            WHERE job_site_id = ?
              AND (job_url = ? OR job_url = ?)
            LIMIT 1
            """,
            [site_id, job_url, norm_url],
        ).fetchone()

        if not row:
            logger.debug(f"[DBTracker] update_job_status: no row found for '{job_url}'")
            return False

        listing_id, current_attempts = row
        new_attempts = current_attempts + attempts_inc
        error_val = last_error if last_error is not None else ""

        conn.execute(
            """
            UPDATE job_listings
               SET status = ?, attempts = ?, last_error = ?, updated_at = ?
             WHERE id = ?
            """,
            [status, new_attempts, error_val, now, listing_id],
        )
        return True

    def get_jobs(self, site_name: str, status: str | None = None) -> list:
        """
        Return all job rows for a site as a list of dicts.
        Optionally filter by status ('discovered', 'applied', 'failed').
        """
        site_id = self._site_id(site_name)
        if site_id is None:
            return []

        conn = self._conn()
        cols = [
            "external_job_id", "job_title", "job_url", "location", "job_type",
            "salary", "description", "requirements", "posted_date", "company",
            "industry", "status", "attempts", "last_error", "created_at", "updated_at",
        ]
        col_sql = ", ".join(cols)

        if status:
            rows = conn.execute(
                f"SELECT {col_sql} FROM job_listings WHERE job_site_id = ? AND status = ?",
                [site_id, status],
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {col_sql} FROM job_listings WHERE job_site_id = ?",
                [site_id],
            ).fetchall()

        return [self._row_to_dict(r, cols) for r in rows]

    def get_job_status(self, site_name: str, job_url: str) -> dict | None:
        """
        Return the full row dict for a specific job URL, or None if not found.
        """
        site_id = self._site_id(site_name)
        if site_id is None:
            return None

        # Normalize on Python side to avoid REGEXP_REPLACE SQL conflicts
        norm_url = self._normalize_url(job_url)
        conn = self._conn()
        cols = [
            "external_job_id", "job_title", "job_url", "location", "job_type",
            "salary", "description", "requirements", "posted_date", "company",
            "industry", "status", "attempts", "last_error", "created_at", "updated_at",
        ]
        col_sql = ", ".join(cols)

        row = conn.execute(
            f"""
            SELECT {col_sql} FROM job_listings
            WHERE job_site_id = ?
              AND (job_url = ? OR job_url = ?)
            LIMIT 1
            """,
            [site_id, job_url, norm_url],
        ).fetchone()

        return self._row_to_dict(row, cols) if row else None


# Module-level singleton — same name as before so all imports work unchanged
tracker = DBTracker()
