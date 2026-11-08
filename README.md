# Connect Suggests — Nordic opening-hours suggestions

Built by **OldJeans** for the **Since AI 2026 × Fonecta** challenge.

**All data is synthetic. No real businesses, customers or Fonecta data.**

Wrong holiday hours turn an online search into a closed door, and they quietly cost
visibility: a listing with missing or outdated hours can drop out of "open now"
searches exactly when holiday demand peaks. Connect Suggests is a reference product
that detects likely wrong hours for Nordic businesses, proposes a correction backed
by evidence, asks the owner to decide without any login, and — only on an explicit
decision — writes the approved hours through the Yext API and reads them back to
confirm. Correct listings stay quiet; uncertainty and genuine conflicts are handled
differently.

```mermaid
flowchart LR
  A[Detect: listing vs evidence] --> B[Suggest: validated candidate + sources]
  B --> C[Contact: templated message, preferred channel]
  C --> D[Decide: owner approves / edits / declines, no login]
  D --> E[Apply and confirm: Yext write, independent read-back]
```

## Run it

Verified on **Python 3.10 in Ubuntu/WSL**. The runtime lock uses
`fcntl`, so **native Windows Python is not supported** — use WSL there. macOS has not
been verified. The basic mock
demo needs **no API keys and no Node.js**.

```sh
git clone https://github.com/OldJeans-sinceAI/Oldjeans-Repo.git
cd Oldjeans-Repo
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_demo.py --presentation --mode mock --port 8000 --mock-port 8787
```

Use `run_demo.py` (it starts the site plus an isolated local Yext mock); do not start
the server with `python -m app.server`. Open **http://localhost:8000** on the machine
running the app and stop with Ctrl+C. The demo clock is frozen at **6 Nov 2026** and
the storylines target **24 Dec 2026** (Christmas Eve). The app binds to loopback only,
so over SSH forward port 8000 to your own machine first. Optional settings can be
copied from `.env.example` to `.env`; the supplied dataset stays unchanged and working
state is written under the ignored `runtime/` directory. Proposals, decisions, and
contact preferences belong to that application state: no custom Yext Knowledge Graph
fields or new publishers are added.

**Guided presentation with interactive decisions.** The default page is an
English-only rehearsal with three businesses in a fixed channel order: WhatsApp,
email, then SMS. Press **Next** to prepare the real 3,032-entity scan and wait for it
to finish before recording. Next guides you through Detect, Suggest and Contact.

At **Decide**, use the customer screen yourself; there is no Next button to make a
decision for you. WhatsApp supports Approve hours, Edit hours (preview, then confirm)
and Keep current hours. In email or SMS, reply `YES`, `NO`, or exact hours such as
`11:00-16:00`, review the preview, then reply `CONFIRM`. `CANCEL` discards a preview.
You can choose any outcome for each business. Once processed, the actual decision
opens **Apply & confirm** automatically. Next then takes you to the next business;
you never need to try every outcome on a single proposal. The final summary reflects
your choices. Reloading an undecided screen does not approve or replay any reply;
unsent text and unconfirmed previews must be entered again.

**Back to Detect** returns to the existing scan without resetting any saved
decisions or sending a message. At Detect, select one of the three prepared
businesses and press Next; a completed business opens its saved result. Next then
visits the remaining businesses. **Restart demo · resets data** is separate and
asks before clearing the rehearsal. Unconfirmed drafts are discarded when leaving
the customer screen. Navigation waits for any reply or decision already in flight.

Only step 4 embeds the phone/monitor customer views. Other steps remain in the
same Next-button presentation. For other businesses, dates and staff-review tests,
open **More tests · advanced workspace** at Detect; this is the manual workspace,
not another required part of the presentation.

Contact is simulated. Decisions and read-back use the real application APIs against
the local Yext mock. Failed or unverified updates never display a successful result.

