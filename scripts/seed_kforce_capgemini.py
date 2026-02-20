"""
Seed KForce and Capgemini into MySQL database.
Run from project root:
    python scripts/seed_kforce_capgemini.py
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db
from sqlalchemy import text
from core.logger import logger

session = db.get_session()

try:
    # ─────────────────────────────────────────
    # What's already in the DB?
    # ─────────────────────────────────────────
    existing_sites = {r[1]: r[0] for r in session.execute(
        text("SELECT id, company_name FROM job_sites")).fetchall()}
    existing_platforms = {r[1]: r[0] for r in session.execute(
        text("SELECT id, name FROM ats_platforms")).fetchall()}
    existing_selectors = {(r[1], r[2]): r[0] for r in session.execute(
        text("SELECT id, job_site_id, type FROM site_selectors")).fetchall()}

    logger.info(f"Existing sites: {existing_sites}")
    logger.info(f"Existing platforms: {existing_platforms}")

    # Compute next IDs
    max_platform_id = max(existing_platforms.values()) if existing_platforms else 0
    max_site_id = max(existing_sites.values()) if existing_sites else 0
    max_sel_id = max(r[0] for r in session.execute(
        text("SELECT id FROM site_selectors")).fetchall()) if existing_selectors else 0

    # ─────────────────────────────────────────
    # KForce
    # ─────────────────────────────────────────
    if 'KForce Custom' not in existing_platforms:
        kforce_plat_id = max_platform_id + 1
        session.execute(text("""
            INSERT INTO ats_platforms (id, name, class_handler, is_headless_required)
            VALUES (:id, 'KForce Custom', 'strategies.custom.kforce.KForceStrategy', 0)
        """), {"id": kforce_plat_id})
        max_platform_id = kforce_plat_id
        logger.info(f"✅ Inserted ats_platform 'KForce Custom' (id={kforce_plat_id})")
    else:
        kforce_plat_id = existing_platforms['KForce Custom']
        logger.info(f"ℹ️ KForce Custom platform already exists (id={kforce_plat_id})")

    if 'KForce' not in existing_sites:
        kforce_site_id = max_site_id + 1
        session.execute(text("""
            INSERT INTO job_sites
                (id, company_name, domain, ats_platform_id, category,
                 search_url_template, apply_url_template, is_active)
            VALUES (
                :id, 'KForce', 'kforce.com', :plat_id, 'Staffing vendor',
                'https://www.kforce.com/find-work/search-jobs/',
                'https://www.kforce.com/Jobs/{job_id}/ApplyOnline/',
                1
            )
        """), {"id": kforce_site_id, "plat_id": kforce_plat_id})
        max_site_id = kforce_site_id
        logger.info(f"✅ Inserted job_site 'KForce' (id={kforce_site_id})")
    else:
        kforce_site_id = existing_sites['KForce']
        logger.info(f"ℹ️ KForce site already exists (id={kforce_site_id})")

    # KForce listing selector
    if (kforce_site_id, 'listing') not in existing_selectors:
        sel_id = max_sel_id + 1
        listing_json = json.dumps({
            "search_input": "input[placeholder=\"Search by Job Title or Skill\"]",
            "search_button": "input.search-icon.submitIcon",
            "container": ".linkForJob",
            "search_keywords": ["Python", "JavaScript", "React", "Node.js", "AWS",
                                "Docker", "Kubernetes", "CI/CD", "REST API", "PostgreSQL"],
            "fields": {
                "title": {"selector": ".linkForJob", "type": "text"},
                "url":   {"selector": ".linkForJob", "attr": "href"}
            }
        })
        session.execute(text("""
            INSERT INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (:id, :site_id, 'listing', :cfg)
        """), {"id": sel_id, "site_id": kforce_site_id, "cfg": listing_json})
        max_sel_id = sel_id
        logger.info(f"✅ Inserted KForce listing selector (id={sel_id})")

    # KForce application selector
    if (kforce_site_id, 'application') not in existing_selectors:
        sel_id = max_sel_id + 1
        app_json = json.dumps({
            "flow_type": "kforce_guest",
            "apply_initiator": "#TK_WIDGET_INITIATOR",
            "apply_link_option": ".TK_WIDGET[rel=\"form\"] a",
            "form_fields": {
                "first_name":             "#firstName",
                "last_name":              "#lastName",
                "email":                  "#emailAddress",
                "email_verify":           "#emailAddressVerify",
                "phone":                  "#phoneNumberAll",
                "zip_code":               "#postalCode",
                "state":                  "#state",
                "resume_upload":          "#uploadFileSystemResume",
                "eligibility_auth":       "#eligibility0",
                "eligibility_employer":   "#eligibility1",
                "eligibility_sponsorship":"#eligibility2",
                "next_btn": "//button[contains(text(), \"Next\") or @id=\"NextButton\"]",
                "submit_btn": "#SubmitButton"
            },
            "questionnaire_answers": {
                "eligibility_auth":        "AuthorizedForAny",
                "eligibility_sponsorship": "No"
            },
            "success_indicators": [
                "Thank you", "Application Received",
                "Successfully Submitted", "received your application"
            ]
        })
        session.execute(text("""
            INSERT INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (:id, :site_id, 'application', :cfg)
        """), {"id": sel_id, "site_id": kforce_site_id, "cfg": app_json})
        max_sel_id = sel_id
        logger.info(f"✅ Inserted KForce application selector (id={sel_id})")

    # ─────────────────────────────────────────
    # Capgemini
    # ─────────────────────────────────────────
    if 'SAP SuccessFactors' not in existing_platforms:
        cap_plat_id = max_platform_id + 1
        session.execute(text("""
            INSERT INTO ats_platforms (id, name, class_handler, is_headless_required)
            VALUES (:id, 'SAP SuccessFactors', 'strategies.custom.capgemini.CapgeminiStrategy', 0)
        """), {"id": cap_plat_id})
        max_platform_id = cap_plat_id
        logger.info(f"✅ Inserted ats_platform 'SAP SuccessFactors' (id={cap_plat_id})")
    else:
        cap_plat_id = existing_platforms['SAP SuccessFactors']
        logger.info(f"ℹ️ SAP SuccessFactors platform already exists (id={cap_plat_id})")

    if 'Capgemini' not in existing_sites:
        cap_site_id = max_site_id + 1
        session.execute(text("""
            INSERT INTO job_sites
                (id, company_name, domain, ats_platform_id, category,
                 search_url_template, apply_url_template, is_active)
            VALUES (
                :id, 'Capgemini', 'capgemini.com', :plat_id, 'Consulting firm',
                'https://www.capgemini.com/us-en/careers/join-capgemini/job-search/?country_code=us-en&country_name=United%20States&size=15',
                'https://career5.successfactors.eu/careers?company=capgemitecP3',
                1
            )
        """), {"id": cap_site_id, "plat_id": cap_plat_id})
        max_site_id = cap_site_id
        logger.info(f"✅ Inserted job_site 'Capgemini' (id={cap_site_id})")
    else:
        cap_site_id = existing_sites['Capgemini']
        logger.info(f"ℹ️ Capgemini site already exists (id={cap_site_id})")

    # Capgemini listing selector
    if (cap_site_id, 'listing') not in existing_selectors:
        sel_id = max_sel_id + 1
        listing_json = json.dumps({
            "search_input": "#searchsubmit",
            "job_cards": "a.table-tr.filter-box.joblink",
            "load_more_button": "a.filters-more",
            "search_keywords": ["AI Architect", "Machine Learning",
                                "Python Engineer", "GenAI Analyst"],
            "fields": {
                "title": {"selector": "div", "type": "text"},
                "url":   {"selector": "a.table-tr", "attr": "href"}
            }
        })
        session.execute(text("""
            INSERT INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (:id, :site_id, 'listing', :cfg)
        """), {"id": sel_id, "site_id": cap_site_id, "cfg": listing_json})
        max_sel_id = sel_id
        logger.info(f"✅ Inserted Capgemini listing selector (id={sel_id})")

    # Capgemini application selector
    if (cap_site_id, 'application') not in existing_selectors:
        sel_id = max_sel_id + 1
        app_json = json.dumps({
            "flow_type": "successfactors_login",
            "apply_button_main": "a.cta-link",
            "sign_in_button": "//a[@onclick=\"openSignInModal()\"]",
            "login_email": "#username",
            "login_password": "#password",
            "login_submit": "#fbqa_signin",
            "form_fields": {
                "first_name":   "#fbclc_fName",
                "last_name":    "#fbclc_lName",
                "phone":        "#tor__fcellPhone",
                "resume_upload":"input[type=\"file\"]",
                "submit_btn":   "#fbqa_apply"
            },
            "questionnaire_answers": {
                "work_authorization":  "Yes",
                "visa_sponsorship":    "No",
                "prior_agreement":     "No",
                "ethnicity":           "South Asian (e.g. Indian)",
                "veteran_status":      "Not a Protected Veteran",
                "disability_status":   "No, I don't have a disability",
                "previous_employment": "No",
                "gender_consent":      "Yes",
                "gender":              "Male",
                "sms_consent":         "Yes"
            },
            "success_indicators": [
                "Thank you", "Application submitted",
                "Successfully applied", "received your application"
            ]
        })
        session.execute(text("""
            INSERT INTO site_selectors (id, job_site_id, type, config_json)
            VALUES (:id, :site_id, 'application', :cfg)
        """), {"id": sel_id, "site_id": cap_site_id, "cfg": app_json})
        max_sel_id = sel_id
        logger.info(f"✅ Inserted Capgemini application selector (id={sel_id})")

    session.commit()
    logger.info("✅ All changes committed!")

    # ─────────────────────────────────────────
    # Final verification
    # ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("FINAL STATE — Active job_sites:")
    print("=" * 60)
    final = session.execute(
        text("SELECT id, company_name, is_active FROM job_sites ORDER BY id")
    ).fetchall()
    for r in final:
        status = "✅ Active" if r[2] else "❌ Inactive"
        print(f"  ID {r[0]}: {r[1]:20s} [{status}]")

    print("\nFINAL STATE — ats_platforms:")
    plt = session.execute(
        text("SELECT id, name, class_handler FROM ats_platforms ORDER BY id")
    ).fetchall()
    for p in plt:
        print(f"  ID {p[0]}: {p[1]:25s} -> {p[2]}")

    print("=" * 60)
    print("\nNow run:")
    print("  python scripts/main.py --site KForce --dry-run")
    print("  python scripts/main.py --site Capgemini --dry-run")

except Exception as e:
    session.rollback()
    logger.error(f"❌ Error: {e}")
    import traceback; traceback.print_exc()
finally:
    session.close()
