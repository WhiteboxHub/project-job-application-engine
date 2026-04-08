import os
import shutil
import duckdb
import sys
import json

def add_insight_global():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'data', 'job_engine.duckdb')
    backup_path = os.path.join(project_root, 'data', 'job_engine_backup.duckdb')
    
    # Backup
    if os.path.exists(db_path):
        print(f"Backing up existing database to {backup_path}...")
        shutil.copy2(db_path, backup_path)
    else:
        print("Database does not exist yet. It will be initialized.")

    print(f"Connecting to DuckDB at {db_path}...")
    conn = duckdb.connect(db_path)
    
    try:
        # 1. Ensure tables exist (in case database was brand new)
        schema_path = os.path.join(project_root, 'db', 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
                # We won't blindly run schema.sql as it might overwrite data if the user has a custom script,
                # but let's just create missing tables safely.
                # Actually, running schema.sql with "CREATE TABLE IF NOT EXISTS" is safer if tables are missing.
                pass
        
        # In case the table ats_platforms doesn't even exist, we should just let DuckDB error, and tell the user to run init_db first.
        
        print("Inserting Insight Global Platform (if not exists)...")
        conn.execute("""
            INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
            VALUES (1, 'Insight Global Custom', 'strategies.custom.InsightGlobalStrategy', false);
        """)
        
        print("Inserting Job Site...")
        conn.execute("""
            INSERT OR IGNORE INTO job_sites (
                id,
                company_name,
                domain,
                ats_platform_id,
                category,
                search_url_template,
                apply_url_template,
                cf_clearance_required,
                is_active
            )
            VALUES (
                1,
                'Insight Global',
                'insightglobal.com',
                1,
                'Staffing vendor',
                'https://insightglobal.com/jobs/',
                'https://jobs.insightglobal.com/users/jobapplynoaccount.aspx?jobid={job_id}',
                false,
                true
            );
        """)
        
        print("Inserting Listing Selectors...")
        listing_json = {
            "container": "div.result",
            "pagination_type": "click_next",
            "pagination_selector": "a[title=\"Page Forward\"]",
            "fields": {
                "job_id": {
                    "selector": "button[id=\"btnSaveJob\"]",
                    "attr": "jobId"
                },
                "title": {
                    "selector": ".job-title a",
                    "type": "text"
                },
                "url": {
                    "selector": ".job-title a",
                    "attr": "href"
                }
            }
        }
        
        conn.execute("""
            INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (
                1,
                1,
                'listing',
                ?
            )
        """, [json.dumps(listing_json)])
        
        print("Inserting Application Selectors...")
        application_json = {
            "flow_type": "legacy_form",
            "form_fields": {
                "first_name": "input[name*=\"FirstName\"]",
                "last_name": "input[name*=\"LastName\"]",
                "email": "input[name*=\"Email\"]",
                "phone": "input[name*=\"Phone\"]",
                "resume_upload": "input[type=\"file\"]",
                "submit_btn": "#ContentPlaceHolder1_cmdApply"
            }
        }
        
        conn.execute("""
            INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (
                2,
                1,
                'application',
                ?
            )
        """, [json.dumps(application_json)])
        
        print("✅ Success! Insight Global configuration added safely.")
        
    except duckdb.CatalogException as e:
        print(f"Database tables have not been created yet ({e}). Please run scripts/init_db.py first, or we can assist further.")
    except Exception as e:
        print(f"Error occurred: {e}")
        # Restore backup if modified
        if os.path.exists(backup_path):
            print("Restoring from backup due to error...")
            conn.close()
            shutil.copy2(backup_path, db_path)
            
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == "__main__":
    add_insight_global()
