import argparse
import json
import os
import sys

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.backend_client import backend_client
from core.logger import logger
from core.trigger_payload import ensure_workflow_log_ids, merge_orchestration_into_run_params
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

    if args.max_apps is not None:
        settings.MAX_APPLICATIONS_PER_RUN = args.max_apps
        logger.info(f"[LIMIT] {args.max_apps} applications per run")

    workflow_log_id = None
    try:
        # 1. Fetch run_parameters strictly from the backend API
        candidate_data = backend_client.fetch_pending_candidates()

        if not candidate_data:
            logger.info("[STOP] No pending candidate found from backend API. Exiting.")
            sys.exit(0)

        # 2. Build structured run_parameters from the backend payload
        from core.run_parameters_builder import run_parameters_builder
        run_parameters = run_parameters_builder.build(candidate_data)
        applicant = run_parameters.get('applicant', {})
        logger.info(f"Successfully built run_parameters for: "
                    f"{applicant.get('first_name')} {applicant.get('last_name')}")

        # 3. Save built run_parameters back to backend DB UI
        candidate_id = candidate_data.get("candidate_id")
        if candidate_id:
            backend_client.update_run_parameters(candidate_id, run_parameters)

        # 4. Execute Engine with run_parameters
        runner = EngineRunner()
        runner.run(
            site_filter=args.site,
            candidate_data=run_parameters,
            workflow_log_id=workflow_log_id,
        )

    except Exception as e:
        if workflow_log_id:
            log_content = ""
            try:
                with open("logs/scheduler_run.log", "r", encoding="utf-8", errors="ignore") as f:
                    log_content = f.read()
            except Exception:
                pass
                
            backend_client.update_workflow_log(
                workflow_log_id,
                "failed",
                error_summary=str(e)[:255],
                logfile=log_content,
            )
        logger.critical(f"Fatal error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
