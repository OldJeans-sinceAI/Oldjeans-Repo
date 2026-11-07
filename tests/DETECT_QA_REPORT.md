# Detect-step QA report – "Connect Suggests – Customer Approves"

Scope: repo ZIP as delivered (branch `fonecta`) vs `Detect_Design_EN.pdf` (pre-implementation review, 2026-11-07).
Rules followed: **no application code was changed**; only tests, fixtures and this report were added.

> **Headline.** The repo has **no Detect layer**. Everything the PDF describes as B, C, E, F/G/H, I and J is absent as code.
> What exists is `examples/baseline.py`: one function, `Baseline.explain()`, that does a rule-based *detect + suggest in one step*
> and returns `(action, hours, basis, evidence)`. That also **violates the PDF's key separation** ("Detect does not choose the
> final proposed hours; Suggest does"). Detect-specific tests are therefore written as a **contract**: they skip until a Detect
> module exists, and were proven correct against a clearly-labelled test double (see §6).

---

## 1. Architecture: files → A–J

| PDF step | What the PDF requires | Where in repo | Status |
|---|---|---|---|
| **A** Source data collected/changed | Trigger a refresh when data changes | nowhere (`Baseline.__init__` re-reads every file on each construction; mock API has no change events) | ❌ |
| **B** Refresh business profile | Coverage · freshness · links · conflicts per business | nowhere. Closest: `Baseline.__init__` builds `closed_signal` (reviews/suggestions) and `dates_by_key` | ❌ |
| **C** Pre-classify strong/partial/limited | Classify by coverage, freshness, consistency | nowhere. The words strong/partial/limited do not appear in any code file | ❌ |
| **D** Select business–date cases | Calendar + events + school breaks | **External**: `evaluation/targets_2026.csv` (calendar only). `baseline.py main()` loops over it. Events/school breaks not used | ⚠️ calendar only |
| **E** Check profile vs target date | Route to F/G/H | nowhere. `explain()` runs one fixed priority chain: closed-signals → centre → last year → peers | ❌ |
| **F** Fast path | Compare displayed state with direct evidence | partly: the "last year" branch of `explain()` (`entry()`, `displayed()`) | ⚠️ |
| **G** Supplement path | Check only missing info (other holidays, centre) | partly: centre branch. "Other own holidays" transfer: absent | ⚠️ |
| **H** Indirect path | Centre · peers · events | partly: centre + peer branch (`peer_benchmarks.csv`). Events: absent | ⚠️ |
| **I** Consolidate finding | 5 finding types, evidence roles, impact priority | nowhere. `explain()` emits `SUGGEST / NO_ACTION / FLAG` | ❌ |
| **J** Pass on finding + evidence | 8-part handoff payload | nowhere. A 4-tuple is returned; `quickstart.py` prints it | ❌ |

### Data files (all present; shapes verified by `test_detect_architecture.py`)

| File | Present | Read by engine? | PDF use |
|---|---|---|---|
| `calendar_special_days.csv` | ✅ | ✅ (`dates_by_key`) | D: dates, `day_key`, `day_class` |
| `entities.json` | ✅ 3,032 | ✅ | E/F/G/H: displayed state, centre link, segment |
| `regular_hours_history.jsonl` | ✅ | ✅ (`regular()`) | B/F: schedule versions |
| `holiday_hours_history.jsonl` | ✅ ~58k rows, none after the 2026-11-06 cutoff | ✅ (`entry()`) | F: matching-holiday history |
| `pilot_decision_log_2025.csv` | ✅ | ❌ **never read** | F: owner-confirmed final hours = *direct* evidence |
| `peer_benchmarks.csv` | ✅ | ✅ | G/H |
| `analytics_daily.parquet` | ✅ (valid parquet) | ❌ **never read** | I: impact/priority |
| `reviews.json` | ✅ 59,856 | ⚠️ only keyword "closed for good" | I: counter/warning evidence |
| also: `local_events.json`, `school_breaks.csv`, `weather_*.csv` | ✅ | ❌ never read | D/G/H contextual |
| also: `publisher_suggestions.json` | ✅ | ⚠️ only `fieldName=="closed"` | counter/warning |

