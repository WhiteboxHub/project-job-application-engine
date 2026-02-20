/*
  Job Application Engine - DuckDB Schema
  Single database for both configuration and history
  Version: 1.1 (Merged HEAD + Bavish)
*/

-- =====================================================
-- CONFIGURATION TABLES
-- =====================================================

-- 1. ATS Platforms (Strategy Definitions)
CREATE TABLE IF NOT EXISTS ats_platforms (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    class_handler VARCHAR(100) NOT NULL,
    is_headless_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Job Sites (Company Configurations)
CREATE TABLE IF NOT EXISTS job_sites (
    id INTEGER PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    domain VARCHAR(255) UNIQUE NOT NULL,
    ats_platform_id INTEGER,
    category VARCHAR(50) NOT NULL CHECK (category IN ('System integrator', 'Consulting firm', 'Staffing vendor', 'Product Company')),
    
    -- Navigation & Templates
    search_url_template TEXT NOT NULL,
    apply_url_template TEXT,
    
    -- Bot Defense & Network
    cf_clearance_required BOOLEAN DEFAULT FALSE,
    proxy_region VARCHAR(10) DEFAULT 'US',
    
    -- Operational Flags
    is_active BOOLEAN DEFAULT TRUE,
    max_applications_per_run INTEGER DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (ats_platform_id) REFERENCES ats_platforms(id)
);

-- 3. Site Selectors (CSS/XPath Configurations as JSON)
CREATE TABLE IF NOT EXISTS site_selectors (
    id INTEGER PRIMARY KEY,
    ats_platform_id INTEGER,
    job_site_id INTEGER,
    type VARCHAR(20) NOT NULL CHECK (type IN ('listing', 'application')),
    config_json JSON NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ats_platform_id) REFERENCES ats_platforms(id),
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id)
);

-- 4. Job Listings (Discovered Jobs Queue)
CREATE SEQUENCE IF NOT EXISTS job_listings_id_seq;
CREATE TABLE IF NOT EXISTS job_listings (
    id INTEGER PRIMARY KEY DEFAULT nextval('job_listings_id_seq'),
    job_site_id INTEGER NOT NULL,
    
    -- Job Data
    external_job_id VARCHAR(100) NOT NULL,
    job_title VARCHAR(255),
    job_url TEXT NOT NULL,
    
    -- Pipeline State
    status VARCHAR(20) DEFAULT 'discovered' CHECK (status IN ('discovered', 'ready_to_apply', 'applied', 'failed', 'blacklisted')),
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE (job_site_id, external_job_id),
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id)
);

-- 5. Applications (Submission History)
CREATE SEQUENCE IF NOT EXISTS applications_id_seq;
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY DEFAULT nextval('applications_id_seq'),
    job_site_id INTEGER NOT NULL,
    job_listing_id INTEGER,
    
    job_title VARCHAR(255),
    job_url TEXT,
    
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'skipped')),
    error_message TEXT,
    
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id),
    FOREIGN KEY (job_listing_id) REFERENCES job_listings(id)
);

-- 6. Metrics (Performance Tracking)
CREATE TABLE IF NOT EXISTS metrics (
    id BIGINT PRIMARY KEY,
    run_date DATE NOT NULL,
    job_site_id INTEGER,
    
    total_jobs_found INTEGER DEFAULT 0,
    total_applications_attempted INTEGER DEFAULT 0,
    total_applications_successful INTEGER DEFAULT 0,
    total_applications_failed INTEGER DEFAULT 0,
    
    avg_application_time_seconds FLOAT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (job_site_id) REFERENCES job_sites(id)
);

-- =====================================================
-- SEED DATA: Insight Global (ID 1)
-- =====================================================
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
VALUES (1, 'Insight Global Custom', 'strategies.custom.InsightGlobalStrategy', false);

INSERT OR IGNORE INTO job_sites (id, company_name, domain, ats_platform_id, category, search_url_template, apply_url_template, cf_clearance_required, is_active)
VALUES (
    1,
    'Insight Global',
    'insightglobal.com',
    1,
    'Staffing vendor',
    'https://insightglobal.com/jobs/',
    'https://jobs.insightglobal.com/users/jobapplynoaccount.aspx?jobid={job_id}',
    false,
    true
);

INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    1, 1, 'listing',
    '{
        "container": "div.result",
        "pagination_type": "click_next",
        "pagination_selector": "a[title=\"Page Forward\"]",
        "fields": {
            "job_id": { "selector": "button[id=\"btnSaveJob\"]", "attr": "jobId" },
            "title": { "selector": ".job-title a", "type": "text" },
            "url": { "selector": ".job-title a", "attr": "href" }
        }
    }'::JSON
);

INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    2, 1, 'application',
    '{
        "flow_type": "legacy_form",
        "form_fields": {
            "first_name": "input[name*=\"FirstName\"]",
            "last_name": "input[name*=\"LastName\"]",
            "email": "input[name*=\"Email\"]",
            "phone": "input[name*=\"Phone\"]",
            "resume_upload": "input[type=\"file\"]",
            "submit_btn": "#ContentPlaceHolder1_cmdApply"
        }
    }'::JSON
);

-- =====================================================
-- SEED DATA: LanceSoft (ID 2)
-- =====================================================
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required) VALUES (
    2, 'JobDiva', 'strategies.custom.LanceSoftStrategy', false
);

INSERT OR IGNORE INTO job_sites (id, ats_platform_id, company_name, domain, category, search_url_template, is_active) VALUES (
    2, 2, 'LanceSoft', 'lancesoft.com', 'Staffing vendor',
    'https://www2.jobdiva.com/portal/?a=3djdnw5yqdh8wl3frr5t6561tvvokq01affwpxt3lcutzo4f8yt1aeiy3msk02or&compid=0&SearchString=',
    true
);

INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json) VALUES (
    3, 2, 'listing',
    '{
        "country_button": "//button[contains(., \"United States\")]",
        "country_dropdown_btn": "//button[contains(., \"Country\")] | //button[contains(., \"Select Country\")]",
        "usa_option": "//a[@class=\"dropdown-item\"][contains(., \"United States\")]",
        "country_fallback": "div.hideshow-country button",
        "search_input": "input.inputbox_search, input[placeholder*=\"Search job title\" i]",
        "job_container": "div.list-group-item.list-group-item-action",
        "job_title": "span.text-capitalize.jd-nav-label.notranslate",
        "job_id": "div.d-flex.text-muted small:nth-child(3)",
        "details_button": "button.btn.jd-btn",
        "next_page_btn": "button[aria-label=\"Next Page\"]"
    }'::JSON
);

INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json) VALUES (
    4, 2, 'application',
    '{
         "apply_button": "#root > div > div > div:nth-child(4) > div:nth-child(1) > button",
         "quick_apply_option": "#applyOptionsModal > div > div > div.modal-body > div > button:nth-child(3) > span",
         "form_modal": "#quickApplyModal",
         "submit_btn": "#quickApplyModal > div > div > div.job-app-btns > div:nth-child(2) > button",
         "next_btn_outline": "button.btn.jd-btn-outline",
         "next_btn_solid": "button.btn.jd-btn:not(.jd-btn-outline)",
         "consent_checkbox": "//div[@id=\"quickApplyModal\"]//input[@type=\"checkbox\"]",
         "file_input": "div#quickApplyModal input[type=\"file\"]",
         "gender_radio": "//input[@type=\"radio\"][@name=\"gender\"][@value=\"1,3\"]",
         "ethnicity_radio": "//input[@type=\"radio\"][@name=\"ethnicity\"][@value=\"1,3\"]",
         "race_radio": "//input[@type=\"radio\"][@name=\"race\"][@value=\"2,8\"]",
         "veteran_radios": "//input[@type=\"radio\"][@name=\"veteran_status\"]"
    }'::JSON
);

-- =====================================================
-- SEED DATA: KForce (ID 3)
-- =====================================================
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
VALUES (3, 'KForce Custom', 'strategies.custom.kforce.KForceStrategy', false);

INSERT OR IGNORE INTO job_sites (id, company_name, domain, ats_platform_id, category, search_url_template, apply_url_template, is_active)
VALUES (
    3, 'KForce', 'kforce.com', 3, 'Staffing vendor',
    'https://www.kforce.com/find-work/search-jobs/',
    'https://www.kforce.com/Jobs/{job_id}/ApplyOnline/',
    true
);

INSERT OR REPLACE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    5, 3, 'listing',
    '{
        "search_input": "input[placeholder=\"Search by Job Title or Skill\"]",
        "search_button": "input.search-icon.submitIcon",
        "container": ".linkForJob",
        "search_keywords": ["Python", "JavaScript", "React", "Node.js", "AWS", "Docker", "Kubernetes", "CI/CD", "REST API", "PostgreSQL"],
        "fields": {
            "title": { "selector": ".linkForJob", "type": "text" },
            "url": { "selector": ".linkForJob", "attr": "href" }
        }
    }'::JSON
);

