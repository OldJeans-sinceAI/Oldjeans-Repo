# Tests

```
tests/
  backend_connection_test.js   existing live-sandbox smoke check (unchanged)
  py/                          Python tests (unittest.TestCase -> run with pytest OR python -m unittest)
  js/                          Node tests (node:test, no extra dependencies)
  QA_REPORT.md                 architecture, feature inventory, test plan, gaps, open questions
```

## Run (offline, no credentials)
```bash
python -W ignore -m unittest discover -s tests/py -t tests/py     # or: pytest -m "not integration"
node --test tests/js/*.test.js
```
Optional: `pip install pandas pyarrow` enables the analytics-endpoint test.
Tests never write `mock_api/state.json` (the mock runs in-process with a temp state file) and never read `.env`.

## `@integration` (real Yext sandbox) – skipped by default
```bash
set -a; source .env; set +a                        # YEXT_BASE_URL, YEXT_API_KEY, YEXT_ENTITY_ID, YEXT_API_VERSION
RUN_INTEGRATION=1 pytest -m integration            # or python -m unittest tests/py/test_integration_sandbox.py
RUN_INTEGRATION=1 node --test tests/js/sandbox.integration.test.js
YEXT_ALLOW_WRITE=1 RUN_INTEGRATION=1 ...           # also enable the write test (one date, restored afterwards)
```

## Reading the results
* `expectedFailure` (Python) / `todo` (Node) = **known gap**, listed in QA_REPORT §4.2. When the app is fixed the test flips to "unexpected success" – then remove the marker.
* Skipped `test_pending_features.py` = requirement from the brief with no implementation yet; the docstring is the acceptance test.
