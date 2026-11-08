"use strict";

// Channel layouts share the existing owner session, decision and result APIs.
function channelOwnerLink(path, channel) {
  const url = new URL(APP_BASE + path, location.origin);
  const view = {EMAIL: "email", SMS: "sms", WHATSAPP: "whatsapp"}[channel];
  url.searchParams.delete("view");
  if (view) url.searchParams.set("view", view);
  return url.pathname + url.search + url.hash;
}

function ownerMockChannel() {
  if (!IS_OWNER) return null;
  const view = new URLSearchParams(location.search).get("view");
  return view === "email" ? "EMAIL" : view === "sms" ? "SMS" : null;
}

function renderChannelOutcome(p, idPrefix = "proposal") {
  if (["EXPIRED", "SUPERSEDED"].includes(p.decision_status)) {
    return `<article class="customer-card cm-outcome" data-channel-outcome><h2>This proposal is no longer available.</h2>${badge(p.decision_status)}<p>No change was applied from this expired or replaced proposal. Return to the guided demo for a current suggestion.</p></article>`;
  }
  if (p.decision_status === "PENDING") return "";
  return `<article class="customer-card cm-outcome" data-channel-outcome id="${idPrefix}-${h(p.proposal_id)}"><p class="eyebrow">${h(p.business_name)} · APPLICATION RESULT</p>${renderResult(p, p._result)}</article>`;
}

