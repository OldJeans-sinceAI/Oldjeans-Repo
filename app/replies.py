"""Map the team's read-only interpreter to the existing owner API contract."""

import os
import re
from .domain import interpret_reply, canonical_hours, HoursError, _ready_edit, _needs
from .teammate.reply_engine import ReplyEngine, DEFAULT_MODEL


class OwnerReplies:
 def __init__(self, engine=None):
  k=os.getenv("GEMINI_API_KEY","") if os.getenv("GEMINI_ENABLED","true").lower()=="true" else ""
  self.engine=engine or ReplyEngine(k,os.getenv("GEMINI_MODEL",DEFAULT_MODEL))

 def health(self):
  return {"provider":"GEMINI" if self.engine.configured else "RULES","model":self.engine.model if self.engine.configured else None,"configured":self.engine.configured,"timeout_ms":round(self.engine.timeout*1000)}

 def interpret(self, text, language, proposal, multiple=False):
  low=text.strip().lower().rstrip(".! ")
  # Exact consent and exact numeric intervals need no remote reasoning.
  s=low in {"yes","approve","ok","sounds good","confirm","no","reject","no thanks","decline","kyllä","hyväksy","sopii","joo","ei","ei kiitos","hylkää","ja","nej","nei","네","승인","좋아요","아니요","거절","closed","kiinni","suljettu","휴무"}
  s=s or bool(re.fullmatch(r"\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}(\s*,\s*\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2})*",low))
  if s:
   d=interpret_reply(text,language,proposal)
   if multiple and d.get("intent")=="APPROVE": d=_needs("Choose the date this reply applies to.",["date"])
   return {**d,"interpretation":{"provider":"RULES","latency_ms":0,"error_code":None}}
  if not self.engine.configured:
   # Preserve strict offline preview; do not parse complex conditional text as consent.
   return {**_needs("Use the buttons or enter exact hours.",["hours"]),"interpretation":{"provider":"RULES","latency_ms":0,"error_code":"NOT_CONFIGURED"}}
  ctx={"change":proposal["change"],"timezone":proposal["timezone"],"current_value":proposal.get("current_value")}
  r=self.engine.interpret(ctx,text)
  m={"provider":"GEMINI","latency_ms":r.latency_ms,"error_code":r.error_code}
  if r.status!="OK": return {"status":"UNAVAILABLE","intent":"UNKNOWN","preview":"Reply interpretation is unavailable. Nothing was changed; retry or use the buttons.","missing_fields":[],"interpretation":m}
  mis=["reopen_date"] if proposal["change"]["kind"]=="REOPEN_DATE" else ["hours"]
  d=_needs("Confirm the exact change using the editor.",mis)
  t=proposal["change"].get("date")
  men=re.findall(r"\d{4}-\d{2}-\d{2}",text)
  if not r.scope_match or r.needs_clarification or any(x!=t for x in men) or (r.date and r.date!=t): return {**d,"interpretation":m}
  if r.intent in ("APPLY","REJECT"):
   if r.hours or (multiple and r.intent=="APPLY" and t not in men): return {**_needs("Choose the date this reply applies to.",["date"]),"interpretation":m}
   it="APPROVE" if r.intent=="APPLY" else "REJECT"
   d={"status":"READY","intent":it,"preview":it+" this proposal.","decision_draft":{"decision":it,"proposal_version":proposal["version"]},"missing_fields":[]}
  elif r.intent=="EDIT" and t and proposal["change"]["kind"]=="DATE_HOURS" and r.hours:
   try:
    hrs=canonical_hours(r.hours)
    d=_ready_edit(proposal,proposal["version"],t,hrs,f"Set {t} to {hrs}.")
   except HoursError: pass
  return {**d,"interpretation":m}
