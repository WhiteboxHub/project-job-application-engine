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
        "first_name":    "input#firstName",
        "last_name":     "input#lastName",
        "email":         "input#emailAddress",
        "email_verify":  "input#emailAddressVerify",
        "phone":         "input#phoneNumberAll",
        "zip_code":      "input#postalCode",
        "country":       "select#countryID",
        "state":         "select#state",
        "resume_upload": "input#uploadFileSystemResume, input[type='file']",
        "submit_btn":    "input#SubmitButton, button[type='submit'], input[type='submit']",
        "next_btn":      "button#btnNext, input#btnNext",
        "eligibility_auth": "input[name*='Authorization'], input[name*='auth']"
    },
    "questionnaire_answers": {
        "eligibility_auth": "AuthorizedForAny"
    },
    "delays": {
        "between_steps_min": 0.7,
        "between_steps_max": 1.5,
        "after_click_min": 1.0,
        "after_click_max": 2.0,
        "form_fill_min": 0.5,
        "form_fill_max": 1.2
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
        true
    )
""")

# Capgemini Listing Selectors
capgemini_listing = {
    "search_input":    "input#searchsubmit",
    "job_cards":       "a.joblink",
    "search_keywords": ["AI Engineer", "Python Developer", "Software Engineer", "Data Engineer"]
}

# Capgemini Application Selectors
capgemini_application = {
    "apply_button_main":  "a.cta-link, a.btn--primary[href*='apply'], button.btn-apply",
    "sign_in_button":     "a[onclick*='openSignInModal']",
    "login_email":        "input#username",
    "login_password":     "input#password",
    "login_submit":       "button#fbqa_signin, button[name='fbqa_signin']",
    "form_fields": {
        "phone":             "input[id*='phoneNumber'], input[placeholder*='phone' i]",
        "legally_entitled":  "input[aria-label*='legally entitled to work']",
        "sponsorship":       "input[aria-label*='require sponsorship']",
        "agreement":         "input[aria-label*='entered into any agreement']",
        "ethnicity":         "input[aria-label='Ethnicity']",
        "veteran":           "input[aria-label='Veteran Status']",
        "disability":        "input[aria-label*='believe you have a disability']",
        "previously_employed": "input[aria-label*='employed by Capgemini Group before']",
        "gender_consent":    "input[aria-label*='explicit consent for Capgemini Group to collect and process information about my gender']",
        "gender":            "input[aria-label='How do you identify?']",
        "sms_consent":       "input[aria-label*='receive communications via SMS']",
        "country":           "input[id*='country'], select[id*='country']",
        "submit_btn":        "button#fbqa_apply"
    },
    "questionnaire_answers": {
        "legally_entitled":  "Yes",
        "sponsorship":       "No",
        "agreement":         "No",
        "ethnicity":         "South Asian",
        "veteran":           "Non-Veteran",
        "disability":        "No, I don’t have a disability",
        "previously_employed": "No",
        "gender_consent":    "Yes",
        "gender":            "Female",
        "sms_consent":       "Yes"
    },
    "delays": {
        "between_steps_min": 1.0,
        "between_steps_max": 2.5,
        "after_login_click": 15.0,
        "form_fill_min": 0.7,
        "form_fill_max": 1.5,
        "dropdown_select_min": 0.5,
        "dropdown_select_max": 1.0,
        "page_load_min": 3.0,
        "page_load_max": 15.0,
        "short_delay_min": 1.0,
        "click_min": 2.0,
        "scroll_min": 1.0,
        "dropdown_open_min": 1.5
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
