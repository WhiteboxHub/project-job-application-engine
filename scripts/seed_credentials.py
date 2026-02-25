"""
Seed script: creates site_credentials table and inserts Dice.com login credentials.
Run once from the project root:
    venv\Scripts\python scripts\seed_credentials.py
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb

DB_PATH = os.path.join("data", "job_engine.duckdb")

conn = duckdb.connect(DB_PATH)

# 1. Create table if not exists
conn.execute("""
CREATE TABLE IF NOT EXISTS site_credentials (
    id          INTEGER PRIMARY KEY,
    job_site_id INTEGER NOT NULL,
    username    VARCHAR(255) NOT NULL,
    password    VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# 2. Ensure Dice ATS platform exists (id=5)
conn.execute("""
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
VALUES (5, 'Dice Custom', 'strategies.custom.DiceStrategy', false)
""")

# 3. Ensure Dice job site exists (id=5)
conn.execute("""
INSERT OR IGNORE INTO job_sites (
    id, ats_platform_id, company_name, domain, category, search_url_template, is_active
) VALUES (
    5, 5, 'Dice', 'dice.com', 'Staffing vendor',
    'https://www.dice.com/jobs?q={keyword}&l={location}', true
)
""")

# 4. Upsert credentials
conn.execute("DELETE FROM site_credentials WHERE job_site_id = 5")
conn.execute("""
INSERT INTO site_credentials (id, job_site_id, username, password)
VALUES (1, 5, 'mayuri.jayaram@gmail.com', 'MayuriP@1984')
""")

conn.commit()

# 5. Verify
row = conn.execute(
    "SELECT username, password FROM site_credentials WHERE job_site_id = 5"
).fetchone()
print(f"✅ Credentials seeded: {row[0]} / {'*' * len(row[1])}")
conn.close()
