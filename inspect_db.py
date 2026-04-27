import duckdb
import os

db_path = "project-job-application-engine/data/job_engine.duckdb"
# If not found, try without Prefix
if not os.path.exists(db_path):
    db_path = "data/job_engine.duckdb"

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
else:
    conn = duckdb.connect(db_path)
    print("--- Job Listings Summary ---")
    try:
        rows = conn.execute("SELECT status, count(*) FROM job_listings GROUP BY status").fetchall()
        for row in rows:
            print(f"Status: {row[0]}, Count: {row[1]}")
    except Exception as e:
        print(f"Error querying job_listings: {e}")
    
    print("\n--- Recent Job Listings ---")
    try:
        # Check column names
        cols = conn.execute("DESCRIBE job_listings").fetchall()
        col_names = [c[0] for c in cols]
        print(f"Columns: {col_names}")
        
        recent = conn.execute("""
            SELECT js.company_name, jl.job_title, jl.status, jl.updated_at 
            FROM job_listings jl
            JOIN job_sites js ON jl.job_site_id = js.id 
            ORDER BY jl.updated_at DESC 
            LIMIT 20
        """).fetchall()
        for r in recent:
            print(r)
    except Exception as e:
        print(f"Error querying recent jobs: {e}")
    conn.close()