// Native-looking mail chrome is separate from the received HTML email.
// Local reply drafts/transcripts contain no owner capabilities and are not persisted.
const emailComposers = new Map();
const emailConversations = new Map();
const emailSending = new Set();
const emailConfirmations = new Map();
function renderEmailProposal(p) {
  if (["EXPIRED", "SUPERSEDED"].includes(p.decision_status)) return renderChannelOutcome(p);
  const pending = p.decision_status === "PENDING";
  const id = p.proposal_id, busy = emailSending.has(id) || !!state.replyBusy[id];
  const thread = emailConversations.get(id) || [];
  const subject = `Please check your ${holidayLabel(p.day_key)} opening hours`;
  const composing = emailComposers.has(id);
  return `<article class="cm-monitor" id="proposal-${h(id)}" aria-label="Desktop email preview">
    <div class="cm-monitor-bezel"><span class="cm-monitor-camera" aria-hidden="true"></span>
      <div class="cm-email" aria-label="Email from Fonecta Connect">
        <div class="cm-email-toolbar"><span class="cm-mail-icon" aria-hidden="true">✉</span><strong>Mail</strong><span class="cm-mail-account">${h(p.business_name)}</span><span class="cm-window-controls" aria-hidden="true">− &nbsp; □ &nbsp; ×</span></div>
        <div class="cm-email-layout">
          <aside class="cm-email-folders" aria-label="Mail folders"><p>Favourites</p><div class="cm-folder active"><span aria-hidden="true">▣</span> Inbox <small>1</small></div><div class="cm-folder"><span aria-hidden="true">✎</span> Drafts <small>${composing ? 1 : 0}</small></div><div class="cm-folder"><span aria-hidden="true">↗</span> Sent</div><div class="cm-folder"><span aria-hidden="true">▤</span> Archive</div><div class="cm-folder"><span aria-hidden="true">⌫</span> Deleted</div></aside>
          <aside class="cm-email-list" aria-label="Message list"><h2>Inbox <small>1 conversation</small></h2><div class="cm-mail-selected" aria-current="true"><strong>Fonecta Connect</strong><span>${h(subject)}</span><small>Hi ${h(p.business_name)}, please review your opening hours…</small><span class="cm-mail-count">${1 + thread.length + (pending ? 0 : 1)} message${thread.length || !pending ? "s" : ""}</span></div></aside>
          <section class="cm-email-reading" aria-label="Reading pane" tabindex="0">
            <header class="cm-email-heading"><h2>${h(subject)}</h2><span class="cm-email-tag">Inbox</span></header>
            <div class="cm-sender"><span class="cm-avatar" aria-hidden="true">F</span><div><strong>Fonecta Connect</strong><small>To: ${h(p.business_name)}</small></div></div>
            <div class="cm-email-body">
              <p>Hi ${h(p.business_name)},</p><p>Please review your opening hours for <strong>${h(whatsappDate(p))}</strong>.</p>
              <table class="cm-email-hours" aria-label="Opening hours"><tbody><tr><th scope="row">Currently shown</th><td>${h(changeText(p.baseline))}</td></tr><tr><th scope="row">Suggested hours</th><td>${h(changeText(p.change))}</td></tr></tbody></table>
              <p>${h(reasonText(p))}</p><p>We have not confirmed your plans for this date. You can accept the suggestion, edit it or keep your current hours.</p>
              ${p.mode === "sandbox" ? `<p class="cm-email-target"><strong>Actual Yext sandbox target:</strong> ${h(p.target_business_name)} (${h(p.target_entity_id)}). This proposal uses demo evidence from ${h(p.business_name)}. A confirmed change writes to this sandbox target.</p>` : ""}
              <p><strong>Reply YES</strong> to accept, <strong>NO</strong> to keep your current hours, or send the hours you want (for example, <strong>10:00-16:00</strong> or <strong>CLOSED</strong>).</p><p>We will send a preview of your decision. Reply <strong>CONFIRM</strong> to that preview before anything changes.</p><p class="cm-signoff">Thank you,<br>Fonecta Connect</p>
            </div>
            ${thread.map(m => `<section class="cm-email-thread-message ${m.direction}" aria-label="${m.direction === "outgoing" ? "Your reply" : "Reply from Fonecta Connect"}"><div class="cm-thread-sender"><strong>${m.direction === "outgoing" ? h(p.business_name) : "Fonecta Connect"}</strong><small>To: ${m.direction === "outgoing" ? "Fonecta Connect" : h(p.business_name)}</small></div><p>${h(m.text)}</p></section>`).join("")}
            ${pending ? (composing ? `<form class="cm-email-composer" data-email-composer="${h(id)}" autocomplete="off"><div class="cm-email-reply-to">↶ <strong>To:</strong> Fonecta Connect</div><textarea id="text-${h(id)}" data-email-text="${h(id)}" rows="5" maxlength="2000" aria-label="Email reply to Fonecta Connect" placeholder="Write your reply…" ${busy ? "disabled" : ""}>${h(emailComposers.get(id) || "")}</textarea><div class="cm-email-compose-actions"><button type="submit" class="cm-email-send" ${busy ? "disabled" : ""}>Send</button><button type="button" data-email-cancel="${h(id)}" ${busy ? "disabled" : ""}>Discard draft</button></div></form>` : `<div class="cm-email-reply-actions"><button type="button" data-email-reply="${h(id)}">↶ Reply</button></div>`) : `<section class="cm-email-thread-message cm-email-receipt" aria-label="Application receipt"><div class="cm-thread-sender"><strong>Fonecta Connect</strong><small>To: ${h(p.business_name)}</small></div><p>${h(replyReceipt(p))}</p></section>`}
          </section>
        </div>
      </div>
      <div class="cm-monitor-chin" aria-hidden="true"><span></span></div>
    </div>
    <div class="cm-monitor-stand" aria-hidden="true"></div><div class="cm-monitor-foot" aria-hidden="true"></div>
  </article>${pending ? "" : renderChannelOutcome(p, "result")}`;
}

