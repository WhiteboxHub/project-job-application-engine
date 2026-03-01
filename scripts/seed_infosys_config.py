import os
import json
import duckdb
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def seed_infosys_config():
    db_path = os.getenv("DUCKDB_PATH")
    token = os.getenv("MOTHERDUCK_TOKEN")
    
    if not db_path:
        print("Error: DUCKDB_PATH not found in .env")
        return

    if db_path.startswith("md:"):
        print(f"Connecting to MotherDuck: {db_path}")
        connection_str = f"{db_path}?motherduck_token={token}" if token else db_path
        conn = duckdb.connect(connection_str)
    else:
        print(f"Connecting to local DuckDB: {db_path}")
        conn = duckdb.connect(db_path)

    # Infosys Data
    job_site_id = 4 # Based on init_db.py
    
    config_json = {
        "search_input": ["input#keyword", "input[name='keyword']", "input.search-keyword"],
        "search_button": ["button#search", "button.search-btn", "input[type='submit']"],
        "next_button": ["a.next", "li.next a", "a[title='Next']", "button.next"],
        "target_keyword": ["ai", "machine learning", "ml", "data science", "engineer", "developer", "technology", "software"],
        "blocked_keyword": ["nurse", "sales", "hr", "marketing", "finance", "legal", "doctor"],
        "location_filter": ["canada", "brazil", "india", "mexico", "united kingdom", "uk", "australia"],
        "apply_button": [
            "//*[@id='sortableHeader']/li/div/div/div/div[2]/a",
            "#sortableHeader li div div div div:nth-child(2) a",
            "#sortableHeader > li > div > div > div > div.apply-button-container > a",
            ".apply-button-container a",
            "a.infosys-apply-link",
            "//a[contains(@class, 'apply')]",
            "//a[contains(text(), 'Apply')]",
            "//button[contains(text(), 'Apply Now')]"
        ],
        "first_time_user_button": [
            "//*[@id='form_application']/div[2]/div[2]//a[contains(@class,'apply-selector-button') or contains(@class,'apply-btn') or contains(text(),'Apply')]",
            "//*[@id='form_application']/div[2]/div[2]//button",
            ".apply-type-container:nth-of-type(2) .apply-selector-button-container a",
            ".apply-type-container:nth-of-type(2) .apply-selector-button-container button",
            ".apply-type-container:last-of-type .apply-selector-button-container a",
            ".apply-selector-button-container a",
            ".apply-selector-button-container button",
            "//div[contains(@class,'apply-type-container')][2]//a",
            "//div[contains(@class,'apply-type-container')][2]//button",
            "//p[contains(text(),'applying for the first time')]/following-sibling::div//a",
            "//p[contains(text(),'applying for the first time')]/following-sibling::div//button",
            ".apply-first-time-button",
            "a.apply-first-time-button",
            "input[value='FirstTime']",
            "#rdoFirstTime"
        ],
        "consent_button": [
            "a.consent-button",
            ".consent-button",
            "//a[@class='consent-button' and text()='Proceed']",
            "//a[contains(@class, 'consent-button')]",
            "//a[contains(text(), 'Proceed')]",
            "button.agree",
            "button.proceed",
            "//button[contains(text(), 'Proceed')]"
        ],
        "forward_navigation": [
            "a#forward-navigation",
            "a.form-next-button",
            "button.save-continue",
            "button.next",
            "//button[contains(., 'Next')]",
            "//a[contains(., 'Next')]",
            "//button[contains(., 'Continue')]",
            "//a[contains(., 'Continue')]",
            "//button[contains(., 'Save')]",
            "//a[contains(., 'Save')]",
            "//button[contains(., 'Proceed')]",
            "//a[contains(., 'Proceed')]",
            "//span[contains(text(), 'Next')]",
            "//span[contains(text(), 'Continue')]"
        ],
        "field_keywords": {
            "first_name": ["first name", "firstname", "given name"],
            "last_name": ["last name", "lastname", "surname", "family name"],
            "email": ["email", "email address"],
            "phone": ["phone", "mobile", "contact number", "cell"],
            "city": ["city", "addrCity", "town"],
            "address": ["address_1", "address", "address 1", "address line 1", "street", "street address", "addr1", "address1"],
            "zip": ["zip", "zip code", "zipcode", "postal", "postal code", "postalcode"],
            "authorized_us": ["authorized to work", "legally authorized", "right to work"],
            "sponsorship": ["sponsorship", "require sponsorship", "visa sponsorship", "h1-b"],
            "education": ["education", "school", "institution", "university", "college", "degree", "qualification", "major"],
            "experience": ["work", "experience", "employer", "company", "designation", "job_title", "position", "responsibilities"],
            "skills": ["skills", "technologies", "tool", "stack"],
            "eeo": ["ethnicity", "race", "race category", "gender", "veteran", "disability", "eeo", "employed", "contract", "arbitration", "other", "additional", "signature", "mutual", "source", "authorized", "relocate", "travel", "sponsorship", "voluntary", "identification", "self-identification", "agreement", "terms", "acknowledge"],
            "ethnicity": ["ethnicity", "hispanic", "latino"],
            "gender": ["gender", "sex"],
            "veteran": ["veteran", "military", "protected"],
            "disability": ["disability", "voluntary self-identification"],
            "employed": ["employed", "previously worked", "employed by infosys"],
            "authorized": ["authorized", "work in the united states", "legally"],
            "arbitration": ["arbitration", "agreement"],
            "relocate": ["relocate"],
            "travel": ["travel"],
            "signature": ["signature", "full name", "legal name"],
            "bachelor_degree_req": ["bachelor", "minimum", "foreign equivalent", "lieu of every year", "three years of relevant", "work experience in lieu", "degree or foreign"],
            "contractual_restrictions": ["contractual", "non-competition", "non-compete", "restrictive covenant", "prevent you from working", "obligations that could prevent", "prior employer"],
            "race": ["race", "race category", "diversity", "ethni"],
            "race_category": ["race", "ethnic origin", "ancestry"],
            "education_school": ["school", "institution", "university", "college", "education][0][school", "education][0][institution"],
            "education_major": ["major", "area", "study", "program", "field", "education][0][major", "education][0][program"],
            "education_degree": ["degree", "qualification", "education][0][degree", "level"],
            "education_end_year": ["graduation", "year", "end_date", "education][0][year", "education][0][end_date"],
            "education_start_year": ["start_year", "from_year", "education][0][start_year", "education][0][from"],
            "education_gpa": ["gpa", "grade", "grade_point", "education][0][gpa"],
            "experience_company": ["company", "employer"],
            "experience_title": ["job_title", "position", "title"]
        },
        "delays": {
            "page_load_min": 6.0,
            "page_load_max": 10.0,
            "form_fill_min": 0.5,
            "after_click_min": 3.0,
            "backend_processing": 40.0,
            "after_upload_popup_wait": 2.0,
            "second_popup_poll_duration": 10,
            "second_popup_poll_interval": 1,
            "after_import_fields_wait": 5.0,
            "after_resume_next_wait": 5.0
        },
        "popup_closers": [
            "span.x-icon",
            ".x-icon",
            "div.close-item button.close",
            "//div[contains(@class, 'close-item')]//button",
            "button[aria-label='Close']",
            "button.close",
            "button#onetrust-accept-btn-handler",
            "//button[contains(text(), 'Close')]",
            "//span[contains(@class, 'x-icon')]/.."
        ],
        "upload_indicators": [
            ".dz-filename", ".dz-success", ".dz-complete", ".upload-success", ".dz-preview", "div.dz-image",
            ".resume-preview", ".file-name", "[id*='resume_name']", "//span[contains(@class, 'dz-filename')]",
            "//div[contains(@class, 'success-message')]", "//span[contains(text(), '.pdf')]",
            "//div[contains(text(), 'uploaded successfully')]", "button.remove", "a.remove",
            "//a[contains(text(), 'Remove')]", "//button[contains(text(), 'Remove')]", "//span[contains(text(), 'Remove')]"
        ],
        "import_fields": ["button.save-button", "//button[contains(text(), 'Import fields')]", "//button[contains(., 'Import fields')]"],
        "submit_button": [".form-submit-button", "input[type='submit']", "//button[contains(text(), 'Submit Application')]", "//button[contains(text(), 'Submit')]"],
        "max_experience_entries": 10
    }

    config_json_str = json.dumps(config_json)
    
    # Check if entry exists
    existing = conn.execute("SELECT id FROM site_selectors WHERE job_site_id = ? AND type = 'application'", [job_site_id]).fetchall()
    
    if existing:
        print(f"Updating existing configuration for Infosys (Site ID: {job_site_id})...")
        conn.execute("UPDATE site_selectors SET config_json = ? WHERE job_site_id = ? AND type = 'application'", [config_json_str, job_site_id])
    else:
        print(f"Inserting new configuration for Infosys (Site ID: {job_site_id})...")
        conn.execute("INSERT INTO site_selectors (job_site_id, type, config_json) VALUES (?, 'application', ?)", [job_site_id, config_json_str])
    
    conn.commit()
    conn.close()
    print("Infosys configuration seeded successfully!")

if __name__ == "__main__":
    seed_infosys_config()
