import copy
import io
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
from app.reset import ResetManager
from app.service import Service, AppError
from app.fleet import FleetRunner
from app.storage import StateError
from test_backend import FakeClient, FakeData, NOW


class ResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = FakeClient()
        self.original = copy.deepcopy(self.client.entities)
        self.client.list_entities = lambda limit=100: iter(
            copy.deepcopy(list(self.client.entities.values()))
        )
        self.s = Service(
            state_dir=self.tmp.name, now=NOW, client=self.client, data=FakeData()
        )
        self.f = FleetRunner(self.s)
        self.addCleanup(self.f.close)
        self.mock_reset = Mock(
            side_effect=lambda: setattr(
                self.client, "entities", copy.deepcopy(self.original)
            )
        )
        self.r = ResetManager(self.s, self.f, mock_reset=self.mock_reset)
        self.r._initial = Mock(return_value=copy.deepcopy(self.original))

    def apply(self):
        self.s.cycle(
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]}
        )
        p = next(reversed(self.s.store.data["proposals"].values()))
        token = self.s.mint_token("A", [p["proposal_id"]])
        self.s.decide(
            p["proposal_id"],
            {"decision": "APPROVE", "proposal_version": p["version"]},
            "approve-" + p["proposal_id"],
        )
        return token, p["proposal_id"]

    def body(self):
        return {
            "confirm_reset": True,
            "preview_token": self.r.preview()["preview_token"],
        }

    def sandbox(self):
        self.client.entities["TARGET"]["hours"] = {}
        self.s = Service(
            state_dir=self.tmp.name + "/sandbox",
            now=NOW,
            client=self.client,
            data=FakeData(),
            mode="sandbox",
            source_id="A",
            target_id="TARGET",
            allow_writes=True,
        )
        self.r = ResetManager(
            self.s, baseline={"sandbox": {"target_entity_id": "TARGET", "hours": {}}}
        )

    def test_mock_reset_backup_revocation_idempotency_and_replay(self):
        token, pid = self.apply()
        body = self.body()
        result = self.r.execute(body, "reset-1")
        self.assertEqual(self.client.entities, self.original)
        self.assertEqual(self.s.cases()["items"], [])
        self.assertEqual(self.s.store.data["operations"], {})
        self.assertEqual(
            self.s.store.data["watchlist"] if "watchlist" in self.s.store.data else {},
            {},
        )
        with self.assertRaises(AppError):
            self.s.exchange_token(token)
        self.assertEqual(self.r.execute(body, "reset-1"), result)
        self.mock_reset.assert_called_once()
        backup = self.s.state_dir / "reset-backups" / result["backup_id"]
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
        self.assertEqual((backup / "app-state.json").stat().st_mode & 0o777, 0o600)
        self.assertEqual(
            len(json.loads((backup / "app-state.json").read_text())["operations"]), 1
        )
        self.s.cycle(
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]}
        )
        new = next(iter(self.s.store.data["proposals"].values()))
        self.assertNotEqual(new["proposal_id"], pid)
        self.assertEqual(new["decision_status"], "PENDING")

    def test_stale_preview_and_active_job_block_before_backup(self):
        body = self.body()
        self.s.store.data["preferences"]["A"] = {"frequency": "PAUSED"}
        with self.assertRaises(AppError) as cm:
            self.r.execute(body, "stale")
        self.assertEqual(cm.exception.code, "RESET_PREVIEW_STALE")
        self.assertFalse((self.s.state_dir / "reset-backups").exists())
        self.f.active = True
        with self.assertRaises(AppError) as cm:
            self.r.preview()
        self.assertEqual(cm.exception.code, "RUN_ACTIVE")
        self.f.active = False

    def test_backup_failure_never_touches_remote(self):
        self.apply()
        body = self.body()
        with patch.object(self.r, "_archive", side_effect=OSError("disk unavailable")):
            with self.assertRaises(OSError):
                self.r.execute(body, "disk")
        self.mock_reset.assert_not_called()
        self.assertFalse(self.s.reset_blocked)
        self.assertEqual(len(self.s.store.data["operations"]), 1)

    def test_sandbox_restores_only_hours_and_rejects_external_changes(self):
        self.sandbox()
        self.apply()
        self.r.execute(self.body(), "real-reset")
        self.assertIsNone(self.client.puts[-1][1]["hours"])
        self.assertEqual(
            self.client.entities["TARGET"].get("name"),
            self.original["TARGET"].get("name"),
        )
        self.assertEqual(self.r.preview()["remote_changed"], False)
        self.client.entities["TARGET"]["hours"] = {"monday": {"isClosed": True}}
        with self.assertRaises(AppError) as cm:
            self.r.preview()
        self.assertEqual(cm.exception.code, "EXTERNAL_CHANGES")

    def test_sandbox_timeout_after_success_is_read_back_not_retried(self):
        self.sandbox()
        self.apply()
        original_put = self.client._req

        def uncertain(*args, **kwargs):
            original_put(*args, **kwargs)
            raise TimeoutError()

        self.client._req = uncertain
        result = self.r.execute(self.body(), "timeout")
        self.assertTrue(result["remote_verified"])
        self.assertEqual(len(self.client.puts), 2)

    def test_partial_reset_survives_restart_and_recovers_without_second_put(self):
        self.sandbox()
        token, _ = self.apply()
        body = self.body()
        save = self.s.store._atomic_write
        self.s.store._atomic_write = Mock(side_effect=StateError("disk"))
        with self.assertRaises(AppError) as cm:
            self.r.execute(body, "partial")
        self.assertEqual(cm.exception.code, "RESET_RECOVERY_REQUIRED")
        self.assertTrue(self.s.reset_blocked)
        self.assertEqual(len(self.s.store.data["operations"]), 1)
        self.s.store._atomic_write = save
        s = Service(
            state_dir=self.s.state_dir,
            now=NOW,
            client=self.client,
            data=FakeData(),
            mode="sandbox",
            source_id="A",
            target_id="TARGET",
            allow_writes=True,
        )
        r = ResetManager(s, baseline=self.r.baseline)
        self.assertTrue(s.reset_blocked)
        before = len(self.client.puts)
        result = r.execute(
            {"confirm_reset": True, "preview_token": r.preview()["preview_token"]},
            "recover",
        )
        self.assertTrue(result["remote_verified"])
        self.assertFalse(s.reset_blocked)
        self.assertEqual(len(self.client.puts), before)
        with self.assertRaises(AppError):
            s.exchange_token(token)

    def test_confirmation_target_and_original_dataset_guard(self):
        with self.assertRaises(AppError):
            self.r.execute({"confirm_reset": False}, "no")
        self.sandbox()
        self.r.baseline["sandbox"]["target_entity_id"] = "OTHER"
        with self.assertRaises(AppError) as cm:
            self.r.preview()
        self.assertEqual(cm.exception.code, "BASELINE_UNAVAILABLE")

    def test_mock_original_checksum_is_checked(self):
        self.r = ResetManager(self.s, self.f, mock_reset=self.mock_reset)
        self.r.baseline["mock_entities_sha256"] = "invalid"
        with self.assertRaises(AppError) as cm:
            self.r.preview()
        self.assertEqual(cm.exception.code, "BASELINE_CHANGED")

    def test_unchanged_mock_reset_accepts_actual_response_envelope_and_repeats(self):
        # The supplied server wraps every response in meta/response, including /mock/reset.
        self.client.base = "http://127.0.0.1:8787"
        self.r.mock_reset = self.r._reset_owned_mock
        self.s.cycle(
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]}
        )
        self.assertTrue(self.s.store.data["cases"])
        self.assertEqual(self.client.entities, self.original)
        with patch("app.reset.urllib.request.urlopen") as request:
            request.side_effect = lambda *a, **k: io.BytesIO(
                b'{"meta":{"errors":[]},"response":{"reset":true}}'
            )
            for i in range(2):
                result = self.r.execute(self.body(), "unchanged-" + str(i))
                self.assertEqual(result["status"], "COMPLETED")
                self.assertEqual(self.s.store.data["cases"], {})
                self.assertFalse(self.s.reset_blocked)
            self.assertEqual(request.call_count, 2)

    def test_mock_reset_rejects_missing_or_false_confirmation(self):
        self.client.base = "http://127.0.0.1:8787"
        for payload in (
            {"meta": {"errors": []}, "response": {}},
            {"meta": {"errors": []}, "response": {"reset": False}},
            {"meta": {"errors": [{"code": 500}]}, "response": {"reset": True}},
        ):
            with self.subTest(payload=payload):
                with patch(
                    "app.reset.urllib.request.urlopen",
                    return_value=io.BytesIO(json.dumps(payload).encode()),
                ):
                    with self.assertRaises(AppError) as cm:
                        self.r._reset_owned_mock()
                    self.assertEqual(cm.exception.code, "RESET_NOT_VERIFIED")
