
import sys
import os
from sqlalchemy import text

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_mysql import db_mysql
from core.logger import logger

def register_infosys():
    session = db_mysql.SessionLocal()
    try:
        logger.info("Registering Infosys ATS Platform...")
        # Check if already exists
        res = session.execute(text("SELECT id FROM ats_platforms WHERE name = 'Infosys Custom'")).fetchone()
        if res:
            platform_id = res[0]
            logger.info(f"Infosys ATS Platform already exists with ID: {platform_id}")
        else:
            session.execute(text(
                "INSERT INTO ats_platforms (name, class_handler, is_headless_required) "
                "VALUES ('Infosys Custom', 'strategies.custom.infosys.InfosysStrategy', 0)"
            ))
            session.commit()
            platform_id = session.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
            logger.info(f"Registered Infosys ATS Platform with ID: {platform_id}")

        logger.info("Registering Infosys Job Site...")
        res = session.execute(text("SELECT id FROM job_sites WHERE domain = 'digitalcareers.infosys.com'")).fetchone()
        if res:
            site_id = res[0]
            logger.info(f"Infosys Job Site already exists with ID: {site_id}")
        else:
            session.execute(text(
                "INSERT INTO job_sites (company_name, domain, ats_platform_id, category, search_url_template, is_active) "
                "VALUES ('Infosys', 'digitalcareers.infosys.com', :pid, 'System integrator', "
                "'https://digitalcareers.infosys.com/infosys/global-careers?location=USA', 1)"
            ), {"pid": platform_id})
            session.commit()
            site_id = session.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
            logger.info(f"Registered Infosys Job Site with ID: {site_id}")

        logger.info("Registering Selectors for Infosys...")
        res = session.execute(text("SELECT id FROM site_selectors WHERE job_site_id = :sid"), {"sid": site_id}).fetchone()
        if not res:
            session.execute(text(
                "INSERT INTO site_selectors (job_site_id, type, config_json) "
                "VALUES (:sid, 'listing', '{\"container\": \".job-listing-item\", \"fields\": {}, \"keyword\": \"AI Engineer\", \"location\": \"USA\"}')"
            ), {"sid": site_id})
            session.commit()
            logger.info("Registered minimal selectors with keyword/location for Infosys.")
        else:
            # Update existing
            session.execute(text(
                "UPDATE site_selectors SET config_json = '{\"container\": \".job-listing-item\", \"fields\": {}, \"keyword\": \"AI Engineer\", \"location\": \"USA\"}' "
                "WHERE job_site_id = :sid"
            ), {"sid": site_id})
            session.commit()
            logger.info("Updated selectors for Infosys.")

        logger.info("Registration complete.")
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    register_infosys()
