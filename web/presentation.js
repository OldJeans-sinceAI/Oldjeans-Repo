"use strict";

// Guided presentation with real, freely chosen owner decisions at step 4.
// Application outcomes always come from the existing authenticated owner APIs.
const PRESENTATION_DATE = "2026-12-24";
const PRESENTATION_KEY = "connect-presentation-v1";
const PRESENTATION_CHAPTERS = [
  {entity: "FI-D0003", channel: "WHATSAPP"},
  {entity: "FI-D0002", channel: "EMAIL"},
  {entity: "FI-D0001", channel: "SMS"},
];
let presentation = {phase: "start", chapter: 0, runId: null, run: null, proposal: null,
  message: null, result: null, cases: [], outcomes: [], busy: false, error: "", ready: false};
let presentationPoll;
function presentationActive() {
  return !APP_BASE && !IS_OWNER && state.tab === "presentation" && state.health?.presentation_mode === true;
}
function savePresentation() {
  const {phase, chapter, runId} = presentation;
  sessionStorage.setItem(PRESENTATION_KEY, JSON.stringify({phase, chapter, runId}));
}
function presentationStep() {
  return {start: 1, scan: 1, suggest: 2, contact: 3, decide: 4, result: 5, complete: 5}[presentation.phase] || 1;
}
function presentationNavigationBusy() {
  // Owner handlers keep these controls/sets busy until their refresh finishes.
  // Back/restart must not change the active owner while a decision is in flight.
  return presentation.busy || Object.values(state.replyBusy).some(Boolean) ||
    emailSending.size > 0 || smsSending.size > 0 || !!document.querySelector(
      '.pt-owner-view [data-decision]:disabled, .pt-owner-view [data-draft]:disabled, dialog[open] [data-confirm-edit]:disabled'
    );
}
function presentationNextChapter() {
  const current = presentation.chapter;
  return [...PRESENTATION_CHAPTERS.keys()].filter(i => i > current)
    .concat([...PRESENTATION_CHAPTERS.keys()].filter(i => i < current))
    .find(i => !presentation.outcomes[i]);
}
function clearPresentationDrafts() {
  state.drafts = {}; state.replyText = {}; state.editing = null;
  emailComposers.clear(); emailConversations.clear(); emailConfirmations.clear();
  smsComposers.clear(); smsConversations.clear(); smsConfirmations.clear();
  if (dialog.open) dialog.close();
}
function backToPresentationDetect(chapter = presentation.chapter) {
  if (!presentationActive() || !presentation.ready || presentationNavigationBusy()) return;
  if (!Number.isInteger(chapter) || chapter < 0 || chapter >= PRESENTATION_CHAPTERS.length) return;
  clearPresentationDrafts();
  Object.assign(presentation, {phase: presentation.runId ? "scan" : "start", chapter,
    proposal: null, message: null, result: null, error: ""});
  state.proposals = [];
  savePresentation(); renderPresentation(); window.scrollTo({top:0,behavior:"instant"});
  if (presentation.run?.status === "RUNNING") void presentationPollScan();
}
function requestPresentationRestart() {
  if (!presentationActive() || !presentation.ready || presentationNavigationBusy() || presentation.run?.status === "RUNNING") return;
  dialog.innerHTML = '<div class="modal-head"><h2>Start a fresh rehearsal?</h2><button class="ghost" data-close aria-label="Close">✕</button></div><p>This restores the presentation mock data and clears its decisions, messages and scan. It does not reset the real Yext sandbox.</p><p>To review another business while keeping your results, use Back to Detect.</p><div class="actions"><button class="primary" data-presentation-reset-confirm>Reset demo & start again</button><button data-close>Keep this rehearsal</button></div>';
  dialog.showModal();
}
function presentationYextView() {
  return `<aside class="pt-yext" aria-label="Yext integration"><div><strong>Where does Yext fit?</strong><p>This rehearsal saves to a local Yext simulator and verifies the result. The real-write test uses the team's Yext sandbox entity: owner approval → save → independent read-back.</p></div>${state.health?.sandbox_available ? '<a class="button-link" data-presentation-yext href="/sandbox/" target="_blank" rel="noopener">Test real Yext apply ↗</a>' : '<span class="pt-muted">Real Yext sandbox is not connected in this launch.</span>'}</aside>`;
}
function presentationPickerView() {
  const d = presentation;
  if (d.run?.status !== "COMPLETED" || d.run.failed_businesses) return "";
  return `<section class="pt-panel pt-picker"><p class="pt-small-label">CONTINUE FROM THIS SCAN</p><h2>Choose a business, then press Next.</h2><p>Use the suggested order, or choose another channel to test. Existing decisions stay saved. A business already decided opens its recorded result; use Restart demo to try a different decision for it.</p><div class="pt-business-options">${PRESENTATION_CHAPTERS.map((c,i) => {
    const item = d.cases.find(x => x.entity_id === c.entity && x.target_date === PRESENTATION_DATE);
    return `<button data-presentation-chapter-pick="${i}" aria-pressed="${i === d.chapter}" ${d.busy ? "disabled" : ""}><span>${c.channel === "WHATSAPP" ? "WhatsApp" : c.channel}</span><strong>${h(item?.business_name || c.entity)}</strong><small>${d.outcomes[i] ? "Result saved" : i === d.chapter ? "Selected for Next" : "Choose this business"}</small></button>`;
  }).join("")}</div><details class="pt-more-tests"><summary>More tests · advanced workspace</summary><p>For other businesses, dates, staff review and contact settings, use the manual workspace. The Next-button demo stays here.</p><a href="/?view=workspace" target="_blank" rel="noopener">Open advanced tests ↗</a></details></section>`;
}
function presentationVerified(p, r, chapter = presentation.chapter) {
  const c = PRESENTATION_CHAPTERS[chapter];
  if (!p || !r || p.entity_id !== c.entity || p.change.date !== PRESENTATION_DATE || p.mode !== "mock" ||
      r.mode !== "mock" || r.proposal_id !== p.proposal_id || r.proposal_version !== p.version ||
      r.source_entity_id !== p.entity_id || r.decision_status !== p.decision_status) return false;
  if (p.decision_status === "REJECTED") return r.application_status === "NOT_STARTED";
  if (!["APPROVED", "EDITED"].includes(p.decision_status)) return false;
  return r.application_status === "SUCCEEDED" && !!r.verified_at &&
    r.final_change?.kind === "DATE_HOURS" && r.final_change.date === p.change.date &&
    typeof r.final_change.hours === "string" && r.final_change.hours.length > 0 &&
    (p.decision_status === "EDITED" || r.final_change.hours === p.change.hours);
}
function presentationRememberResult() {
  const d = presentation;
  if (presentationVerified(d.proposal, d.result)) d.outcomes[d.chapter] = {
    status: d.proposal.decision_status,
    business: d.proposal.business_name,
    hours: changeText(d.proposal.decision_status === "REJECTED" ? d.proposal.baseline : d.result.final_change),
  };
  else delete d.outcomes[d.chapter];
}
function presentationCanAdvance() {
  const d = presentation;
  if (!d.ready || d.busy || (d.error && d.phase !== "start")) return false;
  if (d.phase === "decide") return false;
  if (d.phase === "scan") return d.run?.status === "COMPLETED" && d.run.failed_businesses === 0;
  if (d.phase === "result") return presentationVerified(d.proposal, d.result);
  return true;
}
function presentationNextText() {
  const d = presentation, chapter = PRESENTATION_CHAPTERS[d.chapter];
  return {
    start: "Prepare a fresh rehearsal in the separate demo workspace.",
    scan: "Show a proposal selected from the completed directory scan.",
    suggest: `Prepare the ${chapter.channel === "WHATSAPP" ? "WhatsApp" : chapter.channel} message.`,
    contact: "Open the message as the simulated business owner.",
    decide: "Use the customer screen above. Your confirmed decision opens step 5 automatically.",
    result: presentationNextChapter() !== undefined ? "Continue with the next business that needs a review." : "Show what this complete workflow achieved.",
    complete: "Start a fresh rehearsal. Only presentation data will be reset.",
  }[d.phase];
}
function presentationScanView() {
  const d = presentation, run = d.run, complete = run?.status === "COMPLETED";
  const total = run?.total_businesses ?? state.fleetTotal ?? 3032;
  const scanned = run?.processed_businesses || 0;
  const pct = total ? Math.round(scanned / total * 100) : 0;
  const examples = [
    ["FI-D0003", "A suggestion worth making", "The business has its own holiday-hours history."],
    ["FI-D0011", "A person should take a look", "Possible permanent closure needs staff review."],
    ["FI-D0017", "Not enough evidence? Stay quiet.", "A new customer is deferred, without guessed opening hours."],
  ];
  return `<div class="pt-section-title"><p class="eyebrow">01 / DETECT</p><h1>${complete ? "Every business checked. Each gets the right next step." : "Start with the whole directory."}</h1><p>One scan checks ${Number(total).toLocaleString("en-GB")} businesses and shopping centres for Christmas Eve. No owner is contacted or approved during detection.</p></div>
    <div class="pt-scan-layout"><section class="pt-panel pt-scan"><div class="pt-big-number">${Number(scanned).toLocaleString("en-GB")}<span> / ${Number(total).toLocaleString("en-GB")}</span></div><p>${run ? complete ? "Completed directory scan · 24 December 2026" : "Checking the available evidence…" : "Ready for a fresh rehearsal"}</p><progress value="${pct}" max="100" aria-label="Businesses checked"></progress><div class="pt-counts">${[["SUGGEST","Suggest hours"],["FLAG","Staff review"],["NO_ACTION","No outreach"]].map(([k,label]) => `<div><strong>${run?.counts?.[k] ?? "—"}</strong><span>${label}</span></div>`).join("")}</div>${!complete ? '<p class="pt-muted">Prepare this scan before recording. Next becomes available when the real scan has completed.</p>' : ""}</section><div class="pt-signals">${examples.map(([id,title,explanation]) => {const c = d.cases.find(c => c.entity_id === id && c.target_date === PRESENTATION_DATE); return `<article class="pt-panel"><span class="pt-small-label">${h(c?.action || "EVIDENCE CHECK")}</span><h3>${title}</h3><p>${h(c?.business_name || explanation)}</p>${c ? `<small>${h(c.summary)}</small>` : ""}</article>`;}).join("")}</div></div>`;
}
function presentationProposalView() {
  const p = presentation.proposal;
  const sources = p.evidence.map(e => `<div class="evidence"><small>${h(dateLabel(e.known_at))}</small><p>${h(e.source_file === "holiday_hours_history.jsonl" ? "The business's own recorded hours for this holiday in a previous season." : e.summary)}</p><details><summary>Source details</summary><code>${h(e.source_file)} · ${h(e.source_record)}</code></details></div>`).join("");
  return `<div class="pt-section-title"><p class="eyebrow">02 / SUGGEST</p><h1>A clear change. A clear reason.</h1><p>${h(p.business_name)} · Christmas Eve · 24 December 2026</p></div><section class="pt-panel pt-proposal">${scheduleView(p)}<div class="pt-reason"><span class="pt-symbol">↗</span><div><h2>Why these hours?</h2><p>${h(reasonText(p))}</p><small>Past evidence supports this proposal. This year's plan still needs the owner's confirmation.</small></div></div><div class="pt-evidence"><h3>The evidence behind this proposal</h3>${sources}</div></section>`;
}
function presentationContactView() {
  const p = presentation.proposal, c = PRESENTATION_CHAPTERS[presentation.chapter];
  return `<div class="pt-section-title"><p class="eyebrow">03 / CONTACT</p><h1>Meet the owner where they already are.</h1><p>The message explains both the proposed hours and the reason. Delivery is simulated.</p></div><div class="pt-contact-layout"><section class="pt-panel"><span class="pt-channel-icon">${c.channel === "EMAIL" ? "✉" : "▤"}</span><span class="pt-small-label">PREFERRED CHANNEL</span><h2>${c.channel === "WHATSAPP" ? "WhatsApp" : c.channel}</h2><p>${h(p.business_name)}</p><div class="pt-separator"></div><h3>Low effort. Clear control.</h3><p>${c.channel === "WHATSAPP" ? "Use the message's reply buttons to approve or choose a different response." : "Reply with YES, NO, or the hours you want. Confirm the preview before anything is saved."}</p><small>No login. No real message is sent.</small></section><section class="pt-panel pt-message"><span class="pt-small-label">MESSAGE PREVIEW</span><p>${h(presentation.message?.body || presentation.message?.text || "")}</p><div class="pt-uncertainty">This evidence does not confirm your final plan for this date. You decide.</div></section></div>`;
}
function presentationOwnerView() {
  const d = presentation, c = PRESENTATION_CHAPTERS[d.chapter], p = d.proposal;
  const view = c.channel === "WHATSAPP" ? renderWhatsAppProposal(p) : c.channel === "EMAIL" ? renderEmailProposal(p) : renderSmsProposal(p);
  return `<div class="pt-section-title pt-owner-title"><p class="eyebrow">04 / DECIDE · INTERACTIVE CUSTOMER DEMO</p><h1>Your hours. Your decision.</h1><p>${c.channel === "WHATSAPP" ? "Use Approve hours, Edit hours or Keep current hours in the message. Edited hours need a separate confirmation." : "Reply YES to approve, NO to keep the current hours, or the hours you want. Review the preview, then reply CONFIRM. Use CANCEL to discard it."}</p><p class="pt-owner-help">Choose one outcome for this business. Step 5 opens after your decision is processed. You can try a different choice on another business or a later rehearsal.</p></div><div id="${c.channel.toLowerCase()}-demo" class="pt-owner-view pt-channel-${c.channel.toLowerCase()}" ${d.busy ? 'inert aria-busy="true"' : ""}>${view}</div>`;
}
function presentationResultView() {
  const d = presentation, p = d.proposal, r = d.result, rejected = p.decision_status === "REJECTED";
  const good = presentationVerified(p,r);
  const finalHours = rejected ? changeText(p.baseline) : r?.final_change ? changeText(r.final_change) : "Not verified";
  return `<div class="pt-section-title"><p class="eyebrow">05 / APPLY & CONFIRM</p><h1>${!good ? "This result needs attention." : rejected ? "No means no. The current hours stay." : "Saved. Read back. Verified."}</h1><p>${h(p.business_name)} · ${h(p.decision_status)}</p></div><section class="pt-panel pt-result"><div class="pt-result-symbol">${!good ? "!" : rejected ? "–" : "✓"}</div><div class="pt-before-after"><div><span>Before</span><strong>${h(changeText(p.baseline))}</strong></div><span class="pt-arrow">→</span><div><span>${!good ? "Requested hours · not verified" : rejected ? "Kept unchanged" : "Saved hours"}</span><strong>${h(finalHours)}</strong></div></div><p>${!good ? "The application has not been verified. Check its status before continuing." : rejected ? "The owner declined. No update was requested." : "The backend saved the confirmed hours through the local Yext mock API and read them back to verify the change."}</p>${good && r?.verified_at ? '<span class="pt-verified">✓ Independent read-back passed</span>' : ""}<div class="pt-publishers">${(r?.publishers || []).slice(0,4).map(pub => `<div><strong>${h(pub.publisher_name)}</strong><span>${pub.typical_update_seconds != null ? h(Math.round(pub.typical_update_seconds/60)) + " min typical update" : "Timing unavailable"}</span></div>`).join("")}</div>${!rejected && good ? '<small>Publisher timings are estimates from the mock dataset, not proof of live publication.</small>' : ""}</section>`;
}
function renderPresentation() {
  const d = presentation, c = PRESENTATION_CHAPTERS[d.chapter];
  if (d.phase === "decide") {
    const current = state.proposals.find(p => p.proposal_id === d.proposal?.proposal_id);
    if (current) d.proposal = current;
    if (current && current.decision_status !== "PENDING" && !d.busy && !d.error) {
      // Owner handlers have refreshed their proposal. Fetch the actual result once;
      // this observer never submits a decision or interprets a reply.
      void resolvePresentation();
      return;
    }
  }
  if (d.phase === "result") presentationRememberResult();
  const outcome = journeyOutcome(d.proposal,d.result);
  let body = "";
  if (["start","scan"].includes(d.phase)) body = presentationScanView() + presentationPickerView();
  else if (d.phase !== "complete" && (!d.proposal || d.proposal.entity_id !== c.entity)) body = '<section class="pt-panel"><h1>The rehearsal needs a fresh start.</h1><p>No application result has been assumed.</p></section>';
  else if (d.phase === "suggest") body = presentationProposalView();
  else if (d.phase === "contact") body = presentationContactView();
  else if (d.phase === "decide") body = presentationOwnerView();
  else if (d.phase === "result") body = presentationResultView();
  else body = `<div class="pt-finish"><span class="pt-result-symbol">✓</span><p class="eyebrow">THE COMPLETE LOOP</p><h1>Better hours.<br>Still the owner's decision.</h1><p>One directory scan. Three ways to reach an owner.<br>These are the decisions you made in this rehearsal.</p><div class="pt-finish-cards">${PRESENTATION_CHAPTERS.map((x,i) => { const result = d.outcomes[i]; return `<div class="pt-panel"><span>0${i+1} / ${x.channel}</span><h2>${result?.status === "APPROVED" ? "Approved & saved" : result?.status === "EDITED" ? "Edited & saved" : result?.status === "REJECTED" ? "Declined & kept" : "Not verified"}</h2><p>${h(result?.business || "")}</p><strong>${h(result?.hours || "")}</strong></div>`; }).join("")}</div><small>This rehearsal uses real application APIs with isolated mock data. Real Yext sandbox testing remains a separate, manual workspace.</small></div>`;
  const controls = d.phase === "decide"
    ? '<span class="pt-owner-status" role="status">Your choice in the message ↑</span>'
    : `<button class="primary pt-next" data-presentation-next ${presentationCanAdvance() ? "" : "disabled"}>${d.busy ? '<span class="spinner"></span> Please wait' : d.phase === "complete" ? "Restart demo ↻" : "Next →"}</button>`;
  const completeOutcome = d.outcomes.some(r => r && r.status !== "REJECTED") ? "APPLIED" : "REJECTED";
  app.innerHTML = `<main class="pt-shell"><header class="pt-header">${brand()}<div class="pt-header-right"><span class="pt-demo-badge">INTERACTIVE DEMO · MOCK DATA</span>${state.health?.sandbox_available ? '<a data-presentation-yext href="/sandbox/" target="_blank" rel="noopener">Test real Yext apply ↗</a>' : ""}</div></header><div class="pt-context"><span>CHRISTMAS EVE · 24 DEC 2026</span><span>${["start","scan"].includes(d.phase) ? "ALL BUSINESSES" : d.phase === "complete" ? "REHEARSAL COMPLETE" : `CHAPTER ${d.chapter+1} / 3 · ${c.channel}`}</span></div><nav class="pt-navigation" aria-label="Demo navigation">${!["start","scan"].includes(d.phase) ? `<button data-presentation-detect ${d.busy ? "disabled" : ""}>← Back to Detect</button>` : '<span>Next guides the flow · you decide at step 4</span>'}<button data-presentation-restart ${!d.ready || d.busy || d.run?.status === "RUNNING" ? "disabled" : ""}>Restart demo · resets data</button></nav>${journeySteps(presentationStep(), d.phase === "complete" ? completeOutcome : outcome)}<div class="pt-content" data-presentation-phase="${h(d.phase)}" data-presentation-chapter="${d.chapter}">${body}</div>${["start","scan","result","complete"].includes(d.phase) ? presentationYextView() : ""}${d.error ? `<div class="pt-error" role="alert">${h(d.error)} <button data-presentation-restart ${d.busy ? "disabled" : ""}>Start a fresh rehearsal</button></div>` : ""}<footer class="pt-controls"><div><span class="pt-small-label">${d.busy ? "WORKING" : d.phase === "decide" ? "YOUR TURN · BUSINESS OWNER" : "NEXT IN THIS DEMO"}</span><p>${d.busy ? "Waiting for the application. No step is skipped." : h(presentationNextText())}</p></div>${(d.phase === "result" && !presentationVerified(d.proposal,d.result)) || (d.phase === "decide" && d.error) ? `<button data-presentation-refresh ${d.busy ? "disabled" : ""}>Check application status</button>` : ""}${controls}</footer></main>`;
  if (d.phase === "decide") {
    const pane = document.querySelector(".cm-email-reading");
    if (pane?.querySelector(".outgoing, .cm-email-composer")) pane.scrollTop = pane.scrollHeight;
    const thread = document.querySelector(".cm-sms-thread");
    if (thread?.querySelector(".outgoing")) thread.scrollTop = thread.scrollHeight;
    const chat = document.querySelector(".wa-chat");
    if (chat?.querySelector(".wa-editor, .wa-draft, [role=status]")) chat.scrollTop = chat.scrollHeight;
  }
}
async function presentationPollScan() {
  clearTimeout(presentationPoll);
  if (!presentationActive() || presentation.phase !== "scan" || !presentation.runId) return;
  try {
    presentation.run = await api(`/api/v1/operator/fleet-runs/${encodeURIComponent(presentation.runId)}`);
    if (presentation.run.status === "COMPLETED") {
      presentation.cases = (await api("/api/v1/operator/cases")).items;
    } else if (presentation.run.status !== "RUNNING") {
      presentation.error = "The scan did not finish successfully. Start a fresh rehearsal before presenting.";
    }
    renderPresentation();
    if (presentation.run.status === "RUNNING") presentationPoll = setTimeout(presentationPollScan,1200);
  } catch (error) {
    presentation.error = "The scan could not be checked. Reload to reconnect; no completion has been assumed.";
    renderPresentation();
  }
}
async function presentationLoadChapter() {
  const d = presentation, c = PRESENTATION_CHAPTERS[d.chapter];
  d.cases = (await api("/api/v1/operator/cases")).items;
  const found = d.cases.find(x => x.entity_id === c.entity && x.target_date === PRESENTATION_DATE && x.action === "SUGGEST" && x.proposal_id);
  if (!found) throw new Error("The fixed demo case is not available. Start a fresh rehearsal using the supplied dataset.");
  d.proposal = await api(`/api/v1/proposals/${encodeURIComponent(found.proposal_id)}`);
  if (d.proposal.entity_id !== c.entity || d.proposal.change.date !== PRESENTATION_DATE) throw new Error("This proposal does not match the guided demo.");
  state.proposals = [d.proposal];
  d.result = await api(`/api/v1/proposals/${encodeURIComponent(found.proposal_id)}/result`);
  d.proposal._result = d.result;
  d.message = null;
  if (d.proposal.decision_status !== "PENDING") d.phase = "result";
}
async function presentationMessage() {
  const d = presentation;
  d.message = await api("/api/v1/operator/messages","POST",{entity_id:d.proposal.entity_id,proposal_ids:[d.proposal.proposal_id],delivery_mode:"PREVIEW"},key());
  if (d.message.channel !== PRESENTATION_CHAPTERS[d.chapter].channel || d.message.status !== "DELIVERED_SIMULATED") throw new Error("The fixed demo message is blocked or its channel has changed. Start a fresh rehearsal.");
}
async function presentationOwner() {
  const d = presentation;
  if (!d.message) await presentationMessage();
  const entry = new URL(d.message.owner_entry_path,location.origin);
  const token = new URLSearchParams(entry.hash.slice(1)).get("token");
  if (!token) throw new Error("The owner entry is unavailable.");
  state.owner = await api("/api/v1/session","POST",{token});
  await refreshOwner();
  d.proposal = state.proposals.find(p => p.proposal_id === d.proposal.proposal_id);
  if (!d.proposal) throw new Error("The owner session does not match this proposal.");
}
async function resolvePresentation() {
  const d = presentation;
  if (!presentationActive() || d.busy || !d.proposal) return;
  d.busy = true; d.error = ""; renderPresentation();
  try {
    const id = encodeURIComponent(d.proposal.proposal_id);
    d.proposal = await api(`/api/v1/proposals/${id}`);
    d.result = await api(`/api/v1/proposals/${id}/result`);
    d.proposal._result = d.result;
    state.proposals = [d.proposal];
    d.phase = d.proposal.decision_status === "PENDING" ? "decide" : "result";
    presentationRememberResult();
    savePresentation();
  } catch(error) {
    d.error = "The application result could not be checked. Check its status or reload; no successful update has been assumed.";
  } finally {
    d.busy = false; renderPresentation();
    if (d.phase === "result") window.scrollTo({top:0,behavior:"instant"});
  }
}
async function presentationComplete() {
  // Completion is rechecked from all three server records, whatever the choices.
  for (let i=0;i<PRESENTATION_CHAPTERS.length;i++) {
    presentation.chapter=i;
    await presentationLoadChapter();
    if (!presentationVerified(presentation.proposal,presentation.result)) throw new Error("One business has not reached a verified outcome. Review it before completing the rehearsal.");
    presentationRememberResult();
  }
  presentation.phase="complete";
}
async function preparePresentation() {
  if (!presentationActive() || state.health.mode !== "mock") throw new Error("The guided rehearsal is available only in its isolated mock workspace.");
  const reset = await api("/api/v1/operator/reset");
  await api("/api/v1/operator/reset","POST",{confirm_reset:true,preview_token:reset.preview_token},key());
  // Reset revokes sessions. Re-open the same local operator entry to get fresh cookies.
  await fetch("/",{credentials:"same-origin",cache:"no-store"});
  state.owner = null; state.proposals = []; state.drafts = {}; state.replyText = {}; state.editing = null;
  clearPresentationDrafts();
  Object.assign(presentation,{phase:"scan",chapter:0,proposal:null,message:null,result:null,cases:[],outcomes:[],error:""});
  presentation.run = await api("/api/v1/operator/fleet-runs","POST",{scope:"EXPLICIT_DATE",date:PRESENTATION_DATE});
  presentation.runId = presentation.run.run_id;
  savePresentation();
  await presentationPollScan();
}
async function nextPresentation(restart=false) {
  const d = presentation;
  if (!presentationActive() || presentationNavigationBusy() || (!restart && !presentationCanAdvance())) return;
  if (restart && d.run?.status === "RUNNING") return;
  d.busy = true; d.error = ""; renderPresentation();
  try {
    if (restart || ["start","complete"].includes(d.phase)) await preparePresentation();
    else if (d.phase === "scan") { d.phase="suggest"; await presentationLoadChapter(); }
    else if (d.phase === "suggest") { await presentationMessage(); d.phase="contact"; }
    else if (d.phase === "contact") { await presentationOwner(); d.phase="decide"; }
    else if (d.phase === "result") {
      let next = presentationNextChapter();
      // The local outcome cache is empty after a reload. Read unknown chapters
      // before navigating: completed records are skipped, never replayed.
      while (next !== undefined) {
        d.chapter=next; d.phase="suggest"; await presentationLoadChapter();
        if (!presentationVerified(d.proposal, d.result)) break;
        presentationRememberResult();
        next = presentationNextChapter();
      }
      if (next === undefined) await presentationComplete();
    }
    savePresentation();
  } catch(error) { d.error = error.message || "The demo needs attention. No successful outcome has been assumed."; savePresentation(); }
  finally { d.busy=false; renderPresentation(); window.scrollTo({top:0,behavior:"instant"}); }
}
async function initPresentation() {
  let saved;
  try { saved=JSON.parse(sessionStorage.getItem(PRESENTATION_KEY)||"null"); } catch {}
  const d = presentation;
  try {
    if (saved && Number.isInteger(saved.chapter) && saved.chapter>=0 && saved.chapter<3 && ["start","scan","suggest","contact","decide","owner","preview","result","complete"].includes(saved.phase)) {
      // Old scripted step4 checkpoints become interactive without replaying input.
      const phase = ["owner","preview"].includes(saved.phase) ? "decide" : saved.phase;
      Object.assign(d,{chapter:saved.chapter,phase,runId:typeof saved.runId==="string" ? saved.runId : null});
      if (d.runId) d.run=await api(`/api/v1/operator/fleet-runs/${encodeURIComponent(d.runId)}`);
      if (d.phase!=="start" && !d.runId) d.phase="start";
      if (d.phase==="scan") await presentationPollScan();
      else if (!["start","complete"].includes(d.phase)) {
        await presentationLoadChapter();
        if (d.proposal.decision_status==="PENDING" && ["contact","decide"].includes(d.phase)) {
          await presentationMessage();
          if (d.phase==="decide") await presentationOwner();
        }
      } else if (d.phase==="complete") {
        await presentationComplete();
      }
    }
  } catch(error) { d.phase="start";d.chapter=0;d.runId=null;d.run=null;d.error="The previous rehearsal could not be restored. Next prepares a new isolated rehearsal."; }
  d.ready=true;savePresentation();renderPresentation();
}
document.addEventListener("click",e => {
  if (e.target.closest("[data-presentation-next]")) {
    if (presentation.phase === "complete") requestPresentationRestart();
    else void nextPresentation();
  } else if (e.target.closest("[data-presentation-restart]")) requestPresentationRestart();
  else if (e.target.closest("[data-presentation-reset-confirm]")) {
    if (presentationNavigationBusy()) return;
    dialog.close(); void nextPresentation(true);
  } else if (e.target.closest("[data-presentation-detect]")) backToPresentationDetect();
  else if (e.target.closest("[data-presentation-chapter-pick]")) {
    backToPresentationDetect(Number(e.target.closest("[data-presentation-chapter-pick]").dataset.presentationChapterPick));
  } else if (e.target.closest("[data-presentation-refresh]")) void resolvePresentation();
});