**Restart demo** resets only `runtime/presentation/`. The ordinary `runtime/` state
and optional `runtime/sandbox/` state are kept separate. Gemini is disabled for this
rehearsal, even when a key is configured. **Explore workspace** opens the interactive
UI using the same presentation data. To use the ordinary workspace and optional
Gemini instead, stop the server and run the command without `--presentation`.

**Optional Gemini (owner-reply interpretation).** Set `GEMINI_API_KEY` privately in
`.env` and keep `GEMINI_ENABLED=true`; the key stays server-side and is never sent to
the browser. The tested default model is `gemini-3.5-flash-lite`. Without a key the
demo still runs — buttons, yes/no and exact intervals use local rules, and complex
free text asks uses pattern matching.

**Local Gemma setup (owner-reply interpretation).** Owner replies that are not an exact button, yes/no or hours interval are interpreted by a Gemma 2 2B model that runs on your own machine. It needs no API key and no network access. If the model file is missing or fails to load, the app falls back to Gemini (when `GEMINI_API_KEY` is set) and then to the local rules, so nothing breaks without it. Any model failure, such as a timeout, malformed output or a missing model, returns `UNAVAILABLE` and never produces a decision.

First install the runtime inside the project's virtual environment. This compiles llama.cpp, which takes a few minutes. If the build fails, run `sudo apt install build-essential cmake` and retry.

```bash
cd ~/Programs/Oldjeans-Repo
source .venv/bin/activate
pip install llama-cpp-python
python -c "import llama_cpp; print(llama_cpp.__version__)"   # should print a version
```

Next download the model into `runtime/models/`. The command below fetches the stock instruction-tuned Gemma 2 2B (Q4_K_M, about 1.6 GB), which works as a baseline. Replace it with the fine-tuned GGUF when you have one (see "Fine-tuning" below). Check the size afterwards, because a file of a few KB means the download failed.

```bash
mkdir -p runtime/models
curl -L -o runtime/models/gemma-2-2b-reply.gguf \
  https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf
ls -lh runtime/models/
```

The app uses the model automatically when the file exists. Settings go in `.env` and are all optional: `GEMMA_MODEL_PATH` (default `runtime/models/gemma-2-2b-reply.gguf`), `GEMMA_TIMEOUT` in seconds (default `4`; raise it, for example to `10`, on a slow CPU), and `GEMMA_ENABLED=false` to turn Gemma off. Confirm the app picked it up. The health output should show `"provider": "LOCAL_GEMMA"`, and `GEMINI` or `RULES` instead means the file was not found or failed to load.

```bash
python -c "from app.replies import OwnerReplies; print(OwnerReplies().health())"
```

To try one reply by hand, run the engine directly. Replies such as "yes", "no" or "09:00-16:00" never reach the model, because the app's rules handle them first, so test with a sentence like the one below. The expected result is `intent='EDIT'` with `hours='07:30-15:00'`.

```bash
python - <<'EOF'
from app.teammate.local_engine import LocalGemmaEngine
e = LocalGemmaEngine("runtime/models/gemma-2-2b-reply.gguf")
ctx = {"change": {"kind": "DATE_HOURS", "date": "2026-12-24", "hours": "07:30-13:00"},
       "timezone": "Europe/Helsinki", "current_value": None}
print(e.configured, e.interpret(ctx, "Please close at 15:00 instead"))
EOF
```

**Measuring accuracy.** The evaluation harness runs labelled replies (accept, reject, edit) through the model and reports overall accuracy, accuracy per category and language, a confusion matrix, latency and every failure. A reply counts as correct only if the app would produce the right ready-to-confirm draft, so a hedged answer or the wrong hours is a failure. To build a large dataset, give `docs/reply_dataset_prompt.md` to another LLM, concatenate its outputs into `data.jsonl` and run the commands below. The sample file checks that everything works, and `--min-accuracy` makes the command exit with an error if accuracy is below the threshold. The unit test version is `GEMMA_EVAL_DATASET=data.jsonl python -m unittest test_gemma_accuracy`, run with `PYTHONPATH=tests/product:.`. It also fails if any reject or edit reply is ever classified as an approval.

