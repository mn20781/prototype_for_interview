from __future__ import annotations

import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402


class SentinelMiniEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()

    def test_happy_path_extracts_tasks_with_deadlines(self) -> None:
        response = self.client.post(
            "/api/assist/process",
            json={
                "text": (
                    "Find the key points in this research note and turn them into 3 actionable tasks "
                    "with deadlines if mentioned. We need to finalize the ad copy by Friday. "
                    "John should schedule the vendor call on 2026-05-20. "
                    "Also prepare the launch checklist by next week."
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()

        self.assertEqual(payload["intent"], "create_tasks")
        self.assertGreaterEqual(len(payload["tasks"]), 2)
        self.assertTrue(any(task.get("deadline") == "Friday" for task in payload["tasks"]))
        self.assertTrue(payload["validation"]["passed"])
        self.assertGreaterEqual(len(payload["trace"]), 4)

    def test_missing_deadline_triggers_confirmation_gate(self) -> None:
        response = self.client.post(
            "/api/assist/process",
            json={
                "text": (
                    "Create tasks from this note. Review the partner feedback with legal. "
                    "Draft the reply to the CFO. Confirm the launch checklist by 2026-05-30."
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()

        self.assertEqual(payload["intent"], "create_tasks")
        self.assertLess(payload["confidence"], 0.8)
        self.assertTrue(payload["confirmation_gate"]["required"])
        self.assertEqual(payload["confirmation_gate"]["reason"], "missing_deadline")

    def test_short_input_needs_clarification(self) -> None:
        response = self.client.post(
            "/api/assist/process",
            json={"text": "Help?"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()

        self.assertEqual(payload["intent"], "needs_clarification")
        self.assertTrue(payload["confirmation_gate"]["required"])
        self.assertTrue(payload["validation"]["passed"])


if __name__ == "__main__":
    unittest.main()
