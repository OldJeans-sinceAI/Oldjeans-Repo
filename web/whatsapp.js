"use strict";

// Teammate frontend@755f12b visual, connected to our existing owner APIs.
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
    return `<article class="customer-card wa-outcome" data-wa-outcome><p class="eyebrow">05 / NEEDS REVIEW</p><h2>This proposal is no longer available.</h2>${badge(p.decision_status)}<p>No change was applied from this expired or replaced proposal. Return to the guided demo for a current suggestion.</p></article>`;
  }
  if (p.decision_status !== "PENDING") {
    return `<article class="customer-card wa-outcome" data-wa-outcome id="proposal-${h(id)}"><p class="eyebrow">05 / APPLY & CONFIRM · ${h(p.business_name)}</p>${renderResult(p, p._result)}<p class="decision-hint">${p.decision_status === "REJECTED" ? "Your decision was recorded. No hours were changed." : "This status comes from the application result. Publisher delivery times below are estimates."}</p></article>`;
  }
  const busy = !!state.replyBusy[id];
  const drafted = state.drafts[id] || busy;
  return `<article class="wa-window" id="proposal-${h(id)}" aria-label="WhatsApp conversation with Fonecta Connect">
    <header class="wa-header">
      <a class="icon" href="${APP_BASE}/" aria-label="Back to guided demo">←</a>
      <div class="wa-avatar" aria-hidden="true">F</div>
      <div class="who"><div class="name">Fonecta Connect</div><div class="sub">WhatsApp demo · simulated contact</div></div>
      <span class="wa-header-label">Business hours</span>
    </header>
    <div class="wa-chat" role="region" aria-label="Conversation">
      <div class="wa-messages">
        <div class="chip">OPENING-HOURS SUGGESTION</div>
        <div class="row in"><div class="bubble wa-proposal-message"><div class="text">Hi ${h(p.business_name)}!

Please check your hours for <strong>${h(whatsappDate(p))}</strong>.</div>
          <div class="wa-hours"><div><span>Currently shown</span><strong>${h(changeText(p.baseline))}</strong></div><div><span>We propose</span><strong>${h(changeText(p.change))}</strong></div></div>
          <p class="text">${h(reasonText(p))}</p>
          <p class="text wa-uncertainty">This evidence does not confirm your final plan for this date. You decide.</p>
          ${p.mode === "sandbox" ? `<div class="notice warn">${t("realTarget")}: ${h(p.target_business_name)} · ${h(p.target_entity_id)}<br>${t("sandboxEvidence")}: ${h(p.business_name)}<br>Approval writes to the team's Yext sandbox.</div>` : ""}
          <div class="wa-choices"><button class="primary" data-decision="APPROVE" data-id="${h(id)}">✓ Approve hours</button><button data-edit="${h(id)}">Edit hours</button><button class="ghost" data-decision="REJECT" data-id="${h(id)}">Keep current hours</button></div>
          <small class="wa-choice-help">Buttons work without the reply assistant.</small>
          <details class="wa-evidence"><summary>Why these hours?</summary>${evidence(p.evidence)}</details>
        </div></div>
        ${state.editing === id ? `<div class="row in"><div class="bubble wa-editor"><strong>Choose your hours</strong>${renderEdit(p)}</div></div>` : ""}
        ${drafted && state.replyText[id] ? `<div class="row out"><div class="bubble"><span class="text">${h(state.replyText[id])}</span><div class="meta">Your reply · preview</div></div></div>` : ""}
        ${busy ? '<div class="row in"><div class="bubble" role="status">Reading your reply… Your hours have not changed.</div></div>' : state.drafts[id] ? `<div class="row in"><div class="bubble wa-draft" aria-live="polite">${renderDraft(p)}</div></div>` : ""}
      </div>
    </div>
    <form class="wa-composer" data-wa-composer="${h(id)}" autocomplete="off">
      <div class="pill"><textarea id="text-${h(id)}" data-reply-text="${h(id)}" rows="1" maxlength="2000" placeholder="Type a reply, or use the buttons above" aria-label="Message to Fonecta Connect" ${busy ? "disabled" : ""}>${h(state.replyText[id] || "")}</textarea></div>
      <button class="send" type="submit" aria-label="Preview my reply" ${busy ? "disabled" : ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.01 21 23 12 2.01 3 2 10l15 2-15 2z"/></svg></button>
      <button type="button" data-interpret="${h(id)}" hidden ${busy ? "disabled" : ""}>Preview reply</button>
    </form>
    <p class="wa-privacy">Sending text creates a preview. Confirm it before anything changes. Complex replies may be processed by Gemini.</p>
  </article>`;
}

function renderWhatsAppCustomer() {
  const pending = state.proposals.some(p => p.decision_status === "PENDING");
  const channel = state.preferences?.preferred_channel;
  app.innerHTML = `<main class="customer-shell whatsapp-owner-shell"><header class="customer-header"><div class="customer-brand">${brand()}</div>${language()}</header>${ownerJourney()}
    <div class="wa-intro"><p class="eyebrow">${pending ? "04 / DECIDE · BUSINESS OWNER VIEW" : "05 / APPLY & CONFIRM"}</p><h1>${pending ? "Your hours. Your decision." : "Here is what happened."}</h1><p>${pending ? "You are now the business owner. Review the message and choose what fits your plans." : "The result below shows whether a decision was recorded and a change was applied."}</p></div>
    ${channel && channel !== "WHATSAPP" ? `<div class="notice">This owner's preferred channel is ${h(channel)}. This is a WhatsApp layout preview; their contact preference is unchanged.</div>` : ""}
    ${state.proposals.length > 1 ? '<p class="notice">This message contains several proposals. Decide on each one separately.</p>' : ""}
    <div id="whatsapp-demo">${state.proposals.map(renderWhatsAppProposal).join("")}</div>
    <a class="journey-return" href="${APP_BASE}/">← ${APP_BASE ? "Back to workspace" : "Back to the guided demo"}</a>
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
