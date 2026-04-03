import json
from data.db_connection import db

def check_collabera_selectors():
    try:
        # Query for Collabera selectors
        query = "SELECT type, config_json FROM site_selectors WHERE job_site_id = (SELECT id FROM job_sites WHERE LOWER(company_name) = 'collabera' LIMIT 1)"
        rows = db.execute(query).fetchall()
        
        if not rows:
            print("No Collabera selectors found in site_selectors table.")
            return

        for sel_type, config_json in rows:
            print(f"--- Selector Type: {sel_type} ---")
            if isinstance(config_json, str):
                try:
                    data = json.loads(config_json)
                    print(json.dumps(data, indent=4))
                except json.JSONDecodeError:
                    print(config_json)
            else:
                print(json.dumps(config_json, indent=4))
            print("\n")
            
    except Exception as e:
        print(f"Error querying database: {e}")

if __name__ == "__main__":
    check_collabera_selectors()