```bash
python tools/eval_gemma_replies.py tests/data/reply_eval_sample.jsonl
python tools/eval_gemma_replies.py data.jsonl --min-accuracy 0.9 --report report.json
```

**Fine-tuning (only if accuracy is too low).** Generate synthetic training data, then train on a machine with a GPU, for example a free Google Colab T4. Training needs `unsloth`, `trl` and `datasets`, which the app itself does not need. The training script exports a Q4_K_M GGUF into `gemma-replies-q4/`. Copy that file over `runtime/models/gemma-2-2b-reply.gguf` and rerun the evaluation to compare. The generator's templates are small, so add more phrasings before training.

```bash
python tools/make_reply_dataset.py train.jsonl 1500
python tools/train_gemma_replies.py train.jsonl
```

**Tests that need no model.** These use a fake model and check the engine, the wiring and the harness. One real-model test is skipped until a dataset and model exist.

```bash
PYTHONPATH=tests/product:. python -m unittest test_local_engine test_replies test_gemma_accuracy -v
```

**Optional real Yext sandbox (`--with-sandbox`).** Writing to the team's real Yext
workspace is opt-in and requires mock mode plus configured credentials
(`YEXT_API_KEY`, `YEXT_ENTITY_ID`). It adds a `/sandbox/` workspace that targets a
single shared entity and still requires explicit owner approval before any write. The
bundled reset baseline is verified only for that one entity's `hours`; it is not a
general production reset. Never commit keys.

With those credentials configured, run:

```sh
.venv/bin/python run_demo.py --presentation --mode mock --with-sandbox
```

This keeps the guided mock presentation at `/` and the manual real-Yext workspace
at `/sandbox/`. **Test real Yext apply** in the presentation header and result page
opens the sandbox in a separate tab, preserving the current rehearsal. The sandbox
shows the actual target, an explicit owner approval, and independent read-back;
its return link leads back to the demo. The presentation never approves a sandbox
update. Without a configured sandbox, the demo explains this and shows no live-test
link.

## Build status (scope of this document)

This branch includes the Next-button presentation, the interactive guided journey,
the operator workspace, a WhatsApp phone, an SMS phone and an email desktop mailbox.
WhatsApp uses message buttons. Email and SMS use replies plus a confirmation preview;
they do not pretend to support embedded decision buttons.

The integration passed **109 product tests** on **8 Nov 2026**. Browser checks exercise
the actual 3,032-entity scan, approve/edit/decline, independent mock read-back, reload,
repeat rehearsals and unavailable-backend handling. Tests use isolated mock state;
they do not send real messages or repeat the live sandbox write. The browser scripts
are in `tests/browser/`; Playwright and its Chromium browser are development-only
requirements, not needed to run the site.

## The five steps

1. **Detect** — scan the fleet and compare each listing with dated evidence; classify
   SUGGEST / NO_ACTION / FLAG. No messages or decisions are created here.
2. **Suggest** — select and validate a candidate from ordered evidence, explain the
   sources, and choose whether to propose, flag for staff, or stay silent.
3. **Contact** — build an English message for the owner's preferred channel,
   respecting opt-outs, pauses, and contact cadence. Delivery is always **simulated**.
4. **Decide** — the owner approves, edits, or declines from a capability link, **no
   account creation**. Edited hours and free-text replies are previewed and require
   explicit confirmation before anything is written.
5. **Apply & confirm** — only the approved date/scope is merged into the existing
   hours, then independently read back. Success, pending, failure, and rejection stay
   distinct; publisher timings are estimates, not proof of live publication.

For a manual walkthrough, choose **Explore workspace → Guided demo**, select **2026-12-24**, and click
**Scan all 3032 businesses → Review a suggestion → Prepare the owner message**.
Open the owner view, approve/edit/decline, then return to the guide to inspect the
result. A scan checks the entire directory; each owner decides only their own proposal.
The **Workspace**, **Inbox**, and **Staff review** tabs expose the underlying work.

