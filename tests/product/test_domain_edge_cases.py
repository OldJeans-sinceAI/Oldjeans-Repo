import unittest
from datetime import date, datetime, timezone
from app.domain import (
	HoursError,
	canonical_hours,
	canonical_hours_or_raw,
	validate_hours,
	parse_intervals,
	hours_equal,
	same_open_state,
	hours_string_to_day,
	day_to_hours_string,
	merge_change_into_hours,
	read_back_value,
	change_target_value,
	validate_change,
	relevant_state_hash,
	compute_next_contact_at,
	iso_utc,
	local_date,
	parse_dt,
)
from app.errors import AppError, check_idempotency_key, digest, fingerprint
from app.replies import OwnerReplies


class DomainEdgeCasesTests(unittest.TestCase):
	def test_parse_intervals_overnight_and_24h(self):
		# Overnight range
		ivs = parse_intervals("22:00-02:00")
		self.assertEqual(ivs, [(1320, 1560)])

		# 24 hour range
		ivs_24 = parse_intervals("00:00-23:59")
		self.assertEqual(ivs_24, [(0, 1439)])

		# Multiple intervals
		ivs_multi = parse_intervals("08:00-12:00, 13:00-17:00")
		self.assertEqual(ivs_multi, [(480, 720), (780, 1020)])

	def test_parse_intervals_invalid_specs(self):
		invalid_specs = [
			"",
			"invalid",
			"25:00-26:00",
			"09:00-09:00",
			"09:00-12:00,11:00-14:00",
			"10:00",
			"12:60-14:00",
		]
		for spec in invalid_specs:
			with self.subTest(spec=spec):
				with self.assertRaises(HoursError):
					parse_intervals(spec)

	def test_validate_hours(self):
		self.assertEqual(validate_hours("closed"), "closed")
		self.assertEqual(validate_hours("09:00-17:00"), "09:00-17:00")
		# An omitted time is not an explicit instruction to close the business.
		with self.assertRaises(HoursError):
			validate_hours("")
		with self.assertRaises(HoursError):
			validate_hours("invalid-time")

	def test_hours_equal_and_same_open_state(self):
		self.assertTrue(hours_equal("08:00-12:00,13:00-17:00", "08:00-12:00, 13:00-17:00"))
		self.assertFalse(hours_equal("08:00-12:00", "08:00-13:00"))
		self.assertFalse(hours_equal("invalid", "08:00-12:00"))

		self.assertTrue(same_open_state("closed", "closed"))
		self.assertTrue(same_open_state("08:00-12:00", "09:00-17:00"))
		self.assertFalse(same_open_state("closed", "09:00-17:00"))

	def test_hours_string_conversions(self):
		day_obj = hours_string_to_day("08:00-16:00")
		self.assertEqual(day_obj, {"openIntervals": [{"start": "08:00", "end": "16:00"}]})
		self.assertEqual(day_to_hours_string(day_obj), "08:00-16:00")

		closed_obj = hours_string_to_day("closed")
		self.assertEqual(closed_obj, {"isClosed": True})
		self.assertEqual(day_to_hours_string(closed_obj), "closed")
		self.assertEqual(day_to_hours_string(None), "closed")

	def test_merge_change_into_hours_edge_cases(self):
		base = {
			"monday": {"openIntervals": [{"start": "08:00", "end": "17:00"}]},
			"holidayHours": [{"date": "2026-12-25", "isClosed": True}],
		}

		# DATE_HOURS
		ch_date = {"kind": "DATE_HOURS", "date": "2026-12-24", "hours": "08:00-12:00"}
		merged_date = merge_change_into_hours(base, ch_date)
		self.assertEqual(len(merged_date["holidayHours"]), 2)

		# WEEKLY_HOURS
		ch_weekly = {"kind": "WEEKLY_HOURS", "weekdays": {"monday": "09:00-15:00"}}
		merged_weekly = merge_change_into_hours(base, ch_weekly)
		self.assertEqual(merged_weekly["monday"], {"openIntervals": [{"start": "09:00", "end": "15:00"}]})

		# REOPEN_DATE
		ch_reopen = {"kind": "REOPEN_DATE", "reopen_date": "2027-01-01"}
		merged_reopen = merge_change_into_hours(base, ch_reopen)
		self.assertEqual(merged_reopen["reopenDate"], "2027-01-01")

		# Invalid kind
		with self.assertRaises(HoursError):
			merge_change_into_hours(base, {"kind": "UNKNOWN_KIND"})

	def test_read_back_and_target_values(self):
		hours = {
			"monday": {"openIntervals": [{"start": "08:00", "end": "17:00"}]},
			"holidayHours": [
				{"date": "2026-12-24", "openIntervals": [{"start": "07:30", "end": "13:00"}]},
				{"date": "2026-12-25", "isRegularHours": True},
			],
			"reopenDate": "2027-01-15",
		}

		ch_date = {"kind": "DATE_HOURS", "date": "2026-12-24", "hours": "07:30-13:00"}
		self.assertEqual(read_back_value(hours, ch_date), "07:30-13:00")
		self.assertEqual(change_target_value(ch_date), "07:30-13:00")

		ch_reg = {"kind": "DATE_HOURS", "date": "2026-12-25", "hours": "closed"}
		self.assertEqual(read_back_value(hours, ch_reg), "REGULAR")

		ch_absent = {"kind": "DATE_HOURS", "date": "2026-12-31", "hours": "closed"}
		self.assertEqual(read_back_value(hours, ch_absent), "ABSENT")

		ch_weekly = {"kind": "WEEKLY_HOURS", "weekdays": {"monday": "08:00-17:00"}}
		self.assertEqual(read_back_value(hours, ch_weekly), "monday=08:00-17:00")
		self.assertEqual(change_target_value(ch_weekly), "monday=08:00-17:00")

		ch_reopen = {"kind": "REOPEN_DATE", "reopen_date": "2027-01-15"}
		self.assertEqual(read_back_value(hours, ch_reopen), "2027-01-15")
		self.assertEqual(change_target_value(ch_reopen), "2027-01-15")

		# Unknown kind
		self.assertEqual(read_back_value(hours, {"kind": "UNKNOWN"}), "")
		self.assertEqual(change_target_value({"kind": "UNKNOWN"}), "")

	def test_validate_change(self):
		# Valid changes
		valid_date = validate_change({"kind": "DATE_HOURS", "date": "2026-12-24", "hours": "08:00-12:00"})
		self.assertEqual(valid_date["hours"], "08:00-12:00")

		valid_weekly = validate_change({"kind": "WEEKLY_HOURS", "effective_from": "2026-11-01", "weekdays": {"monday": "08:00-16:00"}})
		self.assertEqual(valid_weekly["weekdays"]["monday"], "08:00-16:00")

		valid_reopen = validate_change({"kind": "REOPEN_DATE", "reopen_date": "2027-01-01"})
		self.assertEqual(valid_reopen["reopen_date"], "2027-01-01")

		# Invalid date format
		with self.assertRaises(ValueError):
			validate_change({"kind": "DATE_HOURS", "date": "invalid-date", "hours": "08:00-12:00"})

		# Empty weekdays
		with self.assertRaises(HoursError):
			validate_change({"kind": "WEEKLY_HOURS", "effective_from": "2026-11-01", "weekdays": {}})

		# Unknown kind
		with self.assertRaises(HoursError):
			validate_change({"kind": "INVALID_KIND"})

	def test_idempotency_key_validation(self):
		check_idempotency_key("valid-key-123")
		with self.assertRaises(AppError) as cm:
			check_idempotency_key(None)
		self.assertEqual(cm.exception.status, 400)
		self.assertEqual(cm.exception.code, "IDEMPOTENCY_KEY_REQUIRED")

		with self.assertRaises(AppError) as cm:
			check_idempotency_key("")
		self.assertEqual(cm.exception.status, 400)

		with self.assertRaises(AppError) as cm:
			check_idempotency_key("x" * 201)
		self.assertEqual(cm.exception.status, 400)

	def test_digest_and_fingerprint(self):
		h1 = digest("hello world")
		self.assertIsInstance(h1, str)
		self.assertEqual(len(h1), 64)

		fp1 = fingerprint({"b": 2, "a": 1})
		fp2 = fingerprint({"a": 1, "b": 2})
		self.assertEqual(fp1, fp2)

	def test_compute_next_contact_at_paused(self):
		now = parse_dt("2026-11-06T10:00:00+02:00")
		res = compute_next_contact_at(now, "Europe/Helsinki", "12-16", "PAUSED")
		self.assertIsNone(res)

	def test_owner_replies_health(self):
		replies = OwnerReplies()
		h = replies.health()
		self.assertIn("provider", h)
		self.assertIn("model", h)
		self.assertIn("configured", h)
		self.assertIn("timeout_ms", h)


if __name__ == "__main__":
	unittest.main()
