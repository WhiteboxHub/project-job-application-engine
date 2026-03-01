"""
Seed LanceSoft (JobDiva) selectors + site configurations into DuckDB.
Run once: python scripts/seed_lancesoft_config.py
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

print(f"Seeding LanceSoft into DuckDB ({db_path})...")

# ===========================================================================
# PLATFORM
# ===========================================================================
conn.execute("INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level) VALUES (7, 'JobDiva', 'strategies.custom.LanceSoftStrategy', 'full')")

# ===========================================================================
# SITE
# ===========================================================================
conn.execute("""
    INSERT INTO job_sites (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
    VALUES (7, 'LanceSoft', 'lancesoft.com', 7, 'Staffing vendor', 'https://www.jobdiva.com/portal/?a=21jdnwxg32t5lixw92s8ng2g2n6uzy2n9tz9rdnsz2n18q3v5pnb7y8m560c5r5i', false)
    ON CONFLICT (domain) DO UPDATE SET 
        id = EXCLUDED.id,
        company_name = EXCLUDED.company_name,
        ats_platform_id = EXCLUDED.ats_platform_id,
        search_url_template = EXCLUDED.search_url_template
""")


# ===========================================================================
# LanceSoft Selectors (From lancesoft.py hardcoded dict)
# ===========================================================================
lancesoft_config = {
    "listing": {
        "country_button": ["//button[contains(., 'United States')]"],
        "country_dropdown_btn": ["//button[contains(., 'Country')] | //button[contains(., 'Select Country')]"],
        "usa_option": ["//a[@class='dropdown-item'][contains(., 'United States')]"],
        "country_fallback": ["div.hideshow-country button"],
        "search_input": ["input.inputbox_search", "input[placeholder*='Search job title' i]"],
        "job_container": ["div.list-group-item.list-group-item-action"],
        "job_title": ["span.text-capitalize.jd-nav-label.notranslate"],
        "job_id": ["div.d-flex.text-muted small:nth-child(3)"],
        "details_button": ["button.btn.jd-btn"],
        "next_page_btn": ["button[aria-label='Next Page']"]
    },
    "application": {
        "apply_button": ["#root > div > div > div:nth-child(4) > div:nth-child(1) > button"],
        "quick_apply_option": ["#applyOptionsModal > div > div > div.modal-body > div > button:nth-child(3) > span"],
        "form_modal": ["#quickApplyModal"],
        "submit_btn": ["#quickApplyModal > div > div > div.job-app-btns > div:nth-child(2) > button"],
        "next_btn_outline": ["button.btn.jd-btn-outline"],
        "next_btn_solid": ["button.btn.jd-btn:not(.jd-btn-outline)"],
        "consent_checkbox": ["//div[@id='quickApplyModal']//input[@type='checkbox']"],
        "file_input": ["div#quickApplyModal input[type='file']"],
        "eeo": {
            "gender_radio": ["//input[@type='radio'][@name='gender'][@value='1,3']"],
            "ethnicity_radio": ["//input[@type='radio'][@name='ethnicity'][@value='1,3']"],
            "race_radio": ["//input[@type='radio'][@name='race'][@value='2,8']"],
            "veteran_radios": ["//input[@type='radio'][@name='veteran_status']"]
        }
    }
}

conn.execute("DELETE FROM site_selectors WHERE job_site_id = 7")
conn.execute("INSERT INTO site_selectors (id, job_site_id, type, config_json) VALUES (?, ?, ?, ?)", 
             [7, 7, 'full_config', json.dumps(lancesoft_config)])

print("Done! LanceSoft seeded with list-based selectors.")
conn.close()