function replyConfirmationText(p, d) {
  const decision = d.decision_draft;
  const change = decision.edited_change || p.change;
  const target = p.mode === "sandbox" ? `\nActual Yext sandbox target: ${p.target_business_name} (${p.target_entity_id}). Demo evidence: ${p.business_name}.` : "";
  const action = decision.decision === "REJECT"
    ? `Keep the current hours: ${changeText(p.baseline)}.`
    : `Change the hours from ${changeText(p.baseline)} to ${changeText(change)}.`;
  return `${p.business_name} · ${whatsappDate(p)}\n${action}${target}\n\nReply CONFIRM to confirm this decision, CANCEL to discard it, or send different hours. Your hours have not changed.`;
}
function replyReceipt(p) {
  if (p.decision_status === "PENDING") return "";
  if (p.decision_status === "REJECTED") return "Your suggestion has been declined. Your current hours have been kept.";
  const r = p._result;
  if (r?.application_status === "SUCCEEDED") return `Your hours have been saved and checked: ${changeText(r.final_change)}.\nPublisher updates may take longer. Saving your hours does not confirm that every listing has updated.`;
  if (["FAILED", "CONFLICT", "REVIEW_REQUIRED"].includes(r?.application_status)) return "We could not verify that your hours were saved. Your confirmation was received, but this update needs review.";
  return "Your decision was received. The application has not yet been verified.";
}
async function sendChannelReply(id, channel) {
  const {conversations, composers, sending, confirmations} = channel;
  if (sending.has(id) || state.replyBusy[id]) return;
  const p = state.proposals.find(x => x.proposal_id === id);
  if (!p || p.decision_status !== "PENDING") return;
  const text = document.getElementById("text-" + id)?.value.trim();
  if (!text || text.length > 2000) return toast(t("replyInvalid"));
  const command = text.toUpperCase().replace(/[.!]$/, "");
  const thread = conversations.get(id) || [];
  conversations.set(id, thread);
  thread.push({direction: "outgoing", text});
  sending.add(id);
  const reply = text => thread.push({direction: "incoming", text});
  let confirming = false;
  try {
    if (command === "CONFIRM") {
      const d = confirmations.get(id);
      // Confirmation belongs only to the last preview this channel actually showed.
      if (!d || d !== state.drafts[id] || d.status !== "READY" ||
          d.decision_draft?.proposal_version !== p.version) {
        confirmations.delete(id);
        delete state.drafts[id];
        reply("No current change is awaiting confirmation. Reply YES, NO, or exact hours such as 10:00-16:00 to create a new preview. Nothing has been changed from this reply.");
      } else {
        confirming = true;
        confirmations.delete(id); // Never reuse this confirmation after a failed/uncertain request.
        await confirmDraft(id);
      }
    } else if (command === "CANCEL") {
      confirmations.delete(id);
      delete state.drafts[id];
      reply("The preview has been discarded. Your hours have not changed. Reply YES, NO, or exact hours when you are ready.");
    } else {
      confirmations.delete(id);
      await interpret(id);
      const d = state.drafts[id];
      if (d?.status === "READY" && ["APPROVE", "EDIT", "REJECT"].includes(d.decision_draft?.decision)) {
        confirmations.set(id, d);
        reply(replyConfirmationText(p, d));
      } else {
        reply("We couldn't determine an exact decision from that reply. Please reply YES to use the suggested hours, NO to keep the current hours, or exact hours such as 10:00-16:00 (or CLOSED). Nothing has been changed.");
      }
    }
  } catch (error) {
    confirmations.delete(id);
    delete state.drafts[id];
    if (confirming) {
      // A lost response may follow a successful write: never claim 'nothing changed'.
      reply("We couldn't verify the outcome of your confirmation. No automatic retry was made. Please check the application status before trying again.");
      try { await refreshOwner(); } catch {}
    } else {
      reply("We couldn't process your reply. Please try YES, NO, or exact hours such as 10:00-16:00. Nothing has been changed from this reply.");
    }
    toast(errorText(error));
  } finally {
    sending.delete(id);
    composers.delete(id);
    renderCustomer();
  }
}

function sendEmailReply(id) {
  return sendChannelReply(id, {conversations: emailConversations, composers: emailComposers, sending: emailSending, confirmations: emailConfirmations});
}

document.addEventListener("click", e => {
  const reply = e.target.closest("[data-email-reply]");
  const cancel = e.target.closest("[data-email-cancel]");
  if (reply) {
    const id = reply.dataset.emailReply;
    emailComposers.set(id, "");
    renderCustomer();
    document.getElementById("text-" + id)?.focus();
  } else if (cancel && !cancel.disabled) {
    emailComposers.delete(cancel.dataset.emailCancel);
    renderCustomer();
  }
});
document.addEventListener("input", e => {
  if (e.target.matches("[data-email-text]")) emailComposers.set(e.target.dataset.emailText, e.target.value);
});
document.addEventListener("submit", e => {
  if (!e.target.matches("[data-email-composer]")) return;
  e.preventDefault();
  void sendEmailReply(e.target.dataset.emailComposer);
});

