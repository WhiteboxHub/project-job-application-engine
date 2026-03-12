"""
Candidate Loader  Merges parsed_resume.json + guest_form_data.json
into a single dict used by the scheduler to drive form filling.

Priority order: guest_form_data.json OVERRIDES parsed_resume.json
(so manual corrections always win).
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

# Paths relative to project root (resolved from this file's location)
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_RESUME_JSON   = os.path.join(_PROJECT_ROOT, "resume", "parsed_resume.json")
_GUEST_JSON    = os.path.join(_PROJECT_ROOT, "data", "guest_form_data.json")


class CandidateLoader:
    """
    Loads candidate data from JSON files.

    Usage:
        candidate = CandidateLoader.load()
        # Returns one unified dict ready to pass as candidate_data to any strategy
    """

    @staticmethod
    def load() -> dict:
        """
        Load and merge both JSON files.

        Returns:
            dict with keys:
                personal_info, address, education, work, skills,
                search, applicant, resume_path, wipro_credentials
        """
        resume_data = CandidateLoader._load_json(_RESUME_JSON, "parsed_resume.json")
        guest_data  = CandidateLoader._load_json(_GUEST_JSON,  "guest_form_data.json")

        if not resume_data and not guest_data:
            logger.error("[ERROR] Both JSON files missing  cannot load candidate data")
            return {}

        # --- Build unified candidate dict ---
        # Start with parsed_resume.json as base
        candidate = {}

        # Personal info from resume
        personal = resume_data.get("personal_info", {})
        candidate["first_name"]  = personal.get("first_name", "")
        candidate["last_name"]   = personal.get("last_name", "")
        candidate["email"]       = personal.get("email", "")
        candidate["phone"]       = personal.get("phone", "")

        # Address from resume
        addr = resume_data.get("address", {})
        candidate["address"] = {
            "street_address": addr.get("street_address", ""),
            "city":           addr.get("city", ""),
            "state":          addr.get("state", ""),
            "zip_code":       addr.get("zip_code", ""),
            "country":        addr.get("country", "United States"),
        }

        # Work / education / skills from resume
        candidate["work"]      = resume_data.get("work", [])
        candidate["education"] = resume_data.get("education", [])
        candidate["skills"]    = resume_data.get("skills", [])

        # Professional summary from resume
        prof = resume_data.get("professional_info", {})
        candidate["title"]   = prof.get("title", "")
        candidate["summary"] = prof.get("summary", "")

        # Resume path
        candidate["resume_path"] = guest_data.get("resume_path", "resume/Ghazal_Sultan.pdf")

        # --- Overlay guest_form_data.json (takes priority) ---
        if guest_data:
            applicant = guest_data.get("applicant", {})

            # Override personal info if present in guest data
            if applicant.get("first_name"):
                candidate["first_name"] = applicant["first_name"]
            if applicant.get("last_name"):
                candidate["last_name"] = applicant["last_name"]
            if applicant.get("email"):
                candidate["email"] = applicant["email"]
            if applicant.get("phone"):
                candidate["phone"] = applicant["phone"]

            # Override address if present
            if applicant.get("street_address"):
                candidate["address"]["street_address"] = applicant["street_address"]
            if applicant.get("city"):
                candidate["address"]["city"] = applicant["city"]
            if applicant.get("state"):
                candidate["address"]["state"] = applicant["state"]
            if applicant.get("zip_code"):
                candidate["address"]["zip_code"] = applicant["zip_code"]

            # Compliance / EEO fields from guest data
            candidate["gender"]               = applicant.get("gender", "")
            candidate["visa_status"]          = applicant.get("visa_status", "")
            candidate["citizenship"]          = applicant.get("citizenship", "")
            candidate["auth_work_country"]    = applicant.get("auth_work_country", "United States")
            candidate["sponsorship_future"]   = applicant.get("sponsorship_future", "No")
            candidate["race"]                 = applicant.get("race", "Opt Out")
            candidate["veteran"]              = applicant.get("veteran", "No")
            candidate["disability"]           = applicant.get("disability", "No")

            # Search parameters
            candidate["search"] = guest_data.get("search", {
                "keywords": ["AI Engineer", "Python"],
                "location": "United States",
                "distance": "0"
            })

            # Credentials (e.g. Wipro login)
            candidate["wipro_credentials"] = guest_data.get("wipro_credentials", {})

            # Full applicant block also attached for strategies that use it directly
            candidate["applicant"] = applicant

        logger.info(
            f"[OK] CandidateLoader: loaded {candidate.get('first_name')} {candidate.get('last_name')} "
            f"| keywords={candidate.get('search', {}).get('keywords', [])}"
        )

        return candidate

    @staticmethod
    def _load_json(path: str, label: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"CandidateLoader: loaded {label}")
            return data
        except FileNotFoundError:
            logger.warning(f"CandidateLoader: {label} not found at {path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"CandidateLoader: {label} is invalid JSON  {e}")
            return {}
