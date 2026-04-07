import duckdb
import json

conn = duckdb.connect('data/job_engine.duckdb')
print("--- Job Sites ---")
sites = conn.execute("SELECT id, company_name, domain, ats_platform_id, is_active FROM job_sites WHERE company_name LIKE '%AE Talents%'").fetchall()
for site in sites:
    print(site)

print("\n--- Site Selectors ---")
if sites:
    site_id = sites[0][0]
    selectors = conn.execute("SELECT id, type, config_json FROM site_selectors WHERE job_site_id = ?", [site_id]).fetchall()
    for sel in selectors:
        print(f"ID: {sel[0]}, Type: {sel[1]}")
        print(json.dumps(json.loads(sel[2]), indent=2))
else:
    print("No AE Talents site found.")

conn.close()
