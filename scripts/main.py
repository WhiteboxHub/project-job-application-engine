import argparse
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.backend_client import backend_client
from core.logger import logger
from core.resume_downloader import resume_downloader
from engine.runner import EngineRunner


def main():
    """Main entry point for the job application engine"""
    parser = argparse.ArgumentParser(description="Job Application Engine CLI")
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without submitting applications"
    )
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    parser.add_argument(
        "--site", type=str, help="Run only a specific site (e.g., 'LanceSoft')"
    )
    parser.add_argument(
        "--max-apps", type=int, help="Maximum number of applications to run"
    )

    args = parser.parse_args()

    # Override settings based on CLI arguments
    if args.dry_run:
        settings.DRY_RUN = True
        logger.info("[MODE] DRY RUN (No applications will be submitted)")

    if args.headless:
        settings.HEADLESS = True
        logger.info("[MODE] HEADLESS Browser")

    if args.max_apps:
        settings.MAX_APPLICATIONS_PER_RUN = args.max_apps
        logger.info(f"[LIMIT] {args.max_apps} applications per run")

    try:
        # 1. Fetch pending automation parameters
        logger.info("Checking for scheduled automation workflows...")
        candidate_data = backend_client.fetch_pending_candidates()

        if not candidate_data:
            logger.info("[STOP] No pending weekly workflow candidate found. Exiting.")
            sys.exit(0)

        logger.info(
            f"Loaded candidate profile dynamically: {candidate_data.get('first_name')} {candidate_data.get('last_name')}"
        )

        # 2. Download resume dynamically if provided
        resume_url = candidate_data.get("resume_url", "")
        if resume_url:
            downloaded_pdf_path = resume_downloader.download(resume_url)
            if downloaded_pdf_path:
                candidate_data["resume_path"] = downloaded_pdf_path
            else:
                logger.error(
                    "[ERROR] Could not download resume PDF. Check URL/permissions. Proceeding may fail uploads."
                )

        # 3. Execute Engine using purely network data
        runner = EngineRunner()
        runner.run(site_filter=args.site, candidate_data=candidate_data)

    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
