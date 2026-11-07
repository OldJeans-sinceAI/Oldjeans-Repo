# QA report – "Connect Suggests – Customer Approves" (Oldjeans-Repo, branch `fonecta`)

Scope of this report: the ZIP as delivered (git HEAD `88c0b18`). Meeting notes (`first day-1.pdf`) were **not** in the ZIP; the challenge brief PDF was (it sits in the repo root) and is used below.

> **Headline finding.** The `fonecta` branch is still the **organisers' starter kit** (mock Yext API + owner simulator + rule-based baseline + scorer + `quickstart.py`) plus a 33-line Node connection check. It contains **no LLM call, no suggestion state machine (`pending/approved/edited/rejected/expired`), no confidence threshold, no expiry logic, no message sender, no customer approve/edit/reject page, and no learning loop.** The "HTML" in the language breakdown is `START_HERE.html` (documentation, no buttons/forms/`fetch`). The other branches (`main`, `test`, `BoilerPlate`, `Cer1004-patch-1`) are either the same kit or an unrelated Streamlit "Näkyvyystesti" app (`app.py`, `core.py`, `render.py`). So the tests below (a) verify everything that exists, (b) pin known gaps as `expectedFailure`/`todo`, and (c) record the contract for missing features as skipped stubs, rather than inventing an implementation.

---

## 1. Architecture & data flow

### 1.1 Components

| Layer | Files | Role |
|---|---|---|
| Data (synthetic, read-only) | `data/*.json, *.jsonl, *.csv, *.parquet`, `labels/`, `evaluation/targets_*.csv` | 3,032 entities, holiday/regular-hours history, reviews, Google user edits, peer benchmarks, calendar, contacts, 2025 pilot log … |
| Mock Yext API (Python, stdlib `http.server`) | `mock_api/server.py`, `hours.py`, `simulator.py`, `sim_data.json` | Same URL shapes as Yext (`/v2/accounts/me/…?api_key=&v=`), in-memory `Store` with write overrides persisted to `mock_api/state.json`; `/sim/v1/owner-response` = simulated customer; `/mock/reset` |
| Yext client (Python) | `examples/yext_client.py` | `YextClient` (GET/PUT, read-modify-write of `holidayHours`), `owner_response()` helper. Base URL from `YEXT_BASE_URL` → same code hits mock **or** `https://sbx-api.yextapis.com` |
| Decision engine | `examples/baseline.py` (`Baseline.explain/predict`) | Rule-based: closed-for-good signals → shopping-centre hours → last year's exception → peer majority |
| Orchestrator / demo | `examples/quickstart.py` | Runs the 5 steps for one business + one day, prints the customer message (fi/sv/nb/en templates) |
| Scorer | `evaluation/evaluate.py` | Objective "suggestion quality" score vs `labels/` |
| JS | `tests/backend_connection_test.js` (+ `package.json`, `.github/workflows/backend-test.yml`) | Only thing in JS: one GET to the real sandbox using `.env` |
| HTML | `START_HERE.html` | Static documentation page. **Not** a customer UI |

### 1.2 Mapping to the 5 steps

| Step | Where it lives today | Notes |
|---|---|---|
| **1 DETECT** | `Baseline.explain()` – uses `entities.json` (displayed hours), `holiday_hours_history.jsonl`, `regular_hours_history.jsonl`, `calendar_special_days.csv` (via `targets_2026.csv` rows), `reviews.json` (+ `publisher_suggestions.json`) for closed-for-good, `peer_benchmarks.csv`, `cities.csv` | **Unused** by the engine: `analytics_daily.parquet` (visibility priority), `pilot_decision_log_2025.csv` (learning), `customer_contacts.csv` (channel/opt-out/standing permission), weather, events, school breaks |
| **2 SUGGEST** | Same function returns `(action, hours, basis, evidence)`; `baseline.py main()` writes a **constant `confidence = 0.6`**. Message wording = static `TXT` templates in `quickstart.py` | **No LLM anywhere.** No threshold consumes the confidence |
| **3 CONTACT** | `quickstart.py` `run()` prints the message | Nothing is sent; no use of preferred channel / language / window / opt-out |
| **4 DECIDE** | `POST /sim/v1/owner-response` → `simulator.respond()` → `ACCEPTED \| EDITED \| REJECTED \| NO_RESPONSE` (+ latency, standing_permission). Client wrapper: `yext_client.owner_response()` | Simulator only; works for `dev`/`demo` entities (403 for scored `test` entities) |
| **5 APPLY** | `YextClient.set_holiday_hours()` → `GET` entity, merge one `holidayHours` date, `PUT` full `hours` → mock or sandbox. Confirmation: `GET …/listings/listings` → `expectedLiveBy` per publisher, printed by `quickstart.py` | Only on ACCEPTED/EDITED. No retry/backoff, no version check |

