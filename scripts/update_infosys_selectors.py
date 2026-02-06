#!/usr/bin/env python3
"""
Script to update Infosys selectors in the database with form field selectors.
"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_mysql import db_mysql
from sqlalchemy import text

# Get current config
query = text("""
    SELECT id, config_json 
    FROM site_selectors 
    WHERE job_site_id = (SELECT id FROM job_sites WHERE domain = 'digitalcareers.infosys.com')
    LIMIT 1
""")

with db_mysql.engine.connect() as conn:
    result = conn.execute(query).fetchone()
    
    if result:
        selector_id, config_str = result
        config = json.loads(config_str)
        
        # Add form selectors
        config["personal_form"] = {
            "first_name": [["css selector", "#firstname"]],
            "last_name": [["css selector", "#lastname"]],
            "email": [["css selector", "#email"]],
            "phone": [["css selector", "#phone"]],
            "address": [["css selector", "#address"]],
            "city": [["css selector", "#city"]],
            "state": [["css selector", "#state"]],
            "zip_code": [["css selector", "#zipcode"]]
        }
        
        config["education_form"] = {
            "school": [["css selector", "#school"]],
            "degree": [["css selector", "#degree"]],
            "area_of_study": [["css selector", "#major"]],
            "graduation_year": [["css selector", "#gradYear"]]
        }
        
        config["work_form"] = {
            "company": [["css selector", "input[name*='company']"]],
            "title": [["css selector", "input[name*='title']"]],
            "start_year": [["css selector", "input[name*='startYear']"]],
            "end_year": [["css selector", "input[name*='endYear']"]],
            "add_button": [["css selector", ".add-work-button"]]
        }
        
        # Update database
        update_query = text("""
            UPDATE site_selectors 
            SET config_json = :config 
            WHERE id = :id
        """)
        
        conn.execute(update_query, {"config": json.dumps(config), "id": selector_id})
        conn.commit()
        
        print("✅ Successfully updated Infosys selectors with form fields!")
        print(f"   - Personal form: {len(config['personal_form'])} fields")
        print(f"   - Education form: {len(config['education_form'])} fields")
        print(f"   - Work form: {len(config['work_form'])} fields")
    else:
        print("❌ No Infosys selectors found in database")
