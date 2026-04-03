import os
import sys
import duckdb

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings

def check_sites():
    conn = duckdb.connect(settings.DUCKDB_PATH)
    try:
        sites = conn.execute("SELECT id, company_name FROM job_sites").fetchall()
        print(f"Found {len(sites)} sites in {settings.DUCKDB_PATH}:")
        for s in sites:
            print(f"- ID {s[0]}: '{s[1]}'")
    except Exception as e:
        print(f"Error checking sites: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_sites()
