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
    """Main entry point for the job application engine"""
    parser = argparse.ArgumentParser(description="Job Application Engine CLI")
    parser.add_argument("--dry-run", action="store_true", help="Run without submitting applications")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--site", type=str, help="Run only a specific site (e.g., 'KForce')")
    parser.add_argument("--max-apps", type=int, help="Maximum number of applications to run")
    
    args = parser.parse_args()
    
    # Override settings based on CLI arguments
    if args.dry_run:
        settings.DRY_RUN = True
        logger.info("🔍 [MODE] DRY RUN (No applications will be submitted)")
        
    if args.headless:
        settings.HEADLESS = True
        logger.info("👻 [MODE] HEADLESS Browser")

    if args.max_apps:
        settings.MAX_APPLICATIONS_PER_RUN = args.max_apps
        logger.info(f"🎯 [LIMIT] {args.max_apps} applications per run")

    try:
        # Validate configuration (optional)
        # validate_secrets()
        
        # Run the engine
        runner = EngineRunner()
        runner.run(site_filter=args.site)
        
    except Exception as e:
        logger.critical(f"❌ [FATAL] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
