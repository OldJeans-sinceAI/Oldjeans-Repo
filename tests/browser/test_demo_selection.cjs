const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function candidate(id, fields = {}) {
  return {entity_id: id, proposal_id: id, action: "SUGGEST", target_date: "2026-12-24", ...fields};
}

function harness(cases = [], businesses = [], statuses = {}, base = "") {
  const requests = [], storage = new Map();
  const context = vm.createContext({
    APP_BASE: base, IS_OWNER: false, URL, clearTimeout, setTimeout,
    location: {origin: "http://demo.test", href: "http://demo.test/"},
    history: {replaceState(_s, _t, path) { context.location.href = new URL(path, context.location.origin).href; }},
    document: {addEventListener() {}}, window: {addEventListener() {}},
    sessionStorage: {getItem(key) { return storage.get(key) || null; }, setItem(key, value) { storage.set(key, value); }, removeItem(key) { storage.delete(key); }},
    state: {cases: [], fleetTotal: 3032, proposals: []},
    errorText: error => error.message,
    h: value => String(value ?? ""), t: value => value,
    refreshCases: async () => { context.state.cases = cases; },
    api: async url => {
      requests.push(url);
      if (url.startsWith("/api/v1/proposals/")) {
        const id = decodeURIComponent(url.split("/").pop());
        return {proposal_id: id, entity_id: cases.find(c => c.proposal_id === id)?.entity_id, decision_status: statuses[id] || "PENDING"};
      }
      if (url.startsWith("/api/v1/operator/businesses?")) {
        const q = new URL(url, "http://demo.test").searchParams.get("q");
        return {items: businesses.filter(b => !q || b.entity_id === q), total: businesses.length};
      }
      throw new Error(`Unexpected request: ${url}`);
    },
  });
  for (const name of ["channel-mockups.js", "whatsapp.js", "demo.js"]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../../web", name), "utf8"), context);
  }
  context.state.demo = vm.runInContext("newDemoState()", context);
  return {context, requests};
}

test("review order wins over WhatsApp even when the directory lists WhatsApp first", async () => {
  const {context, requests} = harness([candidate("EMAIL"), candidate("WA")], [
    {entity_id: "WA", preferred_channel: "WHATSAPP"},
    {entity_id: "EMAIL", preferred_channel: "EMAIL"},
  ]);
  await vm.runInContext("pickDemoSuggestion()", context);
  assert.equal(context.state.demo.proposalId, "EMAIL");
  assert.equal(context.state.demo.stage, 2);
  assert.equal(requests.length, 2);
  await vm.runInContext("pickDemoSuggestion(true)", context);
  assert.equal(context.state.demo.proposalId, "WA");
});

test("progress distinguishes saved, kept, pending, failed and unavailable outcomes", () => {
  const {context} = harness();
  for (const [decision, application, expected, step, detail] of [
    ["PENDING", "NOT_STARTED", "PENDING", 4, "Awaiting decision"],
    ["APPROVED", "SUCCEEDED", "APPLIED", 5, "Saved & verified"],
    ["EDITED", "SUCCEEDED", "APPLIED", 5, "Saved & verified"],
    ["REJECTED", "NOT_STARTED", "REJECTED", 5, "No change needed"],
    ["APPROVED", "FAILED", "FAILED", 5, "Needs attention"],
    ["APPROVED", "CONFLICT", "FAILED", 5, "Needs attention"],
    ["APPROVED", "REVIEW_REQUIRED", "FAILED", 5, "Needs attention"],
    ["APPROVED", "SCHEDULED", "APPLYING", 5, "Awaiting verification"],
    ["STANDING_AUTHORIZED", "PENDING", "APPLYING", 5, "Awaiting verification"],
    ["EXPIRED", "NOT_STARTED", "EXPIRED", 4, "No longer available"],
    ["SUPERSEDED", "NOT_STARTED", "EXPIRED", 4, "No longer available"],
  ]) {
    context.state.proposals = [{decision_status: decision, _result: {application_status: application}}];
    assert.equal(vm.runInContext("ownerJourneyOutcome()", context), expected);
    assert.equal(vm.runInContext("ownerJourneyStep()", context), step);
    const html = vm.runInContext("journeySteps(ownerJourneyStep(), ownerJourneyOutcome())", context);
    assert.match(html, new RegExp(detail));
    const last = [...html.matchAll(/<li\b[^>]*>[\s\S]*?<\/li>/g)].at(-1)[0];
    assert.equal(last.includes('class="done'), expected === "APPLIED", decision + "/" + application);
    if (expected === "EXPIRED") assert.ok(!last.includes("✓"));
    assert.equal((html.match(/aria-current=/g) || []).length, 1);
  }
});

