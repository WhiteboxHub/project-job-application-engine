import json
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db

def update_collabera_selectors():
    try:
        # Verified Search Selectors
        listing_config = {
            "search_input": "input[placeholder='Job Title or Keywords']",
            "location_input": "input[placeholder='Location']",
            "search_button": "button.blue-teal-sm-btn",
            "job_link": "a[href*='job-description']",
            "job_title_selector": "h5",
            "search_keywords": [
                "AI Engineer",
                "Machine Learning Engineer",
                "Python Developer",
                "Data Scientist"
            ]
        }

        # Verified Application Selectors (Inside Iframe)
        application_config = {
            "form_fields": {
                "fullName": "input[placeholder*='Full Name']",
                "email": "input[placeholder*='Email']",
                "phone": "input[placeholder*='Phone']",
                "resume_upload": "input[type='file']",
                "terms_checkbox": "input[type='checkbox']",
                "alert_checkbox": "input[type='checkbox']:nth-of-type(2)",
                "submit_btn": "button.blue-teal-sm-btn, //button[contains(., 'Apply')]"
            },
            "iframe_selector": "iframe"
        }

        # Get Job Site ID for Collabera
        site_id_row = db.execute("SELECT id FROM job_sites WHERE LOWER(company_name) = 'collabera' LIMIT 1").fetchone()
        if not site_id_row:
            print("Collabera not found in job_sites table.")
            return
        
        site_id = site_id_row[0]

        # Get current site_selectors IDs for Collabera
        existing_rows = db.execute("SELECT id, type FROM site_selectors WHERE job_site_id = ?", [site_id]).fetchall()
        existing_ids = {row[1]: row[0] for row in existing_rows}

        def upsert_selector(sel_type, config):
            if sel_type in existing_ids:
                row_id = existing_ids[sel_type]
                print(f"Updating existing {sel_type} (ID: {row_id})...")
                db.execute(
                    "UPDATE site_selectors SET config_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    [json.dumps(config), row_id]
                )
            else:
                print(f"Inserting new {sel_type}...")
                db.execute(
                    "INSERT INTO site_selectors (job_site_id, type, config_json, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    [site_id, sel_type, json.dumps(config)]
                )

        upsert_selector("listing", listing_config)
        upsert_selector("application", application_config)

        print(f"Successfully updated selectors for Collabera (Site ID: {site_id})")
            
    except Exception as e:
        print(f"Error updating selectors: {e}")

if __name__ == "__main__":
    update_collabera_selectors()
