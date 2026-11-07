"""Demo presentation must preserve source records and work without Gemini."""

import copy
import unittest
from unittest.mock import Mock

from app.replies import OwnerReplies
import test_backend


class EnglishDemoTests(unittest.TestCase):
    setUp = test_backend.ProductTests.setUp
    tearDown = test_backend.ProductTests.tearDown
    proposal = test_backend.ProductTests.proposal

    def test_existing_foreign_language_message_renders_english_without_rewriting(self):
        p = self.proposal()
        self.data.contacts["A"].update(
            preferred_language="fi", preferred_channel="EMAIL"
        )
        body = dict(
            entity_id="A", proposal_ids=[p["proposal_id"]], delivery_mode="PREVIEW"
        )
        message = self.s.create_message(body)
        stored = self.s.store.get("messages", message["message_id"])
        stored.update(language="fi", text="Hei! Vahvista aukioloajat.")
        original = copy.deepcopy(stored)
        for rendered in (
            self.s.messages()["items"][0],
            self.s.create_message(body),
            self.s.create_message(body, include_entry=False),
        ):
            self.assertEqual(rendered["language"], "en")
            self.assertIn("Currently shown", rendered["text"])
            self.assertNotIn("Vahvista", rendered["text"])
        self.assertEqual(
            self.s.messages()["items"][0]["subject"],
            "Confirm your special opening hours",
        )
        self.assertEqual(stored, original)
        self.assertEqual(self.s.preferences("A")["preferred_language"], "fi")

    def test_new_messages_are_english_in_storage_and_on_all_delivery_paths(self):
        p = self.proposal()
        for mode in ("PREVIEW", "SCHEDULED"):
            with self.subTest(mode=mode):
                message = self.s.create_message(
                    dict(
                        entity_id="A",
                        proposal_ids=[p["proposal_id"]],
                        delivery_mode=mode,
                    ),
                    include_entry=False,
                )
                self.assertEqual(message["language"], "en")
                self.assertEqual(
                    self.s.store.get("messages", message["message_id"])["language"],
                    "en",
                )
                self.assertIn("Approve / Edit / No thanks", message["text"])
        self.assertEqual(self.s.preferences("A")["preferred_language"], "fi")

    def test_no_model_keeps_ambiguous_reply_pending_then_confirms_exact_edit(self):
        p = self.proposal()
        engine = Mock(configured=False, model="offline", timeout=8.0)
        self.s.replies = OwnerReplies(engine)
        for text in ("Maybe close at five", "Please close at 15:00 instead"):
            result = self.s.interpret(p["proposal_id"], dict(text=text, language="en"))
            self.assertEqual(result["status"], "NEEDS_CLARIFICATION")
            self.assertNotIn("decision_draft", result)
            self.assertEqual(p["decision_status"], "PENDING")
            self.assertEqual(self.client.puts, [])
        result = self.s.interpret(
            p["proposal_id"], dict(text="07:30-15:00", language="en")
        )
        self.assertEqual(result["interpretation"]["provider"], "RULES")
        self.assertEqual(self.client.puts, [])
        final = self.s.decide(
            p["proposal_id"], result["decision_draft"], "offline-confirmed-edit"
        )
        self.assertEqual(final["application_status"], "SUCCEEDED")
        self.assertEqual(final["final_change"]["hours"], "07:30-15:00")
        engine.interpret.assert_not_called()
