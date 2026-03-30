"""
One-time patch: set only LanceSoft (id=2), KForce (id=5), and Experis (id=7) as active.
All other job sites are deactivated.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.logger import logger
import duckdb

db_path = settings.DUCKDB_PATH

if db_path.startswith("md:"):
    token_suffix = f"?motherduck_token={settings.MOTHERDUCK_TOKEN}" if settings.MOTHERDUCK_TOKEN else ""
    conn = duckdb.connect(f"{db_path}{token_suffix}")
else:
    conn = duckdb.connect(db_path)

# Deactivate all sites first
conn.execute("UPDATE job_sites SET is_active = false")

# Activate only LanceSoft (id=2), KForce (id=5), and Experis (id=7)
conn.execute("UPDATE job_sites SET is_active = true WHERE id IN (2, 5, 7)")

# Show result
rows = conn.execute(
    "SELECT id, company_name, is_active FROM job_sites ORDER BY id"
).fetchall()

logger.info("=== job_sites is_active status ===")
for row in rows:
    status = "ACTIVE  ✅" if row[2] else "inactive ❌"
    logger.info(f"  id={row[0]}  {row[1]:<20} → {status}")

conn.close()
logger.info("Patch applied successfully.")