Data notes: history uses two `day_key`s with **no calendar row** (`EVENT` 194 rows, `SCHOOL_BREAK` 58) – step D must derive those
cases from events/school breaks, not the calendar. No history entry post-dates the cutoff (good).

### Routing paths today

| Path | In code? | Notes |
|---|---|---|
| **F Strong / fast** | ⚠️ implicit | "last year's exception" branch; no profile decides it, no applicability recheck |
| **G Partial / supplement** | ❌ | no "only check what is missing" logic; no cross-day inference marked as inference |
| **H Limited / indirect** | ⚠️ implicit | centre + peers are tried in a fixed order for *everyone*, not as a route chosen for limited-evidence businesses |
| **F → G on conflict** | ❌ | a closure mention short-circuits to `FLAG` (and stops); other conflicts are never detected |

### Separation of concerns at handoff (J)

**FAIL.** `Baseline.explain()` returns the proposed hours (`"07:30-13:00"` for Aurora) from the same call that detects the issue;
`quickstart.py` and `baseline.main()` pass it straight on (`confidence` is a constant `0.6`). Detect and Suggest are one function.
Pinned by `test_G5_detect_output_does_not_contain_proposed_hours` (expectedFailure).

---

## 2. Feature inventory – Detect step (from the PDF)

| # | Feature (PDF page) | Status |
|---|---|---|
| B1 | Per-business profile: own-holiday coverage (day_keys, range, latest entry), owner confirmations, regular-hours availability, centre link + historical match rate + comparable-date count, location/segment groups, review/publisher mentions, analytics summary (p.2) | ❌ |
| B2 | Refresh only when source data changes, then reuse; reproducible findings (p.2, p.7) | ❌ |
| C1 | Classify strong / partial / limited by *applicable coverage, freshness, consistency* – not raw volume (p.2) | ❌ |
| D1 | Select business–date cases from calendar (+ events, school breaks) | ⚠️ calendar via targets file |
| E1 | Re-check applicability to the target date; strong→F, partial→G, limited→H | ❌ |
| E2 | F→G when date-specific evidence is missing or conflicting | ❌ |
| F1 | Reconstruct displayed state: dated exception else regular hours; permanent closure ≠ closed day (p.3) | ⚠️ from history, not `entities.json` (17/41,755 rows differ, G11) |
| F2 | Compare with own matching-holiday history | ✅ (inside `explain()`) |
| F3 | Owner confirmation (ACCEPTED/EDITED `final_hours`) as direct evidence | ❌ |
| G1 | Other-holiday own pattern, marked as inference | ❌ |
| G2/H1 | Centre hours with agreement + sample count | ⚠️ centre hours yes, agreement/count no |
| H2 | Peer benchmark by country/tier/segment/day_key, entry-bias aware | ✅ (≥70 % closed, ≥15 % entered) |
| H3 | Nearby businesses, events, school breaks, weather | ❌ |
| I1 | Evidence roles: Direct / Supplementary / Contextual / Counter-warning / Impact | ❌ (single basis string) |
| I2 | Five finding types → routes (Suggest review / opportunity / Retain / Defer / Staff review) | ❌ (`SUGGEST/NO_ACTION/FLAG`) |
| I3 | Impact (search volume, attendance, time to date) sets *priority*, not certainty | ❌ |
| I4 | Dedupe revisions; latest valid revision; honour cutoff | ⚠️ cutoff + latest entry yes; dedupe across sources no |
| J1 | 8-part handoff (identity, trigger, displayed state, finding, support/counter-evidence, uncertainty, route+priority, recheck triggers) | ❌ |
| J2 | No final hours in handoff | ❌ violated |

---

## 3. Tests added (all under `tests/`)

