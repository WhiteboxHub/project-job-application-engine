"""
Seed KForce and Capgemini selectors + site configurations into DuckDB.
Run once: python scripts/seed_kforce_capgemini.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from config.settings import settings

conn = duckdb.connect(settings.DUCKDB_PATH)

print("Seeding KForce and Capgemini into DuckDB...")

# ===========================================================================
# KForce — Platform + Site
# ===========================================================================
conn.execute("""
    INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
    VALUES (5, 'KForce Custom', 'strategies.custom.KForceStrategy', 'manual', false)
""")
conn.execute("""
    INSERT OR IGNORE INTO job_sites
        (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
    VALUES (
        5, 'KForce', 'kforce.com', 5, 'Staffing vendor',
        'https://www.kforce.com/find-work/search-jobs/',
        false
    )
""")

# KForce Listing Selectors
kforce_listing = {
    "search_input":    "input#ctl00_ctl00_MainContent_FullWidth_txtKeyword",
    "search_button":   "button#ctl00_ctl00_MainContent_FullWidth_btnSearch",
    "container":       "a.tile__title-link",
    "search_keywords": ["AI Engineer", "Python Developer", "Machine Learning Engineer"]
}

# KForce Application Selectors
kforce_application = {
    "apply_initiator":    "button.apply-action__btn",
    "apply_link_option":  "a.dropdown-item[href*='apply']",
    "form_fields": {
        "first_name":    "input#ctl00_ctl00_MainContent_FullWidth_txtFirstName",
        "last_name":     "input#ctl00_ctl00_MainContent_FullWidth_txtLastName",
        "email":         "input#ctl00_ctl00_MainContent_FullWidth_txtEmail",
        "email_verify":  "input#ctl00_ctl00_MainContent_FullWidth_txtEmailConfirm",
        "phone":         "input#ctl00_ctl00_MainContent_FullWidth_txtPhone",
        "zip_code":      "input#ctl00_ctl00_MainContent_FullWidth_txtZip",
        "state":         "select#ctl00_ctl00_MainContent_FullWidth_ddlState",
        "resume_upload": "input[type='file']",
        "submit_btn":    "input#ctl00_ctl00_MainContent_FullWidth_btnSubmit",
        "next_btn":      "input#ctl00_ctl00_MainContent_FullWidth_btnNext",
        "eligibility_auth": "input[name*='Authorization']"
    },
    "questionnaire_answers": {
        "eligibility_auth": "AuthorizedForAny"
    },
    "success_indicators": [
        "Thank you for applying",
        "Application submitted",
        "Your application has been received"
    ]
}

# Delete old KForce selectors if any
conn.execute("DELETE FROM site_selectors WHERE job_site_id = 5")

conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (5, 5, 'listing', ?, CURRENT_TIMESTAMP)
""", [json.dumps(kforce_listing)])

conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (6, 5, 'application', ?, CURRENT_TIMESTAMP)
""", [json.dumps(kforce_application)])

print("✅ KForce seeded (id=5, is_active=false — enable manually when ready)")

# ===========================================================================
# Capgemini — Platform + Site
# ===========================================================================
conn.execute("""
    INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
    VALUES (6, 'Capgemini SuccessFactors', 'strategies.custom.CapgeminiStrategy', 'manual', false)
""")
conn.execute("""
    INSERT OR IGNORE INTO job_sites
        (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
    VALUES (
        6, 'Capgemini', 'capgemini.com', 6, 'Consulting firm',
        'https://www.capgemini.com/us-en/careers/join-capgemini/job-search/?country_code=us-en&country_name=United%20States&size=15',
        false
    )
""")

# Capgemini Listing Selectors
capgemini_listing = {
    "search_input":    "input.search-input",
    "job_cards":       "a.job-card__link",
    "search_keywords": ["AI Engineer", "Python Developer", "Data Engineer"]
}

# Capgemini Application Selectors
capgemini_application = {
    "apply_button_main":  "a.btn--primary[href*='apply'], button.btn-apply",
    "sign_in_button":     "//button[contains(text(),'Sign In')] | //a[contains(text(),'Sign In')]",
    "login_email":        "input#username, input[name='username'], input[type='email']",
    "login_password":     "input#password, input[name='password'], input[type='password']",
    "login_submit":       "button#fbqa_signin, button[type='submit']",
    "form_fields": {
        "phone":          "input[id*='phoneNumber'], input[placeholder*='phone' i]",
        "work_auth":      "input[id*='workAuth'], select[id*='workAuth']",
        "country":        "input[id*='country'], select[id*='country']"
    },
    "questionnaire_answers": {
        "work_auth": "I am authorized to work in the United States for any employer"
    },
    "success_indicators": [
        "Application submitted",
        "Thank you for applying",
        "Your application has been received",
        "application was successfully submitted"
    ]
}

# Delete old Capgemini selectors if any
conn.execute("DELETE FROM site_selectors WHERE job_site_id = 6")

conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (7, 6, 'listing', ?, CURRENT_TIMESTAMP)
""", [json.dumps(capgemini_listing)])

conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (8, 6, 'application', ?, CURRENT_TIMESTAMP)
""", [json.dumps(capgemini_application)])

print("✅ Capgemini seeded (id=6, is_active=false — needs CAPGEMINI_EMAIL + PASSWORD in .env)")

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
