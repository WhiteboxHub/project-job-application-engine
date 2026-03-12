"""
Quick script to check job status in the database.
Run: python scripts/check_failed.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb

from config.settings import settings

conn = duckdb.connect(settings.DUCKDB_PATH)

# Status summary
print("\n=== STATUS SUMMARY ===")
rows = conn.execute(
    "SELECT status, COUNT(*) as count FROM job_listings GROUP BY status"
).fetchall()
if rows:
    for r in rows:
        print(f"  {str(r[0]).ljust(15)}: {r[1]} jobs")
else:
    print("  No jobs in database yet.")

# Failed jobs
print("\n=== FAILED JOBS ===")
rows = conn.execute(
    "SELECT job_title, job_url, last_error FROM job_listings WHERE status = 'failed'"
).fetchall()
if rows:
    for r in rows:
        print(f"  Title : {r[0]}")
        print(f"  URL   : {r[1]}")
        print(f"  Error : {r[2]}")
        print()
    print(f"Total failed: {len(rows)}")
else:
    print("  No failed jobs found.")

# Applied jobs
print("\n=== APPLIED JOBS ===")
rows = conn.execute(
    "SELECT job_title, job_url FROM job_listings WHERE status = 'applied'"
).fetchall()
if rows:
    for r in rows:
        print(f"  [{r[0]}] {r[1]}")
    print(f"Total applied: {len(rows)}")
else:
    print("  No applied jobs yet.")

conn.close()
