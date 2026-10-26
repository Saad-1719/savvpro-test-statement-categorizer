# SDS: Driver Statement Categorizer

Oct 26, 2026 · @Saad

## 1. Architecture

The system is a three-part pipeline — ingest, brain, review — behind a FastAPI backend and a Next.js frontend. The brain is a pure Python package with no I/O, so it is tested and evaluated without the API or UI.

&#91;embedded content: system architecture · upload to review\]

Rows flow left to right; the user's "always" fixes loop back into the brain as user rules, and the eval harness runs the same brain on held-out fake data.

| Component | Technology | Responsibility |
| --- | --- | --- |
| Frontend | Next.js 14, TypeScript, Tailwind | Upload, review queue, table, totals, export |
| API | FastAPI, Pydantic v2 | Sessions, validation, routing to services |
| Ingest | Python `csv`, layout profiles | Detect layout, parse, validate, flag |
| Brain | Pure Python package | Merchant key, evidence layers, decision policy, refund linking |
| Rules | YAML + Pydantic loader | Merchant dictionary, keywords, types, deny list |
| Reports | Python | Totals, tax-form summary, CSV export |
| Eval | Python scripts | Fake data generation, precision and coverage |

## 2. Repository structure

A monorepo with a pure-Python brain package, a thin API around it, and a Next.js app. The brain imports nothing from the API or the web. The repository root is the project root (no extra wrapper folder).

```
./
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, routes
│   │   ├── api/                 # request/response schemas, routers
│   │   ├── ingest/
│   │   │   ├── layouts.py       # bank layout profiles + detection
│   │   │   ├── parser.py        # CSV/PDF → raw rows → Transaction
│   │   │   ├── pdf_reader.py    # PDF table → rows (text PDFs only)
│   │   │   └── validate.py      # dates, amounts, duplicates, tax year
│   │   ├── brain/
│   │   │   ├── merchant_key.py  # description cleaning
│   │   │   ├── layers.py        # type, user, dictionary, keyword layers
│   │   │   ├── decide.py        # evidence → Auto / Review / Excluded
│   │   │   ├── refunds.py       # link refunds to categories
│   │   │   └── engine.py        # categorize(transactions, rules)
│   │   ├── rules/
│   │   │   ├── merchants.yaml
│   │   │   ├── keywords.yaml
│   │   │   ├── types.yaml       # transfers, card payments, fees
│   │   │   ├── deny_list.yaml
│   │   │   └── loader.py        # YAML → validated Rule models
│   │   ├── reports/             # totals, tax-form summary, export
│   │   └── models.py            # Pydantic domain models
│   ├── eval/
│   │   ├── generate_data.py     # fake labeled CSVs (seeded)
│   │   └── evaluate.py          # precision, coverage, confusions
│   ├── tests/                   # unit, cases, api
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/                     # Next.js app router pages
│   ├── components/              # UploadZone, TxTable, ReviewQueue, Totals
│   ├── lib/api.ts               # typed API client
│   ├── package.json
│   └── Dockerfile
├── sample_data/                 # fake statements (Phase 1: one layout)
├── docs/                        # SRS, SDS, screenshots/
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Makefile
├── .env.example
├── README.md
├── DESIGN.md
└── AI_USAGE.md
```

## 3. Data model

All models are Pydantic classes in `models.py`. Money is `Decimal`, never float. State lives in memory per upload session; no database is needed for the build.

```python
class Transaction(BaseModel):
    id: str                  # stable hash of file + row number
    source_file: str
    row_number: int
    date: date
    raw_description: str
    amount: Decimal          # negative = money out
    account: str             # "checking" | "credit_card"
    bank_category: str | None  # from card exports, used as weak evidence
    flags: list[str] = []    # duplicate, outside_tax_year

class Evidence(BaseModel):
    layer: str               # type | user | merchant | keyword | bank_category
    rule_id: str
    category: str
    strength: Literal["strong", "medium", "weak"]
    reason: str

class Decision(BaseModel):
    transaction_id: str
    merchant_key: str
    status: Literal["auto", "review", "excluded"]
    category: str | None     # None when review has no suggestion
    suggestion: str | None
    reason: str              # one human-readable sentence
    rule_id: str | None      # rule that produced the decision
    evidence: list[Evidence]
    refund_of: str | None    # Refund rows only: category the refund reduces
    business_pct: int | None # Phone & Data only
    decided_by: Literal["brain", "user"]

class Rule(BaseModel):
    id: str                  # e.g. "merchant.shell"
    layer: str
    match: Literal["exact", "prefix", "contains", "regex"]
    pattern: str
    action: Literal["categorize", "review"] = "categorize"
    category: str | None     # required when action == "categorize"
    reason: str | None       # required when action == "review"
    strength: Literal["strong", "medium", "weak"]
    sign: Literal["debit", "credit", "any"] = "any"
    max_amount: Decimal | None = None   # compared with abs(amount)
```

