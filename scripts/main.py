import argparse
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from config.secrets_validator import validate_secrets
from engine.runner import EngineRunner
from core.logger import logger

def main():
    parser = argparse.ArgumentParser(description="Job Application Engine CLI")
    parser.add_argument("--dry-run", action="store_true", help="Run without submitting applications")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--company", type=str, help="Run only for a specific company name (e.g., 'TekSystems')")

    
    args = parser.parse_args()
    
    # Override settings
    if args.dry_run:
        settings.DRY_RUN = True
        logger.info("Mode: DRY RUN (No applications will be submitted)")
        
    if args.headless:
        settings.HEADLESS = True
        logger.info("Mode: HEADLESS Browser")

    try:
        validate_secrets()
        
        runner = EngineRunner()
        runner.run(company_name=args.company)

        
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
