"use strict";

// A presentation of real API results. No contact or decision is inferred here.
const JOURNEY_STEPS = ["Detect", "Suggest", "Contact", "Decide", "Apply & confirm"];
const demoStorageKey = () => "connect-demo-journey" + APP_BASE;

function newDemoState() {
  let saved = {};
  try { saved = JSON.parse(sessionStorage.getItem(demoStorageKey()) || "{}"); } catch {}
  if (!saved || typeof saved !== "object" || Array.isArray(saved)) saved = {};
  return {
    stage: [1, 2, 3, 4, 5].includes(saved.stage) ? saved.stage : 1,
    date: /^\d{4}-\d{2}-\d{2}$/.test(saved.date || "") ? saved.date : "2026-12-24",
    runId: typeof saved.runId === "string" ? saved.runId : null,
    proposalId: typeof saved.proposalId === "string" ? saved.proposalId : null,
    messageId: typeof saved.messageId === "string" ? saved.messageId : null,
    run: null, proposal: null, message: null, result: null, busy: false, note: "",
  };
}
function saveDemo() {
  const {stage, date, runId, proposalId, messageId} = state.demo;
  // Never keep an owner capability in presentation state.
  sessionStorage.setItem(demoStorageKey(), JSON.stringify({stage, date, runId, proposalId, messageId}));
}
// A decision and a verified application are different facts.
function journeyOutcome(p, r = p?._result) {
  if (!p || p.decision_status === "PENDING") return "PENDING";
  if (["EXPIRED", "SUPERSEDED"].includes(p.decision_status)) return "EXPIRED";
  if (p.decision_status === "REJECTED") return "REJECTED";
  if (r?.application_status === "SUCCEEDED") return "APPLIED";
  if (["FAILED", "CONFLICT", "REVIEW_REQUIRED"].includes(r?.application_status)) return "FAILED";
  return "APPLYING";
}
const resolvedJourney = outcome => ["APPLIED", "REJECTED"].includes(outcome);
function journeySteps(active, outcome = "PENDING") {
  return `<ol class="journey-steps" aria-label="Business hours journey">${JOURNEY_STEPS.map((label, i) => {
    const step = i + 1, current = step === active;
    let status = step < active ? "done" : "", symbol = step < active ? "✓" : step, detail = "";
    if (current && active === 4) {
      detail = outcome === "EXPIRED" ? "No longer available" : "Awaiting decision";
      if (outcome === "EXPIRED") { status = "attention"; symbol = "!"; }
    }
    if (current && active === 5) {
      if (outcome === "APPLIED") { status = "done"; symbol = "✓"; detail = "Saved & verified"; }
      else if (outcome === "REJECTED") { status = "skipped"; symbol = "–"; detail = "No change needed"; }
      else if (outcome === "FAILED") { status = "attention"; symbol = "!"; detail = "Needs attention"; }
      else detail = "Awaiting verification";
    }
    return `<li class="${status}${current ? " current" : ""}" ${current ? 'aria-current="step"' : ""}><span class="journey-number">${symbol}</span><span>${label}</span>${detail ? `<small>${detail}</small>` : ""}</li>`;
  }).join("")}</ol>`;
}
function ownerJourneyOutcome() {
  const outcomes = state.proposals.map(p => journeyOutcome(p));
  if (!outcomes.length) return "PENDING";
  for (const kind of ["PENDING", "EXPIRED", "FAILED", "APPLYING"]) if (outcomes.includes(kind)) return kind;
  return outcomes.includes("APPLIED") ? "APPLIED" : "REJECTED";
}
function ownerJourneyStep() {
  return ["PENDING", "EXPIRED"].includes(ownerJourneyOutcome()) ? 4 : 5;
}
function ownerDemoNavigation() {
  if (!state.proposals.length) return "";
  const outcome = ownerJourneyOutcome(), saved = newDemoState();
  const current = state.proposals.find(p => p.proposal_id === saved.proposalId);
  const next = !APP_BASE && current && saved.runId && resolvedJourney(outcome);
  const title = outcome === "APPLIED" ? "This business is ready." : outcome === "REJECTED" ? "This business keeps its current hours." : outcome === "EXPIRED" ? "This proposal needs a fresh review." : outcome === "FAILED" ? "This update needs attention." : "Continue this walkthrough.";
  return `<section class="journey-continuation" aria-label="Continue the demo"><div><p class="journey-kicker">${resolvedJourney(outcome) ? "BUSINESS REVIEW COMPLETE" : "DEMO NAVIGATION"}</p><h2>${title}</h2><p>${next ? "Continue with the next business from the same directory scan. Its suggestion will open first; contact and approval remain separate steps." : "Return to the workspace to review this business and its current status."}</p></div><div class="journey-continuation-actions">${next ? `<a class="button-link primary" data-next-business href="/?next_business=${encodeURIComponent(current.proposal_id)}">Next business →</a>` : ""}<a class="journey-return ${next ? "" : "button-link"}" href="${APP_BASE}/">${next ? "View this result in the guided demo" : APP_BASE ? "Back to workspace" : "Back to the guided demo"}</a></div></section>`;
}
function demoScanComplete() {
  return ["COMPLETED", "COMPLETED_WITH_ERRORS"].includes(state.demo.run?.status);
}
function renderDemo() {
  const d = state.demo, p = d.proposal, job = d.run;
  const total = job?.total_businesses ?? state.fleetTotal ?? "—";
  const scanning = job?.status === "RUNNING";
  const outcome = journeyOutcome(p, d.result), done = resolvedJourney(outcome);
  let content = "";
  if (d.stage === 1) {
    const pct = job?.total_businesses ? Math.round(job.processed_businesses / job.total_businesses * 100) : 0;
    content = `<div class="journey-kicker">01 / DETECT</div><h2>${demoScanComplete() ? "Your directory scan is ready." : "Start with every business."}</h2><p class="journey-intro">Check opening hours against the available evidence. Find what needs a suggestion, what needs a person, and what can stay as it is.</p><div class="scan-illustration" aria-hidden="true"><div><span>▦</span>Business directory</div><b>→</b><div><span>⌕</span>Evidence check</div><b>→</b><div><span>✓</span>Clear next action</div></div><div class="journey-controls"><label>Target date<input type="date" id="demo-date" value="${h(d.date)}" ${scanning || d.busy ? "disabled" : ""}></label><button class="primary" data-demo-action="scan" ${scanning || d.busy ? "disabled" : ""}>${scanning ? '<span class="spinner"></span> Checking businesses…' : `Scan all ${total} businesses →`}</button></div>${job ? `<div class="journey-scan" aria-live="polite"><div class="meta-row"><strong>${job.processed_businesses.toLocaleString("en-GB")} / ${job.total_businesses.toLocaleString("en-GB")} businesses checked</strong><span>${h(t(job.status))}</span></div><progress value="${pct}" max="100" aria-label="Businesses checked"></progress><div class="journey-counts">${[["SUGGEST", "Suggest hours"], ["FLAG", "Staff review"], ["NO_ACTION", "No outreach"]].map(([key, label]) => `<div><strong>${job.counts[key]}</strong><span>${label}</span></div>`).join("")}</div>${job.failed_businesses ? `<p class="notice warn">${job.failed_businesses} businesses could not be checked. Results cover the completed checks.</p>` : ""}</div>` : `<p class="journey-note">${total} businesses · one date · no automatic messages or approvals</p>`}<div class="journey-next"><span>${demoScanComplete() ? "Review businesses one at a time from this scan. No need to scan again between businesses." : "Suggestions appear once the scan has finished."}</span><button class="primary" data-demo-action="suggest" ${!demoScanComplete() || d.busy ? "disabled" : ""}>Review a suggestion →</button></div>`;
  } else if (d.stage === 2 && p) {
    content = `<div class="journey-kicker">02 / SUGGEST</div><h2>A clear proposal, with a reason.</h2><p class="journey-intro">One recommendation from the directory scan. The owner will decide whether these hours fit their plan.</p><div class="journey-business"><div><strong>${h(p.business_name)}</strong><span>${h(holidayLabel(p.day_key))} · ${h(dateLabel(p.change.date, p.timezone))}</span></div>${badge(p.confidence)}</div>${scheduleView(p)}<div class="journey-reason"><span class="journey-symbol">↗</span><div><h3>Why suggest this?</h3><p>${h(reasonText(p))}</p><small>Evidence supports a proposal. The owner's final plan still needs confirmation.</small></div></div><details class="details"><summary>View the evidence</summary>${evidence(p.evidence)}</details><div class="journey-next"><button class="ghost" data-demo-action="another" ${d.busy ? "disabled" : ""}>Choose another suggestion</button><button class="primary" data-demo-action="contact" ${d.busy ? "disabled" : ""}>Prepare the owner message →</button></div>`;
  } else if (d.stage === 3 && p) {
    const m = d.message;
    content = `<div class="journey-kicker">03 / CONTACT</div><h2>Make the next step easy.</h2><p class="journey-intro">The owner receives the current hours, the proposed change and the reason in one English message.</p>${m ? `<div class="journey-message"><div class="meta-row"><strong>Fonecta Connect</strong><span class="badge mock">${h(m.channel)} · ${h(t(m.status))}</span></div><p class="muted">To ${h(p.business_name)} · English</p>${m.subject ? `<h3>${h(m.subject)}</h3>` : ""}<div class="journey-message-body">${h(m.text)}</div></div><p class="journey-note">Simulated delivery for the demo. No message is sent to a real customer.</p><div class="journey-next"><button class="ghost" data-demo-action="suggest-back">← Review the suggestion</button>${m.owner_entry_path ? `<a class="button-link primary" id="demo-owner-link" href="${h(channelOwnerLink(m.owner_entry_path, m.channel))}">Open the owner view →</a>` : `<div class="notice warn">Contact is blocked by this owner's preferences. <button class="small" data-demo-action="another">Choose another suggestion</button></div>`}</div>` : `<button class="primary" data-demo-action="contact" ${d.busy ? "disabled" : ""}>Prepare the owner message →</button>`}`;
  } else if (d.stage === 4 && p) {
    const expired = outcome === "EXPIRED", m = d.message;
    content = `<div class="journey-kicker">04 / DECIDE</div><h2>${expired ? "This proposal is no longer available." : "The owner's decision comes next."}</h2><p class="journey-intro">${h(p.business_name)} · ${expired ? "The proposal expired or was replaced. No decision can be made on this version." : "The preview is ready. Open the owner view to reply, approve, edit or keep the current hours. No decision has been confirmed yet."}</p><div class="journey-next"><button class="ghost" data-demo-action="refresh">Refresh status</button>${expired ? '<button class="primary" data-demo-action="another">Find another business →</button>' : m?.owner_entry_path ? `<a class="button-link primary" id="demo-owner-link" href="${h(channelOwnerLink(m.owner_entry_path, m.channel))}">Continue as the owner →</a>` : '<button class="primary" data-demo-action="contact">Prepare the owner message →</button>'}</div>`;
  } else if (d.stage === 5 && p) {
    content = `<div class="journey-kicker">05 / OUTCOME · ${h(p.business_name)}</div><h2>${outcome === "REJECTED" ? "The owner chose to keep their hours." : outcome === "APPLIED" ? "The right hours, saved and checked." : outcome === "FAILED" ? "This update needs attention." : "Waiting for a verified result."}</h2>${renderResult(p, d.result, "demo")}<div class="journey-continuation"><div><h3>${done ? "Ready for the next business?" : "This review is not finished yet."}</h3><p>${done ? "Continue from the existing directory scan. The next business opens at Suggest; no new scan or automatic contact is needed." : "Check the result or review this case in Workspace before continuing."}</p></div><div class="journey-continuation-actions">${done ? `<button class="primary" data-demo-action="another" ${d.busy ? "disabled" : ""}>Next business →</button>` : '<button data-tab="overview">Review in Workspace</button>'}<button class="ghost" data-demo-action="refresh">Refresh the result</button></div></div>`;
  } else {
    content = `<p>Loading this walkthrough…</p><button data-demo-action="restart">Start from the scan</button>`;
  }
  return `<section class="journey" id="demo-journey">${d.stage > 1 && p ? `<div class="journey-context"><div><small>DIRECTORY SCAN</small><strong>${job ? `${job.processed_businesses.toLocaleString("en-GB")} businesses checked` : "Existing review queue"}</strong><span>${h(d.date)}</span></div><span class="journey-context-arrow" aria-hidden="true">→</span><div><small>CURRENT BUSINESS</small><strong>${h(p.business_name)}</strong><span>One business at a time</span></div></div>` : ""}${journeySteps(d.stage, outcome)}<div class="journey-card" aria-busy="${d.busy}">${content}${d.note ? `<div class="notice warn" role="status">${h(d.note)}${d.stage === 1 && d.runId ? `<br><button class="small" data-demo-action="refresh">Refresh scan status</button>` : ""}</div>` : ""}</div><div class="journey-caption"><span>Real evidence</span><span>Owner in control</span><span>Check the outcome</span></div></section>`;
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
    } catch (error) {
      state.demo.note = errorText(error);
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
        d.stage = journeyOutcome(d.proposal, d.result) === "EXPIRED" ? 4 : 5;
      } else if ([3, 4, 5].includes(d.stage)) {
        d.result = null;
        if (d.stage === 5) d.stage = 4;
        const messages = await api(`/api/v1/operator/messages?entity_id=${encodeURIComponent(d.proposal.entity_id)}&delivery_mode=PREVIEW&limit=100`);
        d.message = messages.items.find(m => m.message_id === d.messageId && m.proposal_ids.includes(d.proposalId)) || null;
      }
    }
    saveDemo(); scheduleDemoPoll();
  } catch (error) {
    if ([404, 410].includes(error.status)) {
      sessionStorage.removeItem(demoStorageKey());
      state.demo = newDemoState();
      state.demo.note = "This earlier walkthrough is no longer available. Start a new scan.";
    } else throw error;
  }
}
async function pickDemoSuggestion(skipCurrent = false) {
  const d = state.demo;
  await refreshCases();
  const currentEntity = d.proposal?.entity_id || state.cases.find(c => c.proposal_id === d.proposalId)?.entity_id;
  const queue = state.cases.filter(c => c.action === "SUGGEST" && c.proposal_id && c.target_date === d.date);
  const pivot = skipCurrent ? queue.findIndex(c => c.proposal_id === d.proposalId) : -1;
  const ordered = [...queue.slice(pivot + 1), ...queue.slice(0, pivot + 1)];
  const candidates = ordered.filter(c => !skipCurrent || (c.proposal_id !== d.proposalId && c.entity_id !== currentEntity));
  // Follow the review queue without giving any contact channel priority.
  for (const candidate of candidates) {
    let p;
    try { p = await api(`/api/v1/proposals/${encodeURIComponent(candidate.proposal_id)}`); }
    catch (error) { if ([404, 410].includes(error.status)) continue; throw error; }
    if (p.decision_status !== "PENDING") continue;
    const page = await api(`/api/v1/operator/businesses?q=${encodeURIComponent(candidate.entity_id)}&limit=100`);
    const business = page.items.find(b => b.entity_id === candidate.entity_id);
    if (!business || business.source_opted_out) continue;
    d.proposal = p; d.proposalId = p.proposal_id; d.message = null; d.messageId = null; d.result = null; d.stage = 2; d.note = "";
    saveDemo(); return;
  }
  d.note = "No other pending suggestion from another eligible business is available for this date. Your directory scan is kept. Review the cases in Workspace, or choose a new date to scan.";
  d.stage = 1; saveDemo();
}
async function maybeAdvanceToNextBusiness() {
  // This is only a navigation request. Re-check operator state before choosing.
  if (IS_OWNER || APP_BASE) return;
  const url = new URL(location.href), requested = url.searchParams.get("next_business");
  if (requested === null) return;
  url.searchParams.delete("next_business");
  history.replaceState(null, "", url.pathname + url.search + url.hash);
  const d = state.demo;
  if (requested !== d.proposalId || !demoScanComplete() || !resolvedJourney(journeyOutcome(d.proposal, d.result))) {
    d.note = "The next business can be opened after this business's review has finished and the directory scan is ready.";
    return;
  }
  state.tab = "demo";
  try { await pickDemoSuggestion(true); }
  catch (error) { d.note = errorText(error); }
}
document.addEventListener("click", e => {
  if (!IS_OWNER && e.target.closest("#demo-owner-link") && state.demo.proposal?.decision_status === "PENDING") {
    state.demo.stage = 4; saveDemo();
  }
});
async function handleDemoAction(action) {
  const d = state.demo;
  if (d.busy) return;
  d.busy = true; d.note = "";
  render();
  try {
    if (action === "scan") {
      const run = await api("/api/v1/operator/fleet-runs", "POST", {scope: "EXPLICIT_DATE", date: d.date});
      Object.assign(d, {run, runId: run.run_id, stage: 1, proposal: null, proposalId: null, message: null, messageId: null, result: null});
      state.fleet = run; saveDemo(); scheduleDemoPoll();
    } else if (action === "suggest" || action === "another") {
      await pickDemoSuggestion(action === "another");
    } else if (action === "contact") {
      if (!d.proposalId) throw new Error("Choose a suggestion first.");
      d.message = await api("/api/v1/operator/messages", "POST", {entity_id: d.proposal.entity_id, proposal_ids: [d.proposalId], delivery_mode: "PREVIEW"}, key());
      d.messageId = d.message.message_id; d.stage = 3; saveDemo();
    } else if (action === "suggest-back") {
      d.stage = 2; saveDemo();
    } else if (action === "refresh") {
      await restoreDemo();
    } else if (action === "restart") {
      d.stage = 1; saveDemo();
    }
  } catch (error) { d.note = errorText(error); }
  finally { d.busy = false; render(); }
}
function ownerJourney() {
  if (!state.owner || !state.proposals.length) return "";
  const outcome = ownerJourneyOutcome();
  return `<div class="owner-journey">${journeySteps(ownerJourneyStep(), outcome)}<p class="journey-role">${outcome === "PENDING" ? "YOUR TURN · BUSINESS OWNER" : outcome === "EXPIRED" ? "PROPOSAL NO LONGER AVAILABLE" : resolvedJourney(outcome) ? "BUSINESS REVIEW COMPLETE" : "APPLICATION NOT YET VERIFIED"}</p>${resolvedJourney(outcome) ? ownerDemoNavigation() : ""}</div>`;
}
