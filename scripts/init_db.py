"""
Initialize DuckDB — applies schema and seeds all site data.
Run this once before using main.py or scheduler_worker.py.

Usage:
    python scripts/init_db.py
"""

import os
import sys

import duckdb

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.logger import logger


def init_db():
    db_path = settings.DUCKDB_PATH

    if db_path.startswith("md:"):
        logger.info(f"Initializing MotherDuck Cloud at: {db_path}")
        token_suffix = (
            f"?motherduck_token={settings.MOTHERDUCK_TOKEN}"
            if settings.MOTHERDUCK_TOKEN
            else ""
        )
        conn = duckdb.connect(f"{db_path}{token_suffix}")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        logger.info(f"Initializing DuckDB at: {db_path}")
        conn = duckdb.connect(db_path)

    # -----------------------------------------------------------------------
    # Core schema tables
    # -----------------------------------------------------------------------
    logger.info("Creating tables...")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ats_platforms (
            id                   INTEGER PRIMARY KEY,
            name                 VARCHAR(50) NOT NULL,
            class_handler        VARCHAR(100) NOT NULL,
            automation_level     VARCHAR(20) DEFAULT 'manual',
            is_headless_required BOOLEAN DEFAULT TRUE,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Idempotent — add automation_level if not present on older DBs
    try:
        conn.execute(
            "ALTER TABLE ats_platforms ADD COLUMN automation_level VARCHAR(20) DEFAULT 'manual'"
        )
        logger.info("Added automation_level column to ats_platforms")
    except Exception:
        pass  # Column already exists

    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_sites (
            id                       INTEGER PRIMARY KEY,
            company_name             VARCHAR(100) NOT NULL,
            domain                   VARCHAR(255) UNIQUE NOT NULL,
            ats_platform_id          INTEGER,
            category                 VARCHAR(50) NOT NULL,
            search_url_template      TEXT NOT NULL,
            apply_url_template       TEXT,
            cf_clearance_required    BOOLEAN DEFAULT FALSE,
            proxy_region             VARCHAR(10) DEFAULT 'US',
            is_active                BOOLEAN DEFAULT TRUE,
            max_applications_per_run INTEGER DEFAULT 10,
            created_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_selectors (
            id              INTEGER PRIMARY KEY,
            ats_platform_id INTEGER,
            job_site_id     INTEGER,
            type            VARCHAR(20) NOT NULL,
            config_json     JSON NOT NULL,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS job_listings_id_seq
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_listings (
            id              INTEGER PRIMARY KEY DEFAULT nextval('job_listings_id_seq'),
            job_site_id     INTEGER NOT NULL,
            external_job_id VARCHAR(100) NOT NULL,
            job_title       VARCHAR(255),
            job_url         TEXT NOT NULL,
            location        VARCHAR(255),
            job_type        VARCHAR(100),
            salary          VARCHAR(100),
            description     TEXT,
            requirements    TEXT,
            posted_date     VARCHAR(50),
            company         VARCHAR(100),
            industry        VARCHAR(100),
            status          VARCHAR(20) DEFAULT 'discovered',
            attempts        INTEGER DEFAULT 0,
            last_error      TEXT,
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (job_site_id, external_job_id)
        )
    """)

    # Idempotent column additions for existing DBs without the new columns
    for col_def in [
        "location VARCHAR(255)",
        "job_type VARCHAR(100)",
        "salary VARCHAR(100)",
        "description TEXT",
        "requirements TEXT",
        "posted_date VARCHAR(50)",
        "company VARCHAR(100)",
        "industry VARCHAR(100)",
    ]:
        col_name = col_def.split()[0]
        try:
            conn.execute(f"ALTER TABLE job_listings ADD COLUMN {col_def}")
            logger.info(f"Added column '{col_name}' to job_listings")
        except Exception:
            pass  # Column already exists

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS applications_id_seq
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id             INTEGER PRIMARY KEY DEFAULT nextval('applications_id_seq'),
            job_site_id    INTEGER NOT NULL,
            job_listing_id INTEGER,
            job_title      VARCHAR(255),
            job_url        TEXT,
            status         VARCHAR(20) NOT NULL,
            error_message  TEXT,
            applied_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id                              BIGINT PRIMARY KEY,
            run_date                        DATE NOT NULL,
            job_site_id                     INTEGER,
            total_jobs_found                INTEGER DEFAULT 0,
            total_applications_attempted    INTEGER DEFAULT 0,
            total_applications_successful   INTEGER DEFAULT 0,
            total_applications_failed       INTEGER DEFAULT 0,
            avg_application_time_seconds    FLOAT,
            created_at                      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS submitted_jobs (
            job_id     VARCHAR PRIMARY KEY,
            job_title  VARCHAR,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applied_jobs (
            job_id     VARCHAR NOT NULL,
            site       VARCHAR NOT NULL,
            job_title  VARCHAR,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (job_id, site)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_runs (
            id            INTEGER PRIMARY KEY,
            run_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            site          VARCHAR,
            jobs_found    INTEGER DEFAULT 0,
            jobs_applied  INTEGER DEFAULT 0,
            status        VARCHAR DEFAULT 'completed',
            error_message VARCHAR
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS scheduler_runs_seq START 1
    """)

    logger.info("Tables created [OK]")

    # -----------------------------------------------------------------------
    # Seed: ats_platforms
    #
    # Naming convention:
    #   Real shared ATS platform  → platform name as-is  (e.g. jobdiva, lever)
    #   Company-custom portal     → {company}_custom      (e.g. wipro_custom)
    # -----------------------------------------------------------------------
    platform_seeds = [
        # id  name                    class_handler                                   level      headless
        (
            1,
            "insight_global_custom",
            "strategies.custom.InsightGlobalStrategy",
            "manual",
            False,
        ),
        (2, "jobdiva", "strategies.custom.LanceSoftStrategy", "full", False),
        (3, "wipro_custom", "strategies.custom.WiproStrategy", "full", False),
        (4, "infosys_custom", "strategies.custom.InfosysStrategy", "full", False),
        (5, "kforce_custom", "strategies.custom.KForceStrategy", "full", False),
        (6, "lever", "strategies.custom.LeverStrategy", "full", False),
        (7, "capgemini_custom", "strategies.custom.CapgeminiStrategy", "full", False),
    ]
    for pid, name, handler, level, headless in platform_seeds:
        conn.execute(
            """
            INSERT OR IGNORE INTO ats_platforms (id, name, class_handler, automation_level, is_headless_required)
            VALUES (?, ?, ?, ?, ?)
        """,
            [pid, name, handler, level, headless],
        )
        # Also UPDATE so re-runs fix stale values (name, class, level) on existing rows
        conn.execute(
            """
            UPDATE ats_platforms
               SET name                 = ?,
                   class_handler        = ?,
                   automation_level     = ?,
                   is_headless_required = ?
             WHERE id = ?
        """,
            [name, handler, level, headless, pid],
        )

    logger.info("ats_platforms seeded [OK]")

    # -----------------------------------------------------------------------
    # Seed: job_sites
    # -----------------------------------------------------------------------
    # 1. Insight Global  (manual — only run with --site)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, apply_url_template, is_active)
        VALUES (
            1, 'Insight Global', 'insightglobal.com', 1, 'Staffing vendor',
            'https://insightglobal.com/jobs/',
            'https://jobs.insightglobal.com/users/jobapplynoaccount.aspx?jobid={job_id}',
            false
        )
    """)

    # 2. LanceSoft  (uses JobDiva ATS)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            2, 'LanceSoft', 'lancesoft.com', 2, 'Staffing vendor',
            'https://www2.jobdiva.com/portal/?a=3djdnw5yqdh8wl3frr5t6561tvvokq01affwpxt3lcutzo4f8yt1aeiy3msk02or&compid=0&SearchString=',
            true
        )
    """)

    # 3. Wipro  (company-custom portal)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            3, 'Wipro', 'wipro.com', 3, 'System integrator',
            'https://careers.wipro.com/',
            false
        )
    """)

    # 4. Infosys  (company-custom portal)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            4, 'Infosys', 'infosys.com', 4, 'System integrator',
            'https://career.infosys.com/joblist',
            false
        )
    """)

    # 5. KForce  (company-custom portal, inactive until strategy is ready)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            5, 'KForce', 'kforce.com', 5, 'Staffing vendor',
            'https://www.kforce.com/jobs/',
            true
        )
    """)

    # 6. Capgemini  (company-custom portal, inactive until strategy is ready)
    conn.execute("""
        INSERT OR IGNORE INTO job_sites
            (id, company_name, domain, ats_platform_id, category, search_url_template, is_active)
        VALUES (
            6, 'Capgemini', 'capgemini.com', 7, 'System integrator',
            'https://www.capgemini.com/careers/',
            false
        )
    """)

    # -----------------------------------------------------------------------
    # Seed: site_selectors for LanceSoft (job_site_id = 2)
    #
    # type='listing'     → selectors used during job search/discovery
    # type='application' → selectors used during form filling / submission
    # -----------------------------------------------------------------------
    import json as _json

    lancesoft_listing_selectors = {
        "search_keywords": ["AI Engineer", "Machine Learning Engineer", "Data Scientist"],
        "country_button": "//button[contains(., 'United States')]",
        "country_dropdown_btn": "//button[contains(., 'Country')] | //button[contains(., 'Select Country')]",
        "usa_option": "//a[@class='dropdown-item'][contains(., 'United States')]",
        "country_fallback": "div.hideshow-country button",
        "search_input": "input.inputbox_search, input[placeholder*='Search job title' i]",
        "job_container": "div.list-group-item.list-group-item-action",
        "job_title": "span.text-capitalize.jd-nav-label.notranslate",
        "job_id": "div.d-flex.text-muted small:nth-child(3)",
        "details_button": "button.btn.jd-btn",
        "next_page_btn": "button[aria-label='Next Page']",
        "dropdown_country_selectors": [
            "//button[contains(., 'Country')]",
            "//button[contains(., 'Select Country')]",
            "//button[contains(@class, 'country')]",
            "div.hideshow-country button",
            "button[data-toggle='dropdown'][aria-label*='Country']",
        ],
        "usa_dropdown_selectors": [
            "//a[@class='dropdown-item'][contains(., 'United States')]",
            "//div[contains(@class, 'dropdown-menu')]//a[contains(text(), 'United States')]",
            "//li[contains(., 'United States')]//a",
            "//button[contains(., 'United States')]",
            "a.dropdown-item:contains('United States')",
        ],
    }

    lancesoft_application_selectors = {
        "apply_button": "#root > div > div > div:nth-child(4) > div:nth-child(1) > button",
        "quick_apply_option": "#applyOptionsModal > div > div > div.modal-body > div > button:nth-child(3) > span",
        "form_modal": "#quickApplyModal",
        "submit_btn": "#quickApplyModal > div > div > div.job-app-btns > div:nth-child(2) > button",
        "submit_btn_fallback": [
            "#quickApplyModal .job-app-btns button:last-child",
            "#quickApplyModal .job-app-btns button:nth-child(2)",
        ],
        "next_btn_outline": "button.btn.jd-btn-outline",
        "next_btn_solid": "button.btn.jd-btn:not(.jd-btn-outline)",
        "consent_checkbox": "//div[@id='quickApplyModal']//input[@type='checkbox']",
        "file_input": "div#quickApplyModal input[type='file']",
        "gender_radio": "//input[@type='radio'][@name='gender'][@value='1,3']",
        "ethnicity_radio": "//input[@type='radio'][@name='ethnicity'][@value='1,3']",
        "race_radio": "//input[@type='radio'][@name='race'][@value='2,8']",
        "veteran_radios": "//input[@type='radio'][@name='veteran_status']",
        "next_btn_xpath": "//button[contains(@class, 'jd-btn') and not(contains(@class, 'jd-btn-outline'))]//span[contains(., 'Next')]/ancestor::button",
        "phone_xpath": "//label[contains(text(), 'Phone')]/..//input",
    }

    conn.execute(
        """
        INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
        VALUES (9, 2, 'listing', ?)
    """,
        [_json.dumps(lancesoft_listing_selectors)],
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
        VALUES (10, 2, 'application', ?)
    """,
        [_json.dumps(lancesoft_application_selectors)],
    )

    # Idempotent UPDATE in case rows already existed with stale values
    conn.execute(
        "UPDATE site_selectors SET config_json = ? WHERE id = 9",
        [_json.dumps(lancesoft_listing_selectors)],
    )
    conn.execute(
        "UPDATE site_selectors SET config_json = ? WHERE id = 10",
        [_json.dumps(lancesoft_application_selectors)],
    )

    logger.info("site_selectors seeded for LanceSoft [OK]")

    # -----------------------------------------------------------------------
    # Seed: site_selectors for KForce (job_site_id = 5)
    # -----------------------------------------------------------------------
    kforce_listing_selectors = {
        "search_keywords": ["AI Engineer", "Machine Learning", "Data Scientist"],
        "search_input": "//*[@id='site-content']/div/section/div[2]/div/div/div[2]/form/div/div[1]/div/input",
        "location_input": "//*[@id='react-select-2--value']/div[2]",
        "search_button": "//*[@id='site-content']/div/section/div[2]/div/div/div[2]/form/div/div[3]/div/input",
        "pagination_count": "//*[@id='site-content']/div/main/div/div/div/div[2]/div[1]/p[2]/span",
        "pagination_next": "button[aria-label='Next'], .pagination-next > a, //a[contains(@class,'next')]",
        "job_link": "//*[@id='site-content']/div/main/div/div/div/div[2]/ul/li[1]/h2/a",
    }

    kforce_application_selectors = {
        "apply_initiator": "//*[@id='TK_WIDGET_INITIATOR']",
        "apply_link_option": "//*[@id='ApplyWithForm']/div[4]/a",
        "success_indicators": [
            "successfully submitted",
            "thank you for applying",
            "application received",
        ],
        "questionnaire_answers": {
            "eligibility_auth": "AuthorizedForAny",
            "sponsorship_req": "No",
        },
        "form_fields": {
            "first_name": "//*[@id='firstName']",
            "last_name": "//*[@id='lastName']",
            "email": "//*[@id='emailAddress']",
            "email_verify": "//*[@id='emailAddressVerify']",
            "phone": "//*[@id='phoneNumberAll']",
            "zip_code": "//*[@id='postalCode']",
            "state": "//*[@id='state']",
            "country": "//*[@id='countryID']",
            "resume_upload": "//*[@id='uploadFileSystemResume']",
            "eligibility_auth": "//*[@id='eligibility']/ul/li[1]/label/span",
            "submit_btn": "//*[@id='SubmitButton']",
        },
    }

    conn.execute(
        """
        INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
        VALUES (11, 5, 'listing', ?)
    """,
        [_json.dumps(kforce_listing_selectors)],
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json)
        VALUES (12, 5, 'application', ?)
    """,
        [_json.dumps(kforce_application_selectors)],
    )

    conn.execute(
        "UPDATE site_selectors SET config_json = ? WHERE id = 11",
        [_json.dumps(kforce_listing_selectors)],
    )
    conn.execute(
        "UPDATE site_selectors SET config_json = ? WHERE id = 12",
        [_json.dumps(kforce_application_selectors)],
    )

    logger.info("site_selectors seeded for KForce [OK]")

    # -----------------------------------------------------------------------
    # Cleanup: Remove stale rows that db/schema.sql may have inserted.
    # schema.sql used IDs 1-4 for Insight Global and LanceSoft selectors,
    # but init_db.py uses IDs 9-16. Having both causes duplicate/conflicting
    # selector configs for the same job_site_id.
    # -----------------------------------------------------------------------
    for stale_id in [1, 2, 3, 4]:
        conn.execute("DELETE FROM site_selectors WHERE id = ?", [stale_id])
    logger.info("Stale schema.sql selector rows (IDs 1-4) removed [OK]")

    # -----------------------------------------------------------------------
    # Seed: site_selectors for Wipro (job_site_id = 3)
    # Wipro uses SAP SuccessFactors career portal at https://careers.wipro.com/
    # Key names MUST match what wipro.py reads via self.selectors_config.get("key")
    # -----------------------------------------------------------------------
    wipro_listing_selectors = {
        "search_keywords": ["AI Engineer", "Machine Learning Engineer", "Data Scientist"],
        "cookie_accept_button": "button#onetrust-accept-btn-handler, button.accept-cookies",
        "expand_search_button": "//button[contains(@class,'searchOptions') or contains(text(),'More options')]",
        "keyword_input": "//input[@placeholder='Keyword or Job ID' or @id[contains(.,'keyword')]]",
        "location_input": "//input[@placeholder='Location' or @id[contains(.,'location')]]",
        "search_button": "//button[contains(@class,'searchButton') or @data-automation-id='search-button' or contains(text(),'Search')]",
        "next_page": "//a[@data-automation-id='pagination-next-link' and not(contains(@class,'disabled'))] | //a[contains(@title,'Next')][not(contains(@class,'disabled'))]",
    }

    wipro_application_selectors = {
        "apply_button_dropdown": "//button[@id='applyNowDropdown'] | //button[contains(@class,'apply-dropdown') or contains(text(),'Apply')]",
        "apply_button_menu_item": "//a[@data-automation='btn-Apply-Now'] | //a[contains(text(),'Apply Now')]",
        "login_email_input": "//input[@id='username' or @name='username' or @type='email']",
        "login_password_input": "//input[@id='password' or @name='password' or @type='password']",
        "login_submit_button": "//button[@type='submit' or contains(text(),'Sign In') or contains(text(),'Log In')]",
        "first_name_input": "//input[@id[contains(.,'firstName')] or @data-automation-id='formField-firstName']",
        "last_name_input": "//input[@id[contains(.,'lastName')] or @data-automation-id='formField-lastName']",
        "email_input": "//input[@id[contains(.,'email')] or @data-automation-id='formField-email']",
        "phone_input": "//input[@id[contains(.,'phoneNumber')] or @data-automation-id='formField-phone']",
        "preferred_name_input": "//input[@id[contains(.,'preferredName')] or @data-automation-id='formField-preferredName']",
        "social_account_url_input": "//input[@id[contains(.,'socialAccount')] or @id[contains(.,'linkedin')]]",
        "country_code_select": "//select[@id[contains(.,'countryCode')] or @data-automation-id='formField-countryCode']",
        "gender_select": "//select[@id[contains(.,'gender')] or @data-automation-id='formField-gender']",
        "disability_assistance_select": "//select[@id[contains(.,'disability')] or @data-automation-id='formField-disabilityAssistance']",
        "disability_assistance_explain_input": "//input[@id[contains(.,'disabilityExplain')] or @data-automation-id='formField-disabilityExplain']",
        "address_input": "//input[@id[contains(.,'address')] or @data-automation-id='formField-address']",
        "city_input": "//input[@id[contains(.,'city')] or @data-automation-id='formField-city']",
        "zip_input": "//input[@id[contains(.,'postalCode')] or @id[contains(.,'zipCode')]]",
        "country_select": "//select[@id[contains(.,'country')] and not(@id[contains(.,'countryCode')])] | //select[@data-automation-id='formField-country']",
        "state_select": "//select[@id[contains(.,'state')] or @data-automation-id='formField-state']",
        "employee_id_input": "//input[@id[contains(.,'employeeId')] or @data-automation-id='formField-employeeId']",
        "employed_before_select": "//select[@id[contains(.,'employedBefore')] or @data-automation-id='formField-employedBefore']",
        "experience_section_trigger": "//div[contains(@class,'rcmFormSectionTopBar')][.//*[contains(text(),'Professional Experience')]]",
        "job_title_input": "//input[@id[contains(.,'jobTitle')] or @data-automation-id='formField-jobTitle']",
        "company_input": "//input[@id[contains(.,'company')] or @data-automation-id='formField-company']",
        "start_date_input": "//ui5-date-picker-xweb-calendar-widget[@title='Start Date'][not(ancestor::*[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]])]",
        "end_date_input": "//ui5-date-picker-xweb-calendar-widget[@title='End Date'][not(ancestor::*[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]])]",
        "exp_country_select": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//select[@id[contains(.,'country')]]",
        "exp_state_select": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//select[@id[contains(.,'state')]]",
        "exp_city_input": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Professional Experience')]]//input[@id[contains(.,'city')]]",
        "education_section_trigger": "//div[contains(@class,'rcmFormSectionTopBar')][.//*[contains(text(),'Education')]]",
        "edu_type_select": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//select[@id[contains(.,'eduType')] or @id[contains(.,'educationType')]]",
        "edu_degree_select": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//select[@id[contains(.,'degree')]]",
        "edu_school_input": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//input[@id[contains(.,'school')] or @id[contains(.,'university')]]",
        "edu_major_select": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//select[@id[contains(.,'major')]]",
        "edu_start_date": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='Start Date']",
        "edu_end_date": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='End Date']",
        "edu_grad_date": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//ui5-date-picker-xweb-calendar-widget[@title='Year Of Passing']",
        "edu_country_select": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//select[@id[contains(.,'country')]]",
        "edu_state_select": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//select[@id[contains(.,'state')]]",
        "edu_city_input": "//div[contains(@class,'rcmFormSection')][.//*[contains(text(),'Education')]]//input[@id[contains(.,'city')]]",
        "auth_country_select": "//select[@id[contains(.,'authCountry')] or @data-automation-id='formField-authorizationCountry']",
        "auth_work_country_select": "//select[@id[contains(.,'authWorkCountry')] or @data-automation-id='formField-authWorkCountry']",
        "visa_status_select": "//select[@id[contains(.,'visaStatus')] or @data-automation-id='formField-visaStatus']",
        "sponsorship_future_select": "//select[@id[contains(.,'sponsorship')] or @data-automation-id='formField-sponsorshipFuture']",
        "citizenship_select": "//select[@id[contains(.,'citizenship')] or @data-automation-id='formField-citizenship']",
        "govt_employed_select": "//select[@id[contains(.,'govtEmployed')] or @data-automation-id='formField-govtEmployed']",
        "race_select": "//select[@id[contains(.,'race')] or @data-automation-id='formField-race']",
        "veteran_select": "//select[@id[contains(.,'veteran')] or @data-automation-id='formField-veteran']",
        "disability_select": "//select[@id[contains(.,'disability')] and not(@id[contains(.,'Assistance')])]",
        "terms_checkbox": "//input[@type='checkbox'][@id[contains(.,'terms')] or @id[contains(.,'consent')]]",
    }

    conn.execute(
        "INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json) VALUES (15, 3, 'listing', ?)",
        [_json.dumps(wipro_listing_selectors)],
    )
    conn.execute(
        "INSERT OR IGNORE INTO site_selectors (id, job_site_id, type, config_json) VALUES (16, 3, 'application', ?)",
        [_json.dumps(wipro_application_selectors)],
    )
    conn.execute(
        "UPDATE site_selectors SET config_json = ? WHERE id = 15",
        [_json.dumps(wipro_listing_selectors)],
    )
    conn.execute(
        "UPDATE site_selectors SET config_json = ? WHERE id = 16",
        [_json.dumps(wipro_application_selectors)],
    )
    logger.info("site_selectors seeded for Wipro [OK]")

    # Indexes
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_job_sites_active ON job_sites(is_active)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_applications_date ON applications(applied_at)"
    )

    logger.info("")
    logger.info("=" * 50)
    logger.info("DuckDB initialization complete!")
    logger.info("=" * 50)

    # Summary
    sites = conn.execute(
        "SELECT js.company_name, ap.name, ap.automation_level, js.is_active "
        "FROM job_sites js "
        "JOIN ats_platforms ap ON js.ats_platform_id = ap.id "
        "ORDER BY js.id"
    ).fetchall()
    for company, platform, level, active in sites:
        icon = "✅" if level == "full" else "🔧"
        active_str = "" if active else " [INACTIVE]"
        logger.info(f"  {icon}  {company} → [{platform}] ({level}){active_str}")

    conn.close()
    logger.info("\nRun 'python scripts/main.py --site LanceSoft' to start.")


if __name__ == "__main__":
    init_db()
