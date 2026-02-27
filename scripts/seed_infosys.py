"""
Seed Infosys selectors + site configurations into DuckDB.
Run once: python scripts/seed_infosys.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from config.settings import settings

conn = duckdb.connect(settings.DUCKDB_PATH)

print("Seeding Infosys into DuckDB...")

# ===========================================================================
# Infosys — Platform + Site
# ===========================================================================
# Ensure the platform exists (id 4 was already updated in logic, but let's be sure)
conn.execute("""
    INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
    VALUES (4, 'Infosys Custom', 'strategies.custom.InfosysStrategy', 'manual', false)
""")
conn.execute("""
    UPDATE ats_platforms SET class_handler = 'strategies.custom.InfosysStrategy' WHERE id = 4
""")

conn.execute("""
    INSERT OR IGNORE INTO job_sites
        (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
    VALUES (
        4, 'Infosys', 'infosys.com', 4, 'System integrator',
        'https://digitalcareers.infosys.com/infosys/global-careers?location=USA',
        true
    )
""")

# Infosys Listing Selectors
infosys_listing = {
    "search_input": ["input.js_search_cp_jobs", "input[name='search']", "input#keyword"],
    "search_button": ["a.search-jobs-button", "button#search", "button.search-btn"],
    "search_keywords": ["Gen AI Engineer", "Python Developer", "Machine Learning Engineer", "AI Architect"],
    "target_keyword": ["ai", "machine learning", "ml", "data science", "engineer", "developer", "technology", "software", "architect"],
    "blocked_keyword": ["nurse", "sales", "hr", "marketing", "finance", "legal", "doctor"],
    "location_filter": ["canada", "brazil", "india", "mexico", "united kingdom", "uk", "australia"],
    "next_button": ["a.next", "li.next a", "a[title='Next']", "button.next"],
    "search_base": "https://digitalcareers.infosys.com/infosys/global-careers?location={location}"
}

# Infosys Application Selectors
infosys_application = {
    "apply_button": [
        "//*[@id='sortableHeader']/li/div/div/div/div[2]/a",
        "#sortableHeader li div div div div:nth-child(2) a",
        ".apply-button-container a",
        "a.infosys-apply-link",
        "//a[contains(@class, 'apply')]",
        "//a[contains(text(), 'Apply')]"
    ],
    "first_time_user": ["//button[contains(text(), 'First Time User')]"],
    "privacy_consent": ["//a[contains(@class, 'consent-button')]", "button.proceed"],
    "delays": {
        "between_keywords_min": 3.0,
        "between_keywords_max": 5.0,
        "page_load_min": 5.0,
        "page_load_max": 10.0,
        "after_click_min": 2.0,
        "after_click_max": 5.0,
        "form_fill_min": 0.5,
        "form_fill_max": 1.5,
        "backend_processing": 40.0,
        "final_submission_wait": 20.0,
        "after_upload_popup_wait": 2.0,
        "second_popup_poll_duration": 10.0,
        "second_popup_poll_interval": 1.0,
        "after_import_fields_wait": 5.0,
        "after_resume_next_wait": 5.0
    }
}

# Delete old Infosys selectors if any
conn.execute("DELETE FROM site_selectors WHERE job_site_id = 4")

conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (9, 4, 'listing', ?, CURRENT_TIMESTAMP)
""", [json.dumps(infosys_listing)])

conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (10, 4, 'application', ?, CURRENT_TIMESTAMP)
""", [json.dumps(infosys_application)])

print("✅ Infosys seeded (id=4, is_active=true)")

# ===========================================================================
# Verify
# ===========================================================================
print("\n=== Current DB State ===")
rows = conn.execute("""
    SELECT js.id, js.company_name, ap.class_handler, js.is_active,
           (SELECT COUNT(*) FROM site_selectors ss WHERE ss.job_site_id = js.id) as sel_count
    FROM job_sites js
    JOIN ats_platforms ap ON js.ats_platform_id = ap.id
    ORDER BY js.id
""").fetchall()
for r in rows:
    active = "✅ ACTIVE" if r[3] else "💤 inactive"
    print(f"  [{r[0]}] {r[1]:<20} | {r[4]} selectors | {active}")

conn.close()
print("\nDone!")
