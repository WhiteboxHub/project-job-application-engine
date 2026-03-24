"""Tests for trigger response normalization and orchestration merge."""

import unittest
from unittest.mock import patch

from core import trigger_payload


class TestNormalizeTriggerBody(unittest.TestCase):
    def test_flat_dict_unchanged_shape(self):
        raw = {"candidate_id": 1, "email": "a@b.com"}
        out = trigger_payload.normalize_trigger_body(raw)
        self.assertEqual(out["candidate_id"], 1)
        self.assertEqual(out["email"], "a@b.com")

    def test_list_first_dict(self):
        raw = [{"candidate_id": 2}, {"candidate_id": 3}]
        out = trigger_payload.normalize_trigger_body(raw)
        self.assertEqual(out["candidate_id"], 2)

    def test_wrapper_merges_data_and_outer_workflow(self):
        raw = {
            "workflowId": 7,
            "data": {"candidate_id": 99, "email": "x@y.com"},
        }
        out = trigger_payload.normalize_trigger_body(raw)
        self.assertEqual(out["workflowId"], 7)
        self.assertEqual(out["candidate_id"], 99)
        self.assertEqual(out["email"], "x@y.com")


class TestMergeAndEnsure(unittest.TestCase):
    def test_merge_aliases_into_run_params(self):
        payload = {"workflowId": 42, "runId": "run-xyz", "scheduleId": 3, "candidateId": 8}
        rp: dict = {"applicant": {}}
        trigger_payload.merge_orchestration_into_run_params(payload, rp)
        self.assertEqual(rp["workflow_id"], 42)
        self.assertEqual(rp["run_id"], "run-xyz")
        self.assertEqual(rp["schedule_id"], 3)
        self.assertEqual(rp["candidate_id"], 8)

    @patch.object(trigger_payload.settings, "WEEKLY_WORKFLOW_ID", 7)
    def test_ensure_fills_missing_ids(self):
        rp: dict = {"applicant": {}}
        trigger_payload.ensure_workflow_log_ids(rp)
        self.assertEqual(rp["workflow_id"], 7)
        self.assertTrue(rp["run_id"])
        self.assertEqual(len(rp["run_id"]), 36)  # UUID string

    @patch.object(trigger_payload.settings, "WEEKLY_WORKFLOW_ID", 7)
    def test_ensure_preserves_api_ids(self):
        rp = {"workflow_id": 9, "run_id": "fixed-id"}
        trigger_payload.ensure_workflow_log_ids(rp)
        self.assertEqual(rp["workflow_id"], 9)
        self.assertEqual(rp["run_id"], "fixed-id")


if __name__ == "__main__":
    unittest.main()
