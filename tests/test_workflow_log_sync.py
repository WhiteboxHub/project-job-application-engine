"""
Unit tests: orchestrator log PUT sends execution_metadata (output.json shape).
Run: python -m unittest tests.test_workflow_log_sync -v
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from core.backend_client import BackendClient


class TestWorkflowLogSync(unittest.TestCase):
    def test_update_workflow_log_serializes_execution_metadata(self):
        """Non-JSON-native values are coerced via default=str; PUT receives a dict."""
        sample_report = {
            "status": "success",
            "workflow_key": "weekly_automation_application_engine",
            "execution_summary": {
                "total_applications_successful": 1,
                "total_applications_failed": 0,
            },
            "opaque": object(),  # becomes str via default=str
        }

        with patch("core.backend_client.settings") as mock_settings, patch(
            "core.backend_client._bearer_token", return_value="test-token"
        ), patch("core.backend_client.requests.put") as mock_put:
            mock_settings.BACKEND_URL = "https://example.com/api"
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = '{"success": true}'
            mock_put.return_value = mock_resp

            ok = BackendClient.update_workflow_log(
                42,
                "success",
                records_processed=1,
                records_failed=0,
                execution_metadata=sample_report,
            )

            self.assertTrue(ok)
            mock_put.assert_called_once()
            _args, kwargs = mock_put.call_args
            sent = kwargs["json"]
            self.assertIn("execution_metadata", sent)
            meta = sent["execution_metadata"]
            self.assertEqual(meta["status"], "success")
            # round-trip stable
            json.dumps(meta)

    def test_create_workflow_log_accepts_201(self):
        with patch("core.backend_client.requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 201
            mock_resp.json.return_value = {"id": 99}
            mock_post.return_value = mock_resp

            with patch("core.backend_client.settings") as mock_settings:
                mock_settings.BACKEND_URL = "https://example.com/api"
                log_id = BackendClient.create_workflow_log(
                    7, None, "run-abc", parameters_used={"x": 1}
                )

            self.assertEqual(log_id, 99)


if __name__ == "__main__":
    unittest.main()