A `review` rule is how the rules say "we know this merchant and we know we cannot tell": it sends the row to Review with its own reason (e.g. E3's ambiguous Uber debit) instead of a category.

**Session:** `{session_id, transactions, decisions, user_rules, file_summaries}`, held in an in-memory store behind a small interface so a database can replace it later.

## 4. Ingestion design

Ingestion turns any supported CSV into clean `Transaction` objects, or fails loudly with a reason. It never passes a half-read file to the brain.

**Bank layout profiles** (`layouts.py`) — all fake banks:

| Layout | Header signature | Amount rule | Account |
| --- | --- | --- | --- |
| `first_federal_checking` | Date, Description, Amount, Balance | Signed: negative = out | checking |
| `metro_bank_checking` | Posting Date, Details, Debit, Credit | Debit → negative, Credit → positive | checking |
| `nova_card` | Transaction Date, Merchant, Category, Amount | Card convention: charges positive, payments and credits negative; negate every row, so `PAYMENT THANK YOU -850.00` becomes +850.00 | credit\_card |

Phase 1 ships `first_federal_checking` only. The other two are Phase 2; the profile table means each is a new entry plus a test, with no parser changes.

**Steps**

1. **Split into lines of cells.** A file starting with `%PDF-` goes to `pdf_reader.py`: `pdfplumber` extracts the table rows (drawn grid first, text alignment as fallback), empty spacer rows and repeated page headers are dropped. A PDF with no text (a scan) is refused with `pdf_no_text`; no OCR. Anything else is CSV: decode as UTF-8 (fallback latin-1) and sniff the delimiter with `csv.Sniffer`. From here on, CSV and PDF follow the same steps.
2. **Find the header:** scan the first 15 lines for a row matching a layout signature (case-insensitive, trimmed). No match → error "Unrecognized statement layout" listing the supported layouts.
3. **Read data rows** until a blank line or a summary row (`Total`, `Ending Balance`).
4. **Parse each row:** dates with explicit formats in order (`%m/%d/%Y`, `%Y-%m-%d`, `%d %b %Y`); amounts by stripping `$` and `,`, treating `(x)` and `x-` as negative, then applying the layout's sign rule.
5. **Validate:** rows with an unparseable date or amount are skipped and reported; if more than 10% of rows fail, reject the file.
6. **Flag:** duplicates by `(date, description, amount, account)`; rows outside the tax year. The tax year is the year most rows fall in unless the user picks one.
7. **Summarize:** rows read, skipped (with reasons), duplicates, date range, money in, money out.

The file summary is shown to the user before results, so a bad parse is never hidden behind categories.

## 5. Brain design

The brain is a pure function: `categorize(transactions, rules, user_rules) → decisions`. It collects evidence from ordered layers, then a separate decision step applies an explicit policy. Layers never decide alone.

### 5.1 Merchant key

1. Upper-case; collapse whitespace.
2. Record and strip processor prefixes: `SQ *`, `TST*`, `PAYPAL *`, `PP*`, `PYPL*`. The processor is kept as `processor` for reasons.
3. Record and strip refund markers (`REFUND`, `RETURN`, `CREDIT`, `REVERSAL`) as `refund_marker`, so a refund has the same key as the purchase.
4. Strip trailing store numbers and IDs (`#1234`, `0091`, `*AB12CD`), card digits (`XXXX1234`), dates, and US state codes at the end.
5. Keep meaningful suffixes that change meaning: `UBER *TRIP`, `UBER *EATS`.
6. Never strip to empty: if a step would leave nothing, the key keeps what it had before that step. `PAYPAL *XYZ123` → key `XYZ123`, processor PayPal.

Examples: `SHELL OIL 57442 TX` → `SHELL OIL`; `SHELL OIL REFUND` → `SHELL OIL` (refund marker); `SQ *JOES CAR WASH` → `JOES CAR WASH` (processor Square); `JOES CAFE 9921` → `JOES CAFE`.

The output is `MerchantKey(key, processor, refund_marker)`.

### 5.2 Evidence layers (in order)

| Order | Layer | Source | Strength | Example |
| --- | --- | --- | --- | --- |
| 0 | Transaction type | `types.yaml` + sign + account | strong | `TRANSFER TO SAVINGS` → Transfer; card credit `PAYMENT THANK YOU` → Card Payment |
| 1 | User rules | Saved "always" fixes | strong (wins ties) | `JOES CAFE` → Personal |
| 2 | Merchant dictionary | `merchants.yaml`, exact or prefix on key, sign-aware | strong | `SHELL` + debit → Fuel; `UBER` + credit + `PAYOUT` → Platform Income |
| 3 | Keywords | `keywords.yaml`, word-boundary regex | medium | `CAR WASH` → Vehicle Maintenance; `PARKING` → Tolls & Parking |
| 4 | Bank category | Card export's own Category column (Phase 2) | weak | "Gas/Automotive" → suggests Fuel |

**One match per layer.** Inside a layer, only the most specific matching rule produces evidence (ordering in section 6). So `UBER *EATS -24.10` yields one merchant evidence (Personal), not Personal plus whatever a generic `UBER` rule says. Disagreement between *different* layers is what counts as a conflict.

Guards run alongside the layers: the **deny list** (WALMART, AMAZON, COSTCO, TARGET) and **amount limits** on rules (Fuel rules have `max_amount: 100`, compared with the absolute amount).

### 5.3 Decision policy

Applied in this order; the first matching line wins:

1. A **type** rule matched → Excluded (Transfer, Card Payment) or its category (Bank Fees), status Auto.
2. A **user** rule matched → Auto with that category.
3. **Refund**: a credit whose key matches a debit-only merchant rule (the rule is matched with its sign ignored), or that has a refund marker and matches any expense rule → Auto Refund, `refund_of` = that rule's category. A credit with a refund marker and no matching rule → Review ("Refund from an unknown merchant").
4. Merchant on the **deny list** → Review, reason "Ambiguous merchant; could be business or personal".
5. A **review** rule matched (e.g. `UBER` debit with no TRIP/EATS marker) → Review with that rule's reason.
6. A strong rule matched but its **amount limit** was exceeded → Review with suggestion, reason "Amount above fuel limit; may include store items".
7. **Strong evidence, no conflicts** (all non-weak evidence agrees) → Auto.
8. **Conflicting** evidence (two different categories at medium or strong) → Review, listing both reasons.
9. Only **medium or weak** evidence → Review with suggestion.
10. **No evidence**:
    - a processor was stripped → Review, no suggestion, reason "{Processor} payment, merchant unknown" (E10);
    - a credit → Review, "Money in from an unknown source; not assumed to be income";
    - otherwise → Review, no suggestion, reason "Unknown merchant".

Refunds net against `refund_of` in totals and never count as income.

### 5.4 Pseudocode

```python
def decide(tx, evidence, rules) -> Decision:
    by_layer = group(evidence)
    if by_layer.type:
        return auto_or_excluded(by_layer.type[0])
    if by_layer.user:
        return auto(by_layer.user[0])
    if tx.amount > 0 and (refund := refund_match(tx, rules)):
        return auto_refund(refund)            # refund_of = refund.category
    if tx.amount > 0 and key.refund_marker:
        return review("Refund from an unknown merchant")
    if in_deny_list(key.key):
        return review("Ambiguous merchant", suggestion=best(evidence))
    if review_rule := first_review_rule(evidence):
        return review(review_rule.reason)
    if limit_exceeded(tx, by_layer.merchant):  # abs(tx.amount) > rule.max_amount
        return review("Amount above rule limit", suggestion=by_layer.merchant[0].category)
    strong = [e for e in evidence if e.strength == "strong"]
    firm = {e.category for e in evidence if e.strength != "weak"}
    if strong and len(firm) == 1:
        return auto(strong[0])
    if len(firm) > 1:
        return review("Conflicting rules: " + list_reasons(evidence))
    if evidence:
        return review("Weak match only", suggestion=best(evidence))
    if key.processor:
        return review(f"{key.processor} payment, merchant unknown")
    if tx.amount > 0:
        return review("Money in from an unknown source; not assumed to be income")
    return review("Unknown merchant", suggestion=None)
```

`evidence` holds at most one item per layer (section 5.2).

A **strictness** setting (strict / balanced) only changes whether medium-only evidence can ever become Auto. Default is strict: it cannot.

## 6. Rules configuration

Rules are data, not code, so a reviewer can read the brain's knowledge in one place. `loader.py` validates every file against the `Rule` model at startup and fails fast on a bad rule, a duplicate ID or an unknown category.

```yaml
# merchants.yaml
- id: merchant.shell
  match: prefix
  pattern: "SHELL"
  category: Fuel
  strength: strong
  sign: debit
  max_amount: 100

- id: merchant.uber_payout
  match: regex
  pattern: "^UBER.*(PAYOUT|PAYMENT|EARNINGS)"
  category: Platform Income
  strength: strong
  sign: credit

- id: merchant.uber_trip
  match: prefix
  pattern: "UBER *TRIP"
  category: Personal
  strength: strong
  sign: debit

- id: merchant.uber_ambiguous      # E3: catches UBER debits the TRIP/EATS rules did not
  match: prefix
  pattern: "UBER"
  action: review
  reason: "Uber charge with no ride or eats marker"
  strength: strong
  sign: debit

- id: merchant.platform_tips       # checked before payouts (longer regex wins)
  match: regex
  pattern: "^(UBER|DOORDASH|LYFT)\\b.*\\b(TIP|TIPS|BONUS|INCENTIVE|QUEST|PROMO)\\b"
  category: Tips & Bonuses
  strength: strong
  sign: credit

# types.yaml
- id: type.transfer_savings
  match: regex
  pattern: "\\bTRANSFER (TO|FROM) (SAVINGS|CHECKING)\\b"
  category: Transfer
  strength: strong

# deny_list.yaml
- WALMART
- AMAZON
- COSTCO
- TARGET
```

**Rule ordering inside a layer:** higher `priority` first (default 0; used sparingly, e.g. tips over payouts); then exact before prefix before regex before contains; among equals, the longer pattern wins, then the earlier rule in the file. This makes `UBER *EATS` beat a generic `UBER` rule. Only the winning rule produces evidence. The loader also rejects a `categorize` rule without a category and a `review` rule without a reason.

## 7. API design

FastAPI with Pydantic schemas; OpenAPI docs at `/docs`. All endpoints are scoped to a session created by the upload.

| Method | Path | Body / query | Returns |
| --- | --- | --- | --- |
| POST | `/api/sessions` | multipart: `files[]`, `tax_year` | `session_id`, file summaries, decisions |
| GET | `/api/sessions/{id}/transactions` | `status`, `category`, `q` filters | Rows with decisions |
| GET | `/api/sessions/{id}/review` | — | Needs Review rows grouped by merchant key |
| PATCH | `/api/sessions/{id}/transactions/{tx_id}` | `category`, `business_pct` | Updated decision (`decided_by: user`) |
| POST | `/api/sessions/{id}/rules` | `merchant_key`, `category`, `apply_to_existing` | New user rule + count of rows updated |
| GET | `/api/sessions/{id}/summary` | — | Totals per category, unreviewed amount, `tax_form_lines` (+ `tax_form_name`, `tax_form_note`), `is_final` |
| GET | `/api/sessions/{id}/export.csv` | — | CSV download |
| GET | `/api/health` | — | `{status: ok, rules_loaded: n}` |

**Errors** use one shape: `{error: {code, message, details}}` — for example `unrecognized_layout`, `too_many_bad_rows`, `file_too_large` (HTTP 422 or 413).

**Summary rule:** `is_final` is true only when no row has status Review and every Phone & Data row has a business percentage.

## 8. Frontend design

Next.js (App Router, TypeScript) with Tailwind. One page with three steps; state from the API, no client-side decision logic.

| Screen / component | What it shows | Key interactions |
| --- | --- | --- |
| `UploadZone` | Drop area, tax year picker, "Try sample data" button | Upload files; load fake samples in one click |
| `FileSummary` | Per file: layout detected, rows read, skipped with reasons, duplicates, date range | Expand skipped rows |
| `StatusBar` | Counts: Auto · Needs Review · Excluded; Unreviewed $ | Click a count to filter |
| `ReviewQueue` | Needs Review grouped by merchant: key, row count, total, reason, suggestion | Pick category; tick "Always"; apply to group |
| `TxTable` | All rows: date, description, amount, category chip, status badge, reason on hover | Filter, search, edit category inline |
| `Totals` | Income, expenses by category, refunds netted, Unreviewed amount; Final or Draft badge | Toggle tax-form view |
| `ExportButton` | — | Download CSV |

**Design rules**

- Needs Review rows are amber and pinned first; Auto rows show a muted reason; user-decided rows show a "you" badge.
- Totals display **Draft** until Unreviewed is $0.
- Every status badge has a tooltip with the full reason and rule ID.

## 9. Testing and evaluation

**Test layers (pytest)**

| Layer | File | Covers |
| --- | --- | --- |
| Unit | `test_merchant_key.py` | Prefix stripping, store numbers, meaningful suffixes |
| Unit | `test_ingest.py` | 3 layouts, date formats, amount formats, junk rows, duplicates |
| Unit | `test_decide.py` | Each policy line in section 5.3 |
| Unit | `test_rules_loader.py` | Bad YAML, duplicate IDs, unknown categories fail fast |
| Cases | `test_edge_cases.py` | One parametrized test per messy case E1–E20 from the SRS |
| API | `test_api.py` | Upload → review → rule → summary → export, using FastAPI TestClient |
| Eval | `test_eval_gate.py` | Fails CI if test-set precision drops below 98% |

**Fake data generator** (`eval/generate_data.py`)

- Seeded, so output is identical every run.
- Produces 500 labeled rows for one driver year across the 3 layouts: templates per category with realistic noise (store numbers, state codes, processor prefixes, random casing and spacing).
- Injects traps at fixed rates: ambiguous Uber debits, large gas purchases, deny-listed merchants, refunds, transfers, duplicates, unknown merchants.
- Labels include the **expected status**: traps are labeled `review`, so sending them to review counts as correct.
- Split 70/30 into `dev.csv` (used while writing rules) and `test.csv` (only used by `evaluate.py`).

**Metrics** (`eval/evaluate.py`)

- **Precision** = correct Auto rows ÷ all Auto rows. Target ≥ 98%.
- **Coverage** = Auto rows ÷ all rows.
- **Missed reviews** = trap rows that were auto-categorized. Target 0.
- **Confusion pairs** = top 5 expected → predicted mistakes.

Output is a Markdown table pasted into the README and attached to the pull request.

## 10. DevOps, security and build schedule

**DevOps**

- `docker compose up` runs backend on :8000 and frontend on :3000.
- `Makefile`: `make dev`, `make test`, `make eval`, `make lint`, `make data`.
- GitHub Actions on every push and PR: Ruff, pytest (including the eval gate), ESLint, and `next build`.
- Python 3.12 with `uv` or pip; Node 20.

**Security and data**

- No secrets are needed; `.env.example` holds only `API_URL` and `MAX_UPLOAD_MB`.
- `.gitignore` blocks `.env`, uploads and any `*.real.csv`.
- Uploads are parsed in memory, capped at 5 MB, and limited to `.csv` with a content check.
- CORS allows only the frontend origin.
- All sample data comes from the seeded generator.

**Known limits (stated in the README)**

- Precision is measured on data we generated, against rules we wrote, so it is an upper bound. Real statements will be noisier; the strict policy protects precision by sending more rows to review.
- US formats and USD only.
- Sessions are in memory and lost on restart.

**Build schedule (today)** — Phase 1 first, see SRS "Delivery phases"

| Time | Work | Done when |
| --- | --- | --- |
| 15:00–15:30 | Repo scaffold, CI (Ruff + pytest), Makefile, start `AI_USAGE.md` log | CI green on empty tests |
| 15:30–16:15 | Ingestion: `first_federal_checking` layout, parsing, validation | `test_ingest.py` passes |
| 16:15–18:15 | Brain: merchant key, layers, decision, refunds, YAML rules | E1–E15, E17–E20 pass at brain level |
| 18:15–19:00 | Data generator and evaluation | Precision and coverage printed |
| 19:00–21:00 | API and Next.js UI, including phone % | Upload → review → totals → export works |
| 21:00 | **Phase 1 complete**: commit, push, open draft PR |  |
| 21:00–21:45 | Phase 2 in this order: `nova_card` layout → `metro_bank_checking` (E16) → multi-file → tax-form view → eval gate in CI → Docker | Each item with its tests |
| 21:45 | **Feature freeze** |  |
| 21:45–23:00 | README, DESIGN, AI\_USAGE, screenshots and GIF | Docs complete |
| 23:00–23:30 | Mark PR ready with results table | PR open |
| 23:30–23:59 | Buffer |  |

**Cut order if late:** everything in Phase 2 can be cut, from the end of its list backwards. Never cut tests, evaluation or docs.
