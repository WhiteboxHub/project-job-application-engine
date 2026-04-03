import json
import os
from data.db_connection import db

def export_collabera_selectors():
    try:
        # Query for Collabera selectors
        query = "SELECT type, config_json FROM site_selectors WHERE job_site_id = (SELECT id FROM job_sites WHERE LOWER(company_name) = 'collabera' LIMIT 1)"
        rows = db.execute(query).fetchall()
        
        if not rows:
            print("No Collabera selectors found in site_selectors table.")
            return

        export_data = {}
        for sel_type, config_json in rows:
            if isinstance(config_json, str):
                try:
                    data = json.loads(config_json)
                    export_data[sel_type] = data
                except json.JSONDecodeError:
                    export_data[sel_type] = config_json
            else:
                export_data[sel_type] = config_json
        
        output_path = os.path.join(os.getcwd(), "tmp", "collabera_db_selectors.json")
        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=4)
        print(f"Exported Collabera selectors to {output_path}")
            
    except Exception as e:
        print(f"Error querying database: {e}")

if __name__ == "__main__":
    export_collabera_selectors()
