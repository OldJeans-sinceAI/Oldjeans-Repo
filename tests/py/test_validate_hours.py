"""Unit tests: server.validate_hours - the guard that decides whether an APPLY (PUT) is accepted."""
import copy
import unittest

import helpers
from helpers import full_week

import server


def with_holiday(*items):
    h = full_week()
    h["holidayHours"] = list(items)
    return h


class WeekdayRules(unittest.TestCase):
    def test_full_week_is_valid(self):
        self.assertEqual(server.validate_hours(full_week()), [])

    def test_partial_week_rejected(self):
        h = full_week()
        del h["sunday"]
        self.assertTrue(any("all seven weekdays" in e for e in server.validate_hours(h)))

    def test_unknown_key_rejected(self):
        h = full_week()
        h["bogus"] = 1
        self.assertTrue(any("unknown key" in e for e in server.validate_hours(h)))

    def test_not_an_object(self):
        self.assertEqual(server.validate_hours("closed"), ["hours must be an object"])

    def test_reopen_date_and_conversation_flag_allowed(self):
        h = full_week()
        h.update({"reopenDate": "2027-05-01", "holidayHoursConversationEnabled": True})
        self.assertEqual(server.validate_hours(h), [])


class IntervalRules(unittest.TestCase):
    def check(self, day, fragment):
        h = full_week()
        h["monday"] = day
        errs = server.validate_hours(h)
        self.assertTrue(any(fragment in e for e in errs), errs)

    def test_bad_time_format(self):
        self.check({"openIntervals": [{"start": "9:00", "end": "17:00"}]}, "HH:MM")

    def test_hour_out_of_range(self):
        self.check({"openIntervals": [{"start": "09:00", "end": "24:00"}]}, "HH:MM")

    def test_start_equals_end(self):
        self.check({"openIntervals": [{"start": "10:00", "end": "10:00"}]}, "start equals end")

    def test_overlap(self):
        self.check({"openIntervals": [{"start": "09:00", "end": "13:00"}, {"start": "12:00", "end": "18:00"}]}, "overlap")

    def test_closed_with_intervals(self):
        self.check({"isClosed": True, "openIntervals": [{"start": "09:00", "end": "10:00"}]}, "cannot be closed")

    def test_missing_end(self):
        self.check({"openIntervals": [{"start": "09:00"}]}, "start and end")

    def test_past_midnight_and_24h_are_valid(self):
        for day in ({"openIntervals": [{"start": "18:00", "end": "02:00"}]},
                    {"openIntervals": [{"start": "00:00", "end": "23:59"}]},
                    {"openIntervals": [{"start": "10:00", "end": "14:00"}, {"start": "17:00", "end": "22:00"}]}):
            h = full_week()
            h["monday"] = day
            self.assertEqual(server.validate_hours(h), [], day)


class HolidayRules(unittest.TestCase):
    def test_closed_regular_and_special_are_valid(self):
        h = with_holiday({"date": "2026-12-24", "openIntervals": [{"start": "07:30", "end": "13:00"}]},
                         {"date": "2026-12-25", "isClosed": True},
                         {"date": "2026-12-26", "isRegularHours": True})
        self.assertEqual(server.validate_hours(h), [])

    def test_exactly_one_flag_required(self):
        for item in ({"date": "2026-12-24"},
                     {"date": "2026-12-24", "isClosed": True, "isRegularHours": True},
                     {"date": "2026-12-24", "isClosed": True,
                      "openIntervals": [{"start": "10:00", "end": "11:00"}]}):
            errs = server.validate_hours(with_holiday(item))
            self.assertTrue(any("exactly one" in e for e in errs), (item, errs))

    def test_bad_date(self):
        for d in ("24.12.2026", "2026-13-01", "", "2026-02-30"):
            errs = server.validate_hours(with_holiday({"date": d, "isClosed": True}))
            self.assertTrue(any("bad date" in e for e in errs), (d, errs))

    def test_duplicate_date(self):
        errs = server.validate_hours(with_holiday({"date": "2026-12-24", "isClosed": True},
                                                  {"date": "2026-12-24", "isRegularHours": True}))
        self.assertTrue(any("duplicate" in e for e in errs))

    def test_holiday_hours_must_be_list(self):
        h = full_week()
        h["holidayHours"] = {"date": "2026-12-24"}
        self.assertTrue(any("must be a list" in e for e in server.validate_hours(h)))

    def test_holiday_item_interval_errors_are_reported(self):
        errs = server.validate_hours(with_holiday({"date": "2026-12-24",
                                                   "openIntervals": [{"start": "13:00", "end": "07:30x"}]}))
        self.assertTrue(errs)

    def test_validation_does_not_mutate_input(self):
        h = with_holiday({"date": "2026-12-24", "isClosed": True})
        before = copy.deepcopy(h)
        server.validate_hours(h)
        self.assertEqual(h, before)


if __name__ == "__main__":
    unittest.main()