### 1.3 How Python, HTML and JS interact
They don't, yet. Python (mock API + client + engine) is the whole loop. JS is an isolated CI smoke test of the **real** sandbox. HTML is docs. The only shared contract is the Yext URL/`v=` convention and the `.env` variables (`YEXT_BASE_URL/API_KEY/ENTITY_ID/API_VERSION`).

### 1.4 LLM and state machine
* **LLM:** not called anywhere (searched all branches/history: no Anthropic/OpenAI client).
* **State machine:** not stored anywhere. Closest things: simulator decision vocabulary (`ACCEPTED/EDITED/REJECTED/NO_RESPONSE`, upper-case, no `pending`/`expired`), the 2025 pilot log (`decision` column), and Yext *publisher-suggestion* statuses (`WAITING_ON_CUSTOMER/ACCEPTED/REJECTED/EXPIRED`, a different concept). The only persisted state is `mock_api/state.json` (`overrides`, `update_log`) – entity hours, not suggestion status.

---

## 2. Feature inventory (what exists + evaluation criteria)

Legend: ✅ implemented · ⚠️ partial · ❌ missing.

### Step 1 – DETECT
| Feature | Input | Output | Success criteria | State |
|---|---|---|---|---|
| Displayed-hours reconstruction | entity, date, snapshot 6 Nov | what Google shows (exception or regular) | equals `displayed_hours_at_snapshot` label | ✅ |
| Last-year exception | history rows `< snapshot` | candidate hours, evidence `(date, hours)` | no future leakage (back-test honesty) | ✅ |
| Shopping-centre rule | centre entity's holiday entry | candidate + centre name | tenant follows published centre hours | ✅ |
| Peer majority rule | benchmarks (≥70 % closed, ≥15 % entered) | `closed` + share | only fires with strong majority | ✅ |
| Closed-for-good → `FLAG` | reviews (150 d, multilingual keywords), Google edits | `FLAG` | never `SUGGEST` to a dead business | ✅ |
| Visibility prioritisation | `analytics_daily.parquet` | ranking | high-view dates first | ❌ (scorer reports it; engine ignores) |
| Reviews/events/weather/school breaks as signals | files | extra candidates | ≥ baseline score (54.5) | ❌ |

### Step 2 – SUGGEST
| Feature | Input | Output | Success criteria | State |
|---|---|---|---|---|
| Hours string suggestion | `explain()` | `closed` / `HH:MM-HH:MM[,…]` | valid per `is_valid_hours`, ≠ displayed hours | ✅ |
| Reason/basis for audit trail | — | `LAST_YEAR/SHOPPING_CENTRE/PEERS/CLOSED_SIGNALS` + evidence | every SUGGEST has evidence | ✅ |
| Confidence score | — | constant 0.6 | calibrated, threshold-gated | ⚠️ constant, unused |
| LLM explanation (fi/sv/nb/en) | basis + evidence | friendly text | correct language/hours; safe fallback | ❌ (static templates only) |

### Step 3 – CONTACT
| Feature | Input | Output | Success criteria | State |
|---|---|---|---|---|
| Message rendering | entity, day, basis | text with greeting, reason, "Google now shows", suggestion, 3 buttons | understandable at a glance; local date/weekday format | ⚠️ printed only |
| Channel / window / opt-out | `customer_contacts.csv` | send decision | opt-outs never contacted | ❌ |
| No-login link | — | signed URL | single-use, tamper-proof | ❌ |

### Step 4 – DECIDE
| Feature | Input | Output | Success criteria | State |
|---|---|---|---|---|
| Owner simulator | entity, date, proposed hours, channel, messageId, sendHour | decision, final hours, latency, standing_permission | deterministic; exact→accept; wrong state never accepted; reject→no hours | ✅ |
| Approve / Edit / Reject UI | click | decision | works without login on mobile | ❌ |
| Expiry (`expired`) | pending age / date passed | status | late answer not applied | ❌ |
| State storage (`pending…`) | — | persisted status | legal transitions only | ❌ |

