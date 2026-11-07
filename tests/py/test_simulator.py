"""Unit tests: mock_api/simulator.py - the owner-response model behind step 4 (DECIDE).

The simulator is seeded by a hash of its inputs, so every test is deterministic; the statistical assertions use
wide tolerances over thousands of seeds.
"""
import unittest
from collections import Counter

import helpers  # noqa: F401
from simulator import CHANNEL_FACTOR, LATENCY_MEDIAN_MIN, respond

TRUTH_OPEN, TRUTH_CLOSED = "10:00-15:00", "closed"


def sample(truth, proposed, resp=0.97, channel="SMS", n=1500, **kw):
    return [respond(truth, proposed, resp, channel, "t", i, **kw) for i in range(n)]


class Determinism(unittest.TestCase):
    def test_same_inputs_same_output(self):
        a = respond(TRUTH_OPEN, "10:00-16:00", 0.9, "SMS", "seed", 1)
        b = respond(TRUTH_OPEN, "10:00-16:00", 0.9, "SMS", "seed", 1)
        self.assertEqual(a, b)

    def test_different_seed_can_differ(self):
        outs = {respond(TRUTH_OPEN, "10:00-16:00", 0.9, "SMS", "seed", i)["decision"] for i in range(200)}
        self.assertGreater(len(outs), 1)


class ResponseContract(unittest.TestCase):
    def test_decision_domain_and_field_semantics(self):
        for proposed in (TRUTH_OPEN, "10:00-16:00", "closed", "09:00-15:00,17:00-20:00"):
            for r in sample(TRUTH_OPEN, proposed, n=300):
                self.assertIn(r["decision"], ("ACCEPTED", "EDITED", "REJECTED", "NO_RESPONSE"))
                if r["decision"] == "NO_RESPONSE":
                    self.assertIsNone(r["final_hours"])
                    self.assertIsNone(r["latency_minutes"])
                    self.assertFalse(r["standing_permission"])
                elif r["decision"] == "REJECTED":
                    self.assertIsNone(r["final_hours"])        # nothing is applied on a reject
                    self.assertGreaterEqual(r["latency_minutes"], 1)
                elif r["decision"] == "EDITED":
                    self.assertEqual(r["final_hours"], TRUTH_OPEN)  # owner edits to the true hours
                else:
                    self.assertIn(r["final_hours"], (TRUTH_OPEN, proposed))

    def test_exact_proposal_is_accepted_never_edited_or_rejected(self):
        decisions = Counter(r["decision"] for r in sample(TRUTH_OPEN, TRUTH_OPEN))
        self.assertEqual(set(decisions) - {"ACCEPTED", "NO_RESPONSE"}, set())
        self.assertGreater(decisions["ACCEPTED"], 0)

    def test_wrong_open_closed_state_is_never_accepted(self):
        for truth, prop in ((TRUTH_OPEN, "closed"), (TRUTH_CLOSED, "10:00-15:00")):
            decisions = Counter(r["decision"] for r in sample(truth, prop))
            self.assertEqual(decisions["ACCEPTED"], 0)
            self.assertGreater(decisions["REJECTED"], 0)
            self.assertGreater(decisions["EDITED"], 0)
            self.assertGreater(decisions["REJECTED"], decisions["EDITED"])  # 60/40 split

    def test_near_miss_is_mostly_edited(self):
        decisions = Counter(r["decision"] for r in sample(TRUTH_OPEN, "10:00-15:30"))
        self.assertGreater(decisions["EDITED"], decisions["ACCEPTED"] * 3)
        self.assertEqual(decisions["REJECTED"], 0)

    def test_standing_permission_only_with_acceptance(self):
        rs = sample(TRUTH_OPEN, TRUTH_OPEN, n=3000)
        perms = [r for r in rs if r["standing_permission"]]
        self.assertTrue(perms)
        self.assertTrue(all(r["decision"] == "ACCEPTED" for r in perms))
        self.assertTrue(0.05 < len(perms) / sum(r["decision"] == "ACCEPTED" for r in rs) < 0.2)  # ~12 %


class ResponseRate(unittest.TestCase):
    def rate(self, **kw):
        rs = sample(TRUTH_OPEN, TRUTH_OPEN, n=2000, **kw)
        return sum(r["decision"] != "NO_RESPONSE" for r in rs) / len(rs)

    def test_zero_responsiveness_never_responds(self):
        self.assertEqual(self.rate(resp=0.0), 0.0)

    def test_probability_is_capped_at_97_percent(self):
        r = sample(TRUTH_OPEN, TRUTH_OPEN, resp=5.0, channel="WHATSAPP", n=2000)
        share = sum(x["decision"] != "NO_RESPONSE" for x in r) / len(r)
        self.assertTrue(0.93 < share < 1.0, share)

    def test_channel_factor_matters(self):
        sms = sum(r["decision"] != "NO_RESPONSE" for r in sample(TRUTH_OPEN, TRUTH_OPEN, 0.8, "SMS"))
        push = sum(r["decision"] != "NO_RESPONSE" for r in sample(TRUTH_OPEN, TRUTH_OPEN, 0.8, "APP_PUSH"))
        self.assertGreater(sms, push)
        self.assertEqual(set(CHANNEL_FACTOR), set(LATENCY_MEDIAN_MIN))

    def test_unknown_channel_uses_default_factor_without_crashing(self):
        r = respond(TRUTH_OPEN, TRUTH_OPEN, 0.9, "CARRIER_PIGEON", "x")
        self.assertIn(r["decision"], ("ACCEPTED", "NO_RESPONSE"))

    def test_sending_at_night_lowers_response_rate(self):
        day = sum(r["decision"] != "NO_RESPONSE" for r in sample(TRUTH_OPEN, TRUTH_OPEN, 0.8, send_hour=10))
        night = sum(r["decision"] != "NO_RESPONSE" for r in sample(TRUTH_OPEN, TRUTH_OPEN, 0.8, send_hour=3))
        self.assertGreater(day, night)


class Latency(unittest.TestCase):
    def median(self, channel):
        xs = sorted(r["latency_minutes"] for r in sample(TRUTH_OPEN, TRUTH_OPEN, 0.97, channel, n=1500)
                    if r["latency_minutes"])
        return xs[len(xs) // 2]

    def test_email_is_much_slower_than_sms(self):
        self.assertGreater(self.median("EMAIL"), 3 * self.median("SMS"))

    def test_latency_is_a_positive_int(self):
        for r in sample(TRUTH_OPEN, TRUTH_OPEN, n=200):
            if r["latency_minutes"] is not None:
                self.assertIsInstance(r["latency_minutes"], int)
                self.assertGreaterEqual(r["latency_minutes"], 1)

    def test_long_tail_exists_which_matters_for_expiry_logic(self):
        """Some replies take >1 day even on SMS - any 'expired' rule must cope with late answers."""
        slow = [r for r in sample(TRUTH_OPEN, TRUTH_OPEN, 0.97, "EMAIL", n=2000)
                if r["latency_minutes"] and r["latency_minutes"] > 24 * 60]
        self.assertTrue(slow)


if __name__ == "__main__":
    unittest.main()
