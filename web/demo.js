"use strict";

// A presentation of real API results. No contact or decision is inferred here.
const JOURNEY_STEPS = ["Detect", "Suggest", "Contact", "Decide", "Apply & confirm"];
const demoStorageKey = () => "connect-demo-journey" + APP_BASE;

function newDemoState() {
 let s = {};
 try { s = JSON.parse(sessionStorage.getItem(demoStorageKey()) || "{}"); } catch (e) {
  console.warn("Failed to parse stored demo state:", e);
  sessionStorage.removeItem(demoStorageKey());
 }
 if (!s || typeof s !== "object" || Array.isArray(s)) s = {};
 return {
  stage: [1, 2, 3, 5].includes(s.stage) ? s.stage : 1,
  date: /^\d{4}-\d{2}-\d{2}$/.test(s.date || "") ? s.date : "2026-12-24",
  runId: typeof s.runId === "string" ? s.runId : null,
  proposalId: typeof s.proposalId === "string" ? s.proposalId : null,
  messageId: typeof s.messageId === "string" ? s.messageId : null,
  run: null, proposal: null, message: null, result: null, busy: false, note: "",
 };
}
function saveDemo() {
 const {stage: st, date: dt, runId: rId, proposalId: pId, messageId: mId} = state.demo;
 // Never keep an owner capability in presentation state.
 sessionStorage.setItem(demoStorageKey(), JSON.stringify({stage: st, date: dt, runId: rId, proposalId: pId, messageId: mId}));
}
function journeySteps(active, finished = false) {
 return `<ol class="journey-steps" aria-label="Business hours journey">${JOURNEY_STEPS.map((label, i) => {
  const st = i + 1, dn = st < active || (finished && st === active);
  return `<li class="${dn ? "done" : st === active ? "current" : ""}" ${st === active ? 'aria-current="step"' : ""}><span class="journey-number">${dn ? "✓" : st}</span><span>${label}</span></li>`;
 }).join("")}</ol>`;
}
function demoScanComplete() {
 return ["COMPLETED", "COMPLETED_WITH_ERRORS"].includes(state.demo.run?.status);
}
function renderDemo() {
 const d = state.demo, p = d.proposal, j = d.run;
 const tot = j?.total_businesses ?? state.fleetTotal ?? "—";
 const sc = j?.status === "RUNNING";
 const dn = d.result?.application_status === "SUCCEEDED" || d.result?.decision_status === "REJECTED";
 let c = "";
 if (d.stage === 1) {
  const pct = j?.total_businesses ? Math.round(j.processed_businesses / j.total_businesses * 100) : 0;
  c = `<div class="journey-kicker">01 / DETECT</div><h2>Start with every business.</h2><p class="journey-intro">Check opening hours against the available evidence. Find what needs a suggestion, what needs a person, and what can stay as it is.</p><div class="scan-illustration" aria-hidden="true"><div><span>▦</span>Business directory</div><b>→</b><div><span>⌕</span>Evidence check</div><b>→</b><div><span>✓</span>Clear next action</div></div><div class="journey-controls"><label>Target date<input type="date" id="demo-date" value="${h(d.date)}" ${sc || d.busy ? "disabled" : ""}></label><button class="primary" data-demo-action="scan" ${sc || d.busy ? "disabled" : ""}>${sc ? '<span class="spinner"></span> Checking businesses…' : `Scan all ${tot} businesses →`}</button></div>${j ? `<div class="journey-scan" aria-live="polite"><div class="meta-row"><strong>${j.processed_businesses.toLocaleString("en-GB")} / ${j.total_businesses.toLocaleString("en-GB")} businesses checked</strong><span>${h(t(j.status))}</span></div><progress value="${pct}" max="100" aria-label="Businesses checked"></progress><div class="journey-counts">${[["SUGGEST", "Suggest hours"], ["FLAG", "Staff review"], ["NO_ACTION", "No outreach"]].map(([k, l]) => `<div><strong>${j.counts[k]}</strong><span>${l}</span></div>`).join("")}</div>${j.failed_businesses ? `<p class="notice warn">${j.failed_businesses} businesses could not be checked. Results cover the completed checks.</p>` : ""}</div>` : `<p class="journey-note">${tot} businesses · one date · no automatic messages or approvals</p>`}<div class="journey-next"><span>${demoScanComplete() ? "The scan is ready. Follow one real suggestion next." : "Suggestions appear once the scan has finished."}</span><button class="primary" data-demo-action="suggest" ${!demoScanComplete() || d.busy ? "disabled" : ""}>Review a suggestion →</button></div>`;
 } else if (d.stage === 2 && p) {
  c = `<div class="journey-kicker">02 / SUGGEST</div><h2>A clear proposal, with a reason.</h2><p class="journey-intro">One recommendation from the directory scan. The owner will decide whether these hours fit their plan.</p><div class="journey-business"><div><strong>${h(p.business_name)}</strong><span>${h(holidayLabel(p.day_key))} · ${h(dateLabel(p.change.date, p.timezone))}</span></div>${badge(p.confidence)}</div>${scheduleView(p)}<div class="journey-reason"><span class="journey-symbol">↗</span><div><h3>Why suggest this?</h3><p>${h(reasonText(p))}</p><small>Evidence supports a proposal. The owner's final plan still needs confirmation.</small></div></div><details class="details"><summary>View the evidence</summary>${evidence(p.evidence)}</details><div class="journey-next"><button class="ghost" data-demo-action="another" ${d.busy ? "disabled" : ""}>Choose another suggestion</button><button class="primary" data-demo-action="contact" ${d.busy ? "disabled" : ""}>Prepare the owner message →</button></div>`;
 } else if (d.stage === 3 && p) {
  const m = d.message;
  c = `<div class="journey-kicker">03 / CONTACT</div><h2>Make the next step easy.</h2><p class="journey-intro">The owner receives the current hours, the proposed change and the reason in one English message.</p>${m ? `<div class="journey-message"><div class="meta-row"><strong>Fonecta Connect</strong><span class="badge mock">${h(m.channel)} · ${h(t(m.status))}</span></div><p class="muted">To ${h(p.business_name)} · English</p>${m.subject ? `<h3>${h(m.subject)}</h3>` : ""}<div class="journey-message-body">${h(m.text)}</div></div><p class="journey-note">Simulated delivery for the demo. No message is sent to a real customer.</p><div class="journey-next"><button class="ghost" data-demo-action="suggest-back">← Review the suggestion</button>${m.owner_entry_path ? `<a class="button-link primary" id="demo-owner-link" href="${h(whatsappOwnerLink(m.owner_entry_path))}">Open the owner’s WhatsApp →</a>` : `<div class="notice warn">Contact is blocked by this owner's preferences. <button class="small" data-demo-action="another">Choose another suggestion</button></div>`}</div>` : `<button class="primary" data-demo-action="contact" ${d.busy ? "disabled" : ""}>Prepare the owner message →</button>`}`;
 } else if (d.stage === 5 && p) {
  c = `<div class="journey-kicker">05 / OUTCOME</div><h2>${d.result?.decision_status === "REJECTED" ? "The owner chose to keep their hours." : dn ? "The right hours, saved and checked." : "Follow the decision through."}</h2>${renderResult(p, d.result, "demo")}<div class="journey-next"><button class="ghost" data-demo-action="refresh">Refresh the result</button><button class="primary" data-demo-action="another">Follow another suggestion →</button></div>`;
 } else {
  c = `<p>Loading this walkthrough…</p><button data-demo-action="restart">Start from the scan</button>`;
 }
 return `<section class="journey" id="demo-journey">${journeySteps(d.stage, dn)}<div class="journey-card" aria-busy="${d.busy}">${c}${d.note ? `<div class="notice warn" role="status">${h(d.note)}${d.stage === 1 && d.runId ? `<br><button class="small" data-demo-action="refresh">Refresh scan status</button>` : ""}</div>` : ""}</div><div class="journey-caption"><span>Real evidence</span><span>Owner in control</span><span>Verified outcome</span></div></section>`;
}

