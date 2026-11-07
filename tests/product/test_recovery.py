import copy, unittest
from pathlib import Path
from unittest.mock import patch
import test_backend as fixtures
from app.service import Service
from app.storage import StateStore, StateError
from app.domain import evaluate_context, parse_dt, hours_string_to_day


class RecoveryTests(unittest.TestCase):
    setUp = fixtures.ProductTests.setUp
    tearDown = fixtures.ProductTests.tearDown
    proposal = fixtures.ProductTests.proposal
    approve = fixtures.ProductTests.approve

    def test_AC15_crash_after_remote_write_before_result_saved(self):
        p = self.proposal()
        original = self.s.store.save
        failed = [False]

        def save():
            if not failed[0] and any(
                o["status"] == "SUCCEEDED"
                for o in self.s.store.data["operations"].values()
            ):
                failed[0] = True
                raise StateError("simulated loss after remote write")
            original()

        with patch.object(self.s.store, "save", save):
            with self.assertRaises(StateError):
                self.approve(p)
        self.assertEqual(len(self.client.puts), 1)
        restored = Service(
            state_dir=self.tmp.name,
            now=fixtures.NOW,
            client=self.client,
            data=self.data,
        )
        restored.tick()
        result = restored.decide(
            p["proposal_id"], dict(proposal_version=1, decision="APPROVE"), "decision-1"
        )
        self.assertEqual(result["application_status"], "SUCCEEDED")
        self.assertEqual(len(self.client.puts), 1)

    def test_AC15_permission_error_not_retried(self):
        p = self.proposal()

        def deny(method, path, body=None):
            self.client.puts.append((path, body))
            raise RuntimeError("PUT entities/A -> 403: permission denied")

        self.client._req = deny
        r = self.approve(p)
        self.assertEqual(len(self.client.puts), 1)
        self.assertEqual(r["application_status"], "FAILED")
        self.assertFalse(r["retryable"])

    def test_AC15_third_party_state_conflict(self):
        p = self.proposal()
        self.client.failure = "third"
        r = self.approve(p)
        self.assertEqual(r["application_status"], "CONFLICT")
        self.assertEqual(len(self.client.puts), 1)

    def test_AC16_missing_primary_does_not_silently_reset(self):
        self.proposal()
        Path(self.tmp.name, "state.json").unlink()
        with self.assertRaises(StateError):
            StateStore(str(Path(self.tmp.name, "state.json")))

    def test_AC17_bundle_ambiguity_and_gap(self):
        p = self.proposal(day="2026-11-07")
        q = self.proposal(day="2026-11-08")
        m = self.s.create_message(
            dict(
                entity_id="A",
                proposal_ids=[p["proposal_id"], q["proposal_id"]],
                delivery_mode="SCHEDULED",
            )
        )
        self.assertEqual(len(m["proposal_ids"]), 2)
        self.assertTrue(
            any(
                "CONTACT_WINDOW_GAP" in gap
                for gap in self.s.store.get("cases", p["case_id"])["gaps"]
            )
        )
        self.assertEqual(len(self.client.puts), 0)

    def test_AC21_standing_authorized_and_paused(self):
        self.s.create_permission(
            "A",
            dict(
                day_keys=["XMAS_EVE"],
                change_kind="DATE_HOURS",
                purpose="CORRECTION",
                expires_at="2027-01-01T00:00:00Z",
                confirmed=True,
            ),
        )
        p = self.proposal()
        self.assertEqual(p["decision_status"], "STANDING_AUTHORIZED")
        self.assertEqual(len(self.client.puts), 1)

    def test_AC22_permission_negation_and_split_edit(self):
        p = self.proposal()
        r = self.s.interpret(
            p["proposal_id"], dict(text="do not allow future changes", language="en")
        )
        self.assertNotEqual(r["intent"], "SET_STANDING_PERMISSION")
        r = self.s.interpret(
            p["proposal_id"], dict(text="09:00-12:00,13:00-18:00", language="en")
        )
        self.assertEqual(
            r["decision_draft"]["edited_change"]["hours"], "09:00-12:00,13:00-18:00"
        )
        self.assertEqual(len(self.client.puts), 0)

    def test_AC23_internal_weekly_proposal(self):
        hours = copy.deepcopy(fixtures.WEEK)
        hours["monday"] = hours_string_to_day("08:00-16:00")
        self.data.regular = {"A": [dict(effective_from="2026-11-10", hours=hours)]}
        d = evaluate_context(
            self.data.context("A", "2026-11-10", "REGULAR", "REGULAR"),
            parse_dt(fixtures.NOW),
        )["detection"]
        d["detection_id"] = "weekly-input"
        d["baseline"] = dict(
            kind="WEEKLY_HOURS",
            effective_from="2026-11-10",
            weekdays={"monday": "07:30-18:00"},
        )
        d["evidence"] = [
            dict(
                evidence_id="own",
                source_file="regular_hours_history.jsonl",
                source_record="A/2026-11-10",
                role="DIRECT",
                summary="Owner confirmed weekly schedule",
                known_at=fixtures.NOW,
            )
        ]
        c = self.s.ingest_detection(d)
        p = self.s.proposal(c["proposal_id"])
        self.assertEqual(p["change"]["kind"], "WEEKLY_HOURS")
        self.assertEqual(self.approve(p)["application_status"], "SCHEDULED")
        self.s.fixed_now = parse_dt("2026-11-12T10:00:00Z")
        self.s.tick()
        self.assertEqual(
            self.s.result(p["proposal_id"])["application_status"], "REVIEW_REQUIRED"
        )
        self.assertEqual(len(self.client.puts), 0)

    def test_AC24_internal_reopen_proposal(self):
        self.client.entities["A"]["hours"]["reopenDate"] = "2027-01-15"
        hours = dict(copy.deepcopy(fixtures.WEEK), reopenDate="2027-01-01")
        self.data.regular = {"A": [dict(effective_from="2026-11-01", hours=hours)]}
        d = evaluate_context(
            self.data.context("A", "2027-01-01", "NEW_YEARS_DAY", "PUBLIC_HOLIDAY"),
            parse_dt(fixtures.NOW),
        )["detection"]
        d["detection_id"] = "reopen-input"
        d["baseline"] = dict(kind="REOPEN_DATE", reopen_date="2027-01-15")
        d["evidence"] = [
            dict(
                evidence_id="own",
                source_file="regular_hours_history.jsonl",
                source_record="A/2026-11-01",
                role="DIRECT",
                summary="Owner reopening plan",
                known_at=fixtures.NOW,
            )
        ]
        c = self.s.ingest_detection(d)
        p = self.s.proposal(c["proposal_id"])
        self.assertEqual(p["change"]["reopen_date"], "2027-01-01")
        self.approve(p)
        self.assertEqual(self.client.entities["A"]["hours"]["reopenDate"], "2027-01-01")
        self.assertFalse(self.client.entities["A"]["closed"])

    def test_no_duplicate_proposal_for_already_approved_failed_write(self):
        p = self.proposal()
        self.client.failure = "before"
        self.approve(p)
        self.assertEqual(self.proposal()["proposal_id"], p["proposal_id"])
        self.assertEqual(len(self.s.store.data["proposals"]), 1)

    def test_cycle_identity_survives_restart(self):
        request = dict(scope="EXPLICIT_DATES", entity_ids=["A"], dates=["2026-12-24"])
        first = self.s.cycle(request)
        restarted = Service(
            state_dir=self.tmp.name,
            now=fixtures.NOW,
            client=self.client,
            data=self.data,
        )
        second = restarted.cycle(request)
        self.assertNotEqual(first["cycle_id"], second["cycle_id"])
