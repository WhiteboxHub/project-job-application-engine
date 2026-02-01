-- Add TekSystems to ATS Platforms and Job Sites

-- 1. Insert Strategy
INSERT INTO `ats_platforms` 
(`name`, `class_handler`, `is_headless_required`) 
VALUES 
('TekSystems Custom', 'strategies.custom.TekSystemsStrategy', 1);

-- 2. Insert Job Site
-- Note: Using dynamic ID retrieval for safety
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
    'TekSystems', 
    'careers.teksystems.com', 
    (SELECT id FROM ats_platforms WHERE name = 'TekSystems Custom'), 
    'Staffing vendor', 
    'https://careers.teksystems.com/us/en/search-results?keywords={keyword}', 
    NULL, 
    0, 
    'US'
);

-- 3. Insert Selectors
INSERT INTO `site_selectors` (`job_site_id`, `type`, `config_json`)
VALUES 
(
    (SELECT id FROM job_sites WHERE domain = 'careers.teksystems.com'),
    'listing', 
    '{
        "container": "div.job-result", 
        "fields": {
            "title": {"selector": "h2", "type": "text"},
            "url": {"selector": "a", "attr": "href"}
        }
    }'
);
