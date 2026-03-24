"""
Backend Client - Communicates with wbl-backend to fetch weekly workflows.
"""

from datetime import datetime, timezone
from typing import Any

import requests

from config.settings import settings
from core.logger import logger
from core.wbl_api_auth import build_api_headers

# Must match automation_workflows.workflow_key in WBL (e.g. workflow id 7:
# "weekly_automation_application_engine") — same idea as hiring_cafe_job_extractor in Exec Metadata.
JOB_APPLICATION_ENGINE_WORKFLOW_KEY = "weekly_automation_application_engine"


def _merge_parameters_used(
    run_parameters: dict | None, report: dict | None
) -> dict[str, Any]:
    """
    Prefer non-null workflow identifiers from run_parameters so the UI log
    matches the schedule row even when output.json echoed null ids from the tracker.
    """
    from_report = (report or {}).get("parameters_used") or {}
    base = dict(from_report)
    rp = run_parameters or {}
    for key in ("workflow_id", "schedule_id", "run_id", "candidate_id"):
        v = rp.get(key)
        if v is not None:
            base[key] = v
    return base


def build_job_application_execution_metadata(report: dict | None) -> dict[str, Any]:
    """
    Structured execution_metadata for automation_workflow_log, aligned with
    hiring-cafe-engine (workflow key + summary fields + full output payload).
    """
    r = report or {}
    ex = r.get("execution_summary") or {}
    return {
        "workflow": JOB_APPLICATION_ENGINE_WORKFLOW_KEY,
        "timestamp": r.get("finished_at"),
        "total_jobs_found": ex.get("total_jobs_found"),
        "total_applications_successful": ex.get("total_applications_successful"),
        "total_applications_failed": ex.get("total_applications_failed"),
        "total_applications_attempted": ex.get("total_applications_attempted"),
        "run_status": r.get("status"),
        "candidate_name": r.get("candidate_name"),
        "output_json": r,
    }


class BackendClient:
    """Client for fetching candidate data from the wbl-backend."""

    @staticmethod
    def fetch_pending_candidates() -> dict:
        """
        Fetches the pending candidate run JSON from the backend trigger endpoint.
        Returns the parsed JSON response if successful, or {} on failure/empty.
        """
        if not settings.BACKEND_URL or not settings.TRIGGER_ENDPOINT:
            logger.error(
                "Missing backend API configuration (BACKEND_URL or TRIGGER_ENDPOINT)."
            )
            return {}

        # Merge URL robustly using URL joining to prevent double slashes
        base = settings.BACKEND_URL.rstrip("/")
        endpoint = settings.TRIGGER_ENDPOINT.lstrip("/")
        url = f"{base}/{endpoint}"

        headers = build_api_headers(json_body=False)

        logger.info(f"Fetching run_parameters from Backend API: {url}...")

        try:
            response = requests.get(url, headers=headers, timeout=15)
            # Backend may return 404 or empty list if no candidate is pending
            if response.status_code == 200:
                data = response.json()
                # Backend endpoint could return an array, dict, or message string
                if data:
                    logger.info(
                        "Successfully fetched candidate run_parameters from backend."
                    )
                    return data
                else:
                    logger.info("No active candidates to process according to backend.")
                    return {}
            else:
                logger.warning(
                    f"Backend API returned status {response.status_code}: {response.text}"
                )
                return {}

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with Backend API: {e}")
            return {}

    @staticmethod
    def update_run_parameters(candidate_id: int, parameters: dict) -> bool:
        """Saves the completely built run_parameters JSON back to the DB."""
        if not settings.BACKEND_URL:
            return False

        base = settings.BACKEND_URL.rstrip("/")
        url = f"{base}/weekly-workflow/update-parameters/{candidate_id}"

        headers = build_api_headers(json_body=True)

        try:
            logger.info(f"Saving run_parameters back to DB UI for candidate {candidate_id}...")
            response = requests.post(url, headers=headers, json=parameters, timeout=15)
            if response.status_code == 200:
                logger.info("Successfully updated database UI with generated run_parameters!")
                return True
            else:
                logger.warning(f"Failed to save to DB UI. Status {response.status_code}: {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to communicate with DB UI: {e}")
            return False

    @staticmethod
    def create_workflow_log(run_parameters: dict) -> bool:
        """
        Creates a running execution log entry in automation_workflow_log.
        Safe no-op when workflow metadata is unavailable.
        """
        if not settings.BACKEND_URL:
            return False

        workflow_id = run_parameters.get("workflow_id")
        run_id = run_parameters.get("run_id")
        if not workflow_id or not run_id:
            logger.info(
                "Skipping workflow log creation (missing workflow_id or run_id in run_parameters)."
            )
            return False

        url = f"{settings.BACKEND_URL.rstrip('/')}/automation-workflow-log/"
        headers = build_api_headers(json_body=True)

        payload = {
            "workflow_id": workflow_id,
            "schedule_id": run_parameters.get("schedule_id"),
            "run_id": run_id,
            "status": "running",
            "parameters_used": run_parameters,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code in (200, 201):
                logger.info(
                    f"Created workflow execution log for run_id={run_id}, workflow_id={workflow_id}."
                )
                return True
            logger.warning(
                f"Failed creating workflow log. Status {response.status_code}: {response.text}"
            )
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Workflow log create call failed: {e}")
            return False

    @staticmethod
    def update_workflow_log(run_parameters: dict, report: dict, error: str | None = None) -> bool:
        """
        Updates automation_workflow_log by run_id with final execution JSON metadata.
        """
        if not settings.BACKEND_URL:
            return False

        run_id = (run_parameters or {}).get("run_id")
        if not run_id:
            logger.info("Skipping workflow log update (missing run_id in run_parameters).")
            return False

        url = f"{settings.BACKEND_URL.rstrip('/')}/automation-workflow-log/by-run-id/{run_id}"
        headers = build_api_headers(json_body=True)

        execution_summary = (report or {}).get("execution_summary", {})
        records_processed = execution_summary.get("total_applications_successful", 0)
        records_failed = execution_summary.get("total_applications_failed", 0)
        final_status = (report or {}).get("status", "failed")
        status_map = {
            "success": "success",
            "completed_with_errors": "partial_success",
            "failed": "failed",
        }

        payload = {
            "status": status_map.get(final_status, "failed"),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "records_processed": records_processed,
            "records_failed": records_failed,
            "parameters_used": _merge_parameters_used(run_parameters, report),
            "execution_metadata": build_job_application_execution_metadata(report),
        }
        if error:
            payload["status"] = "failed"
            payload["error_summary"] = str(error)

        try:
            response = requests.patch(url, headers=headers, json=payload, timeout=20)
            if response.status_code == 200:
                logger.info(f"Updated workflow execution log for run_id={run_id}.")
                return True
            logger.warning(
                f"Failed updating workflow log. Status {response.status_code}: {response.text}"
            )
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Workflow log update call failed: {e}")
            return False


backend_client = BackendClient()
