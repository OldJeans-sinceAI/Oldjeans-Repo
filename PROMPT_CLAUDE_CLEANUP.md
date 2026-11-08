# Master Codebase Optimization & Cleanup Prompt for Claude 3.5 / 5.5 Sonnet

> **Role & Task Description**: Act as a Lead Software Architect and Principal Python/Node Engineer reviewing the **Connect Suggests – Nordic Opening-Hours Simulator** repository (`Oldjeans-Repo`). Perform comprehensive, safe, and verified cleanups, performance optimizations, and checks for obsolete or misaligned repository components without breaking any core domain contracts or acceptance tests.

---

## Repository Architecture Overview & Key Findings

1. **`app/domain.py`** (~61k chars):
   - Pure domain logic for schedule parsing (`HH:MM-HH:MM`), canonical validation (`parse_intervals`, `canonical_hours`, overnight rollovers), evidence aggregation (`DetectContext`), decision engine (`evaluate_context`, `_select_candidate`), natural language reply interpretation (`interpret_reply`), and synthetic data loading (`DataStore`).
   - Note duplication of spatial/Haversine math in `DataStore.add_context()` and `DataStore.neighbour_context()`.
   - Hardcoded timezone offsets (`_WINTER_OFFSETS`) and static evaluation window assumptions.

2. **`app/service.py`** (~64k chars):
   - Business orchestration layer (`Service`), managing thread locking (`self.lock`), JSON state storage (`StateStore`), background scheduled jobs/ticks (`tick()`), proposal/decision lifecycles, and integration with `YextClient` (`examples/yext_client.py`).
   - In-memory lookups for messages, proposals, permissions, and preferences perform linear scans $O(N)$ over `self.store.data` dict values.

3. **`app/server.py`** (~20k chars):
   - Low-level standard library `ThreadingHTTPServer` (`WebServer`) and `BaseHTTPRequestHandler` (`Handler`).
   - Host header loopback checks, CSRF validation via `hmac.compare_digest`, JSON Schema validation (`Draft202012Validator`), and API endpoint routing.

4. **Configuration & Documentation Discrepancies**:
   - `README.md` refers to a "Näkyvyystesti" DDGS search tool and Finnish documentation, whereas `START_HERE.md` and the `app/` codebase implement the "Connect Suggests" Nordic opening-hours simulator.
   - Dependency mix: Node.js 20.11.0 (`package.json`, `.nvmrc`) for JS backend connection test vs Python 3.9+ standard library + `pandas`/`pyarrow`/`jsonschema`/`playwright` (`requirements.txt`).

---

## Targeted Tasks for Claude Sonnet 5.5

### Task 1: Reconcile Obsolete & Misaligned Documentation
- **Issue**: `README.md` describes an unrelated local DDGS search/visibility evaluation script not present in the main simulator backend.
- **Action**: Update `README.md` to cleanly align with `START_HERE.md` and the actual `app/` Python simulator framework. Clearly detail both Python (`requirements.txt`) and Node.js (`package.json`, `.nvmrc`) requirements, environment variable setups (`.env`, `env_mockup`), API server startup commands (`python -m app.server` or `python mock_api/server.py`), and test execution steps (`npm run test:yext`, `python evaluation/evaluate.py`).

---

### Task 2: Domain Logic Optimization (`app/domain.py`)
- **Haversine Math Refactoring**: Extract a unified, module-level helper `haversine_distance_meters(lat1, lon1, lat2, lon2) -> float` to eliminate duplicated math loops inside `DataStore.add_context()` and `DataStore.neighbour_context()`.
- **Memory & Allocation Efficiency**: Audit `copy.deepcopy` calls inside high-frequency context evaluation pathways (`evaluate_context`, `_select_candidate`). Replace unnecessary deep copies of immutable or simple dictionary objects with shallow copies or targeted dict comprehensions.
- **Regex & Interval Parsing Safety**: Verify `parse_intervals()` handles edge cases (e.g., `00:00-23:59`, multi-range splits, overnight spans across midnight) while keeping error raising strictly on `HoursError` (which maps to HTTP 422).

---

### Task 3: State Storage & Service Layer Refactoring (`app/service.py`)
- **In-Memory Indexing**: Optimize lookup methods (`messages()`, `permissions()`, `preferences()`, `cases()`) by adding internal entity-indexed lookup maps (e.g. `self._messages_by_entity`) to avoid repeating $O(N)$ filter iterations on large state stores.
- **Lock Granularity & I/O Isolation**: Ensure file system operations (`self.store.save()`, `DataStore` reloading) and remote HTTP calls via `YextClient` do not block `self.lock` unnecessarily, while retaining strict ACID-like atomic state guarantees.
- **Language & Message Text Formatting**: Standardize multi-language template generation (`_message_text`) across English (`en`), Finnish (`fi`), Swedish (`sv`), Norwegian (`nb`), and Korean (`ko`).

---

### Task 4: HTTP Server & Security Enhancements (`app/server.py`)
- **Unified Security Header Generation**: Consolidate response headers (`Content-Security-Policy`, `X-Content-Type-Options`, `SameSite` cookies) in `Handler.reply()` to reduce duplicate string construction per request.
- **Route Dispatching**: Clean up long regex conditional matches in `dispatch()` into a dispatch table or structured path pattern matcher.
- **Sanitization Check**: Ensure access log output (`log_message`) continues suppressing query parameters, secrets, bearer tokens, and request bodies.

---

## Verification & Acceptance Checklist

- [ ] **Syntax & Compilation**: Python files must compile cleanly with zero errors (`python -m py_compile app/*.py`).
- [ ] **Schema Conformance**: JSON response structures must adhere to `config/openapi.json` schemas.
- [ ] **Contract Preservation**: Preserved HTTP status code mappings (`400`, `401`, `403`, `404`, `409`, `410`, `422`, `503`).
- [ ] **Test Execution**: Ensure tests in `tests/` pass cleanly after refactoring.
