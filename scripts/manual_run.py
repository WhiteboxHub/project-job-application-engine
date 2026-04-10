import sys
import os
import json
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.getcwd())

from config.settings import settings
from core.logger import logger
from engine.runner import EngineRunner

def manual_run():
    """Run the engine manually for a specific candidate, skipping the backend check."""
    
    # 1. Define your test candidate here
    candidate_data = {
        "candidate_name": "Ramani Moganti",
        "email": "ramanim.ip@gmail.com",
        "applicant": {
            "first_name": "Ramani",
            "last_name": "Moganti",
            "email": "ramanim.ip@gmail.com",
            "phone": "925-238-9487"
        },
        "search": {
            "keywords": ["AI Data Scientist", "Python Developer"],
            "location": "United States"
        },
        "resume_path": os.path.join(os.getcwd(), "resume/downloads/candidate_resume_downloaded.pdf")
    }

    logger.info(f"[MANUAL RUN] Starting engine for {candidate_data['candidate_name']}")
    
    # Optional: Force dry run or headless mode via code if desired
    # settings.DRY_RUN = True
    
    try:
        runner = EngineRunner()
        # You can specify site_filter="Experis" to run only one site
        runner.run(site_filter="Experis", candidate_data=candidate_data)
        logger.info("[MANUAL RUN] Completed successfully.")
    except Exception as e:
        logger.error(f"[MANUAL RUN] Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    manual_run()
