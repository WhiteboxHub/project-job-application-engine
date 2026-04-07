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

        # US state abbreviation → full name lookup
        _STATE_MAP = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
            "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
            "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
            "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
        }

        # Parse city/state from address string like "5325 Hazeltine Lane, Dublin, CA-94568"
        city = "San Ramon"
        state = "California"
        if db_address and "," in db_address:
            address_parts = [p.strip() for p in db_address.split(",")]
            # Second part is typically the city
            if len(address_parts) >= 2:
                city = address_parts[1].strip()
            # Last part may be "CA-94568" or "CA 94568" or just "CA"
            if len(address_parts) >= 3:
                last_seg = address_parts[-1].strip()
                # Extract the 2-letter state code before any digit/dash
                import re as _re
                m = _re.match(r"([A-Za-z]{2})", last_seg)
                if m:
                    abbr = m.group(1).upper()
                    state = _STATE_MAP.get(abbr, abbr)
                    # Also try to extract zip from the same segment if not provided
                    if not db_zip_code:
                        zm = _re.search(r"(\d{5})", last_seg)
                        if zm:
                            db_zip_code = zm.group(1)

        # 2. Re-Implemented: Download (but do NOT parse) the Resume so the WebDriver can upload it
        local_resume_path = ""
        if db_resume_url:
            try:
                logger.info("Downloading physical resume for Selenium upload...")
                local_resume_path = resume_downloader.download(db_resume_url)
            except Exception as e:
                logger.error(f"Failed to download physical resume for upload: {e}")

        # 3. Extract keywords from Whitebox API or use new AI/GenAI defaults
        api_keywords = candidate_data.get("keywords", [])
        if not api_keywords:
            api_keywords = [
                "AI Data Scientist",
                "MLOps Engineer",
                "Data Scientist (AI)",
                "AI Engineer",
                "Machine Learning Engineer",
                "Generative AI Engineer",
                "LLM Engineer",
                "AI",
                "PYTHON"
            ]

        # 4. Construct the clean, minimal JSON
        run_parameters = {
            "candidate_id": candidate_data.get("candidate_id"),
            "search": {
                "distance": "0",
                "keywords": api_keywords,
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
            run_parameters["resume_path"] = local_resume_path

        logger.info(f"Successfully built clean run_parameters for {first_name} {last_name}")
        return run_parameters

run_parameters_builder = RunParametersBuilder()
