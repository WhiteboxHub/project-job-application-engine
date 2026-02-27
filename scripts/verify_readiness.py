import pymysql
import json

conn = pymysql.connect(host='127.0.0.1', port=3306, user='root', password='M@hi14119866', database='new_db')
cur = conn.cursor()

print("--- Checking Candidate: Ghazal Sultan ---")
cur.execute("SELECT id, full_name, email FROM candidate WHERE full_name LIKE '%Ghazal%' OR email LIKE '%ghazal%'")
candidate = cur.fetchone()
if candidate:
    c_id = candidate[0]
    print(f"Found Candidate: ID={c_id}, Name={candidate[1]}, Email={candidate[2]}")
    
    print("\n--- Checking Marketing Flags ---")
    cur.execute("SELECT id, candidate_id, marketing_flag, is_processed, status FROM candidate_marketing WHERE candidate_id = %s", (c_id,))
    marketing = cur.fetchone()
    if marketing:
        print(f"Marketing Row: ID={marketing[0]}, Flag={marketing[2]}, Processed={marketing[3]}, Status={marketing[4]}")
    else:
        print("[ERROR] No entry in candidate_marketing for this candidate!")
else:
    print("[ERROR] Candidate 'Ghazal Sultan' not found in candidate table!")

print("\n--- Checking Target Sites Status ---")
target_sites = ['LanceSoft', 'Infosys', 'Wipro', 'KForce']
for site in target_sites:
    cur.execute("SELECT id, is_active FROM job_sites WHERE company_name = %s", (site,))
    res = cur.fetchone()
    if res:
        print(f"Site '{site}': ID={res[0]}, Active={res[1]}")
    else:
        print(f"[ERROR] Site '{site}' not found!")

conn.close()
