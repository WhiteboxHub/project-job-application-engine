import os
import sys
import json

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from engine.runner import EngineRunner
from core.logger import logger

def run_local():
    """Run AE Talents with hardcoded test data to bypass the Backend API."""
    
    # 1. Configuration Overrides
    settings.DRY_RUN = True  # Set to False to actually submit applications
    settings.HEADLESS = False # See the browser in action
    
    logger.info("[LOCAL TEST] Starting AE Talents with manual candidate data...")

    # 2. Mock Candidate Data (Payload expected by AETalentsStrategy)
    # This structure matches what the backend would normally provide.
    test_candidate_data = {
        "candidate_id": 999,
        "applicant": {
            "first_name": "Sai",
            "last_name": "Tadikonda",
            "email": "sairam818595@gmail.com",
            "phone": "555-0199",
            "visa_status": "H1B",
            "workstatus": "H1B"
        },
        "search": {
            "keywords": ["AI Engineer", "Machine Learning"],
            "keyword": "AI Engineer",
            "location": "United States"
        },
        # BaseStrategy.get_resume_path() searches for this key or fallbacks to settings
        "resume_path": "resume/downloads/candidate_resume_downloaded.pdf" 
    }

    # 3. Initialize and Run Engine
    runner = EngineRunner()
    try:
        runner.run(
            site_filter="AE Talents Group", 
            candidate_data=test_candidate_data
        )
    except Exception as e:
        logger.error(f"Engine test failed: {e}")

if __name__ == "__main__":
    run_local()
