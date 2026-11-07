import copy, json, tempfile, unittest, builtins
from pathlib import Path
from unittest.mock import patch
from app.domain import DataStore, DataError, evaluate_context, parse_dt
from test_backend import FakeData, NOW

ROOT = Path(__file__).resolve().parents[2]


class SourceTests(unittest.TestCase):
    def test_AC31_optional_missing_and_critical_corrupt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake = FakeData()
            (root / "entities.json").write_text(
                json.dumps({"response": {"entities": list(fake.entities.values())}})
            )
            (root / "calendar_special_days.csv").write_text(
                "country,date,day_key,day_type,day_class\nFI,2026-12-24,XMAS_EVE,EVE,EVE_MAJOR\n"
            )
            (root / "customer_contacts.csv").write_text(
                "entity_id,preferred_channel,preferred_language,best_contact_window\nA,SMS,fi,12-16\n"
            )
            data = DataStore(temp)
            self.assertIn("holiday_hours_history.jsonl", data.unavailable)
            out = evaluate_context(
                data.context("A", "2026-12-24", "XMAS_EVE", "EVE"), parse_dt(NOW)
            )
            self.assertEqual(out["action"], "NO_ACTION")
            self.assertTrue(out["detection"]["gaps"])
            (root / "calendar_special_days.csv").write_text("wrong,columns\na,b\n")
            with self.assertRaises(DataError):
                DataStore(temp)

    def test_AC27_truth_isolation_and_real_scenarios(self):
        original = builtins.open
        accessed = []

        def checked(path, *args, **kwargs):
            text = str(path)
            self.assertNotIn("labels/", text)
            self.assertNotIn("sim_data.json", text)
            accessed.append(text)
            return original(path, *args, **kwargs)

        with patch("builtins.open", checked):
            data = DataStore(str(ROOT / "data"))
            for eid, expected in [
                ("FI-D0001", "SUGGEST"),
                ("FI-D0011", "FLAG"),
                ("FI-D0013", "NO_ACTION"),
                ("FI-D0017", "NO_ACTION"),
            ]:
                with self.subTest(entity=eid):
                    self.assertEqual(
                        evaluate_context(
                            data.context(eid, "2026-12-24", "XMAS_EVE", "EVE"),
                            parse_dt(NOW),
                        )["action"],
                        expected,
                    )
        self.assertTrue(accessed)

    def test_AC08_latest_revision_cutoff(self):
        data = DataStore(str(ROOT / "data"))
        eid = "FI-D0001"
        base = copy.deepcopy(data.holiday[(eid, "2025-12-24")][-1])
        base.update(
            date="2026-12-24",
            entered_at="2026-11-05T12:00:00Z",
            holidayHours={"date": "2026-12-24", "isClosed": True},
        )
        data.holiday[(eid, "2026-12-24")] = [
            base,
            dict(
                base,
                entered_at="2026-11-07T12:00:00Z",
                holidayHours={
                    "date": "2026-12-24",
                    "openIntervals": [{"start": "08:00", "end": "20:00"}],
                },
            ),
        ]
        ctx = data.context(eid, "2026-12-24", "XMAS_EVE", "EVE")
        self.assertEqual(ctx.owner_confirmation["hours"], "closed")
        self.assertEqual(ctx.owner_confirmation["known_at"], "2026-11-05T12:00:00Z")

    def test_source_updates_reload_and_fail_closed(self):
        from app.service import Service, AppError
        from test_backend import FakeClient

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "data"
            root.mkdir()
            fake = FakeData()
            (root / "entities.json").write_text(
                json.dumps({"response": {"entities": list(fake.entities.values())}})
            )
            calendar = "country,date,day_key,day_type,day_class\nFI,2026-12-24,XMAS_EVE,EVE,EVE_MAJOR\n"
            (root / "calendar_special_days.csv").write_text(calendar)
            (root / "customer_contacts.csv").write_text(
                "entity_id,preferred_channel,preferred_language,best_contact_window\nA,SMS,fi,12-16\n"
            )
            service = Service(
                state_dir=str(Path(temp) / "state"),
                now=NOW,
                client=FakeClient(),
                data=DataStore(str(root)),
            )
            self.assertFalse(service._refresh_sources())
            (root / "calendar_special_days.csv").write_text("invalid\n")
            with self.assertRaises(AppError):
                service._refresh_sources()
            self.assertEqual(service.health()["status"], "NOT_READY")
            (root / "calendar_special_days.csv").write_text(calendar)
            self.assertTrue(service._refresh_sources())
            self.assertTrue(service.health()["data_ready"])
