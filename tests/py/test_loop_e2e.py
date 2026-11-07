"""End-to-end tests of the five-step loop (Detect -> Suggest -> Contact -> Decide -> Apply) on the mock.

Two layers:
  * QuickstartLoop  - drives examples/quickstart.py `run()` unchanged and asserts on what it prints / writes.
  * LoopBranches    - a thin orchestration written in the test from the PUBLIC pieces (Baseline, owner simulator
                      endpoint, YextClient) so each DECIDE outcome (approve / edit / reject / no reply) and the
                      'customer has the last word' guard can be forced deterministically.
No network, no real Yext. Each test starts from a reset mock.
"""
import contextlib
import io
import unittest
from datetime import date

import helpers
from helpers import DEMO_FI, XMAS_EVE, MockTestCase, http

import quickstart
from baseline import Baseline
from yext_client import YextClient, owner_response


def run_quickstart(base, eid, day):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        quickstart.run(eid, date.fromisoformat(day), base)
    return buf.getvalue()


class QuickstartLoop(MockTestCase):
    def holiday(self, eid, day):
        yx = YextClient(base_url=self.base, api_key="demo", v="20261106")
        return [h for h in yx.get_entity(eid)["hours"].get("holidayHours", []) if h["date"] == day]

    def test_happy_path_aurora_christmas_eve_all_five_steps(self):
        out = run_quickstart(self.base, DEMO_FI, XMAS_EVE)
        for marker in ("1 DETECT", "2 SUGGEST", "3 CONTACT", "4 DECIDE", "5 APPLY"):
            self.assertIn(marker, out)
        self.assertIn("07:30-18:00", out)                       # what Google currently shows
        self.assertIn("SUGGEST 07:30-13:00", out)
        self.assertIn("owner simulator → ACCEPTED", out)        # deterministic for this seed
        self.assertEqual(self.holiday(DEMO_FI, XMAS_EVE),
                         [{"date": XMAS_EVE, "openIntervals": [{"start": "07:30", "end": "13:00"}]}])
        self.assertIn("Google (Search & Maps)", out)            # confirmation: where the hours show
        self.assertIn("~2 min", out)

    def test_contact_message_finnish_has_reason_suggestion_and_three_buttons(self):
        out = run_quickstart(self.base, DEMO_FI, XMAS_EVE)
        self.assertIn("Hei Kahvila Aurora!", out)
        self.assertIn("Jouluaatto on torstaina 24.12.", out)
        self.assertIn("Viime vuonna olitte auki klo 7.30–13", out)         # the reason (last year)
        self.assertIn("Siksi Google näyttää nyt: auki klo 7.30–18", out)    # why it matters
        self.assertIn("Ehdotamme: 24.12. auki klo 7.30–13", out)           # the suggestion
        self.assertIn("[Hyväksy] [Muokkaa] [Ei kiitos]", out)              # Approve / Edit / Decline

    def test_contact_message_swedish_and_norwegian(self):
        sv = run_quickstart(self.base, "SE-D0008", XMAS_EVE)
        self.assertIn("Hej Kafé Linnea!", sv)
        self.assertIn("[Godkänn] [Ändra] [Nej tack]", sv)
        self.assertIn("Vi föreslår: 24/12 stängt", sv)       # Swedish date style d/m
        no = run_quickstart(self.base, "NO-D0009", "2026-12-25")
        self.assertIn("[Godkjenn] [Endre] [Nei takk]", no)
        self.assertIn("Vi foreslår: 25.12. stengt", no)

    def test_shopping_centre_reason_names_the_centre(self):
        out = run_quickstart(self.base, "FI-D0004", "2026-12-24")
        self.assertIn("Shopping centre", out)                    # DETECT cites the centre as evidence
        self.assertIn("SUGGEST", out)
        self.assertIn("Muoti Lyhty", out)

    def test_new_customer_without_history_still_gets_a_message_based_on_peers(self):
        out = run_quickstart(self.base, "FI-D0017", "2026-12-25")
        self.assertIn("similar businesses that entered this day were closed", out)
        self.assertIn("Useimmat vastaavat yritykset", out)     # PEERS wording in the message
        self.assertNotIn("Viime vuonna", out)                  # never claims history that does not exist
        self.assertIn("3 CONTACT", out)

    def test_closed_for_good_business_is_routed_to_a_human_and_nothing_is_sent_or_written(self):
        out = run_quickstart(self.base, "FI-D0011", "2026-11-08")
        self.assertIn("→ FLAG", out)
        self.assertIn("Route to a human", out)
        self.assertNotIn("3 CONTACT", out)
        self.assertNotIn("4 DECIDE", out)
        self.assertEqual(self.api.store.update_log, [])

    def test_already_correct_business_gets_no_message(self):
        out = run_quickstart(self.base, "FI-D0013", "2026-12-24")
        self.assertIn("NO_ACTION", out)
        self.assertNotIn("3 CONTACT", out)
        self.assertEqual(self.api.store.update_log, [])

    def test_non_target_day_and_unknown_entity_exit_with_message(self):
        with self.assertRaises(SystemExit) as a, contextlib.redirect_stdout(io.StringIO()):
            quickstart.run(DEMO_FI, date(2026, 3, 3), self.base)
        self.assertIn("not a target day", str(a.exception))
        with self.assertRaises(SystemExit) as b, contextlib.redirect_stdout(io.StringIO()):
            quickstart.run("NOPE", date(2026, 12, 24), self.base)
        self.assertIn("Unknown entity", str(b.exception))

    def test_scored_test_entity_stops_at_decide_without_writing(self):
        """Owner simulator answers only for dev/demo entities (403). The loop must degrade gracefully."""
        bl = Baseline(2026)
        import csv, os
        for r in csv.DictReader(open(os.path.join(helpers.ROOT, "evaluation", "targets_2026.csv"), encoding="utf-8")):
            if r["split"] == "test" and bl.explain(r["entity_id"], date.fromisoformat(r["date"]), r["day_key"])[0] == "SUGGEST":
                out = run_quickstart(self.base, r["entity_id"], r["date"])
                self.assertIn("owner simulator answers only for dev and demo", out)
                self.assertNotIn("5 APPLY    written", out)
                self.assertEqual(self.api.store.update_log, [])
                return
        self.fail("no test-split suggestion found")

    def test_quickstart_main_isolates_state_from_the_repo_state_file(self):
        import os
        self.assertFalse(os.path.exists(os.path.join(helpers.ROOT, "mock_api", "state.json")),
                         "mock_api/state.json must not be created by tests/quickstart")