**Where AI is used.** Detect, Suggest, and Contact are deterministic evidence rules and
templates. A generative model (Gemini, when configured) is used only to interpret a
*complex* natural-language owner reply; exact replies and buttons use a local parser.
The product does **not** claim an AI that invents every schedule or message. Confirmed
owner outcomes are recorded and reused as evidence — this is **history reuse, not model
training**; no trained ranker ships in this branch.

## Data sources that mattered most

| Signal | How we used it | Production counterpart |
|---|---|---|
| Owner holiday-hours history (`holiday_hours_history.jsonl`) | Primary evidence: the owner's own confirmed exceptions for the same holiday seed a proposed time | Connect audit log |
| Calendar of special days (`calendar_special_days.csv`, FI/SE/NO) | Identify which dates need a decision (holidays, eves, observances) | Public-holiday APIs and municipality calendars |
| Shopping-centre schedules + peer benchmarks (`entities.json`, `peer_benchmarks.csv`) | Corroborate proposals where the business has demonstrated centre alignment or sufficient supporting evidence; nearby businesses alone do not determine hours | Centre operators' schedules and anonymised Connect history |
| Publisher suggestions + reviews (`publisher_suggestions.json`, `reviews.json`) | Signals that a listing may be wrong; combined evidence can trigger staff review, never an unapproved write | Yext Publisher Suggestions / Reviews |
| Daily analytics (`analytics_daily.parquet`) | Help prioritise business impact; the evaluator reports at-risk search views protected | Yext Analytics Reports |

## Customer with no history

For **2026-12-24**, a **new customer with no exception history and no previous decisions** —
`FI-D0017` Kahvila Kipinä — does not receive guessed hours. The system returns
an internal NO_ACTION/defer and generates **no customer message**, recording "not
enough evidence to propose exact hours; recheck when relevant owner evidence arrives."
Related cases: `FI-D0011` (possible permanent closure) is **flagged** for staff rather than
suggested, and `FI-D0013` (already-correct hours) is left **retained** in silence.

## Final customer messages (as text)

All delivery is simulated. **English is the demo's supported language** for both UI
and outbound messages. The exact contact-preview text for synthetic business
`FI-D0001` (Kahvila Aurora) is:

```text
Hi Kahvila Aurora!

2026-12-24 (Christmas Eve)
Currently shown: 07:30-18:00.
Your confirmed hours for this holiday in a previous season support these times.
We propose: 07:30-13:00.

Approve / Edit / No thanks
```

The owner view includes this uncertainty statement:

> This evidence does not confirm your final plan for this date. You decide.

Follow-ups are displayed in the owner view; no external follow-up message is sent:

- **Approve:** "Hours saved and checked." followed by "We read the hours back after
  saving to verify the change." This is shown only after the read-back matches.
- **Edit:** enter `07:30-15:00`, preview, and confirm separately. The outcome displays
  the edited date and hours, then the same saved-and-checked confirmation. Without a
  model, exact hours or the manual editor still work.
- **Decline:** "Current hours kept." followed by "No update was requested."

For a successful save, the publisher section says: "These are typical timings from
the mock dataset, not confirmation of live publication."

## Real Yext apply and reset proof

On 7 Nov 2026 an end-to-end live write was verified against a single shared sandbox
entity (`SinceAI18`): owner approval → app decisions API → Yext PUT of one date
(`2026-12-24` → 07:30–13:00) → independent GET read-back, with unrelated hours
preserved. This proves the write path on **one** entity; bulk detection stays on the
**3,032-entity** mock directory (businesses and shopping centres). Reset restores only that entity's `hours` to its verified
pre-change state and stops with a conflict rather than overwriting unexpected external
changes. Publisher timings come from the supplied `listings.json` as **estimates** —
not observation of live propagation at Google or any publisher.

