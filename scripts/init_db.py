"""
Initialize DuckDB  applies schema.sql and seeds all site data.
Run this once before using main.py or scheduler_worker.py.

Usage:
    python scripts/init_db.py
"""
import sys
import os
import duckdb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.logger import logger


def init_db():
    db_path = settings.DUCKDB_PATH
    
    if db_path.startswith("md:"):
        logger.info(f"Initializing MotherDuck Cloud at: {db_path}")
        token_suffix = f"?motherduck_token={settings.MOTHERDUCK_TOKEN}" if settings.MOTHERDUCK_TOKEN else ""
        conn = duckdb.connect(f"{db_path}{token_suffix}")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        logger.info(f"Initializing DuckDB at: {db_path}")
        conn = duckdb.connect(db_path)

    # -----------------------------------------------------------------------
    # Core schema tables
    # -----------------------------------------------------------------------
    logger.info("Creating tables...")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ats_platforms (
            id INTEGER PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            class_handler VARCHAR(100) NOT NULL,
            automation_level VARCHAR(20) DEFAULT 'manual',
            is_headless_required BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Add automation_level column if it doesn't already exist (idempotent)
    try:
        conn.execute("ALTER TABLE ats_platforms ADD COLUMN automation_level VARCHAR(20) DEFAULT 'manual'")
        logger.info("Added automation_level column to ats_platforms")
    except Exception:
        pass  # Column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_sites (
            id INTEGER PRIMARY KEY,
            company_name VARCHAR(100) NOT NULL,
            domain VARCHAR(255) UNIQUE NOT NULL,
            ats_platform_id INTEGER,
            category VARCHAR(50) NOT NULL,
            search_url_template TEXT NOT NULL,
            apply_url_template TEXT,
            cf_clearance_required BOOLEAN DEFAULT FALSE,
            proxy_region VARCHAR(10) DEFAULT 'US',
            is_active BOOLEAN DEFAULT TRUE,
            max_applications_per_run INTEGER DEFAULT 10,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_selectors (
            id INTEGER PRIMARY KEY,
            ats_platform_id INTEGER,
            job_site_id INTEGER,
            type VARCHAR(20) NOT NULL,
            config_json JSON NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS job_listings_id_seq
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_listings (
            id INTEGER PRIMARY KEY DEFAULT nextval('job_listings_id_seq'),
            job_site_id INTEGER NOT NULL,
            external_job_id VARCHAR(100) NOT NULL,
            job_title VARCHAR(255),
            job_url TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'discovered',
            attempts INTEGER DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (job_site_id, external_job_id)
        )
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS applications_id_seq
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY DEFAULT nextval('applications_id_seq'),
            job_site_id INTEGER NOT NULL,
            job_listing_id INTEGER,
            job_title VARCHAR(255),
            job_url TEXT,
            status VARCHAR(20) NOT NULL,
            error_message TEXT,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id BIGINT PRIMARY KEY,
            run_date DATE NOT NULL,
            job_site_id INTEGER,
            total_jobs_found INTEGER DEFAULT 0,
            total_applications_attempted INTEGER DEFAULT 0,
            total_applications_successful INTEGER DEFAULT 0,
            total_applications_failed INTEGER DEFAULT 0,
            avg_application_time_seconds FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Tracking tables (from db_duckdb.py schema)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS submitted_jobs (
            job_id VARCHAR PRIMARY KEY,
            job_title VARCHAR,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applied_jobs (
            job_id    VARCHAR NOT NULL,
            site      VARCHAR NOT NULL,
            job_title VARCHAR,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (job_id, site)
        )
    """)
    conn.execute("""
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
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS scheduler_runs_seq START 1
    """)

    logger.info("Tables created [OK]")

    # -----------------------------------------------------------------------
    # Seed: Insight Global
    # -----------------------------------------------------------------------
    conn.execute("""
        INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
        VALUES (1, 'Insight Global Custom', 'strategies.custom.InsightGlobalStrategy', 'manual', false)
    """)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, apply_url_template, is_active)
        VALUES (
            1, 'Insight Global', 'insightglobal.com', 1, 'Staffing vendor',
            'https://insightglobal.com/jobs/',
            'https://jobs.insightglobal.com/users/jobapplynoaccount.aspx?jobid={job_id}',
            true
        )
    """)

    # -----------------------------------------------------------------------
    # Seed: LanceSoft  (automation_level = 'full')
    # -----------------------------------------------------------------------
    conn.execute("""
        INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
        VALUES (2, 'JobDiva', 'strategies.custom.LanceSoftStrategy', 'full', false)
    """)
    # Update in case row already existed without automation_level
    conn.execute("""
        UPDATE ats_platforms SET automation_level = 'full' WHERE id = 2
    """)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            2, 'LanceSoft', 'lancesoft.com', 2, 'Staffing vendor',
            'https://www2.jobdiva.com/portal/?a=3djdnw5yqdh8wl3frr5t6561tvvokq01affwpxt3lcutzo4f8yt1aeiy3msk02or&compid=0&SearchString=',
            true
        )
    """)

    # -----------------------------------------------------------------------
    # Seed: Infosys  (automation_level = 'manual')
    # -----------------------------------------------------------------------
    conn.execute("""
        INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
        VALUES (4, 'Infosys Custom', 'strategies.custom.InfosysStrategy', 'manual', false)
    """)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            4, 'Infosys', 'infosys.com', 4, 'System integrator',
            'https://career.infosys.com/joblist',
            true
        )
    """)

    # -----------------------------------------------------------------------
    # Seed: Wipro  (automation_level = 'manual')
    # -----------------------------------------------------------------------
    conn.execute("""
        INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
        VALUES (3, 'Wipro Custom', 'strategies.custom.WiproStrategy', 'manual', false)
    """)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            3, 'Wipro', 'wipro.com', 3, 'System integrator',
            'https://careers.wipro.com/',
            true
        )
    """)

    # Indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_sites_active ON job_sites(is_active)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(applied_at)")

    logger.info("")
    logger.info("=" * 50)
    logger.info("DuckDB initialization complete!")
    logger.info("=" * 50)

    # Show summary
    sites = conn.execute(
        "SELECT js.company_name, ap.automation_level FROM job_sites js "
        "JOIN ats_platforms ap ON js.ats_platform_id = ap.id ORDER BY js.id"
    ).fetchall()
    for (name, level) in sites:
        icon = "" if level == "full" else ""
        logger.info(f"  {icon}  {name} ({level})")

    conn.close()
    logger.info("\nRun 'python scripts/main.py --site LanceSoft' to start.")


if __name__ == "__main__":
    init_db()