test("mixed owner bundles do not announce completion before every decision and apply finishes", () => {
  const {context} = harness();
  assert.equal(vm.runInContext("ownerJourneyOutcome()", context), "PENDING");
  assert.equal(vm.runInContext("ownerDemoNavigation()", context), "");
  for (const [status, expected] of [["PENDING", "PENDING"], ["EXPIRED", "EXPIRED"], ["APPROVED", "APPLYING"], ["REJECTED", "APPLIED"]]) {
    context.state.proposals = [{decision_status: "EDITED", _result: {application_status: "SUCCEEDED"}}, {decision_status: status}];
    assert.equal(vm.runInContext("ownerJourneyOutcome()", context), expected);
  }
});

test("next business skips another proposal for the same company and retains the scan", async () => {
  const {context, requests} = harness([candidate("A"), candidate("A2", {entity_id: "A"}), candidate("B")], [{entity_id: "A"}, {entity_id: "B"}]);
  Object.assign(context.state.demo, {proposalId: "A", proposal: {entity_id: "A"}, runId: "scan-1", run: {status: "COMPLETED"}});
  await vm.runInContext("pickDemoSuggestion(true)", context);
  assert.equal(context.state.demo.proposalId, "B");
  assert.equal(context.state.demo.runId, "scan-1");
  assert.equal(context.state.demo.stage, 2);
  assert.ok(!requests.some(url => url.includes("/A2") || url.includes("/messages") || url.includes("/fleet-runs")));
});

test("stale queue entries are skipped; service failures remain visible", async () => {
  for (const status of [404, 410, 500]) {
    const {context} = harness([candidate("A"), candidate("B")], [{entity_id: "B"}]);
    const api = context.api;
    context.api = async url => { if (url.endsWith("/A")) throw Object.assign(new Error("Read failed"), {status}); return api(url); };
    if (status === 500) await assert.rejects(vm.runInContext("pickDemoSuggestion()", context), /Read failed/);
    else { await vm.runInContext("pickDemoSuggestion()", context); assert.equal(context.state.demo.proposalId, "B"); }
  }
});

test("next intent is consumed once, validated against this completed business, and read-only", async () => {
  const {context, requests} = harness([candidate("A"), candidate("B")], [{entity_id: "B"}]);
  Object.assign(context.state.demo, {runId: "scan-1", run: {status: "COMPLETED"}, proposalId: "A", proposal: {entity_id: "A", decision_status: "APPROVED"}, result: {application_status: "SUCCEEDED"}});
  context.location.href = "http://demo.test/?next_business=A";
  await vm.runInContext("maybeAdvanceToNextBusiness()", context);
  assert.equal(context.location.href, "http://demo.test/");
  assert.equal(context.state.demo.proposalId, "B");
  const count = requests.length;
  await vm.runInContext("maybeAdvanceToNextBusiness()", context);
  assert.equal(requests.length, count);
  assert.ok(requests.every(url => !/messages|decisions|fleet-runs/.test(url)));
});

test("unresolved, mismatched and scanless next intents never skip a business", async () => {
  for (const scenario of ["pending", "failed", "expired", "mismatch", "no-scan", "running"]) {
    const {context, requests} = harness([candidate("B")], [{entity_id: "B"}]);
    Object.assign(context.state.demo, {run: {status: "COMPLETED"}, proposalId: "A", proposal: {decision_status: "APPROVED"}, result: {application_status: "SUCCEEDED"}});
    if (scenario === "pending") context.state.demo.proposal.decision_status = "PENDING";
    if (scenario === "expired") context.state.demo.proposal.decision_status = "EXPIRED";
    if (scenario === "failed") context.state.demo.result.application_status = "FAILED";
    if (scenario === "no-scan") context.state.demo.run = null;
    if (scenario === "running") context.state.demo.run.status = "RUNNING";
    context.location.href = "http://demo.test/?next_business=" + (scenario === "mismatch" ? "OTHER" : "A");
    await vm.runInContext("maybeAdvanceToNextBusiness()", context);
    assert.equal(context.state.demo.proposalId, "A", scenario);
    assert.equal(requests.length, 0, scenario);
    assert.ok(!context.location.href.includes("next_business"));
  }
});

