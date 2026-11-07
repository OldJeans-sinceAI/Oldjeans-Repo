"""Detect A-J CONTRACT tests (Detect_Design_EN.pdf, 7 pages). Black-box: they call only
    build_profile(tables, entity_id, cutoff)  and  run_case(tables, entity_id, target_date, cutoff)
on whatever `detect_adapter.load()` finds.

    * repo today (no Detect layer)      -> every test SKIPS with the gap message   (pytest -rs shows it)
    * DETECT_IMPL=reference             -> runs against tests/py/reference_detect.py (proves the tests are sound)
    * after the team adds examples/detect.py -> runs against the real code, unchanged

Boundary values of thresholds are never tested: the PDF says thresholds are "not final".
"""
import json
import unittest

import detect_adapter
import detect_fixtures as fx
from detect_fixtures import CUTOFF, TARGET

IMPL, LABEL = detect_adapter.load()
ROLES = {"direct", "supplementary", "contextual", "counter_warning"}
FORBIDDEN_KEYS = {"proposed_hours", "suggested_hours", "suggestion", "proposal", "new_hours", "recommended_hours",
                  "final_hours", "proposed"}


def keys_deep(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from keys_deep(v)
    elif isinstance(o, list):
        for v in o:
            yield from keys_deep(v)


@unittest.skipIf(IMPL is None, detect_adapter.GAP)
class Base(unittest.TestCase):
    def run_case(self, t, eid="FI-D0001", target=TARGET, cutoff=CUTOFF):
        return IMPL.run_case(t, eid, target, cutoff)

    @staticmethod
    def kinds(h, role=None):
        return {e["kind"] for e in h["evidence"] if role is None or e["role"] == role}

    @staticmethod
    def roles(h):
        return {e["role"] for e in h["evidence"]}

    def aurora(self, **kw):
        t = fx.empty_tables()
        fx.add_entity(t, "FI-D0001", regular="07:30-18:00", name="Kahvila Aurora", **kw)
        return t


# ============================================================================ golden path
class GoldenPathKahvilaAurora(Base):
    """PDF p.7: displayed 07:30-18:00, owner entered 07:30-13:00 last year, no 2026 exception
    -> 'Possible missing exception' -> Suggest review. Historical hours are evidence, not the proposal."""

    def check(self, h):
        self.assertEqual(h["displayed_state"]["hours"], "07:30-18:00")
        self.assertEqual(h["displayed_state"]["source"], "regular")           # no exception for 2026-12-24
        self.assertEqual(h["finding"]["type"], "possible_error_omission")
        self.assertEqual(h["finding"]["summary"], "Possible error/omission")
        self.assertEqual(h["route"], "suggest_review")
        direct = [e for e in h["evidence"] if e["role"] == "direct"]
        self.assertTrue(direct, "dated own-history evidence must be passed to Suggest")
        self.assertEqual((direct[0]["content"], direct[0]["applicable_date"], direct[0]["entered_at"]),
                         ("07:30-13:00", "2025-12-24", "2025-12-21T20:00:00"))
        self.assertEqual(h["uncertainty"]["evidence_strength"], "strong")
        self.assertEqual(h["path"]["trace"], ["F"])                          # strong evidence -> fast path
        self.assertFalse(FORBIDDEN_KEYS & set(keys_deep(h)), "Detect must not carry a proposal")

    def test_in_memory_aurora(self):
        self.check(self.run_case(fx.tables_for_golden_aurora()))

    def test_real_dataset_aurora(self):
        t = fx.real_tables()
        self.assertEqual(t["entities"]["FI-D0001"]["name"], "Kahvila Aurora")
        self.check(IMPL.run_case(t, "FI-D0001", TARGET, CUTOFF))

    def test_aurora_with_the_exception_already_set_is_retained(self):
        t = self.aurora(exceptions={"2026-12-24": "07:30-13:00"})
        fx.rich_history(t, "FI-D0001")
        h = self.run_case(t)
        self.assertEqual((h["finding"]["type"], h["route"]), ("state_aligned", "retain"))
        self.assertEqual(h["displayed_state"]["source"], "exception")
        self.assertEqual(h["displayed_state"]["exception_version"], "2026-12-24")


# ============================================================================ routing E -> F / G / H
class Routing(Base):
    def test_F_strong_profile_with_full_coverage_takes_the_fast_path(self):
        t = self.aurora()
        fx.rich_history(t, "FI-D0001")
        h = self.run_case(t)
        self.assertEqual(h["path"]["profile"], "strong")
        self.assertEqual(h["path"]["trace"], ["F"])
        self.assertEqual(self.roles(h), {"direct"}, "fast path compares displayed state with direct evidence only")

    def test_F_owner_confirmation_alone_makes_a_strong_profile(self):
        t = self.aurora()
        t["pilot_log"].append({"suggestion_id": "sug-1", "entity_id": "FI-D0001", "date": "2025-12-24",
                               "day_key": "XMAS_EVE", "decision": "EDITED", "final_hours": "08:00-12:00",
                               "decided_at": "2025-12-08T10:00:00"})
        h = self.run_case(t)
        self.assertEqual(h["path"]["profile"], "strong")
        self.assertIn("owner_confirmation", self.kinds(h, "direct"))

    def test_G_partial_profile_supplements_instead_of_fast_path(self):
        t = self.aurora()
        fx.thin_history(t, "FI-D0001")
        h = self.run_case(t)
        self.assertEqual(h["path"]["profile"], "partial")
        self.assertEqual(h["path"]["trace"], ["G"])
        self.assertIn("supplementary", self.roles(h))
        self.assertNotIn("direct", self.roles(h))
        cross_day = [e for e in h["evidence"] if e["kind"] == "own_other_holidays"]
        self.assertTrue(cross_day and cross_day[0]["is_inference"], "cross-day transfer must be marked as inference")

    def test_G_strong_profile_but_missing_date_specific_evidence_moves_F_to_G(self):
        t = self.aurora()
        fx.rich_history(t, "FI-D0001", xmas_eve=None)           # plenty of history, none for XMAS_EVE
        h = self.run_case(t)
        self.assertEqual(h["path"]["profile"], "strong")
        self.assertEqual(h["path"]["trace"][-1], "G")
        self.assertNotIn("H", h["path"]["trace"])
        self.assertIn("supplementary", self.roles(h))
        self.assertTrue(any("own evidence" in m for m in h["uncertainty"]["missing"]),
                        "missing date-specific evidence must be listed as uncertainty")

    def test_H_limited_profile_uses_indirect_evidence(self):
        t = self.aurora()                                        # zero own history
        fx.add_peer(t)
        h = self.run_case(t)
        self.assertEqual(h["path"]["profile"], "limited")
        self.assertEqual(h["path"]["trace"], ["H"])
        self.assertNotIn("direct", self.roles(h))
        self.assertIn("peer_benchmark", self.kinds(h))

    def test_H_checks_centre_peers_and_events(self):
        t = self.aurora(centre="FI-MALL1")
        fx.add_entity(t, "FI-MALL1", exceptions={"2026-12-24": "closed"}, name="Kauppakeskus")
        fx.add_peer(t)
        t["events"].append({"@id": "ev:1", "start_time": "2026-12-24T12:00", "end_time": "2026-12-24T15:00",
                            "x_country": "FI", "x_expected_attendance": 5000,
                            "location": {"address_locality": "Helsinki"}})
        h = self.run_case(t)
        self.assertEqual(h["path"]["trace"], ["H"])
        self.assertTrue({"shopping_centre", "peer_benchmark", "event"} <= self.kinds(h))
        centre = next(e for e in h["evidence"] if e["kind"] == "shopping_centre")
        self.assertIn("centre_agreement", centre)               # PDF p.4: agreement + sample count express strength
        self.assertIn("comparable_dates", centre)

    def test_H_limited_evidence_alone_does_not_force_staff_review(self):
        t = self.aurora()
        fx.add_peer(t)
        self.assertNotEqual(self.run_case(t)["route"], "staff_review")

    def test_fallback_F_to_G_when_conflicting_evidence_is_found(self):
        t = self.aurora()
        fx.rich_history(t, "FI-D0001")                           # would be a clean F ...
        t["suggestions"].append({"id": "ps-9", "locationId": "FI-D0001", "fieldName": "hours",
                                 "status": "WAITING_ON_CUSTOMER", "dateCreated": "2026-10-01",
                                 "suggestedContent": json.dumps({"holidayHours": [
                                     {"date": "2026-12-24", "openIntervals": [{"start": "10:00", "end": "15:00"}]}]})})
        h = self.run_case(t)
        self.assertEqual(h["path"]["profile"], "strong")
        self.assertEqual(h["path"]["trace"], ["F", "G"], "F must hand over to G on material conflict")
        self.assertIn("counter_warning", self.roles(h))
        self.assertNotEqual(h["route"], "retain", "a fast decision must be paused when a counter signal exists")

    def test_closure_mention_pauses_the_fast_path_too(self):
        t = self.aurora()
        fx.rich_history(t, "FI-D0001")
        fx.add_review(t, "FI-D0001", "Kahvila on lopettanut toimintansa pysyvästi")
        self.assertEqual(self.run_case(t)["path"]["trace"], ["F", "G"])


# ============================================================================ synthesis I
class Synthesis(Base):
    def test_material_conflict_routes_to_staff_review(self):
        t = self.aurora()
        fx.rich_history(t, "FI-D0001")
        fx.add_review(t, "FI-D0001", "Stängt för gott sedan oktober")
        h = self.run_case(t)
        self.assertEqual((h["finding"]["type"], h["route"]), ("material_conflict", "staff_review"))
        w = [e for e in h["evidence"] if e["role"] == "counter_warning"]
        self.assertTrue(w and w[0]["source"] == "reviews.json" and w[0]["ref"], "warning needs a source reference")

    def test_insufficient_evidence_routes_to_defer_and_records_recheck_triggers(self):
        h = self.run_case(self.aurora())                          # no history, no centre, no peers, no events
        self.assertEqual((h["finding"]["type"], h["route"]), ("insufficient_evidence", "defer"))
        self.assertEqual(h["uncertainty"]["evidence_strength"], "none")
        self.assertTrue(h["recheck_triggers"], "Defer must record review triggers")

    def test_state_and_evidence_align_routes_to_retain(self):
        t = self.aurora(exceptions={"2026-12-24": "07:30-13:00"})
        fx.rich_history(t, "FI-D0001")
        self.assertEqual(self.run_case(t)["route"], "retain")

    def test_event_only_is_an_opportunity_not_a_correction(self):
        t = self.aurora()
        t["events"].append({"@id": "ev:2", "start_time": "2026-12-24T18:00", "end_time": "2026-12-24T22:00",
                            "x_country": "FI", "x_expected_attendance": 20000,
                            "location": {"address_locality": "Helsinki"}})
        h = self.run_case(t)
        self.assertEqual(h["finding"]["type"], "new_trading_opportunity")
        self.assertEqual(h["route"], "suggest_review")
        self.assertIn("opportunity", h["finding"]["tags"])
        self.assertNotEqual(h["finding"]["type"], "possible_error_omission")
        self.assertEqual(h["uncertainty"]["evidence_strength"], "none",
                         "an event cannot substitute for evidence that specific hours are correct")

    def test_priority_comes_from_impact_not_from_certainty(self):
        def mk(views):
            t = self.aurora()
            fx.rich_history(t, "FI-D0001")
            t["analytics"]["FI-D0001"] = {"search_views_daily": views}
            return self.run_case(t)
        hi, lo = mk(5000), mk(1)
        self.assertEqual(hi["finding"]["type"], lo["finding"]["type"])
        self.assertEqual(hi["uncertainty"], lo["uncertainty"])
        self.assertNotEqual(hi["priority"], lo["priority"])

    def test_same_inputs_give_identical_findings(self):
        t = fx.tables_for_golden_aurora()
        a, b = self.run_case(t), self.run_case(t)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))

    def test_evidence_entered_after_the_cutoff_is_ignored(self):
        t = self.aurora()
        fx.add_hol(t, "FI-D0001", "2025-12-24", "XMAS_EVE", "07:30-13:00", entered_at="2026-11-20T10:00:00")
        h = self.run_case(t)
        self.assertEqual(h["path"]["profile"], "limited")
        self.assertNotIn("direct", self.roles(h))

    def test_repeated_revisions_of_one_date_count_once_latest_wins(self):
        t = self.aurora()
        fx.rich_history(t, "FI-D0001", xmas_eve=None)
        fx.add_hol(t, "FI-D0001", "2025-12-24", "XMAS_EVE", "10:00-13:00", "2025-12-10T10:00:00")
        fx.add_hol(t, "FI-D0001", "2025-12-24", "XMAS_EVE", "07:30-13:00", "2025-12-21T20:00:00")
        direct = [e for e in self.run_case(t)["evidence"] if e["role"] == "direct" and e["applicable_date"] == "2025-12-24"]
        self.assertEqual([e["content"] for e in direct], ["07:30-13:00"])


