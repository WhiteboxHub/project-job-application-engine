import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db
from models.config_models import JobSite, SiteSelector
from sqlalchemy.orm import Session

def seed_wipro_selectors():
    print("🌱 Seeding Wipro selectors...")
    
    session = db.get_session()
    try:
        # Find Wipro job site
        wipro_site = session.query(JobSite).filter(JobSite.company_name == 'Wipro').first()
        
        if not wipro_site:
            print("❌ Wipro job site not found in database. Please run init_db.py or add it manually.")
            return

        print(f"✓ Found Wipro site (ID: {wipro_site.id})")
        
        # Define selectors
        listing_selectors = {
            # Search Form
            'keyword_input': "input[data-testid='searchByKeywords'], input[name='q'], input.form-control[placeholder*='Skills']",
            'location_input': "input[data-testid='searchByLocation'], input[name='locationsearch'], input.location-input",
            'search_button': "button[data-testid='submitJobSearchBtn'], button.keywordsearchbutton, button[title='Search Jobs']",
            
            # Job Listings
            'job_container': "li[data-testid='jobCard'], li[class*='jobCard']",
            'job_title': "a[data-testid^='jobCardTitle'], a[class*='jobCardTitle']",
            'job_link': "a[data-testid^='jobCardTitle'], a[class*='jobCardTitle']",
            'job_id': "span[data-help-id^='jobCardFooterValue']:first-of-type, div[data-help-id^='jobCardFooterRow'] span[class*='jobCardFooterValue']:first-of-type",
            
            # Pagination
            'next_page': "button[data-testid='goToNextPageBtn'], button[aria-label='Go to next page'], button:contains('Next')",
            'page_numbers': "ul[data-help-id='paginatorWrapperUl'] li, nav[data-testid='paginatorWrapper'] li",
        }
        
        application_selectors = {
            # Apply Button
            'apply_button_dropdown': "button#unifyApplyNowTopButton, button.unify-apply-now, button[id*='ApplyNow']",
            'apply_button_menu_item': "a#applyOption--manual, a.applyOption[aria-label='Apply Now'], ul#unifyApplyNowButtonListDropDown a:first-child",
            
            # Login Form
            'login_email_input': "input#username, input[name='username']",
            'login_password_input': "input#password, input[name='password']",
            'login_submit_button': "button:contains('Sign In'), span.aquabtn button, span.aquabtn.active button",
            'create_account_link': "a[href*='register'], a:contains('Create an account')",
            
            # Form Navigation
            'expand_all_sections': "a#30:_expandAllSections, a.expandCollapseTxt, a:contains('Expand all sections')",
            
            # Profile Information
            'first_name_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='firstName']"],
            'last_name_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='lastName']"],
            'phone_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='cellPhone']"],
            'email_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='contactEmail']"],
            'preferred_name_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='preferredName']"],
            'social_account_url_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='custSocialURL']"],
            'country_code_select': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@aria-label='Country Code']"],
            'gender_select': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@aria-label='Gender']"],
            'disability_assistance_select': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[contains(@aria-label, 'assistance to complete the application')]"],
            'disability_assistance_explain_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//textarea[contains(@name, 'custCandidateAssist')]"],
            'employed_before_select': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[contains(@aria-label, 'employed with Wipro')]"],
            'employee_id_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='custCandidateFillEmpID']"],
            'address_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='address']"],
            'city_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='city']"],
            'zip_input': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@name='zip']"],
            'country_select': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@aria-label='Country/Region']"],
            'state_select': ["//div[contains(@class, 'rcmFormSection')][.//span[normalize-space(.)='Profile Information']]//input[@aria-label='State / Province']"],

            # Experience
            'experience_section_trigger': [
                "//span[contains(normalize-space(.), 'Experience')]",
                "//button[contains(@class, 'rcmFormSectionTopBar')][.//span[contains(normalize-space(.), 'Experience')]]",
                "//div[contains(@class, 'rcmFormSectionTopBar')][.//span[contains(normalize-space(.), 'Experience')]]",
                "//button[contains(., 'Experience')]",
                "//a[contains(., 'Experience')]"
            ],
            'add_experience_btn': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'addRowButton')]",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//div[contains(@class, 'addRowButton')]",
                "div.rcmFormSection:contains('Experience') div.addRowButton"
            ],
            'job_title_input': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Title')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//label[contains(normalize-space(.), 'Title')]/following::input[1]",
                "input[name*='title'][id*='Experience']"
            ],
            'company_input': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Employer')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//label[contains(normalize-space(.), 'Employer')]/following::input[1]",
                "input[name*='employer'][id*='Experience']"
            ],
            'start_date_input': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Start Date')]]//ui5-date-picker-xweb-calendar-widget",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//label[contains(normalize-space(.), 'Start Date')]/following::ui5-date-picker-xweb-calendar-widget[1]"
            ],
            'end_date_input': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'End Date')]]//ui5-date-picker-xweb-calendar-widget",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//label[contains(normalize-space(.), 'End Date')]/following::ui5-date-picker-xweb-calendar-widget[1]"
            ],
            'exp_country_select': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Country')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//label[contains(normalize-space(.), 'Country')]/following::input[1]"
            ],
            'exp_state_select': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'State')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//label[contains(normalize-space(.), 'State')]/following::input[1]"
            ],
            'exp_city_input': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Experience')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'City')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Experience')]//label[contains(normalize-space(.), 'City')]/following::input[1]"
            ],

            # Education
            'education_section_trigger': [
                "//span[contains(normalize-space(.), 'Education')]",
                "//button[contains(@class, 'rcmFormSectionTopBar')][.//span[contains(normalize-space(.), 'Education')]]",
                "//div[contains(@class, 'rcmFormSectionTopBar')][.//span[contains(normalize-space(.), 'Education')]]",
                "//button[contains(., 'Education')]",
                "//a[contains(., 'Education')]"
            ],
            'add_education_btn': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'addRowButton')]",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//div[contains(@class, 'addRowButton')]",
                "div.rcmFormSection:contains('Education') div.addRowButton"
            ],
            'edu_type_select': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Education Type')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'Education Type')]/following::input[1]"
            ],
            'edu_degree_select': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Degree')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'Degree')]/following::input[1]"
            ],
            'edu_school_input': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'College') or contains(normalize-space(.), 'University')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'College') or contains(normalize-space(.), 'University')]/following::input[1]"
            ],
            'edu_major_select': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Major')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'Major')]/following::input[1]"
            ],
            'edu_start_date': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Start Date')]]//ui5-date-picker-xweb-calendar-widget",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'Start Date')]/following::ui5-date-picker-xweb-calendar-widget[1]"
            ],
            'edu_end_date': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'End Date')]]//ui5-date-picker-xweb-calendar-widget",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'End Date')]/following::ui5-date-picker-xweb-calendar-widget[1]"
            ],
            'edu_grad_date': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Passing')]]//ui5-date-picker-xweb-calendar-widget",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'Passing')]/following::ui5-date-picker-xweb-calendar-widget[1]"
            ],
            'edu_country_select': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'Country')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'Country')]/following::input[1]"
            ],
            'edu_state_select': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'State')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'State')]/following::input[1]"
            ],
            'edu_city_input': [
                "//div[contains(@class, 'rcmFormSection')][.//span[contains(normalize-space(.), 'Education')]]//div[contains(@class, 'RCMFormField')][.//label[contains(normalize-space(.), 'City')]]//input",
                "//div[contains(@class, 'rcmFormSection')][contains(., 'Education')]//label[contains(normalize-space(.), 'City')]/following::input[1]"
            ],
            
            # Job Specific Information
            'auth_country_select': "input[aria-label*='legally authorized to work'], input[title*='legally authorized to work']",
            'auth_work_country_select': "input[aria-label='Work Authorization Country'], input[title='Work Authorization Country']",
            'visa_status_select': "input[aria-label='Visa Status'], input[title='Visa Status']",
            'sponsorship_future_select': "input[aria-label*='require sponsorship'], input[title*='require sponsorship']",
            'citizenship_select': "input[aria-label='Citizenship'], input[title='Citizenship']",
            'govt_employed_select': "input[aria-label*='employed with government'], input[title*='employed with government']",
            'race_select': "input[aria-label='Race/Ethnicity'], input[title='Race/Ethnicity']",
            'veteran_select': "input[aria-label='Protected Veteran'], input[title='Protected Veteran']",
            'disability_select': "input[aria-label='Disability'], input[title='Disability']",
            
            # Resume Upload
            'resume_upload_trigger': "div.attachActions, span.addAttachments, span[class*='addAttachments']",
            'resume_upload_input': "input[type='file'], input[name*='file'], input[id*='file']",
            'upload_success_indicator': ".upload-success, .file-uploaded, span.filename",
            
            # Form Submission
            'save_draft_button': "span.rcmSaveButton, span[role='button']:contains('Save')",
            'submit_button': "span[id*='submitBtn'], span.rcmSaveButton:contains('Apply'), span[role='button']:contains('Apply')",
            'next_button': "button.next, button[type='button']:contains('Next')",
            
            # Consent/Terms
            'terms_checkbox': "input[type='checkbox'][name*='terms'], input#terms-consent",
        }
        
        # Use raw SQL to avoid SQLAlchemy JSON type issues
        from sqlalchemy import text
        
        # Delete existing selectors for Wipro
        print("  Cleaning up old selectors...")
        session.execute(
            text("DELETE FROM site_selectors WHERE job_site_id = :site_id"),
            {"site_id": wipro_site.id}
        )
        
        # Get max ID to generate new IDs manually
        result = session.execute(text("SELECT COALESCE(MAX(id), 0) FROM site_selectors"))
        max_id = result.scalar()
        
        # Insert new selectors
        print(f"  Inserting new selectors starting with ID {max_id + 1}...")
        session.execute(
            text("""
                INSERT INTO site_selectors (id, ats_platform_id, job_site_id, type, config_json, updated_at)
                VALUES (:id1, :ats_id, :site_id, 'listing', :listing_json, CURRENT_TIMESTAMP),
                       (:id2, :ats_id, :site_id, 'application', :app_json, CURRENT_TIMESTAMP)
            """),
            {
                "id1": max_id + 1,
                "id2": max_id + 2,
                "ats_id": wipro_site.ats_platform_id,
                "site_id": wipro_site.id,
                "listing_json": json.dumps(listing_selectors),
                "app_json": json.dumps(application_selectors)
            }
        )
        
        session.commit()
        print("✅ Wipro selectors seeded successfully!")
        
    except Exception as e:
        print(f"❌ Error seeding selectors: {e}")
        session.rollback()
    finally:
        db.close_session(session)

if __name__ == "__main__":
    seed_wipro_selectors()
