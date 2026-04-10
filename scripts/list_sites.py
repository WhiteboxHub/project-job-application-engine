import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db

def list_sites():
    conn = db.get_connection()
    try:
        sql = """
            SELECT
                js.id,
                js.company_name,
                ap.name as platform,
                ap.automation_level,
                js.is_active
            FROM job_sites js
            JOIN ats_platforms ap ON js.ats_platform_id = ap.id
            ORDER BY js.id
        """
        rows = conn.execute(sql).fetchall()
        print(f"\nFound {len(rows)} job site(s) in DuckDB:")
        print("-" * 60)
        for r in rows:
            icon = "✅" if r[3] == "full" else "🔧"
            status = "ACTIVE" if r[4] else "INACTIVE"
            print(f"{icon} ID: {r[0]:<2} | {r[1]:<15} | Platform: {r[2]:<15} | {status}")
        print("-" * 60)
    finally:
        # Connection is a singleton, but good practice to mention
        pass


if __name__ == "__main__":
    list_sites()