let demoPoll;
function scheduleDemoPoll() {
 clearTimeout(demoPoll);
 if (state.demo.run?.status !== "RUNNING" || IS_OWNER) return;
 demoPoll = setTimeout(async () => {
  try {
   state.demo.run = await api(`/api/v1/operator/fleet-runs/${encodeURIComponent(state.demo.runId)}`);
   if (state.tab === "demo") render();
   scheduleDemoPoll();
  } catch (e) {
   state.demo.note = errorText(e);
   if (state.tab === "demo") render();
   // Explicit retry via the scan button; do not mark a failed poll complete.
  }
 }, 1200);
}
async function restoreDemo() {
 const d = state.demo;
 try {
  if (d.runId) d.run = await api(`/api/v1/operator/fleet-runs/${encodeURIComponent(d.runId)}`);
  else if (state.fleet?.scope === "EXPLICIT_DATE" && state.fleet.date === d.date) {
   d.run = state.fleet; d.runId = state.fleet.run_id;
  }
  if (d.proposalId) {
   d.proposal = await api(`/api/v1/proposals/${encodeURIComponent(d.proposalId)}`);
   if (d.proposal.decision_status !== "PENDING") {
    d.result = await api(`/api/v1/proposals/${encodeURIComponent(d.proposalId)}/result`);
    d.stage = 5;
   } else if (d.stage === 3) {
    const ms = await api(`/api/v1/operator/messages?entity_id=${encodeURIComponent(d.proposal.entity_id)}&delivery_mode=PREVIEW&limit=100`);
    d.message = ms.items.find(m => m.message_id === d.messageId) || null;
   }
  }
  saveDemo(); scheduleDemoPoll();
 } catch (e) {
  if ([404, 410].includes(e.status)) {
   sessionStorage.removeItem(demoStorageKey());
   state.demo = newDemoState();
   state.demo.note = "This earlier walkthrough is no longer available. Start a new scan.";
  } else throw e;
 }
}
async function pickDemoSuggestion(skipCurrent = false) {
 const d = state.demo;
 await refreshCases();
 const cnds = state.cases.filter(c => c.action === "SUGGEST" && c.proposal_id && c.target_date === d.date && (!skipCurrent || c.proposal_id !== d.proposalId));
 // Prefer an actual WhatsApp contact, using the existing paginated directory.
 // Keep the source preference intact; no synthetic channel override is stored.
 const byE = new Map(cnds.map(c => [c.entity_id, c]));
 let fb = null;
 async function select(c) {
  const p = await api(`/api/v1/proposals/${encodeURIComponent(c.proposal_id)}`);
  if (p.decision_status !== "PENDING") return false;
  d.proposal = p; d.proposalId = p.proposal_id; d.message = null; d.messageId = null; d.result = null; d.stage = 2;
  saveDemo(); return true;
 }
 if (cnds.length) {
  for (let offset = 0; ; offset += 100) {
   const page = await api(`/api/v1/operator/businesses?offset=${offset}&limit=100`);
   for (const b of page.items) {
    const c = byE.get(b.entity_id);
    if (!c || b.source_opted_out) continue;
    if (b.preferred_channel === "WHATSAPP") {
     if (await select(c)) return;
    } else if (!fb) {
     const p = await api(`/api/v1/proposals/${encodeURIComponent(c.proposal_id)}`);
     if (p.decision_status === "PENDING") fb = c;
    }
   }
   if (offset + page.items.length >= page.total || !page.items.length) break;
  }
  // The owner page labels this as a layout preview for their actual channel.
  if (fb && await select(fb)) return;
 }
 d.note = "No other pending suggestion is available for this date. Choose a new date and scan again, or review the cases in Workspace.";
 d.stage = 1; saveDemo();
}
async function handleDemoAction(act) {
 const d = state.demo;
 if (d.busy) return;
 d.busy = true; d.note = "";
 render();
 try {
  if (act === "scan") {
   const r = await api("/api/v1/operator/fleet-runs", "POST", {scope: "EXPLICIT_DATE", date: d.date});
   Object.assign(d, {run: r, runId: r.run_id, stage: 1, proposal: null, proposalId: null, message: null, messageId: null, result: null});
   state.fleet = r; saveDemo(); scheduleDemoPoll();
  } else if (act === "suggest" || act === "another") {
   await pickDemoSuggestion(act === "another");
  } else if (act === "contact") {
   if (!d.proposalId) throw new Error("Choose a suggestion first.");
   d.message = await api("/api/v1/operator/messages", "POST", {entity_id: d.proposal.entity_id, proposal_ids: [d.proposalId], delivery_mode: "PREVIEW"}, key());
   d.messageId = d.message.message_id; d.stage = 3; saveDemo();
  } else if (act === "suggest-back") {
   d.stage = 2; saveDemo();
  } else if (act === "refresh") {
   await restoreDemo();
  } else if (act === "restart") {
   d.stage = 1; saveDemo();
  }
 } catch (e) { d.note = errorText(e); }
 finally { d.busy = false; render(); }
}
function ownerJourney() {
 if (!state.owner || !state.proposals.length) return "";
 const pnd = state.proposals.some(p => p.decision_status === "PENDING");
 const dn = state.proposals.every(p => p._result?.application_status === "SUCCEEDED" || p.decision_status === "REJECTED");
 return `<div class="owner-journey">${journeySteps(pnd ? 4 : 5, dn)}<p class="journey-role">${pnd ? "YOUR TURN · BUSINESS OWNER" : "YOUR DECISION · YOUR HOURS"}</p></div>`;
}
