import pymysql, json

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='M@hi14119866', database='new_db')
cur = conn.cursor()

# Check ats_platforms
print("=== ats_platforms ===")
cur.execute("SELECT id, name, class_handler, automation_level FROM ats_platforms")
for r in cur.fetchall(): print(r)

# Check candidate table
print("\n=== candidate TABLE ===")
try:
    cur.execute("SELECT * FROM candidate LIMIT 5")
    for r in cur.fetchall(): print(r)
except Exception as e: print("ERROR:", e)

# Check candidate_marketing table
print("\n=== candidate_marketing TABLE ===")
try:
    cur.execute("DESCRIBE candidate_marketing")
    for c in cur.fetchall(): print(c[0], c[1])
    cur.execute("SELECT id, candidate_id, marketing_flag, is_processed, status FROM candidate_marketing LIMIT 5")
    for r in cur.fetchall(): print(r)
except Exception as e: print("ERROR:", e)

# Check job_sites with ats_platform_id
print("\n=== job_sites with ats_platform_id ===")
cur.execute("SELECT id, company_name, is_active, ats_platform_id FROM job_sites")
for r in cur.fetchall(): print(r)

conn.close()
