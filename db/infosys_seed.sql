-- Add Infosys to ATS Platforms and Job Sites

-- 1. Insert Strategy
INSERT INTO `ats_platforms` 
(`name`, `class_handler`, `is_headless_required`) 
VALUES 
('Infosys Custom', 'strategies.custom.infosys.InfosysStrategy', 0)
ON DUPLICATE KEY UPDATE `name`=`name`;

-- 2. Insert Job Site
INSERT INTO `job_sites` 
(
    `company_name`, 
    `domain`, 
    `ats_platform_id`, 
    `category`, 
    `search_url_template`, 
    `apply_url_template`, 
    `cf_clearance_required`, 
    `proxy_region`
) 
VALUES 
(
    'Infosys', 
    'digitalcareers.infosys.com', 
    (SELECT id FROM ats_platforms WHERE name = 'Infosys Custom'), 
    'System integrator', 
    'https://digitalcareers.infosys.com/infosys/global-careers?location=USA', 
    NULL, 
    0, 
    'US'
)
ON DUPLICATE KEY UPDATE `company_name`=`company_name`;

-- 3. Insert Selectors
INSERT INTO `site_selectors` (`job_site_id`, `type`, `config_json`)
VALUES 
(
    (SELECT id FROM job_sites WHERE domain = 'digitalcareers.infosys.com'),
    'listing', 
    '{
        "container": ".job-listing-item", 
        "fields": {},
        "keyword": "AI Engineer",
        "location": "USA"
    }'
)
ON DUPLICATE KEY UPDATE `config_json`=`config_json`;
