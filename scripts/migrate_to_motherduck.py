
import duckdb
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))
from config.settings import settings

def migrate():
    local_db = "data/job_engine.duckdb"
    md_db = settings.DUCKDB_PATH
    
    if not md_db.startswith("md:"):
        print(f"Error: DUCKDB_PATH in .env is not a MotherDuck path: {md_db}")
        return

    print(f"🚀 Starting migration from {local_db} to {md_db}...")
    
    if settings.MOTHERDUCK_TOKEN:
        os.environ["MOTHERDUCK_TOKEN"] = settings.MOTHERDUCK_TOKEN
    else:
        print("Warning: MOTHERDUCK_TOKEN not found in settings. Make sure it is in your .env")

    try:
        # Connect to MotherDuck
        conn = duckdb.connect(md_db)
        
        # Attach local database
        print(f"📦 Attaching local database: {local_db}")
        # Use local_db as the identifier to avoid any 'main' confusion
        conn.execute(f"ATTACH '{local_db}' AS local_db (READ_ONLY)")
        
        # List of tables to migrate
        tables = [
            'ats_platforms',
            'job_sites',
            'site_selectors',
            'applied_jobs',
            'scheduler_runs',
            'submitted_jobs',
            'applications',
            'metrics',
            'job_listings'
        ]
        
        for table in tables:
            print(f"🔄 Migrating table: {table}")
            
            # Check if table exists in local_db using direct duckdb_tables catalog
            exists = conn.execute(f"SELECT count(*) FROM duckdb_tables() WHERE database_name='local_db' AND table_name='{table}'").fetchone()[0]
            if not exists:
                print(f"  ⚠️ Table {table} not found in local DB. Skipping.")
                continue
                
            # Create table in MD if not exists
            # We use local schema as template - reach via local_db.{table}
            conn.execute(f"CREATE TABLE IF NOT EXISTS main.{table} AS SELECT * FROM local_db.{table} WHERE 1=0")
            
            # Clear target table to ensure fresh copy of latest selectors/config
            print(f"  🧹 Clearing target table {table} in MotherDuck...")
            conn.execute(f"DELETE FROM main.{table}")
            
            # Copy data
            print(f"  📥 Copying rows for {table}...")
            conn.execute(f"INSERT INTO main.{table} SELECT * FROM local_db.{table}")
            
            count = conn.execute(f"SELECT count(*) FROM main.{table}").fetchone()[0]
            print(f"  ✅ Done. Row count in MotherDuck: {count}")
            
        print("\n✨ Migration complete! All selectors and data are now in MotherDuck.")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == "__main__":
    migrate()
