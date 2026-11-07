"""Unit tests: mock_api/hours.py (opening-hours primitives used by every step of the loop)."""
import unittest

import helpers  # noqa: F401  (sets sys.path)
from hours import (boundary_diff, hours_str_to_yext_day, is_valid_hours, ivs_to_str, m2t, parse_week, same_state,
                   str_to_ivs, t2m, week_to_yext, yext_day_to_str, yext_to_week)


class TimeConversion(unittest.TestCase):
    def test_roundtrip(self):
        for t in ("00:00", "07:30", "12:05", "23:59"):
            self.assertEqual(m2t(t2m(t)), t)

    def test_m2t_wraps_past_midnight(self):
        self.assertEqual(m2t(1440), "00:00")
        self.assertEqual(m2t(1560), "02:00")


class ParseWeek(unittest.TestCase):
    def test_ranges_and_lists(self):
        w = parse_week("mo-fr 09:00-17:00; sa 10:00-14:00")
        self.assertEqual([w[i] for i in range(5)], [[(540, 1020)]] * 5)
        self.assertEqual(w[5], [(600, 840)])
        self.assertEqual(w[6], [])  # Sunday not listed -> closed

    def test_split_day(self):
        self.assertEqual(parse_week("mo 10:00-14:00,17:00-22:00")[0], [(600, 840), (1020, 1320)])

    def test_past_midnight_end_is_next_day(self):
        self.assertEqual(parse_week("fr 18:00-02:00")[4], [(1080, 1560)])

    def test_24h_convention_is_not_rolled_over(self):
        self.assertEqual(parse_week("su 00:00-23:59")[6], [(0, 1439)])


class StrToIvs(unittest.TestCase):
    def test_closed_and_empty(self):
        self.assertEqual(str_to_ivs("closed"), [])
        self.assertEqual(str_to_ivs(""), [])
        self.assertEqual(str_to_ivs(None), [])
        self.assertEqual(str_to_ivs("  CLOSED "), [])

    def test_roundtrip_with_ivs_to_str(self):
        for s in ("closed", "09:00-17:00", "10:00-14:00,17:00-22:00", "18:00-02:00", "00:00-23:59"):
            self.assertEqual(ivs_to_str(str_to_ivs(s)), s)


class IsValidHours(unittest.TestCase):
    def test_valid(self):
        for s in ("closed", "09:00-17:00", "10:00-14:00,17:00-22:00", "18:00-02:00", "00:00-23:59"):
            self.assertTrue(is_valid_hours(s), s)

    def test_invalid(self):
        for s in ("", "open", "9:00-17:00", "25:00-26:00", "10:00-24:60", "10:00-12:00,", "10:00", None, 5, "09:00–17:00"):
            self.assertFalse(is_valid_hours(s), repr(s))

    @unittest.expectedFailure
    def test_known_gap_regex_normalises_case_and_spaces_but_the_rest_of_the_function_does_not(self):
        """KNOWN GAP: the regex is applied to s.strip().lower() but the split/range check uses the raw string, so
        ' CLOSED ' / 'Closed' are rejected. Masked today because /sim/v1/owner-response lower-cases first."""
        self.assertTrue(is_valid_hours(" CLOSED "))

    def test_start_equals_end_is_accepted_here_but_rejected_by_the_put_validator(self):
        """Characterisation: owner simulator accepts '10:00-10:00'; PUT /entities rejects it (see test_validate_hours)."""
        self.assertTrue(is_valid_hours("10:00-10:00"))


class YextShapes(unittest.TestCase):
    def test_closed(self):
        self.assertEqual(hours_str_to_yext_day("closed"), {"isClosed": True})
        self.assertEqual(yext_day_to_str({"isClosed": True}), "closed")
        self.assertEqual(yext_day_to_str({}), "closed")
        self.assertEqual(yext_day_to_str(None), "closed")

    def test_open_roundtrip(self):
        for s in ("09:00-17:00", "10:00-14:00,17:00-22:00", "00:00-23:59"):
            self.assertEqual(yext_day_to_str(hours_str_to_yext_day(s)), s)

    def test_week_roundtrip(self):
        week = parse_week("mo-fr 09:00-17:00; sa 10:00-14:00")
        self.assertEqual(yext_to_week(week_to_yext(week)), week)
        self.assertEqual(week_to_yext(week)["sunday"], {"isClosed": True})


class Comparison(unittest.TestCase):
    def test_same_state(self):
        self.assertTrue(same_state("closed", "closed"))
        self.assertTrue(same_state("09:00-17:00", "10:00-12:00"))
        self.assertFalse(same_state("closed", "09:00-17:00"))

    def test_boundary_diff(self):
        self.assertEqual(boundary_diff("closed", "closed"), 0)
        self.assertEqual(boundary_diff("closed", "09:00-17:00"), 9999)
        self.assertEqual(boundary_diff("09:00-17:00", "09:30-17:00"), 30)
        self.assertEqual(boundary_diff("09:00-17:00", "09:00-16:00"), 60)


if __name__ == "__main__":
    unittest.main()
