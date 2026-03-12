import json
from core.logger import logger

def seed_wellfound_selectors(conn):
    """
    Seeds Wellfound-specific selectors into the DuckDB database.
    This is called by init_db.py.
    """
    selectors = {
        "search": {
            "job_title_placeholder": "Job title",
            "location_placeholder": "Location",
            "search_button": "button[type='button'][class*='bg-black']"
        },
        "pagination": {
            "next_button": "a[aria-label='Next page']"
        },
        "listing": {
            "card_link": "a[href*='/jobs/']"
        }
    }

    logger.info("Seeding Wellfound selectors via dedicated script...")
    
    conn.execute("""
        INSERT OR IGNORE INTO site_selectors (id, ats_platform_id, job_site_id, type, config_json)
        VALUES (5, 5, 5, 'full_config', ?)
    """, [json.dumps(selectors)])
    
    logger.info("Wellfound selectors seeded successfully.")

if __name__ == "__main__":
    # Allow running separately if needed
    import duckdb
    import os
    from config.settings import settings
    
    db_path = settings.DUCKDB_PATH
    conn = duckdb.connect(db_path)
    seed_wellfound_selectors(conn)
    conn.close()
