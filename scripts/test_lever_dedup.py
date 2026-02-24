import os
import json
import sqlite3
from strategies.custom.lever import LeverStrategy
from data.db_duckdb import db_duckdb
from core.logger import logger

def test_duplicate_prevention():
    # 1. Setup mock data
    job_id = "test_job_123"
    site = "lever"
    
    # 2. Mark as applied in DuckDB
    logger.info(f"Marking {job_id} as applied in DuckDB...")
    db_duckdb.mark_applied(job_id, site, "Test Job")
    
    # 3. Create a mock hiring_cafe_output.json with this job
    mock_data = {
        "jobs": [
            {
                "job_id": job_id,
                "title": "Test Job (applied)",
                "ats_url": "https://jobs.lever.co/test/applied",
                "ats_platform": "lever"
            },
            {
                "job_id": "test_job_456",
                "title": "Test Job (new)",
                "ats_url": "https://jobs.lever.co/test/new",
                "ats_platform": "lever"
            }
        ]
    }
    
    mock_file = "hiring_cafe_output.json"
    with open(mock_file, "w") as f:
        json.dump(mock_data, f)
        
    # 4. Initialize strategy (dummy driver)
    class DummyDriver:
        def __init__(self):
            self.current_url = ""
            self.page_source = ""
    
    strategy = LeverStrategy(driver=DummyDriver())
    
    # 5. Run find_jobs
    jobs = strategy.find_jobs()
    
    # 6. Verify only test_job_456 is found
    found_ids = [j['job_id'] for j in jobs]
    logger.info(f"Jobs found: {found_ids}")
    
    if "test_job_456" in found_ids and job_id not in found_ids:
        logger.info("✅ SUCCESS: Duplicate job filtered out correctly.")
    else:
        logger.error(f"❌ FAILURE: Expected only ['test_job_456'], got {found_ids}")

if __name__ == "__main__":
    test_duplicate_prevention()