// Only this tab's simulated SMS transcript is kept here; no capabilities or persistence.
const smsConversations = new Map();
const smsComposers = new Map();
const smsSending = new Set();
const smsConfirmations = new Map();

function renderSmsProposal(p) {
  if (["EXPIRED", "SUPERSEDED"].includes(p.decision_status)) return renderChannelOutcome(p);
  const pending = p.decision_status === "PENDING";
  const id = p.proposal_id, busy = smsSending.has(id) || !!state.replyBusy[id];
  const target = p.mode === "sandbox" ? `\n\nActual Yext sandbox target: ${p.target_business_name} (${p.target_entity_id}). Demo evidence: ${p.business_name}. A confirmed change writes to this target.` : "";
  const text = `Hi ${p.business_name}. Please check your hours for ${whatsappDate(p)}.

Currently shown: ${changeText(p.baseline)}
Suggested hours: ${changeText(p.change)}

Reply YES to accept, NO to keep current hours, or send hours such as 10:00-16:00 (or CLOSED). We will send a preview; reply CONFIRM before anything changes.

${reasonText(p)}
Your plan for this date is not confirmed yet.${target}`;
  const transcript = smsConversations.get(id) || [];
  return `<article class="cm-phone" id="proposal-${h(id)}" aria-label="SMS conversation with Fonecta Connect">
    <div class="cm-sms-screen">
      <div class="cm-sms-statusbar" aria-hidden="true"><span>${h(new Intl.DateTimeFormat("en-GB", {hour: "2-digit", minute: "2-digit"}).format(new Date()))}</span><span class="cm-sms-notch"></span><svg viewBox="0 0 40 16"><path d="M1 12h3v3H1zm5-4h3v7H6zm5-4h3v11h-3zm5-3h3v14h-3z" fill="currentColor"/><rect x="24" y="4" width="12" height="9" rx="2" fill="none" stroke="currentColor"/><rect x="26" y="6" width="8" height="5" rx="1" fill="currentColor"/><path d="M38 7v3" stroke="currentColor" stroke-width="2"/></svg></div>
      <header class="cm-phone-header"><a class="cm-sms-back" href="${APP_BASE}/" aria-label="Back to guided demo">‹</a><span class="cm-avatar" aria-hidden="true">F</span><span class="cm-sms-contact">Fonecta Connect <span aria-hidden="true">›</span></span></header>
      <div class="cm-sms-thread" role="region" aria-label="Text messages">
        <p class="cm-thread-label">Text Message · SMS</p>
        <div class="cm-sms-row incoming"><div class="cm-sms-bubble"><span>${h(text)}</span></div></div>
        ${transcript.map(m => `<div class="cm-sms-row ${m.direction}"><div class="cm-sms-bubble"><span>${h(m.text)}</span></div></div>`).join("")}
        ${pending ? "" : `<div class="cm-sms-row incoming cm-sms-receipt"><div class="cm-sms-bubble"><span>${h(replyReceipt(p))}</span></div></div>`}
      </div>
      ${pending ? `<form class="cm-sms-composer" data-sms-composer="${h(id)}" autocomplete="off">
        <span class="cm-sms-plus" aria-hidden="true">＋</span><div class="cm-sms-input"><textarea id="text-${h(id)}" data-sms-text="${h(id)}" rows="1" maxlength="2000" placeholder="Text Message" aria-label="Text message to Fonecta Connect" ${busy ? "disabled" : ""}>${h(smsComposers.get(id) || "")}</textarea><button class="cm-sms-send" type="submit" aria-label="Send reply" ${busy ? "disabled" : ""}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m-6 6 6-6 6 6"/></svg></button></div>
      </form>` : ""}
      <div class="cm-phone-home" aria-hidden="true"><span></span></div>
    </div>
  </article>${pending ? "" : renderChannelOutcome(p, "result")}`;
}