### Step 5 – APPLY
| Feature | Input | Output | Success criteria | State |
|---|---|---|---|---|
| Write holiday hours | entity, date, hours | PUT full `hours` incl. merged `holidayHours` | weekday hours preserved, same date replaced, sorted, idempotent | ✅ |
| Server-side validation | hours JSON | 200 / 400 (code 2201) | rejects bad time, overlap, start=end, dup/bad date, ≠1 flag | ✅ (mock) |
| Confirmation of where hours show | listings | publisher + ETA | `expectedLiveBy` present after PUT | ✅ |
| Error handling (401/404/429/5xx) | — | exception | retry with backoff on 429/5xx | ⚠️ raises, **no retry** |
| Standing permission | `standing_permission_*` | apply-then-inform | no ask for holidays | ❌ |

### Tech-stack / support features
| Feature | Success criteria | State |
|---|---|---|
| Mock API endpoints: entities (list/filter/page/get/PUT), reviews, publisher suggestions, listings, analytics, owner-response, reset | Yext-shaped JSON, error codes 401/400/404/501 | ✅ |
| Scorer `evaluate.py` | published baseline reproduces 54.49 / precision 0.901 / 224 harmful | ✅ |
| JS sandbox check | fails CI when connection fails | ⚠️ always exits 0 |

### Evaluation criteria from the brief → how this suite covers them
| Criterion | Covered by | Gap |
|---|---|---|
| **Suggestion quality** (sensible, data-backed; scored on hidden test) | `test_baseline_detect_suggest.py` (storylines + 41,755-row invariants + back-test honesty), `test_evaluate.py` (every scoring rule, baseline score regression guard) | threshold/LLM untestable |
| **Customer experience** (understand at once, easy approve) | `test_loop_e2e.py` message assertions (reason, suggestion, 3 buttons, fi/sv/nb) | UI untested – doesn't exist; usability needs human review |
| **Reliability** (customer last word, wrong suggestions prevented) | `LoopBranches` (reject/no-response write nothing; wrong state never accepted), `test_mock_api.py` (validator), `test_yext_client.py` failure modes | opt-out, approval-gate property, idempotent double-click not implementable yet |
| **Extensibility** (other use cases) | not testable by behaviour; engine/`TXT`/client are cleanly separable (review item) | — |
| **Learning** (edits/declines improve next suggestion; standing permission) | `test_pending_features.py` stubs | pilot log unused |

---

## 3. Test plan & implementation

Run: see `tests/README.md`. Result in this environment: **192 Python tests (165 run incl. 4 expected-failures = documented gaps; 27 skipped) + 16 JS tests (8 pass, 4 `todo` gaps, 4 `@integration` skipped)**; ~30 s. Sanity-checked by mutation: 7 deliberate bugs injected into a scratch copy of the app code were each caught.

### 3.1 Happy path
| ID | Test (file) | Preconditions | Steps | Expected |
|---|---|---|---|---|
| H1 | `QuickstartLoop.test_happy_path_aurora_christmas_eve_all_five_steps` | fresh mock | run loop FI-D0001 / 2026-12-24 | DETECT shows 07:30-18:00 + last year 07:30-13:00; SUGGEST 07:30-13:00; CONTACT text; DECIDE ACCEPTED; APPLY writes exactly that `holidayHours`; confirmation lists Google ~2 min |
| H2 | `…contact_message_finnish…`, `…swedish_and_norwegian` | – | render messages | greeting, reason, "Google shows now", suggestion, `[Hyväksy][Muokkaa][Ei kiitos]` / sv / nb equivalents, local date style |
| H3 | `DemoStorylines.*` | `Baseline(2026)` | explain demo businesses | Aurora→LAST_YEAR; tenant→SHOPPING_CENTRE; FI-D0011→FLAG only; FI-D0013→silent; FI-D0017 (no history)→PEERS only |
| H4 | `LoopBranches.test_approve_*`, `test_edit_*` | forced decision via scanned `messageId` | approve / edit then APPLY | approve writes the suggestion; edit writes the customer's hours, not the suggestion |
| H5 | `ApplyWritePath.*`, `AgainstMock.test_set_holiday_hours_*` | mock | PUT / `set_holiday_hours` | persists, weekday hours kept, date replaced not duplicated, sorted, idempotent; `expectedLiveBy` appears |
| H6 | `Invariants.*` (41,755 rows) | – | every target row | action ∈ {SUGGEST, NO_ACTION, FLAG}; every suggestion valid, ≠ shown, has evidence |

