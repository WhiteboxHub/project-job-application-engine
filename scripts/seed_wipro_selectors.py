"""
Seed Wipro selectors into DuckDB (listing + application selectors).
Run once: python scripts/seed_wipro_selectors.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from config.settings import settings

conn = duckdb.connect(settings.DUCKDB_PATH)

# Wipro job_site id = 3 (from init_db.py)
WIPRO_SITE_ID = 3

# Clear old Wipro selectors
conn.execute("DELETE FROM site_selectors WHERE job_site_id = ?", [WIPRO_SITE_ID])

# ---- Listing selectors (all keys wipro.py accesses via selectors_config) ----
wipro_listing = {
    # Search form
    "keyword_input":   "input[id*='keyword'], input[placeholder*='Keyword' i], input[placeholder*='Search' i], input[aria-label*='keyword' i]",
    "location_input":  "input[id*='location'], input[placeholder*='Location' i], input[aria-label*='location' i]",
    "search_button":   "button[type='submit'], button[id*='search' i], button.search-btn",

    # Job results
    "job_container":   "li.job-list-item, article.job-card, div.job-listing-item",
    "job_title":       "a.job-title, h2.job-title, span.job-title",
    "job_link":        "a[href*='/job/'], a.job-title",
    "job_id":          "span.job-id, span[class*='job-id'], span[class*='footer-value']",
    "next_page":       "a[aria-label='Next page'], button[aria-label='Next'], li.next a"
}

# ---- Application selectors (all keys wipro.py accesses for form filling) ----
wipro_application = {
    # Apply button flow (two-step)
    "apply_button_dropdown":  "button[title*='Apply' i], button.apply-action",
    "apply_button_menu_item": "li a[href*='apply'], div.dropdown-menu a[title*='Apply Now' i]",

    # Login (for Wipro's candidate portal)
    "login_email_input":    "input[type='email'], input[id*='email']",
    "login_password_input": "input[type='password'], input[id*='password']",
    "login_submit_button":  "button[type='submit'], input[type='submit']",

    # Form expansion
    "expand_all_sections":  "button[title*='Expand' i], a[title*='Expand All' i]",

    # Personal info
    "first_name_input":   "input[id*='firstName' i], input[id*='first_name' i]",
    "last_name_input":    "input[id*='lastName' i],  input[id*='last_name' i]",
    "email_input":        "input[id*='email' i]",
    "phone_input":        "input[id*='phone' i], input[id*='mobile' i]",
    "preferred_name_input":   "input[id*='preferred' i]",
    "social_account_url_input": "input[id*='social' i], input[id*='linkedin' i]",
    "address_input":      "input[id*='address' i], input[id*='street' i]",
    "city_input":         "input[id*='city' i]",
    "zip_input":          "input[id*='zip' i], input[id*='postal' i]",
    "employee_id_input":  "input[id*='employee' i]",

    # Dropdowns
    "country_code_select":  "select[id*='countryCode' i]",
    "gender_select":        "select[id*='gender' i]",
    "disability_assistance_select": "select[id*='disability' i]",
    "disability_assistance_explain_input": "textarea[id*='disabilityExplain' i]",
    "country_select":       "select[id*='country' i]",
    "state_select":         "select[id*='state' i]",
    "employed_before_select": "select[id*='employed' i]",

    # Experience section
    "experience_section_trigger": "a[title*='Experience' i], button[id*='experience' i]",
    "job_title_input":      "input[id*='jobTitle' i], input[id*='job_title' i]",
    "company_input":        "input[id*='company' i], input[id*='employer' i]",
    "start_date_input":     "input[id*='startDate' i], input[id*='start_date' i]",
    "end_date_input":       "input[id*='endDate' i], input[id*='end_date' i]",
    "exp_country_select":   "select[id*='expCountry' i]",
    "exp_state_select":     "select[id*='expState' i]",
    "exp_city_input":       "input[id*='expCity' i]",

    # Education section
    "education_section_trigger": "a[title*='Education' i], button[id*='education' i]",
    "edu_type_select":      "select[id*='eduType' i], select[id*='educationType' i]",
    "edu_degree_select":    "select[id*='degree' i]",
    "edu_school_input":     "input[id*='school' i], input[id*='university' i]",
    "edu_major_select":     "select[id*='major' i], select[id*='field' i]",
    "edu_start_date":       "input[id*='eduStartDate' i]",
    "edu_end_date":         "input[id*='eduEndDate' i]",
    "edu_grad_date":        "input[id*='gradDate' i], input[id*='graduationDate' i]",
    "edu_country_select":   "select[id*='eduCountry' i]",
    "edu_state_select":     "select[id*='eduState' i]",
    "edu_city_input":       "input[id*='eduCity' i]",

    # Work auth / compliance
    "auth_country_select":      "select[id*='authCountry' i]",
    "auth_work_country_select": "select[id*='authWorkCountry' i]",
    "visa_status_select":       "select[id*='visa' i]",
    "sponsorship_future_select": "select[id*='sponsor' i]",
    "citizenship_select":       "select[id*='citizen' i]",
    "govt_employed_select":     "select[id*='govtEmployed' i]",
    "race_select":              "select[id*='race' i]",
    "veteran_select":           "select[id*='veteran' i]",
    "disability_select":        "select[id*='disability' i]",

    # Resume upload
    "resume_upload": "input[type='file']",

    # Terms + submit
    "terms_checkbox": "input[type='checkbox'][id*='terms' i], input[type='checkbox'][id*='consent' i]",
    "submit_button":  "button[type='submit'][id*='submit' i], input[type='submit']",

    # Success detection
    "success_indicators": [
        "Your application has been sent",
        "Application submitted",
        "Thank you for applying"
    ]
}

# Insert new selectors
# Use high IDs (100+) to avoid conflicts with existing records
conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (100, ?, 'listing', ?, CURRENT_TIMESTAMP)
""", [WIPRO_SITE_ID, json.dumps(wipro_listing)])

conn.execute("""
    INSERT INTO site_selectors (id, job_site_id, "type", config_json, updated_at)
    VALUES (101, ?, 'application', ?, CURRENT_TIMESTAMP)
""", [WIPRO_SITE_ID, json.dumps(wipro_application)])

conn.close()
print("✅ Wipro selectors seeded successfully (listing + application)")
print(f"   Site ID: {WIPRO_SITE_ID}")
print(f"   Listing keys: {len(wipro_listing)}")
print(f"   Application keys: {len(wipro_application)}")
