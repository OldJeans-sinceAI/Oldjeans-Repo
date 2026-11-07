"""Map the team's read-only interpreter to the existing owner API contract."""

import os
import re
from .domain import interpret_reply, canonical_hours, HoursError, _ready_edit, _needs
from .teammate.reply_engine import ReplyEngine, DEFAULT_MODEL


class OwnerReplies:
    def __init__(self, engine=None):
        self.engine = engine or ReplyEngine(
            os.getenv("GEMINI_API_KEY", "")
            if os.getenv("GEMINI_ENABLED", "true").lower() == "true"
            else "",
            os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        )

    def health(self):
        return {
            "provider": "GEMINI" if self.engine.configured else "RULES",
            "model": self.engine.model if self.engine.configured else None,
            "configured": self.engine.configured,
            "timeout_ms": round(self.engine.timeout * 1000),
        }

    def interpret(self, text, language, proposal, multiple=False):
        low = text.strip().lower().rstrip(".! ")
        # Exact consent and exact numeric intervals need no remote reasoning.
        simple = low in {
            "yes",
            "approve",
            "ok",
            "sounds good",
            "confirm",
            "no",
            "reject",
            "no thanks",
            "decline",
            "kyllä",
            "hyväksy",
            "sopii",
            "joo",
            "ei",
            "ei kiitos",
            "hylkää",
            "ja",
            "nej",
            "nei",
            "네",
            "승인",
            "좋아요",
            "아니요",
            "거절",
            "closed",
            "kiinni",
            "suljettu",
            "휴무",
        }
        simple = simple or bool(
            re.fullmatch(
                r"\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}(\s*,\s*\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2})*",
                low,
            )
        )
        if simple:
            d = interpret_reply(text, language, proposal)
            if multiple and d.get("intent") == "APPROVE":
                d = _needs("Choose the date this reply applies to.", ["date"])
            return {
                **d,
                "interpretation": {
                    "provider": "RULES",
                    "latency_ms": 0,
                    "error_code": None,
                },
            }
        if not self.engine.configured:
            # Preserve strict offline preview; do not parse complex conditional text as consent.
            return {
                **_needs("Use the buttons or enter exact hours.", ["hours"]),
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
        reply = self.engine.interpret(context, text)
        meta = {
            "provider": "GEMINI",
            "latency_ms": reply.latency_ms,
            "error_code": reply.error_code,
        }
        if reply.status != "OK":
            return {
                "status": "UNAVAILABLE",
                "intent": "UNKNOWN",
                "preview": "Reply interpretation is unavailable. Nothing was changed; retry or use the buttons.",
                "missing_fields": [],
                "interpretation": meta,
            }
        missing = (
            ["reopen_date"]
            if proposal["change"]["kind"] == "REOPEN_DATE"
            else ["hours"]
        )
        d = _needs("Confirm the exact change using the editor.", missing)
        target = proposal["change"].get("date")
        mentioned = re.findall(r"\d{4}-\d{2}-\d{2}", text)
        if (
            not reply.scope_match
            or reply.needs_clarification
            or any(x != target for x in mentioned)
            or (reply.date and reply.date != target)
        ):
            return {**d, "interpretation": meta}
        if reply.intent in ("APPLY", "REJECT"):
            if reply.hours or (
                multiple and reply.intent == "APPLY" and target not in mentioned
            ):
                return {
                    **_needs("Choose the date this reply applies to.", ["date"]),
                    "interpretation": meta,
                }
            intent = "APPROVE" if reply.intent == "APPLY" else "REJECT"
            d = {
                "status": "READY",
                "intent": intent,
                "preview": intent + " this proposal.",
                "decision_draft": {
                    "decision": intent,
                    "proposal_version": proposal["version"],
                },
                "missing_fields": [],
            }
        elif (
            reply.intent == "EDIT"
            and target
            and proposal["change"]["kind"] == "DATE_HOURS"
            and reply.hours
        ):
            try:
                hours = canonical_hours(reply.hours)
                d = _ready_edit(
                    proposal,
                    proposal["version"],
                    target,
                    hours,
                    f"Set {target} to {hours}.",
                )
            except HoursError:
                pass
        return {**d, "interpretation": meta}