### 3.2 Edge cases & failures
| Requirement | Test | What it asserts | Status |
|---|---|---|---|
| **LLM fails / garbage** | `LlmExplanation.*` | fall back to template; LLM text can't change hours | ⏸ skipped – **no LLM in repo** |
| **Confidence below threshold** | `ConfidenceAndGuardrails.test_below_threshold_is_not_sent` | boundary behaviour | ⏸ skipped – no threshold (baseline hard-codes 0.6) |
| **Expired (late answer)** | `SuggestionStateMachine.test_answer_after_the_date_has_passed…`; `Latency.test_long_tail_exists…` (shows >24 h replies happen) | not applied, status `expired` | ⏸ skipped – no expiry |
| **Yext 401** | `FailureModes.test_401_*`, `Auth.test_missing_api_key_is_401`, JS `HTTP 401`; `@integration` invalid key | RuntimeError with status/body; JS reports failure | ✅ (mock cannot reject a *wrong* key → sandbox test) |
| **Yext 404** | `FailureModes.test_404_*`, `AgainstMock.test_unknown_entity_404`, JS | same | ✅ |
| **Yext 429** | `FailureModes.test_429_*`, `test_429_during_apply_leaves_the_write_unconfirmed`, JS | raises; PUT not confirmed | ✅; retry/backoff → `expectedFailure` **(gap)** |
| 5xx / garbage 200 / refused / wrong shape | `FailureModes.*` | which exception types escape | ✅ characterised (RuntimeError vs JSONDecodeError vs URLError vs KeyError) |
| **Customer edits before apply** | `LoopBranches.test_edit_applies_the_customers_hours…`, `test_applying_after_edit_then_a_second_approval_is_idempotent`; `PredictionValidation` for bad edit strings | edited value written | ✅ (edit *validation UI* ⏸) |
| Reject / no reply | `LoopBranches.test_reject…`, `test_no_response…` | zero PUTs, entity unchanged | ✅ |
| Wrong open/closed suggestion | `test_wrong_state_suggestion_is_never_silently_accepted`, `Simulator…wrong_open_closed_state` | never ACCEPTED | ✅ |
| Closed-for-good / already-correct | `QuickstartLoop.test_closed_for_good…`, `…already_correct…` | no message, no write | ✅ |
| Invalid hours at APPLY | `ApplyWritePath.test_invalid_hours…`, `AgainstMock.test_server_side_rejection…` | 400/2201, nothing persisted | ✅ |
| Opt-out | `Invariants.test_known_gap_opted_out…` | no suggestion for opted-out | ❌ `expectedFailure` (28 rows violate) |
| Concurrent writers | `FailureModes.test_apply_is_not_atomic…`, `ApplyWritePath.test_parallel_puts_all_succeed` | documents no ETag; no lost log entries | ✅ characterised |

### 3.3 Mock vs integration
* **Unit / e2e (default):** everything uses the in-process mock (`tests/py/helpers.py::MockApi`, temp state file – `mock_api/state.json` is never touched) or a scripted `StubServer` (for 429/5xx/garbage), or a Node stub server. **No test contacts the internet.** The JS script is run in a temp cwd so `.env` (real key) cannot leak into tests.
* **`@integration`** (`tests/py/test_integration_sandbox.py`, `tests/js/sandbox.integration.test.js`): real `https://sbx-api.yextapis.com`, `me`, `v=20261106`. Skipped unless `RUN_INTEGRATION=1`; Python tests carry `pytest.mark.integration` (`pytest -m "not integration"` for CI). Write tests additionally need `YEXT_ALLOW_WRITE=1`, touch a single date (`YEXT_TEST_DATE`, default 2027-12-24) and restore the original `holidayHours`. Contents: GET 200 + name, 404 unknown id, 401/403 bad key, 4xx without `v`, write → read-back → replace → restore, 4xx on invalid hours.
  *These could not be executed here (no network/credentials). Their logic was dry-run against the mock (5/6 pass; the 6th – "bad key → 401" – fails on the mock by design because the mock accepts any key).*

---

## 4. Open questions & gaps

