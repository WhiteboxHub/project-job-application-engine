import os
import traceback

from core.logger import logger
from core.resume_downloader import resume_downloader

class RunParametersBuilder:
    """Transforms a flat candidate API response directly into purely structured applicant JSON."""

    @staticmethod
    def build(candidate_data: dict) -> dict:
        logger.info("Building run_parameters cleanly entirely from database payload...")

        # 1. Base Structure Defaults
        db_email = candidate_data.get("email", "")
        db_phone = candidate_data.get("google_voice_number", "")
        db_password = candidate_data.get("password", "")
        db_resume_url = candidate_data.get("resume_url", "")
        db_full_name = candidate_data.get("full_name", "")
        db_workstatus = candidate_data.get("workstatus", "")
        db_address = candidate_data.get("address", "")
        db_zip_code = candidate_data.get("zip_code", "")
        db_linkedin = candidate_data.get("linkedin_username", "")
        
        # Determine Name
        first_name = ""
        last_name = ""
        if db_full_name:
            name_parts = db_full_name.split()
            if len(name_parts) >= 2:
                first_name = name_parts[0].title()
                last_name = " ".join(name_parts[1:]).title()
            elif name_parts:
                first_name = name_parts[0].title()

        # Parse realistic city/state strings if provided in Address manually
        city = "San Ramon"
        state = "California"
        if db_address and "," in db_address:
            address_parts = [p.strip() for p in db_address.split(",")]
            city = address_parts[0]
            if len(address_parts) > 1:
                state = address_parts[1]

        # 2. Re-Implemented: Download (but do NOT parse) the Resume so the WebDriver can upload it
        local_resume_path = ""
        if db_resume_url:
            try:
                logger.info("Downloading physical resume for Selenium upload...")
                local_resume_path = resume_downloader.download(db_resume_url)
            except Exception as e:
                logger.error(f"Failed to download physical resume for upload: {e}")

        # 3. Construct the clean, minimal JSON
        run_parameters = {
            "search": {
                "distance": "0",
                "keywords": ["AI", "Python"],
                "location": "United States"
            },
            "applicant": {
                "first_name": first_name,
                "last_name": last_name,
                "email": db_email,
                "phone": db_phone,
                "workstatus": db_workstatus,
                "linkedin": db_linkedin,
                "address": {
                    "city": city,
                    "state": state,
                    "street": db_address,
                    "zip_code": db_zip_code,
                    "country": "United States"
                }
            },
            "resume_url": db_resume_url
        }
        
        # Inject the file path for the LanceSoft upload button!
        if local_resume_path:
            run_parameters["resume"] = {"path": local_resume_path}

        logger.info(f"Successfully built clean run_parameters for {first_name} {last_name}")
        return run_parameters

run_parameters_builder = RunParametersBuilder()
