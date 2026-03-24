"""
Smoke test: POST /orchestrator/logs then PUT execution_metadata (same as runner).

Run from project root: python scripts/verify_orchestrator_log_put.py
Uses .env auth. Creates one real log row on the backend — use only when acceptable.
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from core.backend_client import backend_client


def main() -> int:
    run_id = str(uuid.uuid4())
    wf_id = int(settings.WEEKLY_WORKFLOW_ID)
    log_id = backend_client.create_workflow_log(
        wf_id,
        None,
        run_id,
        parameters_used={
            "source": "verify_orchestrator_log_put.py",
            "run_id": run_id,
        },
    )
    if log_id is None:
        print("FAIL: create_workflow_log returned no id (check auth / API).")
        return 1
    print(f"OK: POST created automation_workflow_logs id={log_id}")

    meta = {
        "workflow_key": "weekly_automation_application_engine",
        "status": "success",
        "verify_script": True,
        "run_id": run_id,
        "workflow_id": wf_id,
        "execution_summary": {
            "total_jobs_found": 0,
            "total_applications_attempted": 0,
            "total_applications_successful": 0,
            "total_applications_failed": 0,
        },
        "successful_applications": [],
        "failed_applications": [],
    }
    ok = backend_client.update_workflow_log(
        log_id,
        "success",
        records_processed=0,
        records_failed=0,
        execution_metadata=meta,
    )
    if ok:
        print(
            f"OK: PUT execution_metadata succeeded for id={log_id} "
            "(same path as EngineRunner after output.json)."
        )
        return 0
    print(f"FAIL: update_workflow_log did not return success for id={log_id}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
