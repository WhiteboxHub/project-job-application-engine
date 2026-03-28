import argparse
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
        # 1. Fetch pending automation parameters from the Production API
        candidate_data = backend_client.fetch_pending_candidates()

        if not candidate_data:
            logger.info("[STOP] No pending weekly workflow candidate found. Exiting.")
            logger.info(
                "[EXIT] no_pending_candidate_from_api — engine did not run; "
                "no output.json from this process."
            )
            sys.exit(0)

        # 2. Transform the raw database row into structured run_parameters 
        # (This automatically downloads the folder link resume and extracts names!)
        from core.run_parameters_builder import run_parameters_builder
        run_parameters = run_parameters_builder.build(candidate_data)

        merge_orchestration_into_run_params(candidate_data, run_parameters)
        ensure_workflow_log_ids(run_parameters)

        logger.info("Successfully processed candidate into structured run_parameters JSON.")

        wf_id = run_parameters.get("workflow_id")
        sched_id = run_parameters.get("schedule_id")
        run_id = run_parameters.get("run_id")
        run_id_str = str(run_id).strip() if run_id is not None else ""
        if wf_id is not None and run_id_str:
            slim_params = {
                "candidate_id": run_parameters.get("candidate_id"),
                "workflow_id": wf_id,
                "schedule_id": sched_id,
                "run_id": run_id_str,
            }
            workflow_log_id = backend_client.create_workflow_log(
                int(wf_id),
                int(sched_id) if sched_id is not None else None,
                run_id_str,
                parameters_used=slim_params,
            )
            if workflow_log_id is not None:
                logger.info(
                    f"[WORKFLOW_LOG] Created row id={workflow_log_id}; will attach execution_metadata after run."
                )
            else:
                logger.warning(
                    "[WORKFLOW_LOG] create_workflow_log returned no id (check API response / auth)."
                )
        else:
            logger.warning(
                "[WORKFLOW_LOG] Skipping create: missing workflow_id or run_id in API payload. "
                f"workflow_id={wf_id!r} run_id={run_id!r} "
                f"top_level_keys={list(sorted(candidate_data.keys()))}"
            )

        # 3. Save the built JSON back to the backend Database so it appears in the UI
        candidate_id = candidate_data.get("candidate_id")
        if candidate_id:
            backend_client.update_run_parameters(candidate_id, run_parameters)

        # 4. Execute Engine using the pristine, fully-built JSON payload
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