### 4.1 Questions for you (code vs. PDFs / task description)
1. **Where is the real application?** The brief/task describes an LLM step, a `pending/approved/edited/rejected/expired` state machine, a confidence threshold, an HTML customer page and "JS Yext API scripts". None exist on `fonecta`/`main`. Is there another branch/repo, or is the team about to build them? I'd then add real tests instead of the skipped stubs.
2. **State vocabulary:** simulator/pilot log use `ACCEPTED/EDITED/REJECTED/NO_RESPONSE`; you specified `approved/edited/rejected/expired/pending`. Is `NO_RESPONSE` ⇒ `expired`? What is the expiry rule (N hours after send? the day *before* the special day? after the date?)?
3. **Confidence threshold:** value, and what happens below it (stay quiet vs. ask vs. `FLAG`)? The brief says "send only when confident; otherwise ask, or stay quiet".
4. **LLM role:** wording only, or also choosing hours? Which provider/model, languages, and what is the fallback?
5. **Meeting notes (`first day-1.pdf`)** were not in the ZIP – please attach; I can't check them against the code.
6. **Contradiction to confirm:** START_HERE says "the demo should respect opt-outs and standing permissions", yet baseline/quickstart ignore both (28 suggestions for 6 opted-out businesses). Intended to live in the contact layer you will build?

### 4.2 Defects / risks found (tests pin them)
| # | Finding | Evidence | Test |
|---|---|---|---|
| D1 | **CI cannot fail**: JS script swallows errors, exit code 0 → green workflow even on 401/404/429 | `backend_connection_test.js` catch block | JS `todo` |
| D2 | `YEXT_BASE_URL` convention clash: JS needs a **trailing slash** (`${baseUrl}v2/…`), Python/START_HERE use **none** | `.env` has slash; brief/START_HERE don't | JS `todo` |
| D3 | A garbage 200 prints "✅ Success!" **and** "❌ Connection failed" | success logged before `.response.name` is read | JS `todo` |
| D4 | No timeout in the JS axios call | script | JS `todo` |
| D5 | Python client: no retry/backoff on 429/5xx; failures surface as 4 different exception types | `_req` | `FailureModes` |
| D6 | APPLY is read-modify-write without version check → concurrent edits overwritten | `set_holiday_hours` | `test_apply_is_not_atomic…` |
| D7 | Opt-outs ignored by baseline (28 rows) | `customer_contacts.csv` | `expectedFailure` |
| D8 | `is_valid_hours(' CLOSED ')` is `False` although the regex normalises case/space | `hours.py` | `expectedFailure` |
| D9 | `'10:00-10:00'` valid for the simulator, invalid for PUT validator (inconsistent) | `hours.py` vs `server.py` | `test_start_equals_end…` |
| D10 | Scorer: `SUGGEST` with blank hours silently becomes "closed" | `norm('')` | `expectedFailure` |
| D11 | Mock accepts **any** non-empty `api_key`; mock has **no 429/5xx** → those paths only testable with stubs / sandbox | `_auth` | `test_mock_does_not_validate_key_value` |
| D12 | Default `v` differs: Python client `20261101`, JS `20261106`, brief example `20261106` | code | – (config) |
| D13 | `README.md` documents an unrelated project (Näkyvyystesti); `package.json` has no test script except the live connection check | repo | – |
| D14 | **Secrets:** the ZIP contains a populated `.env` (32-char key). It is git-ignored/untracked, but if this ZIP was shared, treat the key as exposed and rotate it | `.env` | – |
| D15 | `datetime.utcnow()` deprecated (Py 3.12); unclosed files in loaders (noise only) | server/baseline | – |

### 4.3 Assumptions I made
* "Pytest" = pytest-compatible: tests are `unittest.TestCase` classes (stdlib) so they run under both `pytest` and `python -m unittest`. **pytest itself was not installable in the sandbox, so I executed them with `unittest`;** `pytest.ini`/`conftest.py` (marker registration) are therefore unexecuted.
* "Jest/Mocha" → Node's built-in `node:test` (Node ≥ 20 per `.nvmrc`) to avoid new dependencies; `package.json` is untouched. Suggested scripts: `"test:unit": "node --test tests/js/*.test.js"`, `"test:integration": "RUN_INTEGRATION=1 node --test tests/js/sandbox.integration.test.js"`.
* Deterministic outcomes (e.g. Aurora 24 Dec → ACCEPTED) depend on the simulator's seeded hash and the current dataset; they'll change if data/seeds change.
* No application code was modified. Running the suite creates no files in the repo (state goes to a temp dir).

### 4.4 Not testable without more information
LLM prompts/fallbacks · confidence threshold · expiry · state transitions & double-click safety · tokenised no-login links · HTML UI behaviour/accessibility/mobile · message delivery & channel fallback · standing-permission flow · learning from edits/declines · visibility-weighted prioritisation · real sandbox behaviour (rate limits, whether `holidayHours`-only PUT is accepted, `v=` error codes, propagation timing) · the hidden test split / organisers' score.