| File | Tests | Runs today? |
|---|---|---|
| `py/test_detect_architecture.py` | 29: data-file shapes, Aurora precondition in real data, 12 gap tests (G1–G11), 2 regression guards (no eval-answer leakage; cutoff honoured) | ✅ 16 pass · 12 xfail (gaps) · 1 skip (parquet columns need pandas/pyarrow) |
| `py/test_detect_contract.py` | 25: golden path (in-memory **and** real data), routing F/G/H + fallback, synthesis I, handoff J | ⏭ skips with gap message until `detect` exists; **25/25 pass** with `DETECT_IMPL=reference` |
| `py/test_apply_sandbox_strict.py` | 24: A/B call shape (read-only), Apply strict-schema, PUT payload on the wire, `listings.json` confirmation, 3 `@integration` | ✅ 21 pass · 3 `@integration` skipped |
| `js/apply_schema.integration.test.js` | 2 `@integration` live read-only checks | ⏭ needs `RUN_INTEGRATION=1` + creds |
| helpers: `detect_fixtures.py`, `detect_adapter.py`, `reference_detect.py` | – | – |

Full suite now: **198 passed, 47 skipped, 16 xfailed** (was 161 / 21 / 4). With the reference double: 223 passed, 22 skipped.

**Mutation check** (each break must be caught): contract tests killed 7/7 mutants (leaked proposal, no F→G fallback,
insufficient→staff_review, ignored cutoff, limited→G, conflict ignored, no revision dedupe); Apply tests killed 4/4
(extra PUT field, dropped `reopenDate`, new `hours` key, account ≠ `me`).

Golden path, Kahvila Aurora (`FI-D0001`, 2026-12-24): displayed 07:30–18:00 (regular, no exception) · own history
2025-12-24 07:30–13:00 entered 2025-12-21T20:00 → expects finding *Possible error/omission*, route *Suggest review*, path F,
evidence strength strong, and **no proposed-hours key** anywhere in the payload.

### Run
```bash
python -W ignore -m pytest -q -m "not integration"                       # everything offline
python -W ignore -m pytest -rs tests/py/test_detect_contract.py          # shows GAP G1 skip reason
DETECT_IMPL=reference python -W ignore -m pytest tests/py/test_detect_contract.py   # proves the tests work
python -W ignore -m pytest -rx tests/py/test_detect_architecture.py      # lists every known gap
node --test tests/js/*.test.js
set -a; source .env; set +a; RUN_INTEGRATION=1 python -m pytest -m integration     # live sandbox (read-only)
YEXT_ALLOW_WRITE=1 RUN_INTEGRATION=1 python -m pytest -m integration              # + one-date write, restored
```
JS note: the repo's JS tests use Node's built-in runner (no Jest installed, and package installs are blocked in this environment),
so the new JS file matches that convention. Say if you want a Jest port.

---

## 4. Critical gaps for you to fix

| ID | Severity | Gap | Pinned by |
|---|---|---|---|
| **G1** | 🔴 Critical | No profile refresh (B) / pre-classification (C): strong/partial/limited does not exist | `G1`, `G1b`, contract skips |
| **G2** | 🔴 Critical | No routing E → F / G / H, no F→G fallback | `G2` |
| **G5** | 🔴 Critical | **Detect returns the proposed hours** – Detect/Suggest not separated | `G5` |
| **G3** | 🔴 Critical | No synthesis I (5 finding types, roles, routes) | `G3` |
| **G4** | 🔴 Critical | No handoff J payload | `G4` |
| G6 | 🟠 High | analytics, pilot log, events, school breaks, weather never read | `G6` |
| G7 | 🟠 High | Owner confirmations (pilot log `final_hours`) not used as direct evidence | `G7` |
| G8 | 🟠 High | Evidence has no provenance (source, applicable date, entry time, record ref) | `G8` |
| G9 | 🟠 High | Closure signal = hard `FLAG` + stop, not a counter-warning routed as "material conflict → staff review" | `G9` |
| G10 | 🟡 Medium | No data-change refresh trigger (A) | `G10` |
| G11 | 🟡 Medium | Displayed state from history ≠ `entities.json` for 17/41,755 target rows | `G11` |
| – | 🟡 Medium | `confidence` is constant 0.6, nothing consumes it (inherited from the earlier QA report) | `tests/QA_REPORT.md` |

