"""
DBTracker — DuckDB-backed job tracker with per-candidate support.

The unique key is (job_site_id, job_url, candidate_email).
This means the same job posting is tracked independently per candidate,
so Candidate B is never blocked by Candidate A's applied status.

All public methods accept an optional `candidate_email` parameter.
When omitted, it falls back to the sentinel '__anon__' so old callers
that don't pass a candidate email continue to work unchanged.

Public API:
  - add_discovered_jobs(site_name, jobs, candidate_email=None)  -> int
  - update_job_status(site_name, job_url, status, ..., candidate_email=None) -> bool
  - get_jobs(site_name, status, candidate_email=None)  -> list[dict]
  - get_job_status(site_name, job_url, candidate_email=None)  -> dict | None
  - ensure_file(site_name)  -> no-op (kept for API compat)
"""

from datetime import datetime

from core.logger import logger

_ANON = "__anon__"   # Sentinel used when no candidate e-mail is supplied


class DBTracker:
    """
    DuckDB-backed job tracker.
    Table: job_listings, keyed on (job_site_id, job_url, candidate_email).
    """

    # ---------------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------------

    def _conn(self):
        """Return the shared DuckDB connection."""
        from data.db_connection import db
        return db.get_connection()

    def _site_id(self, site_name: str) -> int | None:
        """Resolve company name → job_sites.id (case-insensitive)."""
        conn = self._conn()
        row = conn.execute(
            "SELECT id FROM job_sites WHERE LOWER(company_name) = LOWER(?)", [site_name]
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

    def _email(self, candidate_email: str | None) -> str:
        """Normalise candidate e-mail — fall back to sentinel if not provided."""
        return (candidate_email or "").strip().lower() or _ANON

    def _ensure_candidate_column(self):
        """
        Idempotently add the candidate_email column to job_listings.
        Safe to call on every run — DuckDB raises if the column already
        exists, which we silently catch.
        """
        conn = self._conn()
        try:
            conn.execute(
                "ALTER TABLE job_listings "
                "ADD COLUMN candidate_email VARCHAR(255) DEFAULT '__anon__'"
            )
            logger.info("[DBTracker] Added candidate_email column to job_listings")
        except Exception:
            pass  # Column already exists — this is expected after first run

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def ensure_file(self, site_name: str):
        """No-op — kept for API compatibility with old CSV tracker."""
        pass

    def add_discovered_jobs(
        self,
        site_name: str,
        jobs: list,
        candidate_email: str | None = None,
    ) -> int:
        """
        Insert jobs not yet seen for this (site, candidate) pair.
        Returns the number of new rows added.
        """
        from hashlib import md5

        self._ensure_candidate_column()

        site_id = self._site_id(site_name)
        if site_id is None:
            logger.warning(f"[DBTracker] Unknown site '{site_name}' — cannot add jobs")
            return 0

        email = self._email(candidate_email)
        conn = self._conn()
        now = datetime.utcnow()

        # Pre-fetch existing (url, candidate) pairs so we can count net-new rows
        existing_urls = {
            row[0]
            for row in conn.execute(
                "SELECT job_url FROM job_listings "
                "WHERE job_site_id = ? AND candidate_email = ?",
                [site_id, email],
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
                    INSERT INTO job_listings
                        (job_site_id, external_job_id, job_title, job_url,
                         location, job_type, salary, description, requirements,
                         posted_date, company, industry, candidate_email,
                         status, attempts, last_error, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            'discovered', 0, '', ?, ?)
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
                        email,
                        now,
                        now,
                    ],
                )
                existing_urls.add(url)   # guard against duplicates in the same batch
                added += 1
            except Exception as e:
                logger.warning(f"[DBTracker] Failed to insert job '{url}': {e}")

        logger.debug(
            f"[DBTracker] add_discovered_jobs: {added} new row(s) "
            f"for '{site_name}' / '{email}'"
        )
        return added

    def update_job_status(
        self,
        site_name: str,
        job_url: str,
        status: str,
        attempts_inc: int = 0,
        last_error: str | None = None,
        candidate_email: str | None = None,
    ) -> bool:
        """
        Update the status of a (job_url, candidate) pair.
        Returns True if a matching row was found and updated.
        """
        self._ensure_candidate_column()

        site_id = self._site_id(site_name)
        if site_id is None:
            logger.warning(
                f"[DBTracker] Unknown site '{site_name}' — cannot update status"
            )
            return False

        email = self._email(candidate_email)
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
              AND candidate_email = ?
              AND (job_url = ? OR job_url = ?)
            LIMIT 1
            """,
            [site_id, email, job_url, norm_url],
        ).fetchone()

        if not row:
            logger.debug(
                f"[DBTracker] update_job_status: no row for '{job_url}' / '{email}'"
            )
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

    def get_jobs(
        self,
        site_name: str,
        status: str | None = None,
        candidate_email: str | None = None,
    ) -> list:
        """
        Return all job rows for a (site, candidate) pair as a list of dicts.
        Optionally filter by status ('discovered', 'applied', 'failed').
        """
        self._ensure_candidate_column()

        site_id = self._site_id(site_name)
        if site_id is None:
            return []

        email = self._email(candidate_email)
        conn = self._conn()
        cols = [
            "external_job_id", "job_title", "job_url", "location", "job_type",
            "salary", "description", "requirements", "posted_date", "company",
            "industry", "candidate_email", "status", "attempts", "last_error",
            "created_at", "updated_at",
        ]
        col_sql = ", ".join(cols)

        if status:
            rows = conn.execute(
                f"SELECT {col_sql} FROM job_listings "
                f"WHERE job_site_id = ? AND candidate_email = ? AND status = ?",
                [site_id, email, status],
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {col_sql} FROM job_listings "
                f"WHERE job_site_id = ? AND candidate_email = ?",
                [site_id, email],
            ).fetchall()

        return [self._row_to_dict(r, cols) for r in rows]

    def get_job_status(
        self,
        site_name: str,
        job_url: str,
        candidate_email: str | None = None,
    ) -> dict | None:
        """
        Return the full row dict for a specific (job_url, candidate) pair,
        or None if not found.
        """
        self._ensure_candidate_column()

        site_id = self._site_id(site_name)
        if site_id is None:
            return None

        email = self._email(candidate_email)
        # Normalize on Python side to avoid REGEXP_REPLACE SQL conflicts
        norm_url = self._normalize_url(job_url)
        conn = self._conn()
        cols = [
            "external_job_id", "job_title", "job_url", "location", "job_type",
            "salary", "description", "requirements", "posted_date", "company",
            "industry", "candidate_email", "status", "attempts", "last_error",
            "created_at", "updated_at",
        ]
        col_sql = ", ".join(cols)

        row = conn.execute(
            f"""
            SELECT {col_sql} FROM job_listings
            WHERE job_site_id = ?
              AND candidate_email = ?
              AND (job_url = ? OR job_url = ?)
            LIMIT 1
            """,
            [site_id, email, job_url, norm_url],
        ).fetchone()

        return self._row_to_dict(row, cols) if row else None


# Module-level singleton — same name as before so all imports work unchanged
tracker = DBTracker()
