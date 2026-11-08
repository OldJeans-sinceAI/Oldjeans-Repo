"use strict";

// Fixed presentation script. It orchestrates the same owner APIs and channel views
// as the interactive product. No simulated result can advance the application step.
const PRESENTATION_DATE = "2026-12-24";
const PRESENTATION_KEY = "connect-presentation-v1";
const PRESENTATION_CHAPTERS = [
  {entity: "FI-D0003", channel: "WHATSAPP", decision: "APPROVE", title: "One tap to approve", reply: "YES"},
  {entity: "FI-D0002", channel: "EMAIL", decision: "EDIT", title: "A reply to make it yours", reply: "11:00-16:00"},
  {entity: "FI-D0001", channel: "SMS", decision: "REJECT", title: "The freedom to say no", reply: "NO"},
];
let presentation = {phase: "start", chapter: 0, runId: null, run: null, proposal: null,
  message: null, result: null, cases: [], busy: false, error: "", ready: false};
let presentationPoll;
function presentationActive() {
  return !APP_BASE && !IS_OWNER && state.tab === "presentation" && state.health?.presentation_mode === true;
}
function savePresentation() {
  const {phase, chapter, runId} = presentation;
  sessionStorage.setItem(PRESENTATION_KEY, JSON.stringify({phase, chapter, runId}));
}
function presentationStep() {
  return {start: 1, scan: 1, suggest: 2, contact: 3, owner: 4, preview: 4, result: 5, complete: 5}[presentation.phase] || 1;
}
function presentationExpected(p, r, chapter = presentation.chapter) {
  const c = PRESENTATION_CHAPTERS[chapter];
  if (!p || !r || p.entity_id !== c.entity || p.change.date !== PRESENTATION_DATE || p.mode !== "mock") return false;
  if (c.decision === "REJECT") return p.decision_status === "REJECTED" && r.application_status === "NOT_STARTED";
  const status = c.decision === "EDIT" ? "EDITED" : "APPROVED";
  const hours = c.decision === "EDIT" ? c.reply : p.change.hours;
  return p.decision_status === status && r.application_status === "SUCCEEDED" && !!r.verified_at && r.final_change?.hours === hours;
}
function presentationCanAdvance() {
  const d = presentation;
  if (!d.ready || d.busy || (d.error && d.phase !== "start")) return false;
  if (d.phase === "scan") return d.run?.status === "COMPLETED" && d.run.failed_businesses === 0;
  if (d.phase === "result") return presentationExpected(d.proposal, d.result);
  return true;
}
function presentationNextText() {
  const d = presentation, chapter = PRESENTATION_CHAPTERS[d.chapter];
  return {
    start: "Prepare a fresh rehearsal in the separate demo workspace.",
    scan: "Show a proposal selected from the completed directory scan.",
    suggest: `Prepare the ${chapter.channel === "WHATSAPP" ? "WhatsApp" : chapter.channel} message.`,
    contact: "Open the message as the simulated business owner.",
    owner: chapter.decision === "APPROVE" ? "Act as the owner and press Approve hours. This saves to the local mock." : `Send the scripted owner reply: ${chapter.reply}. No change is saved yet.`,
    preview: "Send CONFIRM as the simulated owner. This records the decision.",
    result: d.chapter < 2 ? "Continue with the next channel and owner decision." : "Show what this complete workflow achieved.",
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
  return `<div class="pt-section-title pt-owner-title"><p class="eyebrow">04 / DECIDE · SIMULATED OWNER</p><h1>${d.phase === "preview" ? "The preview puts the owner in control." : c.title + "."}</h1><p>${d.phase === "preview" ? "The reply has been interpreted, but nothing has been applied. Next sends the owner's explicit confirmation." : c.channel === "WHATSAPP" ? "The presenter uses Next to simulate the owner's Approve hours button." : `The presenter uses Next to send the fixed reply “${c.reply}”. Email and SMS use replies, not decision buttons.`}</p></div><div id="${c.channel.toLowerCase()}-demo" class="pt-owner-view pt-channel-${c.channel.toLowerCase()}" inert>${view}</div>`;
}
function presentationResultView() {
  const d = presentation, p = d.proposal, r = d.result, rejected = p.decision_status === "REJECTED";
  const good = presentationExpected(p,r);
  const finalHours = rejected ? changeText(p.baseline) : r?.final_change ? changeText(r.final_change) : "Not verified";
  return `<div class="pt-section-title"><p class="eyebrow">05 / APPLY & CONFIRM</p><h1>${!good ? "This result needs attention." : rejected ? "No means no. The current hours stay." : "Saved. Read back. Verified."}</h1><p>${h(p.business_name)} · ${h(PRESENTATION_CHAPTERS[d.chapter].decision)}</p></div><section class="pt-panel pt-result"><div class="pt-result-symbol">${!good ? "!" : rejected ? "–" : "✓"}</div><div class="pt-before-after"><div><span>Before</span><strong>${h(changeText(p.baseline))}</strong></div><span class="pt-arrow">→</span><div><span>${rejected ? "Kept unchanged" : "Saved hours"}</span><strong>${h(finalHours)}</strong></div></div><p>${!good ? "The application has not been verified. Do not present this as a successful update." : rejected ? "The owner declined. No update was requested." : "The backend saved the confirmed hours through the local Yext mock API and read them back to verify the change."}</p>${r?.verified_at ? '<span class="pt-verified">✓ Independent read-back passed</span>' : ""}<div class="pt-publishers">${(r?.publishers || []).slice(0,4).map(pub => `<div><strong>${h(pub.publisher_name)}</strong><span>${pub.typical_update_seconds != null ? h(Math.round(pub.typical_update_seconds/60)) + " min typical update" : "Timing unavailable"}</span></div>`).join("")}</div>${!rejected && good ? '<small>Publisher timings are estimates from the mock dataset, not proof of live publication.</small>' : ""}</section>`;
}
function renderPresentation() {
  const d = presentation, c = PRESENTATION_CHAPTERS[d.chapter];
  const outcome = journeyOutcome(d.proposal,d.result);
  let body = "";
  if (["start","scan"].includes(d.phase)) body = presentationScanView();
  else if (d.phase !== "complete" && (!d.proposal || d.proposal.entity_id !== c.entity)) body = '<section class="pt-panel"><h1>The rehearsal needs a fresh start.</h1><p>No application result has been assumed.</p></section>';
  else if (d.phase === "suggest") body = presentationProposalView();
  else if (d.phase === "contact") body = presentationContactView();
  else if (["owner","preview"].includes(d.phase)) body = presentationOwnerView();
  else if (d.phase === "result") body = presentationResultView();
  else body = `<div class="pt-finish"><span class="pt-result-symbol">✓</span><p class="eyebrow">THE COMPLETE LOOP</p><h1>Better hours.<br>Still the owner's decision.</h1><p>One directory scan. Three ways to reach an owner.<br>Approve, edit or decline — with a verified outcome.</p><div class="pt-finish-cards">${PRESENTATION_CHAPTERS.map((x,i) => `<div class="pt-panel"><span>0${i+1} / ${x.channel}</span><h2>${x.decision === "APPROVE" ? "Approved & saved" : x.decision === "EDIT" ? "Edited & saved" : "Declined & kept"}</h2></div>`).join("")}</div><small>This rehearsal uses real application APIs with isolated mock data. Real Yext sandbox testing remains a separate, manual workspace.</small></div>`;
  app.innerHTML = `<main class="pt-shell"><header class="pt-header">${brand()}<div class="pt-header-right"><span class="pt-demo-badge">SCRIPTED DEMO · MOCK DATA</span><a href="/?view=workspace">Explore workspace ↗</a></div></header><div class="pt-context"><span>CHRISTMAS EVE · 24 DEC 2026</span><span>${["start","scan"].includes(d.phase) ? "ALL BUSINESSES" : d.phase === "complete" ? "REHEARSAL COMPLETE" : `CHAPTER ${d.chapter+1} / 3 · ${c.channel} · ${c.decision}`}</span></div>${journeySteps(presentationStep(), d.phase === "complete" ? "APPLIED" : outcome)}<div class="pt-content" data-presentation-phase="${h(d.phase)}" data-presentation-chapter="${d.chapter}">${body}</div>${d.error ? `<div class="pt-error" role="alert">${h(d.error)} <button data-presentation-restart>Start a fresh rehearsal</button></div>` : ""}<footer class="pt-controls"><div><span class="pt-small-label">${d.busy ? "WORKING" : "NEXT IN THIS DEMO"}</span><p>${d.busy ? "Waiting for the application. No step is skipped." : h(presentationNextText())}</p></div><button class="primary pt-next" data-presentation-next ${presentationCanAdvance() ? "" : "disabled"}>${d.busy ? '<span class="spinner"></span> Please wait' : d.phase === "complete" ? "Restart demo ↻" : "Next →"}</button></footer></main>`;
  if (["owner","preview"].includes(d.phase)) {
    for (const el of document.querySelectorAll(".cm-email-reading,.cm-sms-thread,.wa-chat")) {
      if (d.phase === "preview") el.scrollTop = el.scrollHeight;
    }
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
  if (d.proposal.entity_id !== c.entity || d.proposal.change.date !== PRESENTATION_DATE) throw new Error("This proposal does not match the scripted demo.");
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
async function presentationSendReply(text) {
  const d = presentation, c = PRESENTATION_CHAPTERS[d.chapter], id = d.proposal.proposal_id;
  if (c.channel === "EMAIL") emailComposers.set(id,text);
  else smsComposers.set(id,text);
  renderPresentation();
  const input = document.getElementById("text-"+id);
  if (!input) throw new Error("The owner reply composer is unavailable.");
  input.value = text;
  if (c.channel === "EMAIL") await sendEmailReply(id); else await sendSmsReply(id);
  d.proposal = state.proposals.find(p => p.proposal_id === id) || d.proposal;
  if (text !== "CONFIRM" && (state.drafts[id]?.status !== "READY" || state.drafts[id]?.decision_draft?.decision !== c.decision)) throw new Error("The reply did not produce the expected preview. Nothing will be confirmed automatically.");
}
async function presentationReadResult() {
  const d = presentation, id = d.proposal.proposal_id;
  d.proposal = await api(`/api/v1/proposals/${encodeURIComponent(id)}`);
  d.result = await api(`/api/v1/proposals/${encodeURIComponent(id)}/result`);
  d.proposal._result = d.result;
  state.proposals = [d.proposal];
  d.phase = "result";
  if (!presentationExpected(d.proposal,d.result)) throw new Error("The decision or saved hours could not be verified. The demo stops here instead of showing success.");
}
async function preparePresentation() {
  if (!presentationActive() || state.health.mode !== "mock") throw new Error("The scripted rehearsal is available only in its isolated mock workspace.");
  const reset = await api("/api/v1/operator/reset");
  await api("/api/v1/operator/reset","POST",{confirm_reset:true,preview_token:reset.preview_token},key());
  // Reset revokes sessions. Re-open the same local operator entry to get fresh cookies.
  await fetch("/",{credentials:"same-origin",cache:"no-store"});
  state.owner = null; state.proposals = []; state.drafts = {}; state.replyText = {};
  emailComposers.clear(); emailConversations.clear(); emailConfirmations.clear();
  smsComposers.clear(); smsConversations.clear(); smsConfirmations.clear();
  Object.assign(presentation,{phase:"scan",chapter:0,proposal:null,message:null,result:null,cases:[],error:""});
  presentation.run = await api("/api/v1/operator/fleet-runs","POST",{scope:"EXPLICIT_DATE",date:PRESENTATION_DATE});
  presentation.runId = presentation.run.run_id;
  savePresentation();
  await presentationPollScan();
}
async function nextPresentation(restart=false) {
  const d = presentation;
  if (!presentationActive() || d.busy || (!restart && !presentationCanAdvance())) return;
  d.busy = true; d.error = ""; renderPresentation();
  try {
    if (restart || ["start","complete"].includes(d.phase)) await preparePresentation();
    else if (d.phase === "scan") { d.phase="suggest"; await presentationLoadChapter(); }
    else if (d.phase === "suggest") { await presentationMessage(); d.phase="contact"; }
    else if (d.phase === "contact") { await presentationOwner(); d.phase="owner"; }
    else if (d.phase === "owner") {
      if (PRESENTATION_CHAPTERS[d.chapter].decision === "APPROVE") {
        await decide(d.proposal.proposal_id,"APPROVE");
        await presentationReadResult();
      } else { await presentationSendReply(PRESENTATION_CHAPTERS[d.chapter].reply); d.phase="preview"; }
    } else if (d.phase === "preview") { await presentationSendReply("CONFIRM"); await presentationReadResult(); }
    else if (d.phase === "result") {
      if (d.chapter === PRESENTATION_CHAPTERS.length-1) d.phase="complete";
      else { d.chapter++; d.phase="suggest"; await presentationLoadChapter(); }
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
    if (saved && Number.isInteger(saved.chapter) && saved.chapter>=0 && saved.chapter<3 && ["start","scan","suggest","contact","owner","preview","result","complete"].includes(saved.phase)) {
      Object.assign(d,{chapter:saved.chapter,phase:saved.phase,runId:typeof saved.runId==="string" ? saved.runId : null});
      if (d.runId) d.run=await api(`/api/v1/operator/fleet-runs/${encodeURIComponent(d.runId)}`);
      if (d.phase!=="start" && !d.runId) d.phase="start";
      if (d.phase==="scan") await presentationPollScan();
      else if (!["start","complete"].includes(d.phase)) {
        await presentationLoadChapter();
        if (d.proposal.decision_status==="PENDING" && ["contact","owner","preview"].includes(d.phase)) {
          await presentationMessage();
          if (["owner","preview"].includes(d.phase)) await presentationOwner();
          if (d.phase==="preview") await presentationSendReply(PRESENTATION_CHAPTERS[d.chapter].reply);
        }
      } else if (d.phase==="complete") {
        // Re-derive completion from all three server records, not browser storage.
        for (let i=0;i<3;i++) {
          d.chapter=i; await presentationLoadChapter();
          if (!presentationExpected(d.proposal,d.result)) throw new Error("An earlier rehearsal is incomplete. Start a fresh rehearsal.");
        }
        d.phase="complete";
      }
    }
  } catch(error) { d.phase="start";d.chapter=0;d.runId=null;d.run=null;d.error="The previous rehearsal could not be restored. Next prepares a new isolated rehearsal."; }
  d.ready=true;savePresentation();renderPresentation();
}
document.addEventListener("click",e => {
  if (e.target.closest("[data-presentation-next]")) void nextPresentation();
  else if (e.target.closest("[data-presentation-restart]")) void nextPresentation(true);
});