⚠️ **Security:** the ZIP contains a populated `.env` (sandbox API key). It is git-ignored, but don't share the ZIP outside the team and rotate the key if it ever left it.

---

## 5. Interface contract the tests expect (add as `examples/detect.py`)

```python
build_profile(tables, entity_id, cutoff: date) -> dict              # B–C; must contain "path": "strong"|"partial"|"limited"
run_case(tables, entity_id, target_date: date, cutoff: date,
         trigger: dict | None = None) -> dict                       # D–J, the handoff
```
`tables` = dict of in-memory rows shaped like the data files (`entities`, `regular_history`, `holiday_history`, `pilot_log`,
`calendar`, `peers`, `reviews`, `suggestions`, `events`, `analytics`) – see `tests/py/detect_fixtures.py`. If your loaders differ,
adapt `detect_adapter.py`, not the assertions.

Handoff keys: `case_identity{business_id,target_date,information_cutoff}`, `trigger{type,day_key}`,
`displayed_state{hours,source,regular_schedule_version,exception_version}`, `finding{type,tags,summary}`,
`evidence[{role,kind,source,content,applicable_date,entered_at,ref,is_inference}]` with
`role ∈ {direct,supplementary,contextual,counter_warning}`, `uncertainty{evidence_strength,missing}`,
`route ∈ {suggest_review,retain,defer,staff_review}`, `priority`, `recheck_triggers[]`, `path{profile,trace}` (trace e.g. `["F","G"]`).
Finding types: `possible_error_omission`, `new_trading_opportunity`, `state_aligned`, `insufficient_evidence`, `material_conflict`.
Forbidden anywhere in the payload: `proposed_hours`, `suggested_hours`, `final_hours`, `proposal`, `suggestion`, `new_hours`, `recommended_hours`.

---

## 6. About `reference_detect.py` (test double)

~200 lines in `tests/py/`, clearly marked "TEST DOUBLE – not application code". It exists only to show the contract tests are
executable and can fail. It is **not** a proposed design: its thresholds (≥4 holiday day_keys = strong; peers ≥30 samples/≥70 % closed;
centre ≥3 comparable dates/≥70 % agreement) are placeholders and the tests never probe boundaries. Informational run on the real
data with those placeholders: 2,729 strong · 241 partial · 62 limited; Aurora → F → *possible error* → Suggest review; `FI-D0011`
(closed for good) → F→G → *material conflict* → Staff review.

---

## 7. Questions where the PDF is ambiguous or the code contradicts it

1. **Partial vs limited.** PDF: partial = "direct evidence has gaps, supplementary exists"; limited = "own history absent *or not applicable to this date*". Is a business with rich history for other holidays but none for this `day_key` *partial* (profile level) or *strong, then moved F→G* (case level)? Tests accept either profile but require the route to end in G.
2. **Where does `FLAG` belong?** Closure mentions are *counter/warning* evidence (→ material conflict → staff review) in the PDF, but `Baseline` treats them as a terminal action before any other evidence is looked at. Should a closed-for-good signal still show the other evidence in the handoff?
3. **Owner confirmation scope.** A 2025 ACCEPTED/EDITED value for XMAS_EVE – direct evidence for 2026-12-24, or only for its own date with "later revisions" checked? Tests treat it as direct for the same `day_key`.
4. **Displayed state source.** PDF p.3 says reconstruct from `entities.json`; the code uses history `< snapshot`. Which is authoritative where they differ (G11, e.g. FI-00330)?
5. **Case selection (D).** `EVENT`/`SCHOOL_BREAK` cases have no calendar rows; should Detect generate them itself, or will `targets_2026.csv` keep supplying them?
6. **Should Detect pass historical hours as evidence only?** Tests assume yes (content allowed inside `evidence`, never as a `proposed_*` field).
