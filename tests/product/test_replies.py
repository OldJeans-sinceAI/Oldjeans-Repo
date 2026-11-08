import copy
import unittest
from unittest.mock import Mock
from pathlib import Path
import json
from jsonschema import Draft202012Validator
from app.replies import OwnerReplies
from app.teammate.reply_engine import Reply

P = {
    "version": 3,
    "entity_id": "A",
    "timezone": "Europe/Helsinki",
    "change": {"kind": "DATE_HOURS", "date": "2026-12-24", "hours": "07:30-13:00"},
}


class RepliesTests(unittest.TestCase):
    def adapter(self, reply=None, configured=True):
        e = Mock(configured=configured, model="test", timeout=8.0)
        e.interpret.return_value = reply or Reply(
            "OK", "EDIT", "07:30-15:00", "2026-12-24", True, False
        )
        return OwnerReplies(e), e

    def test_no_model_for_exact_buttons_and_hours(self):
        a, e = self.adapter()
        for text, intent in [
            ("yes", "APPROVE"),
            ("no", "REJECT"),
            ("09:00-16:00", "EDIT"),
        ]:
            self.assertEqual(a.interpret(text, "en", P)["intent"], intent)
        e.interpret.assert_not_called()

    def test_edit_is_draft_only_and_bound_to_proposal(self):
        a, e = self.adapter()
        before = copy.deepcopy(P)
        result = a.interpret("Please close at 15:00 instead", "en", P)
        self.assertEqual(
            result["decision_draft"],
            {
                "proposal_version": 3,
                "decision": "EDIT",
                "edited_change": {
                    "kind": "DATE_HOURS",
                    "date": "2026-12-24",
                    "hours": "07:30-15:00",
                },
                "confirmed": True,
            },
        )
        self.assertEqual(P, before)
        sent = e.interpret.call_args.args[0]
        self.assertNotIn("entity_id", sent)
        self.assertNotIn("version", sent)
        schemas = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "config/openapi.json"
            ).read_text()
        )["components"]["schemas"]
        Draft202012Validator(
            {
                "$ref": "#/components/schemas/InterpretResponse",
                "components": {"schemas": schemas},
            }
        ).validate(result)

    def test_outage_never_generates_decision(self):
        for code in [
            "TIMEOUT",
            "RATE_LIMITED",
            "AUTH_ERROR",
            "PROVIDER_UNAVAILABLE",
            "INVALID_OUTPUT",
        ]:
            a, _ = self.adapter(Reply("UNAVAILABLE", error_code=code))
            d = a.interpret("Looks good, go ahead", "en", P)
            self.assertEqual(d["status"], "UNAVAILABLE")
            self.assertNotIn("decision_draft", d)

    def test_invalid_hours_scope_and_uncertainty_need_clarification(self):
        for r in [
            Reply("OK", "EDIT", "25:00-27:00", "2026-12-24", True, False),
            Reply("OK", "EDIT", "09:00-16:00", "2026-12-25", True, False),
            Reply("OK", "EDIT", "09:00-16:00", "2026-12-24", False, False),
            Reply("OK", "APPLY", "", "", True, True),
            Reply("OK"),
        ]:
            a, _ = self.adapter(r)
            d = a.interpret("a complex reply", "en", P)
            self.assertEqual(d["status"], "NEEDS_CLARIFICATION")
            self.assertNotIn("decision_draft", d)

    def test_input_dates_independently_restrict_model(self):
        a, _ = self.adapter(Reply("OK", "APPLY", "", "2026-12-24", True, False))
        self.assertEqual(
            a.interpret("Approve 2026-12-25", "en", P)["status"], "NEEDS_CLARIFICATION"
        )
        self.assertEqual(
            a.interpret("Looks good, go ahead", "en", P, True)["status"],
            "NEEDS_CLARIFICATION",
        )
        self.assertEqual(
            a.interpret("Approve 2026-12-24", "en", P, True)["status"], "READY"
        )

    def test_complex_negation_never_uses_old_closed_rule(self):
        a, e = self.adapter(Reply("OK"))
        d = a.interpret("Do not close, unless it rains", "en", P)
        e.interpret.assert_called_once()
        self.assertNotIn("decision_draft", d)

    def test_offline_complex_reply_keeps_pending(self):
        a, _ = self.adapter(configured=False)
        self.assertEqual(
            a.interpret("maybe five", "en", P)["status"], "NEEDS_CLARIFICATION"
        )

    def test_multilingual_exact_replies(self):
        a, _ = self.adapter()
        for text, language, intent in [
            ("ja", "sv", "APPROVE"),
            ("nej", "sv", "REJECT"),
            ("nei", "nb", "REJECT"),
            ("네", "ko", "APPROVE"),
            ("아니요", "ko", "REJECT"),
            ("suljettu", "fi", "EDIT"),
            ("closed", "en", "EDIT"),
        ]:
            with self.subTest(text=text, language=language):
                res = a.interpret(text, language, P)
                self.assertEqual(res["intent"], intent)
                self.assertEqual(res["status"], "READY")
                self.assertEqual(res["interpretation"]["provider"], "RULES")

    def test_health_response(self):
        a, _ = self.adapter(configured=True)
        h = a.health()
        self.assertEqual(h["provider"], "GEMINI")
        self.assertTrue(h["configured"])
        self.assertEqual(h["model"], "test")

        a_off, _ = self.adapter(configured=False)
        h_off = a_off.health()
        self.assertEqual(h_off["provider"], "RULES")
        self.assertFalse(h_off["configured"])
        self.assertIsNone(h_off["model"])


class ReplyServiceTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from test_backend import FakeClient, FakeData, NOW
        from app.service import Service

        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.client = FakeClient()
        self.s = Service(
            state_dir=self.tmp.name,
            mode="mock",
            now=NOW,
            client=self.client,
            data=FakeData(),
        )
        cycle = self.s.cycle(
            {"scope": "EXPLICIT_DATES", "entity_ids": ["A"], "dates": ["2026-12-24"]}
        )
        case = self.s.store.get("cases", cycle["case_ids"][0])
        self.p = self.s.proposal(case["proposal_id"])
        engine = Mock(configured=True, model="test", timeout=8.0)
        engine.interpret.return_value = Reply(
            "OK", "EDIT", "07:30-15:00", "2026-12-24", True, False
        )
        self.s.replies = OwnerReplies(engine)

    def test_gemini_preview_does_not_write_until_confirmed(self):
        d = self.s.interpret(
            self.p["proposal_id"],
            {"text": "Please close at 15:00 instead", "language": "en"},
        )
        self.assertEqual(self.p["decision_status"], "PENDING")
        self.assertEqual(self.client.puts, [])
        r = self.s.decide(self.p["proposal_id"], d["decision_draft"], "confirmed-edit")
        self.assertEqual(r["application_status"], "SUCCEEDED")
        self.assertEqual(len(self.client.puts), 1)

    def test_decided_and_expired_proposals_never_call_provider(self):
        from app.service import AppError

        for state in ["REJECTED", "EXPIRED"]:
            self.p["decision_status"] = state
            with self.assertRaises(AppError):
                self.s.interpret(
                    self.p["proposal_id"],
                    {"text": "Looks good, go ahead", "language": "en"},
                )
        self.s.replies.engine.interpret.assert_not_called()
