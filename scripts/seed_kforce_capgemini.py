"""
Seed KForce and Capgemini selectors + site configurations into DuckDB.
Run once: python scripts/seed_kforce_capgemini.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import duckdb
from config.settings import settings

db_path = settings.DUCKDB_PATH
if db_path.startswith("md:"):
    token_suffix = f"?motherduck_token={settings.MOTHERDUCK_TOKEN}" if settings.MOTHERDUCK_TOKEN else ""
    conn = duckdb.connect(f"{db_path}{token_suffix}")
else:
    conn = duckdb.connect(db_path)

print(f"Seeding KForce and Capgemini into DuckDB ({db_path})...")

# ===========================================================================
# PLATFORMS
# ===========================================================================
conn.execute("INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level) VALUES (5, 'KForce Custom', 'strategies.custom.KForceStrategy', 'full')")
conn.execute("INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level) VALUES (6, 'SuccessFactors', 'strategies.custom.CapgeminiStrategy', 'full')")

# ===========================================================================
# SITES
# ===========================================================================
conn.execute("DELETE FROM job_sites WHERE id IN (5, 6)")
conn.execute("""
    INSERT INTO job_sites (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
    VALUES (5, 'KForce', 'kforce.com', 5, 'Staffing vendor', 'https://www.kforce.com/find-work/search-jobs/', true)
""")

conn.execute("""
    INSERT INTO job_sites (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
    VALUES (6, 'Capgemini', 'capgemini.com', 6, 'Consulting firm', 'https://www.capgemini.com/us-en/careers/join-capgemini/job-search/?country_code=us-en&country_name=United%20States&size=15', false)
""")

# ===========================================================================
# KForce Selectors (Verified via Subagent)
# ===========================================================================
kforce_config = {
    "listing": {
        "search_input": ["input[placeholder='Search by Job Title or Skill']", "input#ctl00_ctl00_MainContent_FullWidth_txtKeyword"],
        "search_button": ["input.search-icon.submitIcon", "button#ctl00_ctl00_MainContent_FullWidth_btnSearch"],
        "job_cards": ["a.linkForJob", "a.tile__title-link"],
        "search_keywords": ["AI Engineer", "Python Developer", "Machine Learning Engineer"]
    },
    "application": {
        "apply_button_main": ["//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]", "//a[contains(text(), 'Apply')]"],
        "dropdown_option": ["img[title='Form']", "//span[contains(text(), 'Apply Today')]"],
        "local_resume_radio": ["#resumeUploadType_0"],
        "form_fields": {
            "first_name":     ["#firstName"],
            "last_name":      ["#lastName"],
            "email":          ["#emailAddress"],
            "email_verify":   ["#emailAddressVerify"],
            "phone":          ["#phoneNumberAll"],
            "zip_code":       ["#postalCode"],
            "state_dropdown": ["#state"],
            "resume_upload":  ["#uploadFileSystemResume"],
            "eligibility":    ["#eligibility0"],
            "submit_btn":     ["#SubmitButton"]
        }
    }
}

conn.execute("DELETE FROM site_selectors WHERE job_site_id = 5")
conn.execute("INSERT INTO site_selectors (id, job_site_id, type, config_json) VALUES (?, ?, ?, ?)", 
             [5, 5, 'full_config', json.dumps(kforce_config)])

# ===========================================================================
# Capgemini Selectors
# ===========================================================================
capgemini_config = {
    "listing": {
        "search_input": ["input#searchsubmit"],
        "job_cards": ["a.joblink"],
        "search_keywords": ["AI Engineer", "Python Developer"]
    },
    "application": {
        "apply_button_main": ["a.cta-link", "a.btn--primary[href*='apply']", "button.btn-apply"],
        "login_popup_trigger": ["a[onclick*='openSignInModal']"],
        "login_email": ["input#username"],
        "login_password": ["input#password"],
        "login_submit": ["button#fbqa_signin"],
        "form_fields": {
            "phone": ["input[id*='phoneNumber']", "input[placeholder*='phone' i]"],
            "submit_btn": ["button#fbqa_apply"]
        }
    }
}

conn.execute("DELETE FROM site_selectors WHERE job_site_id = 6")
conn.execute("INSERT INTO site_selectors (id, job_site_id, type, config_json) VALUES (?, ?, ?, ?)", 
             [6, 6, 'full_config', json.dumps(capgemini_config)])

print("Done! KForce and Capgemini seeded with verified list-based selectors.")
conn.close()