test("Decide survives reload; expired restore stays at Decide, not Apply", async () => {
  const {context} = harness();
  Object.assign(context.state.demo, {stage: 4, proposalId: "A"});
  vm.runInContext("saveDemo()", context);
  assert.equal(vm.runInContext("newDemoState().stage", context), 4);
  context.api = async url => url.endsWith("/result") ? {application_status: "NOT_STARTED"} : {proposal_id: "A", decision_status: "EXPIRED"};
  await vm.runInContext("restoreDemo()", context);
  assert.equal(context.state.demo.stage, 4);
});

test("owner next CTA needs a matching saved journey and is never offered in sandbox", () => {
  for (const base of ["", "/sandbox"]) {
    const {context} = harness([], [], {}, base);
    Object.assign(context.state.demo, {proposalId: "A", runId: "scan-1"});
    vm.runInContext("saveDemo()", context);
    context.state.proposals = [{proposal_id: "A", decision_status: "REJECTED"}];
    assert.equal(vm.runInContext("ownerDemoNavigation()", context).includes("data-next-business"), !base);
    context.state.proposals[0].proposal_id = "OTHER";
    assert.ok(!vm.runInContext("ownerDemoNavigation()", context).includes("data-next-business"));
  }
});

test("selection skips wrong dates, flags, decided, opted-out and missing contacts", async () => {
  const cases = [candidate("WRONG", {target_date: "2026-12-25"}),
    candidate("FLAG", {action: "FLAG"}), candidate("DONE"), candidate("OUT"),
    candidate("MISSING"), candidate("SMS")];
  const businesses = [{entity_id: "OUT", source_opted_out: true},
    {entity_id: "SMS", preferred_channel: "SMS", source_opted_out: false}];
  const snapshot = JSON.stringify(businesses);
  const {context} = harness(cases, businesses, {DONE: "APPROVED"});
  await vm.runInContext("pickDemoSuggestion()", context);
  assert.equal(context.state.demo.proposalId, "SMS");
  assert.equal(JSON.stringify(businesses), snapshot);
});

test("an empty eligible queue returns to Detect without creating a message", async () => {
  const {context, requests} = harness([candidate("OUT")], [{entity_id: "OUT", source_opted_out: true}]);
  context.state.demo.stage = 5;
  await vm.runInContext("pickDemoSuggestion()", context);
  assert.equal(context.state.demo.stage, 1);
  assert.match(context.state.demo.note, /No other pending suggestion/);
  assert.ok(requests.every(url => !url.includes("/messages")));
});

test("prepared message channel controls owner layout and preserves scope and token", () => {
  for (const base of ["", "/sandbox"]) {
    for (const channel of ["EMAIL", "SMS", "PHONE", "WHATSAPP"]) {
      const {context} = harness([], [], {}, base);
      Object.assign(context.state.demo, {
        stage: 3, proposal: {business_name: "Example cafe"},
        message: {channel, status: "PREVIEW", text: "Please check your hours.", owner_entry_path: "/customer#token=fixture-token"},
      });
      const html = vm.runInContext("renderDemo()", context);
      const href = html.match(/id="demo-owner-link" href="([^"]+)"/)[1];
      const url = new URL(href, "http://demo.test");
      assert.equal(url.pathname, base + "/customer");
      assert.equal(url.hash, "#token=fixture-token");
      assert.equal(url.searchParams.get("view"), ({EMAIL: "email", SMS: "sms", WHATSAPP: "whatsapp"})[channel] || null);
      assert.match(html, /Open the owner view/);
    }
  }
});
