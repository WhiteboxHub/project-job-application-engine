"""
Backend Client - Communicates with wbl-backend to fetch weekly workflows.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from config.settings import settings
from core.logger import logger
from core.trigger_payload import normalize_trigger_body


def _bearer_token() -> Optional[str]:
    """
    Prefer API_TOKEN, else login (AUTH_*), else INTERNAL_SECRET_KEY — same idea as hiring-cafe-engine.
    """
    if settings.API_TOKEN and str(settings.API_TOKEN).strip():
        return str(settings.API_TOKEN).strip()
    if all([settings.AUTH_URL, settings.AUTH_USERNAME, settings.AUTH_PASSWORD]):
        from core.auth_service import auth_service

        token = auth_service.get_access_token()
        if token:
            return token
    if settings.INTERNAL_SECRET_KEY:
        return settings.INTERNAL_SECRET_KEY
    return None


def _api_headers(*, json_body: bool = False) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if json_body:
        headers["Content-Type"] = "application/json"
    token = _bearer_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


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

        headers = _api_headers(json_body=False)
        params = {"workflow_id": settings.WEEKLY_WORKFLOW_ID}

        logger.info(
            f"Fetching run_parameters from Backend API: {url} "
            f"(workflow_id={settings.WEEKLY_WORKFLOW_ID})..."
        )

        try:
            response = requests.get(url, headers=headers, params=params, timeout=15)
            # Backend may return 404 or empty list if no candidate is pending
            if response.status_code == 200:
                data = response.json()
                # Backend endpoint could return an array, dict, or message string
                if not data:
                    logger.info("No active candidates to process according to backend.")
                    return {}
                normalized = normalize_trigger_body(data)
                if not normalized:
                    logger.info(
                        "No active candidates: trigger body empty after normalization."
                    )
                    return {}
                logger.info(
                    "Successfully fetched candidate run_parameters from backend."
                )
                return normalized
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

        headers = _api_headers(json_body=True)

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
    def _orchestrator_url(path: str) -> str:
        base = settings.BACKEND_URL.rstrip("/")
        suffix = path.lstrip("/")
        return f"{base}/orchestrator/{suffix}"

    @staticmethod
    def create_workflow_log(
        workflow_id: int,
        schedule_id: Optional[int],
        run_id: str,
        parameters_used: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        POST /orchestrator/logs — same pattern as hiring-cafe-engine scheduler.
        Returns new log row id, or None on failure.
        """
        if not settings.BACKEND_URL:
            logger.warning("BACKEND_URL not set; skipping automation_workflow_logs create.")
            return None

        url = BackendClient._orchestrator_url("logs")
        payload: Dict[str, Any] = {
            "workflow_id": workflow_id,
            "schedule_id": schedule_id,
            "run_id": run_id,
            "status": "running",
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
        if parameters_used is not None:
            payload["parameters_used"] = parameters_used

        try:
            response = requests.post(
                url, headers=_api_headers(json_body=True), json=payload, timeout=30
            )
            if response.status_code in (200, 201):
                try:
                    data = response.json()
                except Exception as parse_err:
                    logger.error(f"create_workflow_log: invalid JSON body: {parse_err}")
                    return None
                log_id = data.get("id")
                if log_id is not None:
                    try:
                        log_id_int = int(log_id)
                    except (TypeError, ValueError):
                        logger.warning(
                            f"create_workflow_log: non-numeric id in response {log_id!r}"
                        )
                        return None
                    logger.info(
                        f"Created automation_workflow_logs row id={log_id_int} run_id={run_id}"
                    )
                    return log_id_int
                logger.warning(
                    f"create_workflow_log: 200 but no 'id' in body keys={list(data.keys())} body={data!r}"
                )
                return None
            logger.warning(
                f"create_workflow_log failed: {response.status_code} {response.text}"
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"create_workflow_log request failed: {e}")
        return None

    @staticmethod
    def update_workflow_log(
        log_id: int,
        status: str,
        *,
        records_processed: int = 0,
        records_failed: int = 0,
        execution_metadata: Optional[Dict[str, Any]] = None,
        error_summary: Optional[str] = None,
    ) -> bool:
        """PUT /orchestrator/logs/{id} — persist execution_metadata (e.g. output.json payload)."""
        if not settings.BACKEND_URL:
            return False

        url = BackendClient._orchestrator_url(f"logs/{log_id}")
        payload: Dict[str, Any] = {
            "status": status,
            "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "records_processed": records_processed,
            "records_failed": records_failed,
        }
        if execution_metadata is not None:
            # Ensure JSON-serializable payload (mirrors hiring-cafe-engine passing plain dicts).
            try:
                payload["execution_metadata"] = json.loads(
                    json.dumps(execution_metadata, default=str)
                )
            except (TypeError, ValueError) as ser_err:
                logger.error(f"execution_metadata not JSON-serializable: {ser_err}")
                payload["execution_metadata"] = {"error": "serialization_failed", "detail": str(ser_err)}
        if error_summary is not None:
            payload["error_summary"] = error_summary

        try:
            response = requests.put(
                url, headers=_api_headers(json_body=True), json=payload, timeout=60
            )
            if response.status_code == 200:
                logger.info(
                    f"[WORKFLOW_LOG] PUT ok id={log_id} status={status} "
                    f"(execution_metadata={'yes' if execution_metadata is not None else 'no'})"
                )
                return True
            logger.error(
                f"update_workflow_log failed: {response.status_code} {response.text[:2000]}"
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"update_workflow_log request failed: {e}")
        return False


    @staticmethod
    def update_schedule(
        schedule_id: int,
        last_run_at: Optional[str] = None,
        next_run_at: Optional[str] = None,
    ) -> bool:
        """
        PUT /automation-workflow-schedule/{schedule_id}
        Updates last_run_at and next_run_at on the workflow schedule so the
        Workflows Scheduler UI always shows accurate timing after each engine run.
        """
        if not settings.BACKEND_URL or not schedule_id:
            return False

        base = settings.BACKEND_URL.rstrip("/")
        url = f"{base}/automation-workflow-schedule/{schedule_id}"
        payload: Dict[str, Any] = {}
        if last_run_at:
            payload["last_run_at"] = last_run_at
        if next_run_at:
            payload["next_run_at"] = next_run_at

        if not payload:
            return False

        try:
            response = requests.put(
                url, headers=_api_headers(json_body=True), json=payload, timeout=15
            )
            if response.status_code == 200:
                logger.info(
                    f"[SCHEDULE] Updated schedule id={schedule_id} "
                    f"last_run={last_run_at} next_run={next_run_at}"
                )
                return True
            logger.warning(
                f"[SCHEDULE] update_schedule failed: {response.status_code} {response.text[:200]}"
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"[SCHEDULE] update_schedule request failed: {e}")
        return False


backend_client = BackendClient()
