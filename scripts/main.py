import argparse
import json
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
        # 1. Fetch pending automation parameters from the Production API
        candidate_data = backend_client.fetch_pending_candidates()

        if not candidate_data:
            logger.info("[STOP] No pending weekly workflow candidate found. Exiting.")
            sys.exit(0)

        # 2. Transform the raw database row into structured run_parameters 
        # (This automatically downloads the folder link resume and extracts names!)
        from core.run_parameters_builder import run_parameters_builder
        run_parameters = run_parameters_builder.build(candidate_data)
        
        logger.info("Successfully processed candidate into structured run_parameters JSON.")

        # 3. Save the built JSON back to the backend Database so it appears in the UI
        candidate_id = candidate_data.get("candidate_id")
        if candidate_id:
            backend_client.update_run_parameters(candidate_id, run_parameters)

        # 3b. Create a "running" execution log row for workflow log grid (if metadata exists)
        backend_client.create_workflow_log(run_parameters)

        # 4. Execute Engine using the pristine, fully-built JSON payload
        runner = EngineRunner()
        runner.run(site_filter=args.site, candidate_data=run_parameters)

        # 5. Push final output.json metadata to workflow logs for UI visibility
        output_path = os.path.join("data", "output.json")
        report_payload = {}
        if os.path.exists(output_path):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    report_payload = json.load(f)
            except Exception as parse_err:
                logger.warning(f"Could not parse output report for workflow log update: {parse_err}")

        backend_client.update_workflow_log(run_parameters, report_payload)

    except Exception as e:
        # Attempt to mark workflow execution log as failed when run_id is available.
        try:
            if "run_parameters" in locals():
                backend_client.update_workflow_log(
                    run_parameters, {}, error=str(e)
                )
        except Exception:
            pass
        logger.critical(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
