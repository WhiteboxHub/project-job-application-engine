import os
import traceback

from core.logger import logger
from core.resume_downloader import resume_downloader
from scripts.parse_resume import parse_resume

class RunParametersBuilder:
    """Transforms a flat candidate API response into the exactly formatted massive JSON required by the Engine."""

    @staticmethod
    def build(candidate_data: dict) -> dict:
        logger.info("Building run_parameters from candidate payload to match precise JSON structure...")

        # 1. Base Structure Defaults
        db_email = candidate_data.get("email", "")
        db_phone = candidate_data.get("google_voice_number", "9252389487")
        db_password = candidate_data.get("password", "")
        db_resume_url = candidate_data.get("resume_url", "")
        
        parsed_first = ""
        parsed_last = ""
        parsed_edu = []
        parsed_work = []
        
        # 2. Extract live fields from physical PDF
        if db_resume_url:
            try:
                local_resume_path = resume_downloader.download(db_resume_url)
                if local_resume_path and os.path.exists(local_resume_path):
                    logger.info("Parsing downloaded resume...")
                    parsed_resume = parse_resume(local_resume_path)
                    
                    personal = parsed_resume.get("personal_info", {})
                    parsed_first = personal.get("first_name", "")
                    parsed_last = personal.get("last_name", "")
                    parsed_edu = parsed_resume.get("education", [])
                    parsed_work = parsed_resume.get("work", [])
            except Exception as e:
                logger.error(f"Failed to process physical resume: {e}")

        first_name = parsed_first if parsed_first else ""
        last_name = parsed_last if parsed_last else ""

        # Intelligent Fallback: Since the DB natively provides full_name, use it!
        db_full_name = candidate_data.get("full_name", "")
        if not first_name and db_full_name:
            name_parts = db_full_name.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0].title()
                last_name = " ".join(name_parts[1:]).title()
            elif name_parts:
                first_name = name_parts[0].title()
                
        # Hard Fallback from the user's template just in absolute worst-case scenario
        first_name = first_name if first_name else "Ramani"
        last_name = last_name if last_name else "Moganti"

        # Format Education dynamically or use safety fallback
        edu_list = parsed_edu if parsed_edu else [
            {
                "city": "Vizag", "major": "Mathematics", 
                "state": "Andhra Pradesh", "degree": "Bsc", 
                "country": "India", "end_date": "06/01/1993", 
                "start_date": "07/14/1990", "university": "Andhra University", 
                "education_type": "University", "year_of_passing": "06/01/1993"
            }
        ]
        
        # Format work dynamically or use safety fallback
        work_list = parsed_work if parsed_work else [
            {
                "city": "San Mateo", "state": "California", 
                "title": "AIML Engineer", "company": "Lucid Motors", 
                "country": "United States", "end_date": "Present", 
                "location": "San Mateo, CA", "start_date": "10/01/2024"
            }
        ]

        # 3. Construct the MASSIVE perfect JSON template
        run_parameters = {
            "search": {
                "distance": "0",
                "keywords": ["AI", "Python"],
                "location": "United States"
            },
            "applicant": {
                "email": db_email,
                "phone": db_phone,
                "first_name": first_name,
                "last_name": last_name,
                "preferred_name": first_name,
                "countrycode": "USA (+1)",
                "social_account_url": "",
                "address": {
                    "city": "San Ramon",
                    "state": "California",
                    "street": "9673 Tareyton Ave",
                    "country": "United States",
                    "zip_code": "94583"
                },
                "personal_info": {
                    "race": "Opt Out",
                    "gender": "Female",
                    "veteran": "No",
                    "disability": "No",
                    "disability_assistance": "No",
                    "disability_assistance_explain": ""
                },
                "work_authorization": {
                    "citizenship": "American",
                    "visa_status": "Citizen",
                    "authorization": "US Citizen",
                    "auth_work_country": "United States",
                    "sponsorship_future": "No",
                    "auth_country_select": "Yes"
                },
                "usa_form": {
                    "travel": "10%",
                    "relocate": "No",
                    "residence": "San Ramon, CA",
                    "certifications": "None",
                    "expected_salary": "$120,000 - $150,000",
                    "relocation_destinations": "Open to all major US hubs"
                },
                "general_usa_form": {
                    "address": "9673 Tareyton Ave, San Ramon CA 94583",
                    "acknowledge": True,
                    "ability_to_perform": "Yes"
                },
                "education": edu_list,
                "employment": {
                    "current": work_list,
                    "govt_employed": "No",
                    "wipro_employee_id": "",
                    "employed_before_wipro": "No"
                }
            },
            "resume_url": db_resume_url,
            "wipro_credentials": {
                "email": db_email,
                "password": db_password
            }
        }

        logger.info(f"Successfully built the massive structured JSON schema for {first_name} {last_name}")
        return run_parameters

run_parameters_builder = RunParametersBuilder()