function sendSmsReply(id) {
  return sendChannelReply(id, {conversations: smsConversations, composers: smsComposers, sending: smsSending, confirmations: smsConfirmations});
}

document.addEventListener("input", e => {
  if (e.target.matches("[data-sms-text]")) smsComposers.set(e.target.dataset.smsText, e.target.value);
});
document.addEventListener("submit", e => {
  if (!e.target.matches("[data-sms-composer]")) return;
  e.preventDefault();
  void sendSmsReply(e.target.dataset.smsComposer);
});
document.addEventListener("keydown", e => {
  if (e.target.matches("[data-sms-composer] textarea") && e.key === "Enter" && !e.shiftKey && !e.isComposing) {
    e.preventDefault();
    e.target.closest("form").requestSubmit();
  }
});
function renderChannelCustomer(channel) {
  const pending = state.proposals.some(p => p.decision_status === "PENDING"), expired = ownerJourneyOutcome() === "EXPIRED";
  const preferred = state.preferences?.preferred_channel;
  app.innerHTML = `<main class="customer-shell channel-owner-shell"><header class="customer-header"><div class="customer-brand">${brand()}</div>${language()}</header>${ownerJourney()}
    <div class="cm-intro"><p class="eyebrow">${ownerJourneyStep() === 4 ? "04 / DECIDE · BUSINESS OWNER VIEW" : "05 / APPLY & CONFIRM"}</p><h1>${pending ? "A message. A clear choice." : expired ? "This proposal is no longer available." : "Here is what happened."}</h1><p>${pending ? "You are now the business owner. Reply to the suggestion and choose what fits your plans." : expired ? "An expired or replaced proposal cannot be decided. Return to the guided demo to review a current suggestion." : "Your decision and its application result are shown below."}</p></div>
    ${preferred && preferred !== channel ? `<div class="notice">This owner's preferred channel is ${h(preferred)}. This is a ${h(channel)} layout preview; their contact preference is unchanged.</div>` : ""}
    ${state.proposals.length > 1 ? '<p class="notice">This message contains several proposals. Decide on each one separately.</p>' : ""}
    <div id="${channel.toLowerCase()}-demo" class="cm-mockups">${state.proposals.map(channel === "EMAIL" ? renderEmailProposal : renderSmsProposal).join("")}</div>
    ${channel === "SMS" && smsSending.size ? '<p class="cm-sms-processing" role="status">Processing this demo reply…</p>' : ""}
    ${channel === "SMS" && pending ? '<p class="cm-sms-help">Reply YES, NO or exact hours to preview a decision. Reply CONFIRM to confirm it, or CANCEL to discard the preview. Complex replies may be processed by Gemini.</p>' : ""}
    ${channel === "EMAIL" && emailSending.size ? '<p class="cm-sms-processing" role="status">Processing this demo reply…</p>' : ""}
    ${channel === "EMAIL" && pending ? '<p class="cm-email-help">Simulated mailbox · No real email is sent. Reply to preview a decision, then reply CONFIRM to apply it. Complex replies may be processed by Gemini.</p>' : ""}
    ${resolvedJourney(ownerJourneyOutcome()) ? "" : ownerDemoNavigation()}
    <details class="cm-settings"><summary>Contact preferences</summary>${renderSettings()}</details>
    <p class="footer-note">Simulated contact. No real ${channel === "EMAIL" ? "email" : "SMS message"} is sent.</p></main>`;
  bindCommon();
  if (channel === "EMAIL") {
    for (const pane of document.querySelectorAll(".cm-email-reading")) {
      if (pane.querySelector(".outgoing, .cm-email-receipt")) pane.scrollTop = pane.scrollHeight;
    }
  }
  if (channel === "SMS") {
    for (const thread of document.querySelectorAll(".cm-sms-thread")) {
      if (thread.querySelector(".outgoing, .cm-sms-receipt")) thread.scrollTop = thread.scrollHeight;
    }
  }
}
