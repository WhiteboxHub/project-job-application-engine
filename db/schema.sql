/*
  Job Application Engine - DuckDB Schema
  Single database for both configuration and history
  Version: 1.0 (KForce Only)
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

-- =====================================================
-- SEED DATA: KForce Configuration
-- =====================================================

-- Insert KForce Strategy
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
VALUES (1, 'KForce Custom', 'strategies.custom.kforce.KForceStrategy', false);

-- Insert KForce Job Site
INSERT OR IGNORE INTO job_sites (
    id,
    company_name,
    domain,
    ats_platform_id,
    category,
    search_url_template,
    apply_url_template,
    is_active
)
VALUES (
    1,
    'KForce',
    'kforce.com',
    1,
    'Staffing vendor',
    'https://www.kforce.com/find-work/search-jobs/',
    'https://www.kforce.com/Jobs/{job_id}/ApplyOnline/',
    true
);

-- Insert KForce Listing Selectors
INSERT OR REPLACE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    1,
    1,
    'listing',
    '{
        "search_input": "input[placeholder=\"Search by Job Title or Skill\"]",
        "search_button": "input.search-icon.submitIcon",
        "container": ".linkForJob",
        "fields": {
            "title": {
                "selector": ".linkForJob",
                "type": "text"
            },
            "url": {
                "selector": ".linkForJob",
                "attr": "href"
            }
        }
    }'::JSON
);

-- Insert KForce Application Selectors
INSERT OR REPLACE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    2,
    1,
    'application',
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
        "success_indicators": [
            "Thank you",
            "Application Received",
            "Successfully Submitted",
            "received your application"
        ]
    }'::JSON
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_job_sites_active ON job_sites(is_active);
CREATE INDEX IF NOT EXISTS idx_job_listings_status ON job_listings(status);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(applied_at);