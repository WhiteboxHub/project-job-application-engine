"""
Normalize weekly-workflow trigger API responses and orchestration fields.

Backends may return flat candidate rows, wrapped {data: ...}, camelCase keys,
or omit workflow_id/run_id (scheduler only queues the candidate). We merge
nested shapes, map aliases, then apply defaults so orchestrator logs always
get a stable workflow_id + run_id when a run proceeds.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Tuple

from config.settings import settings
from core.logger import logger

# Nested blobs merged first; outer keys then overlay (orchestration often on wrapper).
_NESTED_PAYLOAD_KEYS: Tuple[str, ...] = (
    "data",
    "candidate",
    "payload",
    "result",
    "meta",
    "orchestration",
)

_ORCH_ALIASES: Dict[str, Tuple[str, ...]] = {
    "workflow_id": (
        "workflow_id",
        "workflowId",
        "automation_workflow_id",
        "automationWorkflowId",
    ),
    "schedule_id": ("schedule_id", "scheduleId"),
    "run_id": ("run_id", "runId", "execution_run_id", "executionRunId"),
    "candidate_id": ("candidate_id", "candidateId"),
}


def normalize_trigger_body(data: Any) -> Dict[str, Any]:
    """
    Return a single flat dict suitable for RunParametersBuilder and merge.

    - List responses: first non-empty dict (common for batch endpoints).
    - Wrapped responses: merge nested data/candidate/payload/meta/orchestration,
      then overlay top-level orchestration keys from the wrapper.
    """
    if data is None or data == "" or isinstance(data, str):
        return {}
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item:
                return normalize_trigger_body(item)
        return {}
    if not isinstance(data, dict):
        return {}

    has_nested = any(
        k in data and isinstance(data.get(k), Mapping) for k in _NESTED_PAYLOAD_KEYS
    )
    if not has_nested:
        return dict(data)

    merged: Dict[str, Any] = {}
    for nk in _NESTED_PAYLOAD_KEYS:
        blob = data.get(nk)
        if isinstance(blob, Mapping):
            merged.update(dict(blob))
    for k, v in data.items():
        if k in _NESTED_PAYLOAD_KEYS:
            continue
        if v is not None:
            merged[k] = v
    return merged


def merge_orchestration_into_run_params(
    candidate_data: Mapping[str, Any], run_parameters: MutableMapping[str, Any]
) -> None:
    """
    Copy workflow_id, schedule_id, run_id, candidate_id from payload into run_parameters.

    Checks top-level, run_parameters sub-dict, data wrapper, and camelCase aliases.
    """
    nested = candidate_data.get("run_parameters")
    if not isinstance(nested, dict):
        nested = {}
    wrapped = candidate_data.get("data")
    if not isinstance(wrapped, dict):
        wrapped = {}
    sources: Iterable[Mapping[str, Any]] = (
        candidate_data,
        wrapped,
        nested,
    )

    for canon, aliases in _ORCH_ALIASES.items():
        for src in sources:
            for alias in aliases:
                if alias in src and src[alias] is not None:
                    run_parameters[canon] = src[alias]
                    break
            else:
                continue
            break


def ensure_workflow_log_ids(run_parameters: MutableMapping[str, Any]) -> None:
    """
    If API omitted orchestration ids, use configured workflow id and a new UUID run_id
    so POST /orchestrator/logs + PUT execution_metadata still work (Task Scheduler runs).
    """
    wf = run_parameters.get("workflow_id")
    if wf is None:
        run_parameters["workflow_id"] = settings.WEEKLY_WORKFLOW_ID
        logger.info(
            "[WORKFLOW_LOG] workflow_id missing in trigger payload; "
            f"using WEEKLY_WORKFLOW_ID={settings.WEEKLY_WORKFLOW_ID}."
        )

    rid = run_parameters.get("run_id")
    if rid is None or (isinstance(rid, str) and not str(rid).strip()):
        run_parameters["run_id"] = str(uuid.uuid4())
        logger.info(
            "[WORKFLOW_LOG] run_id missing in trigger payload; generated new UUID run_id."
        )
