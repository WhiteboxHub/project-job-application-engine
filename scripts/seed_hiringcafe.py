import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db
from core.logger import logger
import json

def seed_hiringcafe():
    """Seeds the database with hiringcafe.com configuration"""
    try:
        from sqlalchemy import text
        logger.info("Seeding hiring.cafe...")
        
        session = db.get_session()
        
        # Check if already exists
        result = session.execute(text("SELECT id FROM job_sites WHERE domain = 'hiring.cafe'")).fetchall()
        if result and len(result) > 0:
            logger.info("hiring.cafe already exists in database")
            session.close()
            return True
            
        # Get max ats_platform id
        result = session.execute(text("SELECT COALESCE(MAX(id), 0) FROM ats_platforms"))
        ats_platform_id = result.fetchone()[0] + 1
        
        # Insert ATS Platform
        session.execute(
            text("""
            INSERT INTO ats_platforms (id, name, class_handler, is_headless_required)
            VALUES (:id, :name, :class_handler, :is_headless_required)
            """),
            {
                'id': ats_platform_id,
                'name': 'HiringCafe Custom',
                'class_handler': 'strategies.custom.hiringCashby.HiringCafeStrategy',
                'is_headless_required': False
            }
        )

        # Get max job_sites id
        result = session.execute(text("SELECT COALESCE(MAX(id), 0) FROM job_sites"))
        job_site_id = result.fetchone()[0] + 1

        # Insert Job Site
        session.execute(
            text("""
            INSERT INTO job_sites (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
            VALUES (:id, :company_name, :domain, :ats_platform_id, :category, :search_url_template, :is_active)
            """),
            {
                'id': job_site_id,
                'company_name': 'Hiring Cafe',
                'domain': 'hiring.cafe',
                'ats_platform_id': ats_platform_id,
                'category': 'Product Company',
                'search_url_template': 'https://hiring.cafe/?q={keyword}',
                'is_active': True
            }
        )
        
        # Get max site_selectors id
        result = session.execute(text("SELECT COALESCE(MAX(id), 0) FROM site_selectors"))
        base_selector_id = result.fetchone()[0]
        
        # Insert Listing Selectors
        session.execute(
            text("""
            INSERT INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (:id, :job_site_id, :type, :config_json)
            """),
            {
                'id': base_selector_id + 1,
                'job_site_id': job_site_id,
                'type': 'listing',
                'config_json': json.dumps({"job_cards": "a[href*='/job/']"})
            }
        )
        
        # Insert Application Selectors
        session.execute(
            text("""
            INSERT INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (:id, :job_site_id, :type, :config_json)
            """),
            {
                'id': base_selector_id + 2,
                'job_site_id': job_site_id,
                'type': 'application',
                'config_json': json.dumps({"apply_button": "a[href*='apply' i], button"})
            }
        )
        session.commit()
        session.close()
        
        logger.info("Successfully seeded hiring.cafe")
        return True
        
    except Exception as e:
        logger.error(f"Failed to seed hiring.cafe: {e}")
        try:
            session.rollback()
            session.close()
        except:
            pass
        return False

if __name__ == "__main__":
    seed_hiringcafe()
