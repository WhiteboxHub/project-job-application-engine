import sys
import os
import json
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.db_connection import db, Base
from models.config_models import AtsPlatform, JobSite, SiteSelector, JobListing
from core.logger import logger

def init_and_seed():
    print("🚀 Initializing DuckDB and Seeding Integrated Sites...")
    
    # 1. Initialize Schema using SQLAlchemy
    # Explicit creation order for DuckDB
    AtsPlatform.__table__.create(db.engine, checkfirst=True)
    JobSite.__table__.create(db.engine, checkfirst=True)
    SiteSelector.__table__.create(db.engine, checkfirst=True)
    JobListing.__table__.create(db.engine, checkfirst=True)
    print("✅ Schema initialized.")
    
    session = db.get_session()
    try:
        # --- SEED WIPRO ---
        print("🌱 Seeding Wipro...")
        
        # Add Wipro ATS Platform
        wipro_plat = session.query(AtsPlatform).filter_by(name='Wipro Custom').first()
        if not wipro_plat:
            wipro_plat = AtsPlatform(
                name='Wipro Custom',
                class_handler='strategies.custom.wipro.WiproStrategy',
                is_headless_required=False
            )
            session.add(wipro_plat)
            session.flush() # Get ID
            print("  + Added Wipro Custom platform")
        else:
            print("  ✓ Wipro Custom platform exists")
            
        # Add Wipro Job Site
        wipro_site = session.query(JobSite).filter_by(company_name='Wipro').first()
        if not wipro_site:
            wipro_site = JobSite(
                company_name='Wipro',
                domain='wipro.com',
                ats_platform_id=wipro_plat.id,
                category='Consulting firm',
                is_active=True,
                search_url_template='https://careers.wipro.com/careers-home/'
            )
            session.add(wipro_site)
            session.flush()
            print("  + Added Wipro job site")
        else:
            print("  ✓ Wipro job site exists")
            
        # Seeding Wipro Selectors
        listing_selectors = {
            'keyword_input': "input[data-testid='searchByKeywords'], input[name='q'], input.form-control[placeholder*='Skills']",
            'location_input': "input[data-testid='searchByLocation'], input[name='locationsearch'], input.location-input",
            'search_button': "button[data-testid='submitJobSearchBtn'], button.keywordsearchbutton, button[title='Search Jobs']",
            'job_container': "li[data-testid='jobCard'], li[class*='jobCard']",
            'job_title': "a[data-testid^='jobCardTitle'], a[class*='jobCardTitle']",
            'job_link': "a[data-testid^='jobCardTitle'], a[class*='jobCardTitle']",
            'job_id': "span[data-help-id^='jobCardFooterValue']:first-of-type, div[data-help-id^='jobCardFooterRow'] span[class*='jobCardFooterValue']:first-of-type",
            'next_page': "button[data-testid='goToNextPageBtn'], button[aria-label='Go to next page'], button:contains('Next')",
        }
        
        application_selectors = {
            'apply_button_dropdown': "button#unifyApplyNowTopButton, button.unify-apply-now, button[id*='ApplyNow']",
            'apply_button_menu_item': "a#applyOption--manual, a.applyOption[aria-label='Apply Now'], ul#unifyApplyNowButtonListDropDown a:first-child",
            'login_email_input': "input#username, input[name='username']",
            'login_password_input': "input#password, input[name='password']",
            'login_submit_button': "button:contains('Sign In'), span.aquabtn button, span.aquabtn.active button",
            'first_name_input': "//input[@name='firstName']",
            'last_name_input': "//input[@name='lastName']",
            'phone_input': "//input[@name='cellPhone']",
            'email_input': "//input[@name='contactEmail']",
            'resume_upload_input': "input[type='file']",
            'submit_button': "span[id*='submitBtn'], span.rcmSaveButton:contains('Apply'), span[role='button']:contains('Apply')",
        }
        
        # Clear existing selectors for Wipro
        session.query(SiteSelector).filter_by(job_site_id=wipro_site.id).delete()
        
        # Add selectors
        session.add(SiteSelector(
            ats_platform_id=wipro_plat.id,
            job_site_id=wipro_site.id,
            type='listing',
            config_json=listing_selectors
        ))
        session.add(SiteSelector(
            ats_platform_id=wipro_plat.id,
            job_site_id=wipro_site.id,
            type='application',
            config_json=application_selectors
        ))
        
        # --- SEED HIRING CAFE ---
        print("🌱 Seeding Hiring Cafe...")
        
        # Add Hiring Cafe ATS Platform
        hc_plat = session.query(AtsPlatform).filter_by(name='Hiring Cafe Custom').first()
        if not hc_plat:
            hc_plat = AtsPlatform(
                name='Hiring Cafe Custom',
                class_handler='strategies.custom.hiring_cafe.HiringCafeStrategy',
                is_headless_required=False
            )
            session.add(hc_plat)
            session.flush()
            print("  + Added Hiring Cafe Custom platform")
        else:
            print("  ✓ Hiring Cafe Custom platform exists")
            
        # Add Hiring Cafe Job Site
        hc_site = session.query(JobSite).filter_by(company_name='Hiring Cafe').first()
        if not hc_site:
            hc_site = JobSite(
                company_name='Hiring Cafe',
                domain='hiring.cafe',
                ats_platform_id=hc_plat.id,
                category='Product Company',
                is_active=True,
                search_url_template='https://hiring.cafe/'
            )
            session.add(hc_site)
            session.flush()
            print("  + Added Hiring Cafe job site")
        else:
            print("  ✓ Hiring Cafe job site exists")
            
        session.commit()
        print("✅ Integrated Seeding Complete!")
        
    except Exception as e:
        print(f"❌ Error during seeding: {e}")
        session.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close_session(session)

if __name__ == "__main__":
    init_and_seed()
