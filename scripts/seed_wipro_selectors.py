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
    # Search form (SuccessFactors Horizon)
    "keyword_input":   "input[data-testid='searchByKeywords'], input[placeholder*='Skills' i], input[name='q']",
    "location_input":  "input[data-testid='searchByLocation'], input[placeholder*='Location' i], input[name='locationsearch']",
    "search_button":   "button[data-testid='submitJobSearchBtn'], button.keywordsearchbutton",
    "cookie_accept_button": "#cookie-accept, button.cookiemanageracceptall",

    # Job results (Horizon theme)
    "job_container":   "li[data-testid='jobCard'], li.JobsList_jobCard__8wE-Z",
    "job_title":       "a[data-testid^='jobCardTitle_'], a.jobCardTitle",
    "job_link":        "a[data-testid^='jobCardTitle_'], a.jobCardTitle",
    "job_id":          "span[data-help-id^='jobCardFooterValue_'], span.JobsList_jobCardFooterValue__Lc--j",
    "next_page":       "button[data-testid='goToNextPageBtn'], button.Paginator_btn__KRVdV:contains('Next')",
    "location":        "div[data-testid='jobCardLocation'], div.JobsList_jobCardLocation__oMpM+"
}

# ---- Application selectors (all keys wipro.py accesses for form filling) ----
wipro_application = {
    # Apply button flow (two-step - SuccessFactors Horizon)
    "apply_button_dropdown":  ["#unifyApplyNowTopButton", "button[title*='Apply' i]", "button.apply-action"],
    "apply_button_menu_item": ["#applyOption--manual", "li a[href*='apply']", "div.dropdown-menu a[title*='Apply Now' i]"],

    # Login (SuccessFactors Horizon)
    "login_email_input":    ["#username", "input[type='email']", "input[id*='email']"],
    "login_password_input": ["#password", "input[type='password']", "input[id*='password']"],
    "login_submit_button":  ["button[onclick*='validateFields']", "button[type='submit']", "input[type='submit']"],

    # Form navigation & expansion
    "expand_all_sections":  ["[id$=':_expandAllSections']", ".expandCollapseTxt:contains('Expand')"],
    "section_trigger_profile": ["//button[.//span[contains(text(),'Profile')]]", "[id*=':topBar']"],
    "section_trigger_experience": ["//button[.//span[contains(text(),'Experience')]]", "[id*=':topBar']"],
    "section_trigger_education": ["//button[.//span[contains(text(),'Education')]]", "[id*=':topBar']"],
    "section_trigger_job_specific": ["//button[.//span[contains(text(),'Specific')]]", "[id*=':topBar']"],

    # Personal info (Horizon use consistent 'name' attributes)
    "first_name_input":   ["input[name='firstName']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'First Name')]][1]//input"],
    "last_name_input":    ["input[name='lastName']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Last Name')]][1]//input"],
    "email_input":        ["input[name='contactEmail']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Email Address')]][1]//input"],
    "phone_input":        ["input[name='cellPhone']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Phone')]][1]//input"],
    "preferred_name_input":   ["input[name='preferredName']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Preferred Name')]][1]//input"],
    "social_account_url_input": ["input[name='custSocialURL']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Social Account URL')]][1]//input"],
    "address_input":      ["input[name='address']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Address Line 1')]][1]//input"],
    "city_input":         ["input[name='city']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'City')]][1]//input"],
    "zip_input":          ["input[name='zip']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Postal Code')]][1]//input"],
    "employee_id_input":  ["input[name='custCandidateFillEmpID']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Employee ID')]][1]//input"],

    # Searchable Dropdowns (Horizon uses juic.fire searchable inputs)
    "country_code_select":  ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Country Code')]][1]//input", "[id*=':_input']"],
    "gender_select":        ["//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Gender')]]//input", "[id*=':_input']"],
    "disability_assistance_select": ["//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Disability Assistance')]]//input", "[id*=':_input']"],
    "disability_assistance_explain_input": ["input[name='custDisabilityAssistance']", "//div[contains(@class,'RCMFormField')][.//*[contains(text(),'assistance/accommodations')]]//input"],
    "country_select":       ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Country/Region')]][1]//input", "[id*=':_input']"],
    "state_select":         ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Profile Information')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Province') or contains(text(),'State')]][1]//input", "[id*=':_input']"],
    "employed_before_select": ["//div[contains(@class,'RCMFormField')][.//*[contains(text(),'employed with Wipro')]]//input", "[id*=':_input']"],

    # Experience section (Row 1)
    "experience_section_trigger": ["//button[.//span[contains(text(),'Experience')]]", "[id*=':topBar']"],
    "job_title_input":      ["input[name='VFLD13']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Title')]][1]//input"],
    "company_input":        ["input[name='VFLD12']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Company')]][1]//input"],
    "start_date_input":     ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Start Date')]][1]//ui5-date-picker", "[title='Start Date']"],
    "end_date_input":       ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'End Date')]][1]//ui5-date-picker", "[title='End Date']"],
    "exp_country_select":   ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Country')]][1]//input", "[id*=':_input']"],
    "exp_state_select":     ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'State')]][1]//input", "[id*=':_input']"],
    "exp_city_input":       ["input[name='VFLD6']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'City')]][1]//input"],

    # Education section (Row 1)
    "education_section_trigger": ["//button[.//span[contains(text(),'Education')]]", "[id*=':topBar']"],
    "edu_type_select":      ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Education Type')]][1]//input", "[id*=':_input']"],
    "edu_degree_select":    ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Degree')]][1]//input", "[id*=':_input']"],
    "edu_school_input":     ["input[name='VFLD1']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'School/University')]][1]//input"],
    "edu_major_select":     ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Major')]][1]//input", "[id*=':_input']"],
    "edu_start_date":       ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Start Date')]][1]//ui5-date-picker-xweb-calendar-widget"],
    "edu_end_date":         ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'End Date')]][1]//ui5-date-picker-xweb-calendar-widget"],
    "edu_grad_date":        ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Year Of Passing')]][1]//ui5-date-picker-xweb-calendar-widget"],
    "edu_country_select":   ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Country')]][1]//input", "[id*=':_input']"],
    "edu_state_select":     ["//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'State')]][1]//input", "[id*=':_input']"],
    "edu_city_input":       ["input[name='VFLD7']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'City')]][1]//input"],

    # Job-Specific Information
    # Robust label-based selectors instead of titles, as titles change based on selected value
    "auth_country_select":      [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'legally authorized')]][1]//input"
    ],
    "auth_work_country_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Work Authorization Country')]][1]//input"
    ],
    "visa_status_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Visa Status')]][1]//input"
    ],
    "sponsorship_future_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'sponsorship')]][1]//input"
    ],
    "citizenship_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Citizenship')]][1]//input"
    ],
    "govt_employed_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'government')]][1]//input"
    ],
    "race_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Race')]][1]//input"
    ],
    "veteran_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Veteran')]][1]//input"
    ],
    "disability_select": [
        "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Job-Specific')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Disability')]][1]//input"
    ],

    # Resume upload
    "resume_upload_input":   ["input[type='file']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Documents')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Resume')]][1]//input[@type='file']"],
    "resume_upload_trigger": ["span[class*='addAttachments']", "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Documents')]]//div[contains(@class,'RCMFormField')][.//*[contains(text(),'Resume')]][1]//span[contains(@class,'addAttachments')]", "[id*=':_attachIcon']"],
    "upload_success_indicator": ["[id*=':_attachSuccess']:not(.displayNone)", "[id*=':_attachDownloadLabelLink']"],

    # Terms + submit
    "terms_checkbox": ["input[type='checkbox'][name='termsAndConditions']", ".rcmFormElement input[type='checkbox']", "input[type='checkbox'][id*='terms' i]", "input[type='checkbox'][id*='consent' i]"],
    "submit_button":  [
        "[id$=':_submitBtn']", 
        "button[title*='Apply' i]", 
        "button[id*='submit' i]", 
        ".rcmSaveButton:contains('Apply')",
        "//button[.//span[contains(text(),'Apply')]]",
        "//button[.//span[contains(text(),'Submit')]]",
        ".rcmSaveButton"
    ],

    # Success detection
    "success_indicators": [
        "Your application has been sent",
        "Application submitted",
        "Thank you for applying",
        "Ghazal_Sultan.pdf" # Temporary for dry run check if resume persists
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
print("[OK] Wipro selectors seeded successfully (listing + application)")
print(f"   Site ID: {WIPRO_SITE_ID}")
print(f"   Listing keys: {len(wipro_listing)}")
print(f"   Application keys: {len(wipro_application)}")