class LoopBranches(MockTestCase):
    """Force each DECIDE outcome and assert what APPLY does. 'The customer always has the last word.'"""
    BL = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.BL = Baseline(2026)

    def setUp(self):
        super().setUp()
        self.yx = YextClient(base_url=self.base, api_key="demo", v="20261106")

    def decide(self, eid, day, proposed, **extra):
        st, body = http("POST", self.base + "/sim/v1/owner-response",
                        body={"entityId": eid, "date": day, "proposedHours": proposed, **extra})
        self.assertEqual(st, 200, body)
        return body["response"]

    def find(self, wanted, eid, day, proposed, **kw):
        """Find a messageId for which the (deterministic) simulator returns `wanted`."""
        for i in range(400):
            r = self.decide(eid, day, proposed, messageId=f"m{i}", **kw)
            if r["decision"] == wanted:
                return f"m{i}", r
        self.fail(f"no messageId gave {wanted}")

    def apply_if_allowed(self, eid, day, res):
        """The rule under test: only ACCEPTED / EDITED may write; the written value is the customer's final hours."""
        if res["decision"] in ("ACCEPTED", "EDITED"):
            self.yx.set_holiday_hours(eid, day, res["final_hours"])
            return True
        return False

    def entries(self, eid, day):
        return [h for h in self.yx.get_entity(eid)["hours"].get("holidayHours", []) if h["date"] == day]

    # ---- the engine's suggestion for the demo business -------------------------------------------------
    def suggestion(self):
        act, hours, basis, _ = self.BL.explain(DEMO_FI, date(2026, 12, 24), "XMAS_EVE")
        self.assertEqual(act, "SUGGEST")
        return hours

    def test_approve_applies_exactly_the_suggested_hours(self):
        sug = self.suggestion()
        _, res = self.find("ACCEPTED", DEMO_FI, XMAS_EVE, sug)
        self.assertEqual(res["final_hours"], sug)
        self.assertTrue(self.apply_if_allowed(DEMO_FI, XMAS_EVE, res))
        self.assertEqual(self.entries(DEMO_FI, XMAS_EVE)[0]["openIntervals"], [{"start": "07:30", "end": "13:00"}])

    def test_edit_applies_the_customers_hours_not_the_suggestion(self):
        proposed = "07:30-14:00"                       # slightly off the truth (07:30-13:00)
        _, res = self.find("EDITED", DEMO_FI, XMAS_EVE, proposed)
        self.assertNotEqual(res["final_hours"], proposed)
        self.assertTrue(self.apply_if_allowed(DEMO_FI, XMAS_EVE, res))
        self.assertEqual(self.entries(DEMO_FI, XMAS_EVE)[0]["openIntervals"], [{"start": "07:30", "end": "13:00"}])

    def test_reject_changes_nothing(self):
        before = self.yx.get_entity(DEMO_FI)
        _, res = self.find("REJECTED", DEMO_FI, XMAS_EVE, "closed")
        self.assertIsNone(res["final_hours"])
        self.assertFalse(self.apply_if_allowed(DEMO_FI, XMAS_EVE, res))
        self.assertEqual(self.yx.get_entity(DEMO_FI), before)
        self.assertEqual(self.api.store.update_log, [])

    def test_no_response_changes_nothing(self):
        _, res = self.find("NO_RESPONSE", DEMO_FI, XMAS_EVE, "07:30-13:00", channel="APP_PUSH", sendHour=3)
        self.assertIsNone(res["final_hours"])
        self.assertFalse(self.apply_if_allowed(DEMO_FI, XMAS_EVE, res))
        self.assertEqual(self.api.store.update_log, [])

    def test_wrong_state_suggestion_is_never_silently_accepted(self):
        """A suggestion of 'closed' for a day the business is really open must never come back ACCEPTED."""
        seen = {self.decide(DEMO_FI, XMAS_EVE, "closed", messageId=f"w{i}")["decision"] for i in range(150)}
        self.assertNotIn("ACCEPTED", seen)

    def test_decision_is_reproducible_for_the_same_message(self):
        a = self.decide(DEMO_FI, XMAS_EVE, "07:30-13:00", messageId="same")
        b = self.decide(DEMO_FI, XMAS_EVE, "07:30-13:00", messageId="same")
        self.assertEqual(a, b)

    def test_applying_after_edit_then_a_second_approval_is_idempotent(self):
        self.yx.set_holiday_hours(DEMO_FI, XMAS_EVE, "07:30-14:00")
        self.yx.set_holiday_hours(DEMO_FI, XMAS_EVE, "07:30-13:00")
        self.assertEqual(len(self.entries(DEMO_FI, XMAS_EVE)), 1)

    def test_all_demo_suggestions_pass_the_apply_validator(self):
        """Every SUGGEST the engine would send for the 14 demo targets must be writable (no 400 at APPLY time)."""
        import csv, os
        n = 0
        rows = list(csv.DictReader(open(os.path.join(helpers.ROOT, "evaluation", "targets_2026.csv"), encoding="utf-8")))
        for r in rows:
            if r["split"] != "demo":
                continue
            act, hours, _, _ = self.BL.explain(r["entity_id"], date.fromisoformat(r["date"]), r["day_key"])
            if act == "SUGGEST":
                self.yx.set_holiday_hours(r["entity_id"], r["date"], hours)
                n += 1
        self.assertGreater(n, 20)


if __name__ == "__main__":
    unittest.main()
