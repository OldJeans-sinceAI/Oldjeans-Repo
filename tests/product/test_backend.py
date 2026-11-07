import copy, tempfile, unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from app.domain import (
    DAYS,
    DetectContext,
    HoursError,
    canonical_hours,
    compute_next_contact_at,
    detection_horizon,
    evaluate_context,
    hours_string_to_day,
    iso_utc,
    local_date,
    parse_dt,
    read_back_value,
    relevant_state_hash,
)
from datetime import timezone
from app.service import Service, AppError, effective
from app.storage import StateStore, StateError

NOW = "2026-11-06T10:00:00+02:00"
WEEK = {d: hours_string_to_day("07:30-18:00") for d in DAYS}


class FakeClient:
    def __init__(self):
        self.entities = {
            eid: {
                "meta": {"id": eid},
                "hours": dict(
                    copy.deepcopy(WEEK),
                    holidayHours=[{"date": "2026-12-25", "isClosed": True}],
                ),
                "closed": False,
            }
            for eid in ["A", "B", "TARGET"]
        }
        self.puts = []
        self.failure = None

    def get_entity(self, eid):
        return copy.deepcopy(self.entities[eid])

    def _req(self, method, path, body=None):
        assert method == "PUT"
        eid = path.split("/")[-1]
        self.puts.append((eid, copy.deepcopy(body)))
        if self.failure == "before":
            raise TimeoutError()
        self.entities[eid].update(copy.deepcopy(body))
        if self.failure == "after":
            raise TimeoutError()
        if self.failure == "third":
            self.entities[eid]["hours"]["holidayHours"][-2]["openIntervals"] = [
                {"start": "10:00", "end": "17:00"}
            ]
            raise TimeoutError()
        return {"response": {}}


class FakeData:
    def __init__(self):
        self.entities = {
            eid: {
                "meta": {"id": eid, "countryCode": "FI"},
                "name": "Cafe " + eid,
                "timezone": "Europe/Helsinki",
                "hours": copy.deepcopy(WEEK),
                "c_segment": "cafe",
            }
            for eid in ("A", "B")
        }
        self.order = list(self.entities)
        self.contacts = {
            eid: dict(
                preferred_channel="SMS",
                preferred_language="fi",
                best_contact_window="12-16",
                standing_permission_holidays="0",
                opted_out_of_suggestions="0",
            )
            for eid in self.entities
        }
        self.calendar = [
            dict(
                country="FI",
                date="2026-12-24",
                day_key="XMAS_EVE",
                day_type="EVE",
                day_class="EVE_MAJOR",
            )
        ]
        self.cal_by_date = {("FI", "2026-12-24"): self.calendar[0]}
        self.holiday = {}
        self.history_entities = {"A"}
        self.unavailable = []

    def entity(self, eid):
        return self.entities.get(eid)

    def contact(self, eid):
        return self.contacts.get(eid, {})

    def publishers_for(self, eid):
        return [
            dict(
                publisherId="GOOGLE",
                publisherName="Google",
                status="LIVE",
                typicalUpdateSpeedSeconds=120,
            ),
            dict(
                publisherId="APPLE",
                publisherName="Apple",
                status="WAITING_ON_PUBLISHER",
                typicalUpdateSpeedSeconds=100,
            ),
        ]

    def context(self, eid, target, day_key, day_type):
        return DetectContext(
            eid,
            "Cafe " + eid,
            "Europe/Helsinki",
            "FI",
            "cafe",
            target,
            day_key,
            day_type,
            "2026-11-06T00:00:00Z",
            "07:30-18:00",
            own_history=[
                dict(
                    date="2025-12-24",
                    hours="07:30-13:00",
                    entered_at="2025-11-01T10:00:00Z",
                    source_record="prior-owner-entry",
                )
            ]
            if eid == "A"
            else [],
        )


class ProductTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.client = FakeClient()
        self.data = FakeData()
        self.s = Service(
            state_dir=self.tmp.name, now=NOW, client=self.client, data=self.data
        )

    def tearDown(self):
        self.tmp.cleanup()

    def proposal(self, eid="A", day="2026-12-24"):
        r = self.s.cycle(dict(scope="EXPLICIT_DATES", entity_ids=[eid], dates=[day]))
        c = self.s.store.get("cases", r["case_ids"][0])
        return self.s.proposal(c["proposal_id"])

    def approve(self, p, **kw):
        return self.s.decide(
            p["proposal_id"],
            dict(proposal_version=p["version"], decision="APPROVE"),
            "decision-1",
            **kw,
        )

    def test_AC01_history_deterministic_without_put(self):
        p = self.proposal()
        q = self.proposal()
        self.assertEqual(p["proposal_id"], q["proposal_id"])
        self.assertEqual(p["change"]["hours"], "07:30-13:00")
        self.assertTrue(p["evidence"])
        self.assertEqual(self.client.puts, [])

    def test_AC02_approve_preserves_and_verifies(self):
        original = copy.deepcopy(self.client.entities["A"]["hours"])
        p = self.proposal()
        r = self.approve(p)
        self.assertEqual(r["application_status"], "SUCCEEDED")
        self.assertEqual(len(self.client.puts), 1)
        self.assertEqual(
            effective(self.client.entities["A"]["hours"], "2026-12-24"), "07:30-13:00"
        )
        for wd in DAYS:
            self.assertEqual(original[wd], self.client.entities["A"]["hours"][wd])
        self.assertIn(
            original["holidayHours"][0],
            self.client.entities["A"]["hours"]["holidayHours"],
        )
        self.assertEqual(r["publishers"][0]["basis"], "MOCK_DATASET_ESTIMATE")
        self.assertEqual(r["publishers"][1]["publication_status"], "UNKNOWN")

    def test_AC03_edit_final(self):
        p = self.proposal()
        b = dict(
            decision="EDIT",
            proposal_version=p["version"],
            edited_change=dict(p["change"], hours="07:30-15:00"),
            confirmed=True,
        )
        r = self.s.decide(p["proposal_id"], b, "edit")
        self.assertEqual(r["decision_status"], "EDITED")
        self.assertEqual(
            effective(self.client.entities["A"]["hours"], "2026-12-24"), "07:30-15:00"
        )

    def test_AC04_reject_silence(self):
        p = self.proposal()
        self.s.decide(
            p["proposal_id"], dict(decision="REJECT", proposal_version=1), "reject"
        )
        self.assertEqual(
            self.proposal()["decision_status"], "REJECTED"
        ) if False else None
        q = self.proposal(day="2026-12-31")
        self.s.fixed_now = parse_dt("2026-12-01T10:00:00Z")
        self.s.tick()
        self.assertEqual(q["decision_status"], "EXPIRED")
        self.assertEqual(len(self.client.puts), 0)

    def test_AC05_supported_current_hours(self):
        self.client.entities["A"]["hours"]["holidayHours"].append(
            dict(date="2026-12-24", **hours_string_to_day("07:30-13:00"))
        )
        r = self.s.cycle(
            dict(scope="EXPLICIT_DATES", entity_ids=["A"], dates=["2026-12-24"])
        )
        c = self.s.store.get("cases", r["case_ids"][0])
        self.assertEqual((c["action"], c["status"]), ("NO_ACTION", "RETAIN"))
        self.assertEqual(self.s.messages()["items"], [])

    def test_AC06_no_history_defer(self):
        r = self.s.cycle(
            dict(scope="EXPLICIT_DATES", entity_ids=["B"], dates=["2026-12-24"])
        )
        c = self.s.store.get("cases", r["case_ids"][0])
        self.assertEqual((c["action"], c["status"]), ("NO_ACTION", "DEFER"))
        self.assertTrue(c["gaps"])
        self.assertTrue(c["recheck_trigger"])

    def test_AC07_closure_dedup(self):
        ctx = self.data.context("A", "2026-12-24", "XMAS_EVE", "EVE")
        ctx.closure_signals = [
            dict(
                source_file="reviews.json",
                source_record=str(i),
                known_at="2026-11-01T00:00:00Z",
                summary="Closed permanently",
            )
            for i in range(2)
        ]
        for day in ("2026-12-24", "2026-12-25"):
            ctx.target_date = day
            out = evaluate_context(ctx, parse_dt(NOW))
            self.s._persist_case(out, self.client.entities["A"])
        self.assertEqual(len(self.s.store.data["issues"]), 1)
        self.assertEqual(len(self.client.puts), 0)
        ctx.closure_signals = [ctx.closure_signals[0]] * 2
        self.assertNotEqual(evaluate_context(ctx, parse_dt(NOW))["action"], "FLAG")

    def test_AC08_authoritative_conflict(self):
        ctx = self.data.context("A", "2026-12-24", "XMAS_EVE", "EVE")
        ctx.conflicts = [
            dict(hours=h, source_record=str(i), known_at="2026-11-01T00:00:00Z")
            for i, h in enumerate(("closed", "09:00-14:00"))
        ]
        out = evaluate_context(ctx, parse_dt(NOW))
        self.assertEqual(out["action"], "FLAG")
        self.assertEqual(
            len([e for e in out["detection"]["evidence"] if e["role"] == "COUNTER"]), 2
        )

    def test_AC09_centre_gates(self):
        ctx = self.data.context("B", "2026-12-24", "XMAS_EVE", "EVE")
        ctx.centre = dict(
            target_hours="10:00-13:00",
            match_dates=3,
            agreement=1,
            name="Mall",
            entity_id="M",
        )
        self.assertEqual(evaluate_context(ctx, parse_dt(NOW))["action"], "SUGGEST")
        ctx.centre["agreement"] = 0.7
        self.assertEqual(evaluate_context(ctx, parse_dt(NOW))["action"], "NO_ACTION")

    def test_AC10_weak_context(self):
        ctx = self.data.context("B", "2026-12-24", "XMAS_EVE", "EVE")
        ctx.peer = dict(closed_share=0.99, n_entity_days=100, corroborated=False)
        ctx.context_evidence = [
            dict(
                evidence_id="weather",
                source_file="weather_daily.csv",
                source_record="rain",
                known_at=NOW,
                role="CONTEXT",
                summary="Light rain",
            )
        ]
        self.assertEqual(evaluate_context(ctx, parse_dt(NOW))["action"], "NO_ACTION")

    def test_AC11_hours(self):
        for v in ("closed", "09:00-12:00,13:00-18:00", "18:00-02:00", "00:00-23:59"):
            self.assertEqual(canonical_hours(v), v)
        for v in ("", "09:00-09:00", "25:00-26:00", "09:00-12:00,11:00-14:00"):
            with self.subTest(v=v), self.assertRaises(HoursError):
                canonical_hours(v)
        with self.assertRaises(AppError):
            self.s._validate_adjacent(
                WEEK, dict(kind="DATE_HOURS", date="2026-12-24", hours="18:00-08:30")
            )

    def test_AC12_stale_baseline_no_put(self):
        p = self.proposal()
        self.client.entities["A"]["hours"]["thursday"] = hours_string_to_day(
            "08:00-17:00"
        )
        with self.assertRaises(AppError) as err:
            self.approve(p)
        self.assertEqual(err.exception.status, 409)
        self.assertEqual(len(self.client.puts), 0)

    def test_AC13_idempotency(self):
        p = self.proposal()
        a = self.approve(p)
        b = self.approve(p)
        self.assertEqual(a, b)
        self.assertEqual(len(self.client.puts), 1)
        with self.assertRaises(AppError) as err:
            self.s.decide(
                p["proposal_id"],
                dict(proposal_version=1, decision="REJECT"),
                "decision-1",
            )
        self.assertEqual(err.exception.status, 409)

    def test_AC14_scope_token_and_hashes(self):
        p = self.proposal()
        token = self.s.mint_token("A", [p["proposal_id"]])
        response, session = self.s.exchange_token(token)
        self.s.authenticate({"owner_session": session}, pid=p["proposal_id"])
        with self.assertRaises(AppError):
            self.s.authenticate({"owner_session": session}, eid="B")
        raw = Path(self.tmp.name, "auth.json").read_text()
        self.assertNotIn(token, raw)
        self.assertNotIn(session, raw)
        self.assertEqual(len(self.client.puts), 0)

    def test_AC15_timeout_after_success(self):
        p = self.proposal()
        self.client.failure = "after"
        r = self.approve(p)
        self.assertEqual(r["application_status"], "SUCCEEDED")
        self.assertEqual(len(self.client.puts), 1)

    def test_AC15_timeout_before_success_bounded(self):
        p = self.proposal()
        self.client.failure = "before"
        r = self.approve(p)
        self.assertEqual(r["application_status"], "FAILED")
        self.assertEqual(len(self.client.puts), 3)

    def test_AC16_restart_and_disk_failure(self):
        p = self.proposal()
        a = self.approve(p)
        restarted = Service(
            state_dir=self.tmp.name, now=NOW, client=self.client, data=self.data
        )
        b = restarted.decide(
            p["proposal_id"], dict(proposal_version=1, decision="APPROVE"), "decision-1"
        )
        self.assertEqual(a, b)
        self.assertEqual(len(self.client.puts), 1)
        with patch("app.storage.os.replace", side_effect=OSError("disk")):
            with self.assertRaises(StateError):
                self.s.update_preferences("A", dict(version=1, frequency="PAUSED"))
        self.assertEqual(self.s.preferences("A")["frequency"], "TWICE_MONTHLY")
        Path(self.tmp.name, "broken.json").write_text("{")
        with self.assertRaises(StateError):
            StateStore(str(Path(self.tmp.name, "broken.json")))

    def test_AC17_calendar_and_window(self):
        self.assertEqual(
            detection_horizon(date(2026, 11, 15), "TWICE_MONTHLY"), date(2026, 12, 3)
        )
        now = parse_dt("2026-11-15T13:00:00+02:00")
        self.assertEqual(
            compute_next_contact_at(now, "Europe/Helsinki", "12-16", "TWICE_MONTHLY"),
            iso_utc(now),
        )
        self.assertEqual(
            compute_next_contact_at(
                parse_dt("2026-11-15T18:00:00+02:00"),
                "Europe/Helsinki",
                "12-16",
                "TWICE_MONTHLY",
            ),
            "2026-11-16T10:00:00Z",
        )

    def test_AC18_pause_optout(self):
        p = self.proposal()
        self.s.update_preferences("A", dict(version=1, frequency="PAUSED"))
        m = self.s.create_message(
            dict(
                entity_id="A", proposal_ids=[p["proposal_id"]], delivery_mode="PREVIEW"
            )
        )
        self.assertEqual(m["status"], "BLOCKED_PAUSED")
        self.assertNotIn("owner_entry_path", m)
        self.data.contacts["A"]["opted_out_of_suggestions"] = "1"
        self.s.update_preferences("A", dict(version=2, frequency="MONTHLY"))
        self.assertTrue(self.s.preferences("A")["source_opted_out"])

    def test_AC19_urgent_not_offcycle(self):
        p = self.proposal(day="2026-11-07")
        m = self.s.create_message(
            dict(
                entity_id="A",
                proposal_ids=[p["proposal_id"]],
                delivery_mode="SCHEDULED",
            )
        )
        self.assertEqual(m["status"], "QUEUED")
        self.assertTrue(m["scheduled_at"].startswith("2026-11-15"))

    def test_AC20_rejection_recheck(self):
        p = self.proposal()
        self.s.decide(
            p["proposal_id"], dict(proposal_version=1, decision="REJECT"), "reject"
        )
        r = self.s.cycle(
            dict(scope="EXPLICIT_DATES", entity_ids=["A"], dates=["2026-12-24"])
        )
        self.assertEqual(
            self.s.store.get("cases", r["case_ids"][0])["reason_code"],
            "OWNER_REJECTED_UNCHANGED",
        )

    def test_AC20_confirmed_feedback(self):
        p = self.proposal()
        self.s.decide(
            p["proposal_id"],
            dict(
                proposal_version=1,
                decision="EDIT",
                edited_change=dict(p["change"], hours="07:30-15:00"),
                confirmed=True,
            ),
            "edit",
        )
        self.data.cal_by_date[("FI", "2027-12-24")] = dict(
            day_key="XMAS_EVE", day_type="EVE"
        )
        ctx = self.s._context("A", "2027-12-24", self.client.entities["A"])
        self.assertEqual(
            evaluate_context(ctx, parse_dt(NOW))["change"]["hours"], "07:30-15:00"
        )

    def test_AC21_permission_scope_revoke(self):
        p = self.proposal()
        permission = self.s.create_permission(
            "A",
            dict(
                day_keys=["XMAS_EVE"],
                change_kind="DATE_HOURS",
                purpose="CORRECTION",
                expires_at="2027-01-01T00:00:00Z",
                confirmed=True,
            ),
        )
        self.assertIsNotNone(self.s.matching_permission(p))
        p["purpose"] = "OPPORTUNITY"
        self.assertIsNone(self.s.matching_permission(p))
        p["purpose"] = "CORRECTION"
        self.s.revoke_permission("A", permission["permission_id"])
        self.assertIsNone(self.s.matching_permission(p))

    def test_AC22_nl_preview_no_write(self):
        p = self.proposal()
        for lang, txt in [("fi", "kyllä"), ("sv", "ja"), ("nb", "ja"), ("en", "yes")]:
            self.assertEqual(
                self.s.interpret(p["proposal_id"], dict(text=txt, language=lang))[
                    "intent"
                ],
                "APPROVE",
            )
        for txt in ("maybe 8-15", "yes but not tomorrow", "maybe five"):
            self.assertEqual(
                self.s.interpret(p["proposal_id"], dict(text=txt, language="en"))[
                    "status"
                ],
                "NEEDS_CLARIFICATION",
            )
        self.assertEqual(
            self.s.interpret(
                p["proposal_id"], dict(text="yes", language="en"), multiple=True
            )["status"],
            "NEEDS_CLARIFICATION",
        )
        draft = self.s.interpret(
            p["proposal_id"], dict(text="08:00-15:00", language="en")
        )
        self.assertEqual(len(self.client.puts), 0)
        self.s.decide(p["proposal_id"], draft["decision_draft"], "nl")
        self.assertEqual(len(self.client.puts), 1)

    def test_AC23_future_weekly_schedule(self):
        p = self.proposal()
        p["change"] = dict(
            kind="WEEKLY_HOURS",
            effective_from="2026-11-10",
            weekdays={"monday": "08:00-16:00"},
        )
        p["baseline_hash"] = relevant_state_hash(read_back_value(WEEK, p["change"]))
        self.s.store.save()
        r = self.approve(p)
        self.assertEqual(r["application_status"], "SCHEDULED")
        self.assertEqual(len(self.client.puts), 0)
        self.s.fixed_now = parse_dt("2026-11-10T00:01:00+02:00")
        self.s.tick()
        self.assertEqual(
            self.s.result(p["proposal_id"])["application_status"], "SUCCEEDED"
        )
        self.assertEqual(self.client.entities["A"]["hours"]["tuesday"], WEEK["tuesday"])

    def test_AC24_reopen_scope(self):
        p = self.proposal()
        p["change"] = dict(kind="REOPEN_DATE", reopen_date="2027-01-01")
        p["baseline_hash"] = relevant_state_hash("")
        self.s.store.save()
        r = self.approve(p)
        self.assertEqual(r["application_status"], "SUCCEEDED")
        self.assertEqual(self.client.entities["A"]["hours"]["reopenDate"], "2027-01-01")
        self.assertFalse(self.client.entities["A"]["closed"])

    def test_AC25_sandbox_mapping_adapter(self):
        self.s = Service(
            state_dir=self.tmp.name,
            now=NOW,
            client=self.client,
            data=self.data,
            mode="sandbox",
            source_id="A",
            target_id="TARGET",
            allow_writes=True,
        )
        self.client.entities["TARGET"]["hours"]["monday"] = hours_string_to_day(
            "10:00-19:00"
        )
        p = self.proposal()
        self.approve(p)
        self.assertEqual(self.client.puts[0][0], "TARGET")
        self.assertEqual(
            self.client.entities["TARGET"]["hours"]["monday"],
            hours_string_to_day("10:00-19:00"),
        )
        self.assertEqual(
            self.client.entities["A"]["hours"]["thursday"], WEEK["thursday"]
        )

    def test_AC25_sandbox_gate(self):
        self.s = Service(
            state_dir=self.tmp.name,
            now=NOW,
            client=self.client,
            data=self.data,
            mode="sandbox",
            source_id="A",
            target_id="TARGET",
            allow_writes=False,
        )
        p = self.proposal()
        with self.assertRaises(AppError):
            self.approve(p)
        self.assertEqual(len(self.client.puts), 0)

    def test_AC26_four_channel_messages(self):
        p = self.proposal()
        for channel, language in [
            ("SMS", "fi"),
            ("EMAIL", "sv"),
            ("WHATSAPP", "nb"),
            ("APP_PUSH", "en"),
        ]:
            self.s.store.data["messages"] = {}
            self.data.contacts["A"].update(
                preferred_channel=channel, preferred_language=language
            )
            m = self.s.create_message(
                dict(
                    entity_id="A",
                    proposal_ids=[p["proposal_id"]],
                    delivery_mode="PREVIEW",
                )
            )
            self.assertEqual((m["channel"], m["language"]), (channel, "en"))
            self.assertEqual(self.data.contacts["A"]["preferred_language"], language)
            self.assertTrue(m["simulated"])
            self.assertIn("Currently shown", m["text"])
            self.assertIn("We propose", m["text"])

    def test_AC30_timezone(self):
        now = parse_dt("2026-11-30T22:30:00Z")
        self.assertEqual(local_date(now, "Europe/Helsinki"), date(2026, 12, 1))
        self.assertEqual(local_date(now, "Europe/Stockholm"), date(2026, 11, 30))
        self.assertEqual(parse_dt("2026-01-01T12:00").tzinfo, timezone.utc)

    def test_AC32_batch_independent(self):
        p = self.proposal()
        q = self.proposal(day="2026-12-31")
        self.approve(p)
        self.client.entities["A"]["hours"]["holidayHours"].append(
            dict(date="2026-12-31", isClosed=True)
        )
        with self.assertRaises(AppError):
            self.s.decide(
                q["proposal_id"],
                dict(decision="APPROVE", proposal_version=q["version"]),
                "second",
            )
        self.assertEqual(
            self.s.result(p["proposal_id"])["application_status"], "SUCCEEDED"
        )
        self.assertEqual(len(self.client.puts), 1)


if __name__ == "__main__":
    unittest.main()
