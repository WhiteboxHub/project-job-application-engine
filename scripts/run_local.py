import os
import sys
import argparse

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.logger import logger
from engine.runner import EngineRunner

def run_local():
    """Run the engine for a specific site using local data/guest_form_data.json"""
    parser = argparse.ArgumentParser(description="Run job application engine in local mode.")
    parser.add_argument("--site", type=str, required=True, help="Site name (e.g., Collabera, KForce)")
    parser.add_argument("--keywords", type=str, help="Optional comma-separated keywords to override JSON")
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info(f"RUNNING {args.site.upper()} IN LOCAL MODE (Bypassing Backend API)")
    logger.info("=" * 60)
    
    try:
        print(f"DEBUG: Starting EngineRunner for site: {args.site}")
        runner = EngineRunner()
        runner.run(site_filter=args.site, candidate_data=None)
        print("DEBUG: EngineRunner.run() finished.")
        
    except Exception as e:
        logger.critical(f"Local run failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_local()
