import sys
import os
from sqlalchemy.orm import Session

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_mysql import db_mysql
from models.config_models import JobSite, SiteSelector, AtsPlatform
from engine.runner import EngineRunner

def test_selector_loading():
    print("Testing Selector Loading Logic...")
    session = db_mysql.SessionLocal()
    try:
        # 1. Ensure we have at least one site and one platform
        site = session.query(JobSite).first()
        if not site:
            print("No job sites found in DB. Please run init_db.py and seed scripts first.")
            return

        print(f"Testing for Site: {site.company_name} (ID: {site.id})")
        print(f"Platform ID: {site.ats_platform_id}")

        # 2. Query selectors manually to see what's in DB
        selectors_raw = session.query(SiteSelector).filter(
            (SiteSelector.job_site_id == site.id) | 
            (SiteSelector.ats_platform_id == site.ats_platform_id)
        ).all()
        
        print(f"Found {len(selectors_raw)} selector entries in DB.")
        for s in selectors_raw:
            print(f" - Type: {s.type}, Config: {s.config_json}")

        # 3. Simulate the merging logic in EngineRunner
        selectors = {}
        for s in selectors_raw:
            selectors.update(s.config_json)
        
        print(f"Merged Selectors: {selectors}")
        
        # Check for expected keys for Infosys if it's the site
        if site.company_name == "Infosys":
            container = selectors.get("container") or selectors.get("listing_card")
            print(f"Infosys container selector: {container}")
            if not container:
                print("FAILED: No container selector found for Infosys.")
            else:
                print("SUCCESS: Container selector found.")

    finally:
        session.close()

if __name__ == "__main__":
    test_selector_loading()
