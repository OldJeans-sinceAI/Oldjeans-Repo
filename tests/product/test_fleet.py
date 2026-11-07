import copy
import tempfile
import unittest
from unittest.mock import Mock
from app.fleet import FleetRunner
from app.service import Service, AppError
from test_backend import FakeClient, FakeData, NOW


class FleetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = FakeClient()
        self.data = FakeData()
        self.client.list_entities = lambda limit=100: iter(
            copy.deepcopy(list(self.client.entities.values()))
        )
        self.s = Service(
            state_dir=self.tmp.name, now=NOW, client=self.client, data=self.data
        )
        self.f = FleetRunner(self.s)
        self.addCleanup(self.f.close)

    def wait(self):
        self.f.thread.join(5)
        self.assertFalse(self.f.active)
        return self.f.get()["run"]

    def scan(self):
        self.f.start({"scope": "EXPLICIT_DATE", "date": "2026-12-24"})
        return self.wait()

    def test_all_companies_no_apply_even_with_permission(self):
        self.s.matching_permission = Mock(
            return_value={"permission_id": "would-approve"}
        )
        j = self.scan()
        self.assertEqual(j["status"], "COMPLETED")
        self.assertEqual(j["processed_businesses"], 2)
        self.assertEqual(j["case_count"], 2)
        self.assertEqual(sum(j["counts"].values()), 2)
        self.assertEqual(j["ready_businesses"], 1)
        self.assertEqual(self.client.puts, [])
        self.s.matching_permission.assert_not_called()
        self.assertEqual(self.s.store.data["messages"], {})

    def test_contact_separate_deduplicated_and_pending(self):
        j = self.scan()
        for _ in range(2):
            self.f.prepare_contacts(j["run_id"], {"delivery_mode": "PREVIEW"})
            j = self.wait()
        self.assertEqual(j["contact_counts"], {"DELIVERED_SIMULATED": 1})
        self.assertEqual(len(self.s.store.data["messages"]), 1)
        self.assertEqual(self.client.puts, [])
        self.assertTrue(
            all(
                p["decision_status"] == "PENDING"
                for p in self.s.store.data["proposals"].values()
            )
        )
        self.assertFalse(
            any("token" in str(k) for k in self.f.state.data["jobs"][j["run_id"]])
        )

    def test_opt_out_and_pause_hold_for_demo_contact(self):
        self.data.contacts["A"]["opted_out_of_suggestions"] = "1"
        j = self.scan()
        self.f.prepare_contacts(j["run_id"], {"delivery_mode": "PREVIEW"})
        j = self.wait()
        self.assertEqual(j["contact_counts"], {"BLOCKED_OPT_OUT": 1})
        self.assertEqual(self.s.messages()["items"][0].get("owner_entry_path"), None)
        self.data.contacts["A"]["opted_out_of_suggestions"] = "0"
        self.s.store.data["preferences"]["A"] = {"frequency": "PAUSED", "version": 1}
        self.f.prepare_contacts(j["run_id"], {"delivery_mode": "SCHEDULED"})
        j = self.wait()
        self.assertEqual(j["contact_counts"], {"BLOCKED_PAUSED": 1})

    def test_scheduled_obeys_next_contact_and_no_decision(self):
        j = self.scan()
        self.f.prepare_contacts(j["run_id"], {"delivery_mode": "SCHEDULED"})
        j = self.wait()
        m = self.s.messages()["items"][0]
        self.assertEqual(m["status"], "QUEUED")
        self.assertEqual(m["scheduled_at"], self.s.preferences("A")["next_contact_at"])
        self.assertNotIn("owner_entry_path", m)
        self.assertEqual(self.client.puts, [])

    def test_message_filter_keeps_preview_and_schedule_separate(self):
        j = self.scan()
        self.f.prepare_contacts(j["run_id"], {"delivery_mode": "SCHEDULED"})
        self.wait()
        self.f.prepare_contacts(j["run_id"], {"delivery_mode": "PREVIEW"})
        self.wait()
        previews = self.s.messages(delivery_mode="PREVIEW")
        scheduled = self.s.messages(delivery_mode="SCHEDULED")
        self.assertEqual(previews["total"], 1)
        self.assertEqual(scheduled["total"], 1)
        self.assertIn("owner_entry_path", previews["items"][0])
        self.assertNotIn("owner_entry_path", scheduled["items"][0])

    def test_inbox_tokens_save_once_and_keep_owner_scope(self):
        j = self.scan()
        self.f.prepare_contacts(j["run_id"], {"delivery_mode": "PREVIEW"})
        self.wait()
        message = next(iter(self.s.store.data["messages"].values()))
        duplicate = copy.deepcopy(message)
        duplicate["message_id"] = "another-message"
        self.s.store.put("messages", "another-message", duplicate)
        save = self.s.auth.save
        self.s.auth.save = Mock(wraps=save)
        messages = self.s.messages()["items"]
        self.s.auth.save.assert_called_once()
        self.assertEqual(len(messages), 2)
        for m in messages:
            token = m["owner_entry_path"].split("#token=")[1]
            scope, _ = self.s.exchange_token(token)
            self.assertEqual(scope["entity_id"], m["entity_id"])
            self.assertEqual(scope["proposal_ids"], m["proposal_ids"])

    def test_missing_live_entity_is_gap_not_no_action(self):
        del self.client.entities["B"]
        j = self.scan()
        self.assertEqual(j["status"], "COMPLETED_WITH_ERRORS")
        self.assertEqual(j["failed_businesses"], 1)
        self.assertEqual(j["case_count"], 1)
        self.assertEqual(j["errors"][0]["entity_id"], "B")

    def test_active_run_blocks_duplicate_and_restart_marks_interrupted(self):
        self.f.active = True
        with self.assertRaises(AppError):
            self.f.start({"scope": "OPERATIONAL"})
        self.f.active = False
        j = self.scan()
        self.f.state.data["jobs"][j["run_id"]]["status"] = "RUNNING"
        self.f.state.save()
        reopened = FleetRunner(self.s)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get()["run"]["status"], "INTERRUPTED")

    def test_read_failure_reports_failed_not_complete(self):
        self.client.list_entities = Mock(
            side_effect=RuntimeError("private provider text")
        )
        j = self.scan()
        self.assertEqual(j["status"], "FAILED")
        self.assertEqual(j["processed_businesses"], 0)
        self.assertNotIn("private", str(j))

    def test_sandbox_is_not_mass_write_target(self):
        self.s.mode = "sandbox"
        with self.assertRaises(AppError):
            self.f.start({"scope": "OPERATIONAL"})
