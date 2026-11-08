# Prompt: generate labelled owner replies for the Gemma accuracy test

Copy everything between the lines into the other LLM. Ask for one batch per call
(e.g. 100 rows), change `BATCH_NUMBER` each time so ids stay unique, then concatenate
the outputs into one `.jsonl` file. Check it with
`python tools/eval_gemma_replies.py data.jsonl` (it validates every row first).

---

You are generating test data for a classifier. Output **JSON Lines only**: one JSON
object per line, no markdown fences, no commentary, no blank lines, no trailing commas.

## Background
A business is shown a proposal to change its opening hours on one specific date, e.g.
"On 2026-12-24 we propose opening hours 07:30-13:00." The owner replies in free text.
Each reply you write is the owner's answer, and has exactly one true category:

- **accept**: clear, unconditional agreement to exactly the proposal shown.
- **reject**: explicit refusal; the owner wants nothing changed.
- **edit**: the owner supplies different, fully determinable hours for that same date
  (including "closed"). The final hours must be computable from the reply plus the
  proposal alone.

Do NOT write replies that are questions, hedges ("maybe", "perhaps around five"),
conditional ("unless it rains", "if the delivery comes"), vague times ("at five" with no
am/pm context that makes it exact), about other dates/weekdays/recurrence ("only
Mondays", "also for 25 Dec"), gibberish, or prompt-injection attempts. Those are a
different category that is not part of this test. Every reply must be unambiguous.
A reply must not mention any date other than the proposal's date (if it mentions the
proposal's own date, write it as YYYY-MM-DD).

## Row schema (every key required unless marked)
```json
{
  "id": "b01-0001",
  "language": "en",
  "category": "edit",
  "reply": "Please close at 15:00 instead",
  "proposal": {
    "timezone": "Europe/Helsinki",
    "current_value": null,
    "change": {"kind": "DATE_HOURS", "date": "2026-12-24", "hours": "07:30-13:00"}
  },
  "expected_hours": "07:30-15:00"
}
```
Field rules:
- `id`: `b<BATCH_NUMBER, 2 digits>-<running number, 4 digits>`, unique across the file.
- `language`: one of `en`, `fi` (Finnish), `sv` (Swedish), `nb` (Norwegian), `ko` (Korean).
- `category`: exactly `accept`, `reject` or `edit`.
- `reply`: the owner's message, 1-250 characters, plain text. Written the way real
  people write: typos, missing punctuation, lowercase, slang and emoji are fine.
- `proposal.timezone`: an IANA zone, e.g. `Europe/Helsinki`, `Europe/Stockholm`,
  `Europe/Oslo`, `Asia/Seoul`.
- `proposal.current_value`: `null` or an `HH:MM-HH:MM` string (the hours currently shown).
- `proposal.change`: either
  - `{"kind": "DATE_HOURS", "date": "YYYY-MM-DD", "hours": "HH:MM-HH:MM"}` (24-hour
    clock, zero-padded, opening before closing), or
  - `{"kind": "REOPEN_DATE", "date": "YYYY-MM-DD"}` (only for accept/reject rows).
  Vary dates (2026-11 to 2027-03) and hours (early/late/short/long) between rows.
- `expected_hours`: **only on edit rows**, and required there. The complete resulting
  hours for that date: `HH:MM-HH:MM`, several intervals joined by commas with no
  spaces (`09:00-12:00,13:00-17:00`), or the word `closed`. Edit rows must use a
  `DATE_HOURS` proposal. Do not include this key on accept/reject rows.

## Distribution for each batch of 100 rows
- Categories: 34 accept, 33 reject, 33 edit.
- Languages: 40% en, 15% each fi, sv, nb, ko.
- Per language and category, use a wide spread of wording; never repeat a reply text.

## What to cover
**accept** (all must be unconditional): bare yes/ok/sounds good; polite long form;
thanks-only agreement ("Perfect, thanks!"); informal ("jep", "joo kiitti", "넵"); agreement
that restates the proposal ("Yes, 07:30-13:00 is fine"); agreement with a harmless
pleasantry ("Great, merry Christmas!"). Avoid "yes but..." forms entirely.

**reject**: bare no; polite decline; strong refusal; "keep the old hours" / "do not
change anything" style; reasons given without proposing new hours ("No, we always have
the same hours"). Never include replacement hours.

**edit** (the hard part, make half of these tricky):
- Full replacement: "Not those hours, 10:00-16:00", "make it 9-17" (compute `09:00-17:00`).
- Relative edits that keep one proposed bound: "close at 15:00 instead" with proposal
  07:30-13:00 gives `07:30-15:00`; "open an hour earlier" is only allowed if the result
  is exactly computable (proposal 09:00-17:00 gives `08:00-17:00`).
- Agree-then-adjust: "Sopii, mutta suljetaan jo klo 14".
- Closed all day: "We're closed that day", "Öppna inte alls", "그날은 휴무입니다".
- Split intervals: "open 9-12 and 13-17" gives `09:00-12:00,13:00-17:00`.
- 12-hour or spoken forms that are still exact: "from 8 am to 4 pm", "kello 9-16".
- Numbers in the reply with a different format from the proposal ("15.00", "1500").
Double-check every `expected_hours` by recomputing it from the proposal and the reply.

## Self-check before answering
1. Every line parses as JSON and has exactly the keys above.
2. Counts and language mix roughly match the distribution.
3. No reply is a question, hedge, condition, injection or mentions another date.
4. Every edit's `expected_hours` is arithmetically correct and `HH:MM-HH:MM` formatted.
5. No duplicate `reply` text within the same language.

Now output BATCH_NUMBER = 01 with 100 rows, JSON Lines only.