# ============================================================================ handoff J
class Handoff(Base):
    """PDF p.7 table: identity, trigger, displayed state, finding, support/counter-evidence, uncertainty,
    route & priority, recheck triggers."""

    def setUp(self):
        self.h = self.run_case(fx.tables_for_golden_aurora())

    def test_case_identity_trigger_displayed_state(self):
        ci = self.h["case_identity"]
        self.assertEqual((ci["business_id"], ci["target_date"], ci["information_cutoff"]),
                         ("FI-D0001", "2026-12-24", "2026-11-06"))
        self.assertEqual(self.h["trigger"]["type"], "holiday")
        self.assertEqual(self.h["trigger"]["day_key"], "XMAS_EVE")
        ds = self.h["displayed_state"]
        self.assertEqual(ds["hours"], "07:30-18:00")
        self.assertIn("regular_schedule_version", ds)
        self.assertIn("exception_version", ds)

    def test_finding_uncertainty_route_priority_recheck(self):
        for k in ("finding", "uncertainty", "route", "priority", "recheck_triggers", "evidence"):
            self.assertIn(k, self.h)
        self.assertIn("type", self.h["finding"])
        self.assertIn("evidence_strength", self.h["uncertainty"])
        self.assertIn("missing", self.h["uncertainty"])
        self.assertIn(self.h["route"], {"suggest_review", "retain", "defer", "staff_review"})
        self.assertTrue(self.h["priority"])
        self.assertTrue(self.h["recheck_triggers"])

    def test_every_evidence_item_is_traceable(self):
        self.assertTrue(self.h["evidence"])
        for e in self.h["evidence"]:
            self.assertIn(e["role"], ROLES)
            for k in ("content", "source", "applicable_date", "entered_at", "ref"):
                self.assertIn(k, e, f"evidence missing {k}")
            self.assertTrue(e["source"] and e["ref"])

    def test_detect_does_not_choose_the_final_hours(self):
        """Separation of concerns: Suggest, not Detect, picks the proposal (PDF p.1 and p.7)."""
        leaked = FORBIDDEN_KEYS & set(keys_deep(self.h))
        self.assertFalse(leaked, f"handoff carries proposal-like keys: {leaked}")
        self.assertNotIn("hours", self.h["finding"])
        self.assertNotIn("route_to_hours", self.h)

    def test_payload_is_json_serialisable(self):
        json.loads(json.dumps(self.h))


if __name__ == "__main__":
    unittest.main()
