"""
Final Seed for Lever ATS Platform and Selectors into DuckDB
"""

import os
import sys
import json
import duckdb

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.logger import logger

def seed_lever():
    db_path = settings.DUCKDB_PATH
    logger.info(f"Connecting to DuckDB at: {db_path}")
    conn = duckdb.connect(db_path)

    try:
        # 1. Ensure schema is up to date (fix missing automation_level)
        try:
            conn.execute("ALTER TABLE ats_platforms ADD COLUMN automation_level VARCHAR(20) DEFAULT 'manual'")
            logger.info("Added automation_level column to ats_platforms")
        except Exception:
            pass # already exists

        # 2. Seed Lever ATS Platform
        logger.info("Seeding Lever ATS Platform...")
        conn.execute("""
            INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
            VALUES (5, 'Lever', 'strategies.custom.lever.LeverStrategy', 'full', false)
        """)
        
        # 3. Seed generic Lever Job Site
        logger.info("Seeding generic Lever Job Site...")
        conn.execute("""
            INSERT OR IGNORE INTO job_sites
                (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
            VALUES (
                5, 'Lever', 'jobs.lever.co', 5, 'Consulting firm',
                'https://jobs.lever.co/',
                true
            )
        """)

        # 4. Seed Selectors for Lever
        logger.info("Seeding Lever selectors...")
        
        # Application selectors based on user-provided HTML
        app_selectors = {
            "resume": "#resume-upload-input, input[data-qa='input-resume']",
            "full_name": "input[data-qa='name-input'], input[name='name']",
            "email": "input[data-qa='email-input'], input[name='email']",
            "submit": "#btn-submit, button[data-qa='btn-submit'], .template-btn-submit"
        }

        # Clear existing for platform 5
        conn.execute("DELETE FROM site_selectors WHERE ats_platform_id = 5")

        conn.execute("""
            INSERT INTO site_selectors (id, ats_platform_id, job_site_id, type, config_json)
            VALUES (?, ?, ?, ?, ?)
        """, [7, 5, 5, 'application', json.dumps(app_selectors)])

        logger.info("[OK] Lever data seeded successfully.")

    except Exception as e:
        logger.error(f"Error seeding Lever data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    seed_lever()
