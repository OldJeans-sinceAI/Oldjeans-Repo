"""Traceability stubs for requirements that have NO implementation in this repository snapshot.

The task brief (and Fonecta's challenge text) require these, but the ZIP contains no LLM call, no suggestion
state machine, no confidence threshold, no expiry job, no customer-facing approve/edit/reject UI, no message
sender and no learning loop. We deliberately do NOT invent an implementation: each test below is skipped with the
exact contract it will assert. When the team adds the code, delete the skip, import the module and fill in the body
(each docstring = preconditions / steps / expected).

Run `pytest -rs tests/py/test_pending_features.py` to list what is still missing.
"""
import unittest

NOT_BUILT = "NOT IMPLEMENTED in repo snapshot - "


class SuggestionStateMachine(unittest.TestCase):
    """States: pending | approved | edited | rejected | expired."""

    @unittest.skip(NOT_BUILT + "no suggestion store / state field")
    def test_new_suggestion_starts_pending(self):
        """Pre: engine emits SUGGEST. Steps: create suggestion + send message. Expect: status == 'pending', audit row
        has basis/evidence/confidence/created_at."""

    @unittest.skip(NOT_BUILT + "no decision endpoint")
    def test_valid_transitions(self):
        """pending->approved (writes suggested hours), pending->edited (writes customer hours), pending->rejected
        (writes nothing), pending->expired (writes nothing)."""

    @unittest.skip(NOT_BUILT + "no decision endpoint")
    def test_terminal_states_cannot_change(self):
        """Pre: suggestion approved. Steps: click Reject / Edit / Approve again. Expect: 409 / no-op, still approved,
        no second Yext PUT (double-click and replayed-link safety)."""

    @unittest.skip(NOT_BUILT + "no expiry logic (simulator only returns NO_RESPONSE)")
    def test_answer_after_the_date_has_passed_is_expired_and_not_applied(self):
        """Pre: pending suggestion for 2026-12-24. Steps: clock = 2026-12-25, customer clicks Approve. Expect: status
        'expired', page says the date has passed, Yext untouched. Also: job sweeps pending->expired at cutoff."""

    @unittest.skip(NOT_BUILT)
    def test_edit_is_validated_before_apply(self):
        """Edit '25:00-26:00', '10:00-10:00', overlapping or empty input -> 400 to the customer, status stays pending,
        no PUT. Edit to valid '10:00-14:00' -> status 'edited', PUT with the customer's hours (not the suggestion)."""


class ConfidenceAndGuardrails(unittest.TestCase):
    @unittest.skip(NOT_BUILT + "baseline writes a constant confidence=0.6; nothing consumes it")
    def test_below_threshold_is_not_sent(self):
        """Pre: threshold T. Steps: engine yields confidence T-epsilon / T / T+epsilon. Expect: below -> no message
        (or 'ask' / FLAG), at/above -> message. Boundary inclusive/exclusive must match the documented rule."""

    @unittest.skip(NOT_BUILT)
    def test_opt_out_customers_are_never_contacted(self):
        """customer_contacts.opted_out_of_suggestions == 1 -> zero messages, zero suggestions created."""

    @unittest.skip(NOT_BUILT)
    def test_standing_permission_applies_then_informs(self):
        """FI-D0012 (standing_permission_holidays == 1): suggestion applied without asking, customer informed after,
        audit row source == 'standing_permission'. Non-holiday changes still require approval."""

    @unittest.skip(NOT_BUILT)
    def test_nothing_is_published_without_approval_or_standing_permission(self):
        """Property test over all engine outputs: Yext PUT count == approved + edited + standing-permission count."""

    @unittest.skip(NOT_BUILT)
    def test_closed_for_good_is_routed_to_human_review(self):
        """FI-D0011: FLAG creates a review task for staff, no customer message, no suggestion record."""


class LlmExplanation(unittest.TestCase):
    """The LLM only WORDS the explanation; hours must come from the deterministic engine."""

    @unittest.skip(NOT_BUILT + "no LLM client in repo (quickstart uses static templates)")
    def test_llm_output_cannot_change_the_suggested_hours(self):
        """Mock LLM returns text containing different hours. Expect: suggestion.hours unchanged; message states the
        engine's hours; a mismatch between text and hours falls back to the template."""

    @unittest.skip(NOT_BUILT)
    def test_llm_failure_modes_fall_back_to_template(self):
        """For each of: timeout, HTTP 429/500, empty string, non-JSON, wrong language, hallucinated date, >limit length,
        prompt-injection text from a review. Expect: message still sent using the static fi/sv/nb/en template; failure
        logged; no exception to the caller."""

    @unittest.skip(NOT_BUILT)
    def test_message_language_matches_customer_preference(self):
        """customer_contacts.preferred_language in {fi,sv,nb,en} -> message in that language incl. weekday/date format."""

    @unittest.skip(NOT_BUILT)
    def test_llm_never_receives_personal_data_beyond_whats_needed(self):
        """Prompt captured by the mock contains no email/phone from customer_contacts.csv."""


class ContactAndDecideUi(unittest.TestCase):
    @unittest.skip(NOT_BUILT + "no sender, no web UI (START_HERE.html is documentation only)")
    def test_message_contains_signed_single_use_links_no_login(self):
        """Each of Approve / Edit / Decline is a unique unguessable URL; opening it requires no login; a tampered or
        reused token -> 404/410; token bound to one suggestion."""

    @unittest.skip(NOT_BUILT)
    def test_decision_page_renders_hours_reason_and_three_buttons(self):
        """HTML: shows date, current vs suggested hours, reason, and exactly three actions; works at 360px width;
        no JS required for Approve."""

    @unittest.skip(NOT_BUILT)
    def test_confirmation_lists_where_hours_will_show(self):
        """After APPLY: confirmation text lists publishers from /listings with human ETA (Google ~2 min, ...)."""

    @unittest.skip(NOT_BUILT)
    def test_channel_and_send_time_respect_contact_preferences(self):
        """preferred_channel + best_contact_window honoured; fallback channel when the first fails."""


class Learning(unittest.TestCase):
    @unittest.skip(NOT_BUILT + "pilot_decision_log_2025.csv is read by nothing")
    def test_decline_or_edit_changes_the_next_suggestion(self):
        """After customer edits 07:30-13:00 -> 08:00-12:00 for XMAS_EVE, next season's suggestion for the same
        business/day_key is 08:00-12:00 (or confidence rises for the edited value)."""

    @unittest.skip(NOT_BUILT)
    def test_repeated_declines_suppress_that_suggestion_type(self):
        """N consecutive declines for the same day_key -> stop proposing it (or ask once about standing rule)."""


if __name__ == "__main__":
    unittest.main()
