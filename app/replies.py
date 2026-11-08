"""Map the team's read-only interpreter to the existing owner API contract."""

import os
import re
from .domain import interpret_reply, canonical_hours, HoursError, ready_edit, needs_clarification
from .teammate.reply_engine import ReplyEngine, DEFAULT_MODEL


class OwnerReplies:
	def __init__(self, engine=None):
		api_key = (
			os.getenv("GEMINI_API_KEY", "")
			if os.getenv("GEMINI_ENABLED", "true").lower() == "true"
			else ""
		)
		self.engine = engine or ReplyEngine(
			api_key, os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
		)

	def health(self):
		return {
			"provider": "GEMINI" if self.engine.configured else "RULES",
			"model": self.engine.model if self.engine.configured else None,
			"configured": self.engine.configured,
			"timeout_ms": round(self.engine.timeout * 1000),
		}

	def interpret(self, text, language, proposal, multiple=False):
		cleaned_text = text.strip().lower().rstrip(".! ")
		# Exact consent and exact numeric intervals need no remote reasoning.
		is_exact_reply = cleaned_text in {
			"yes", "approve", "ok", "sounds good", "confirm", "no", "reject", "no thanks",
			"decline", "kyllä", "hyväksy", "sopii", "joo", "ei", "ei kiitos", "hylkää",
			"ja", "nej", "nei", "네", "승인", "좋아요", "아니요", "거절", "closed", "kiinni",
			"suljettu", "휴무",
		} or bool(
			re.fullmatch(
				r"\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}(\s*,\s*\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2})*",
				cleaned_text,
			)
		)
		if is_exact_reply:
			rule_result = interpret_reply(text, language, proposal)
			if multiple and rule_result.get("intent") == "APPROVE":
				rule_result = needs_clarification(
					"Choose the date this reply applies to.", ["date"]
				)
			return {
				**rule_result,
				"interpretation": {
					"provider": "RULES",
					"latency_ms": 0,
					"error_code": None,
				},
			}
		if not self.engine.configured:
			# Preserve strict offline preview; do not parse complex conditional text as consent.
			return {
				**needs_clarification("Use the buttons or enter exact hours.", ["hours"]),
				"interpretation": {
					"provider": "RULES",
					"latency_ms": 0,
					"error_code": "NOT_CONFIGURED",
				},
			}
		context = {
			"change": proposal["change"],
			"timezone": proposal["timezone"],
			"current_value": proposal.get("current_value"),
		}
		engine_reply = self.engine.interpret(context, text)
		meta = {
			"provider": "GEMINI",
			"latency_ms": engine_reply.latency_ms,
			"error_code": engine_reply.error_code,
		}
		if engine_reply.status != "OK":
			return {
				"status": "UNAVAILABLE",
				"intent": "UNKNOWN",
				"preview": "Reply interpretation is unavailable. Nothing was changed; retry or use the buttons.",
				"missing_fields": [],
				"interpretation": meta,
			}
		missing_fields = (
			["reopen_date"]
			if proposal["change"]["kind"] == "REOPEN_DATE"
			else ["hours"]
		)
		draft = needs_clarification("Confirm the exact change using the editor.", missing_fields)
		target_date = proposal["change"].get("date")
		mentioned_dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
		if (
			not engine_reply.scope_match
			or engine_reply.needs_clarification
			or any(x != target_date for x in mentioned_dates)
			or (engine_reply.date and engine_reply.date != target_date)
		):
			return {**draft, "interpretation": meta}
		if engine_reply.intent in ("APPLY", "REJECT"):
			if engine_reply.hours or (
				multiple and engine_reply.intent == "APPLY" and target_date not in mentioned_dates
			):
				return {
					**needs_clarification("Choose the date this reply applies to.", ["date"]),
					"interpretation": meta,
				}
			intent_code = "APPROVE" if engine_reply.intent == "APPLY" else "REJECT"
			draft = {
				"status": "READY",
				"intent": intent_code,
				"preview": intent_code + " this proposal.",
				"decision_draft": {
					"decision": intent_code,
					"proposal_version": proposal["version"],
				},
				"missing_fields": [],
			}
		elif (
			engine_reply.intent == "EDIT"
			and target_date
			and proposal["change"]["kind"] == "DATE_HOURS"
			and engine_reply.hours
		):
			try:
				hours = canonical_hours(engine_reply.hours)
				draft = ready_edit(
					proposal,
					proposal["version"],
					target_date,
					hours,
					f"Set {target_date} to {hours}.",
				)
			except HoursError:
				pass
		return {**draft, "interpretation": meta}
