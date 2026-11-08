"use strict";

// Adapted from teammate frontend@755f12b, connected to our existing owner APIs.
// See NOTICE. No separate chat server is used.
function isWhatsAppView() {
  return IS_OWNER && new URLSearchParams(location.search).get("view") === "whatsapp";
}

function whatsappOwnerLink(path) {
  const url = new URL(APP_BASE + path, location.origin);
  url.searchParams.set("view", "whatsapp");
  return url.pathname + url.search + url.hash;
}

function whatsappDate(p) {
  const date = p.change.date;
  if (!date) return dateLabel(p.change.effective_from || p.change.reopen_date, p.timezone);
  return new Intl.DateTimeFormat("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC",
  }).format(new Date(date + "T12:00:00Z"));
}

function renderWhatsAppProposal(p) {
  const id = p.proposal_id;
  if (["EXPIRED", "SUPERSEDED"].includes(p.decision_status)) {
    return `<article class="customer-card wa-outcome" data-wa-outcome><p class="eyebrow">04 / NEEDS REVIEW</p><h2>This proposal is no longer available.</h2>${badge(p.decision_status)}<p>No change was applied from this expired or replaced proposal. Return to the guided demo for a current suggestion.</p></article>`;
  }
  if (p.decision_status !== "PENDING") {
    return `<article class="customer-card wa-outcome" data-wa-outcome id="proposal-${h(id)}"><p class="eyebrow">05 / APPLY & CONFIRM · ${h(p.business_name)}</p>${renderResult(p, p._result)}<p class="decision-hint">${p.decision_status === "REJECTED" ? "Your decision was recorded. No hours were changed." : "This status comes from the application result. Publisher delivery times below are estimates."}</p></article>`;
  }
  const busy = !!state.replyBusy[id];
  const drafted = state.drafts[id] || busy;
  return `<article class="wa-window" id="proposal-${h(id)}" aria-label="WhatsApp conversation with Fonecta Connect">
    <div class="wa-screen">
    <div class="wa-status-bar" aria-hidden="true"><span>${new Intl.DateTimeFormat("en-GB", {hour: "2-digit", minute: "2-digit"}).format(new Date())}</span><span class="wa-notch"></span><svg viewBox="0 0 68 18"><path d="M1 14h3v3H1zm5-4h3v7H6zm5-4h3v11h-3zm5-4h3v15h-3z" fill="currentColor"/><path d="M26 6q9-8 18 0M29 9q6-5 12 0m-9 3q3-2 6 0" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><circle cx="35" cy="15" r="1.4" fill="currentColor"/><rect x="49" y="4" width="15" height="10" rx="2" fill="none" stroke="currentColor"/><rect x="51" y="6" width="11" height="6" rx="1" fill="currentColor"/><path d="M66 7v4" stroke="currentColor" stroke-width="2"/></svg></div>
    <header class="wa-header">
      <a class="icon" href="${APP_BASE}/" aria-label="Back to guided demo"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="m15 4-8 8 8 8"/></svg></a>
      <div class="wa-avatar" aria-hidden="true">F</div>
      <div class="who"><div class="name">Fonecta Connect</div><div class="sub">WhatsApp demo · simulated contact</div></div>
      <span class="wa-call-icons" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="2" y="5" width="13" height="14" rx="3"/><path d="m15 9 6-3v12l-6-3z"/></svg><svg viewBox="0 0 24 24"><path d="m6 3 4 4-3 3c1 3 4 6 7 7l3-3 4 4-2 3C11 23 1 13 3 5z"/></svg></span>
    </header>
    <div class="wa-chat" role="region" aria-label="Conversation">
      <div class="wa-messages">
        <div class="chip">OPENING-HOURS SUGGESTION</div>
        <div class="row in"><div class="wa-message-group"><div class="bubble wa-proposal-message"><div class="text">Hi ${h(p.business_name)}!

Please check your hours for <strong>${h(whatsappDate(p))}</strong>.</div>
          <div class="wa-hours"><div><span>Currently shown</span><strong>${h(changeText(p.baseline))}</strong></div><div><span>We propose</span><strong>${h(changeText(p.change))}</strong></div></div>
          <p class="text">${h(reasonText(p))}</p>
          <p class="text wa-uncertainty">This evidence does not confirm your final plan for this date. You decide.</p>
          ${p.mode === "sandbox" ? `<div class="notice warn">${t("realTarget")}: ${h(p.target_business_name)} · ${h(p.target_entity_id)}<br>${t("sandboxEvidence")}: ${h(p.business_name)}<br>Approval writes to the team's Yext sandbox.</div>` : ""}
          <details class="wa-evidence"><summary>Why these hours?</summary>${evidence(p.evidence)}</details>
          <div class="meta">Suggestion · awaiting your decision</div>
        </div><div class="wa-choices"><button class="primary" data-decision="APPROVE" data-id="${h(id)}">Approve hours</button><button data-edit="${h(id)}">Edit hours</button><button class="ghost" data-decision="REJECT" data-id="${h(id)}">Keep current hours</button></div><small class="wa-choice-help">Buttons work without the reply assistant.</small></div></div>
        ${state.editing === id ? `<div class="row in"><div class="bubble wa-editor"><strong>Choose your hours</strong>${renderEdit(p)}</div></div>` : ""}
        ${drafted && state.replyText[id] ? `<div class="row out"><div class="bubble"><div class="wa-quoted"><strong>Fonecta Connect</strong><span>Suggested hours: ${h(changeText(p.change))}</span></div><span class="text">${h(state.replyText[id])}</span><div class="meta">Your reply · preview</div></div></div>` : ""}
        ${busy ? '<div class="row in"><div class="bubble" role="status">Reading your reply… Your hours have not changed.</div></div>' : state.drafts[id] ? `<div class="row in"><div class="bubble wa-draft" aria-live="polite">${renderDraft(p)}</div></div>` : ""}
      </div>
    </div>
    <form class="wa-composer" data-wa-composer="${h(id)}" autocomplete="off">
      <span class="wa-attach-icon" aria-hidden="true">＋</span>
      <div class="pill"><textarea id="text-${h(id)}" data-reply-text="${h(id)}" rows="1" maxlength="2000" placeholder="Message" aria-label="Message to Fonecta Connect" ${busy ? "disabled" : ""}>${h(state.replyText[id] || "")}</textarea></div>
      <button class="send" type="submit" aria-label="Preview my reply" ${busy ? "disabled" : ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>
      <button type="button" data-interpret="${h(id)}" hidden ${busy ? "disabled" : ""}>Preview reply</button>
    </form>
    <p class="wa-privacy">Sending text creates a preview. Confirm it before anything changes. Complex replies may be processed by Gemini.</p>
    <div class="wa-home-indicator" aria-hidden="true"><span></span></div>
    </div>
  </article>`;
}

function renderWhatsAppCustomer() {
  const pending = state.proposals.some(p => p.decision_status === "PENDING"), expired = ownerJourneyOutcome() === "EXPIRED";
  const channel = state.preferences?.preferred_channel;
  app.innerHTML = `<main class="customer-shell whatsapp-owner-shell"><header class="customer-header"><div class="customer-brand">${brand()}</div>${language()}</header>${ownerJourney()}
    <div class="wa-intro"><p class="eyebrow">${ownerJourneyStep() === 4 ? "04 / DECIDE · BUSINESS OWNER VIEW" : "05 / APPLY & CONFIRM"}</p><h1>${pending ? "Your hours. Your decision." : expired ? "This proposal is no longer available." : "Here is what happened."}</h1><p>${pending ? "You are now the business owner. Review the message and choose what fits your plans." : expired ? "An expired or replaced proposal cannot be decided. Return to the guided demo to review a current suggestion." : "The result below shows whether a decision was recorded and a change was applied."}</p></div>
    ${channel && channel !== "WHATSAPP" ? `<div class="notice">This owner's preferred channel is ${h(channel)}. This is a WhatsApp layout preview; their contact preference is unchanged.</div>` : ""}
    ${state.proposals.length > 1 ? '<p class="notice">This message contains several proposals. Decide on each one separately.</p>' : ""}
    <div id="whatsapp-demo">${state.proposals.map(renderWhatsAppProposal).join("")}</div>
    ${resolvedJourney(ownerJourneyOutcome()) ? "" : ownerDemoNavigation()}
    <details class="wa-settings"><summary>Contact preferences</summary>${renderSettings()}</details>
    <div class="footer-note">Simulated contact. No real WhatsApp message is sent.</div></main>`;
  bindCommon();
  for (const chat of document.querySelectorAll(".wa-chat")) {
    if (chat.querySelector(".wa-editor, .wa-draft, [role=status]")) chat.scrollTop = chat.scrollHeight;
  }
}

document.addEventListener("submit", e => {
  if (!e.target.matches("[data-wa-composer]")) return;
  e.preventDefault();
  e.target.querySelector("[data-interpret]").click();
});
document.addEventListener("keydown", e => {
  if (e.target.matches("[data-wa-composer] textarea") && e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    e.target.closest("form").requestSubmit();
  }
});
