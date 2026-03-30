import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db

def list_sites():
    """List all job sites from DuckDB"""
    try:
        conn = db.get_connection()
        rows = conn.execute("SELECT id, company_name, is_active FROM job_sites").fetchall()
        
        print(f"\nFound {len(rows)} sites in DuckDB:")
        print("-" * 40)
        for r in rows:
            status = "[ACTIVE]" if r[2] else "[OFFLINE]"
            print(f"- ID: {r[0]:2} | {status} | {r[1]}")
        print("-" * 40)
    except Exception as e:
        print(f"Error listing sites: {e}")


if __name__ == "__main__":
    list_sites()