## Scoring and evaluation

```sh
.venv/bin/python -m unittest discover -s tests/product -p 'test_*.py'
.venv/bin/python examples/baseline.py
.venv/bin/python evaluation/evaluate.py --predictions outputs/baseline_predictions_2026.csv
```

An existing saved predictions file (41,755 rows) rescored on the labelled **developer
split** (11,100 rows):

| Set | Score /100 | Exact precision | Recall | Harmful |
|---|---|---|---|---|
| Saved dev predictions | 55.11 | 82.2% | 64% | 382 |
| Supplied baseline (dev) | 54.49 | 90.1% | 59% | 224 |

It protected an estimated **62.7%** of at-risk search views. These are **historical
developer-split** figures — not the organisers' hidden **test** split and not a
re-measurement of the current refactored `main`. Higher recall came with more harmful
suggestions; calibration remains unfinished. Placing `predictions_2026.csv` at the
repository root is optional for the organisers' score (not included here); verify any
file with the official evaluator. To generate this product's optional submission CSV:

```sh
.venv/bin/python -m app.evaluate --output predictions_2026.csv
.venv/bin/python evaluation/evaluate.py --predictions predictions_2026.csv
```

Inference uses the frozen evidence cutoff and does not read the answer labels or
runtime owner decisions. The evaluator reads the labelled dev split separately.

## What we tried that didn't work

- **Slow or failed Gemini replies, including explicit `thinkingLevel` probes.** We
  bound the interpreter to an 8-second budget, use the model default, and
  treat any timeout as "pending" — never as consent or refusal.
- **Auto-resolving ambiguous replies** ("Maybe at five"). These must stay uncommitted
  and ask for exact hours; silence or vagueness is not consent.
- **Treating last season's hours as current fact.** Historical hours are evidence for a
  proposal the owner must confirm, not proof of this year's operation.

## Third-party code, data and licences

Verified versions in the Python 3.10 environment:

| Component | Version | Licence |
|---|---|---|
| python-dotenv | 1.2.1 | BSD-3-Clause |
| jsonschema | 4.25.1 | MIT |
| pandas | 2.3.3 | BSD-3-Clause |
| pyarrow | 22.0.0 | Apache-2.0 |
| numpy | 2.2.6 | BSD-3-Clause |
| playwright | 1.58.0 | Apache-2.0 |

The supplied simulator code is **MIT** and the synthetic data is **CC BY 4.0**
(© 2026 Since AI ry). The reply interpreter and WhatsApp layout incorporate teammate
contributions that carry **no separate licence file** (per `NOTICE`); their source
attribution is preserved and no additional licence or blanket relicensing is asserted.
The listed product dependencies use permissive licences. See [LICENSE.md](LICENSE.md)
and [NOTICE](NOTICE) for the supplied materials and source attribution; these do not
grant a blanket licence to all team additions. The optional Node connection test uses
Axios (MIT), dotenv (BSD-2-Clause), and nodemon (MIT, development tool).

## Optional: Node Yext connection test

Separate from the Python demo (which needs no Node), the repository keeps a teammate
Node.js connection test against a real Yext account. `.nvmrc` selects Node **v20.11.0**.
Configure `YEXT_API_KEY` and `YEXT_ENTITY_ID` privately in `.env`. This older test
expects `YEXT_BASE_URL=https://sbx-api.yextapis.com/` **with the trailing slash**:

```sh
nvm install
nvm use
npm ci
npm run test:yext
```

On success it prints the connected business name. Keys stay out of the repository.

## Roadmap and limitations

- Only opening hours are modelled; the owner simulator is a statistical stand-in, not
  real behaviour, and message delivery is simulated.
- Next: production contact adapters with real operator authentication, live-source
  freshness, and calibrated ranking learned from explicit owner outcomes.
- The bonus "replace a dataset file with a live source" is **not** implemented in this
  branch.