INSERT OR REPLACE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    6, 3, 'application',
    '{
        "flow_type": "kforce_guest",
        "apply_initiator": "#TK_WIDGET_INITIATOR",
        "apply_link_option": ".TK_WIDGET[rel=\"form\"] a",
        "form_fields": {
            "first_name": "#firstName",
            "last_name": "#lastName",
            "email": "#emailAddress",
            "email_verify": "#emailAddressVerify",
            "phone": "#phoneNumberAll",
            "zip_code": "#postalCode",
            "state": "#state",
            "resume_upload": "#uploadFileSystemResume",
            "eligibility_auth": "#eligibility0",
            "eligibility_employer": "#eligibility1",
            "eligibility_sponsorship": "#eligibility2",
            "next_btn": "//button[contains(text(), \"Next\") or @id=\"NextButton\" or contains(@class, \"next-button\")]",
            "submit_btn": "#SubmitButton"
        },
        "questionnaire_answers": {
            "eligibility_auth": "AuthorizedForAny",
            "eligibility_sponsorship": "No"
        },
        "success_indicators": [
            "Thank you", "Application Received", "Successfully Submitted", "received your application"
        ]
    }'::JSON
);

-- =====================================================
-- SEED DATA: Capgemini (ID 4)
-- =====================================================
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
VALUES (4, 'SAP SuccessFactors', 'strategies.custom.capgemini.CapgeminiStrategy', false);

INSERT OR IGNORE INTO job_sites (id, company_name, domain, ats_platform_id, category, search_url_template, apply_url_template, is_active)
VALUES (
    4, 'Capgemini', 'capgemini.com', 4, 'Consulting firm',
    'https://www.capgemini.com/us-en/careers/join-capgemini/job-search/?country_code=us-en&country_name=United%20States&size=15',
    'https://career5.successfactors.eu/careers?company=capgemitecP3',
    true
);

INSERT OR REPLACE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    7, 4, 'listing',
    '{
        "search_input": "#searchsubmit",
        "job_cards": "a.table-tr.filter-box.joblink",
        "load_more_button": "a.filters-more",
        "clear_filters": "button.remove-all-tags",
        "search_keywords": ["AI Architect", "Machine Learning", "Python Engineer", "GenAI Analyst"],
        "fields": {
            "title": { "selector": "div", "type": "text" },
            "url": { "selector": "a.table-tr", "attr": "href" }
        }
    }'::JSON
);

INSERT OR REPLACE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    8, 4, 'application',
    '{
        "flow_type": "successfactors_login",
        "apply_button_main": "a.cta-link",
        "sign_in_button": "//a[@onclick=\"openSignInModal()\"]",
        "login_email": "#username",
        "login_password": "#password",
        "login_submit": "#fbqa_signin",
        "form_fields": {
            "first_name": "#fbclc_fName",
            "last_name": "#fbclc_lName",
            "phone": "#tor__fcellPhone",
            "resume_upload": "input[type=\"file\"]",
            "work_authorization": "#13\\:_input",
            "visa_sponsorship": "#17\\:_input",
            "prior_agreement": "#21\\:_input",
            "ethnicity": "#25\\:_input",
            "veteran_status": "#29\\:_input",
            "disability_status": "#33\\:_input",
            "previous_employment": "#37\\:_input",
            "gender_consent": "#41\\:_input",
            "gender": "#45\\:_input",
            "sms_consent": "#57\\:_input",
            "submit_btn": "#fbqa_apply"
        },
        "questionnaire_answers": {
            "work_authorization": "Yes",
            "visa_sponsorship": "No",
            "prior_agreement": "No",
            "ethnicity": "South Asian (e.g. Indian)",
            "veteran_status": "Not a Protected Veteran",
            "disability_status": "No, I don’t have a disability",
            "previous_employment": "No",
            "gender_consent": "Yes",
            "gender": "Male",
            "sms_consent": "Yes"
        },
        "success_indicators": [
            "Thank you", "Application submitted", "Successfully applied", "received your application"
        ]
    }'::JSON
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_job_sites_active ON job_sites(is_active);
CREATE INDEX IF NOT EXISTS idx_job_listings_status ON job_listings(status);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(applied_at);
