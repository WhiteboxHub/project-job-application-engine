/*
  Job Application Engine - DuckDB Schema
  Single database for both configuration and history
  Version: 1.0
*/

-- =====================================================
-- CONFIGURATION TABLES
-- =====================================================

-- 1. ATS Platforms (Strategy Definitions)
CREATE TABLE IF NOT EXISTS ats_platforms (
    id INTEGER PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    class_handler VARCHAR(100) NOT NULL,  -- e.g., 'strategies.custom.InsightGlobalStrategy'
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
    search_url_template TEXT NOT NULL,  -- URL with {keyword}, {location} placeholders
    apply_url_template TEXT,            -- URL with {job_id} placeholder
    
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
    ats_platform_id INTEGER,  -- Default selectors for generic ATS
    job_site_id INTEGER,      -- Specific override for a single site
    
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

-- =====================================================
-- HISTORY TABLES
-- =====================================================

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
-- SEED DATA: Insight Global Configuration
-- =====================================================

-- Insert Strategy
INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, is_headless_required)
VALUES (1, 'Insight Global Custom', 'strategies.custom.InsightGlobalStrategy', false);

-- Insert Site
INSERT OR IGNORE INTO job_sites (
    id,
    company_name,
    domain,
    ats_platform_id,
    category,
    search_url_template,
    apply_url_template,
    cf_clearance_required,
    is_active
)
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

-- Insert Listing Selectors
INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    1,
    1,
    'listing',
    '{
        "container": "div.result",
        "pagination_type": "click_next",
        "pagination_selector": "a[title=\"Page Forward\"]",
        "fields": {
            "job_id": {
                "selector": "button[id=\"btnSaveJob\"]",
                "attr": "jobId"
            },
            "title": {
                "selector": ".job-title a",
                "type": "text"
            },
            "url": {
                "selector": ".job-title a",
                "attr": "href"
            }
        }
    }'::JSON
);

-- Insert Application Selectors
INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
VALUES (
    2,
    1,
    'application',
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

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_job_sites_active ON job_sites(is_active);
CREATE INDEX IF NOT EXISTS idx_job_listings_status ON job_listings(status);
CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(applied_at);
