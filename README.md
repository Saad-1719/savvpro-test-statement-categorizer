# Driver Statement Categorizer

Sorts a rideshare or delivery driver's bank statement into tax categories, so tax time takes minutes instead of a weekend.

The driver uploads a statement (CSV or text-based PDF). Every transaction gets a category and a one-line reason: Fuel, Platform Income, Tolls & Parking, Personal, and so on. When the app is not sure, it does not guess. The row goes to **Needs Review**, grouped by merchant, so one click fixes the whole group. At the end the driver gets category totals, an informational Schedule C summary and a CSV export for their accountant.

**The brain is our own code, with no AI model in it.** It is a fixed set of rules in YAML files and a 10-step decision policy. Every row's reason traces back to a rule ID.

- How the brain decides, with worked examples: [DESIGN.md](DESIGN.md)
- How AI tools were used to build this: [AI_USAGE.md](AI_USAGE.md)
- Requirements and design written before the code: [docs/SRS.md](docs/SRS.md), [docs/SDS.md](docs/SDS.md)

## Results

Measured on 149 held-out fake transactions that were never used while writing the rules (`make eval`):

| Metric | Value |
| --- | --- |
| Precision of Auto rows | **100.0%** (90/90) |
| Coverage (Auto ÷ all rows) | 60.4% |
| Sent to Needs Review | 28.2% |
| Excluded correctly (transfers, card payments, duplicates) | 17/17 |
| Traps decided automatically (should have gone to review) | **0** |

Read these numbers with care: we wrote both the fake data and the rules, so this is an upper bound. See [Known limits](#known-limits). CI fails if precision drops below 98% or if any trap is decided automatically.

**Tests:** 155 backend tests (all 20 messy cases from the SRS, each step of the decision policy, ingestion, PDFs, the rules loader, session expiry, the API journey including all-or-nothing bulk edits, speed), 41 frontend tests (unit, component and a whole-page flow) and 4 browser end-to-end tests with Playwright against the real backend. CI runs all of them and builds both Docker images. Categorizing 5,000 rows takes about 0.2 s.

## Run it

**With Docker** (nothing else to install):

```bash
make up          # same as: docker compose up --build
```

**Or locally** with Python 3.12+ and Node 20+:

```bash
make install     # backend venv (pinned versions from requirements.lock) + frontend packages
make dev         # backend on :8000, frontend on :3000
```

Open http://localhost:3000 and click **Try sample CSV** or **Try sample PDF**. Or drop in any file from [sample_data/](sample_data/README.md).

<details>
<summary>Without make</summary>

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload --port 8000     # API docs: http://localhost:8000/docs

# Frontend (second terminal)
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

</details>

### Other commands

| Command | What it does |
| --- | --- |
| `make test` | All backend and frontend tests |
| `make e2e` | Browser tests (Playwright) against the real backend and frontend |
| `make lint` | Ruff, ESLint and the TypeScript check |
| `make eval` | Precision and coverage on the held-out test set |
| `make data` | Rebuild the labeled eval data (seeded, so identical every run) |
| `make samples` | Rebuild the sample PDFs and test files in `sample_data/` |
| `make lock` | Re-pin the backend's runtime dependencies after changing `pyproject.toml` |

No keys or secrets are needed. Every setting has a safe default. [.env.example](.env.example) lists them all: the API URL, the CORS origin, the upload size limit, the session lifetime and limit, and the log level. The backend reads them in one place, [backend/app/config.py](backend/app/config.py).

## What it handles

The SRS lists 20 messy cases, and each one has a test. A few of them:

| Statement row | Result |
| --- | --- |
| `UBER TECHNOLOGIES PAYOUT +412.30` vs `UBER *TRIP -18.40` | Platform Income vs Personal: same company, different meaning |
| `UBER BV -9.99` | Needs Review: an Uber charge with no ride or eats marker |
| `SHELL OIL REFUND +20.00` | Refund, subtracted from Fuel; never counted as income |
| `CHEVRON 0091 -142.00` | Needs Review: over the $100 fuel limit, may include store items |
| `WALMART SUPERCENTER #2231` | Needs Review: the store sells both business and personal things |
| `SAFEWAY FUEL 1187` | Needs Review: the merchant says Personal, the keyword says Fuel; both reasons shown |
| `VERIZON WRLS -85.00` | Phone & Data; counts only after the driver enters a business-use % |
| `VENMO CASHOUT +150.00` | Needs Review: money in from an unknown source is not assumed to be income |
| The same row twice | Flagged and counted once; the user can keep it if it was a real second purchase |
| A row from last year | Flagged; never counted |
| A scanned PDF | Refused with a clear message; no OCR guessing |

## Project layout

```
backend/
  app/ingest/     read CSV and PDF files, find the header, parse dates and amounts, flag rows
  app/brain/      merchant key, evidence layers, decision policy (pure Python, no I/O)
  app/rules/      the brain's knowledge as YAML: merchants, keywords, types, deny list, categories
  app/reports/    totals, tax-form summary, review groups, CSV export
  app/api/        FastAPI routes (thin) and request/response shapes
  app/services.py the actions: upload, change rows (one or many, all-or-nothing), save "always" rules
  app/store.py    in-memory sessions (expire when idle, capped) and user rules, with locks
  app/config.py   all settings, from environment variables
  app/main.py     app setup: CORS, logging, one error format for every failure
  eval/           fake data generator, evaluation, sample file builders
  tests/
frontend/         Next.js 14 + TypeScript + Tailwind: one page, no decision logic
sample_data/      fake statements, plus broken files that must be refused
docs/             SRS and SDS
```

## Known limits

- **The precision number is optimistic.** The same person wrote the fake data and the rules. Real statements are noisier: new merchants, odd abbreviations. The strict policy protects precision by sending more rows to review, so real coverage will be lower.
- **Two bank layouts** (signed Amount; separate Debit/Credit), both from made-up banks. Adding one is a new entry in `layouts.py` plus a test.
- **Text-based PDFs only.** Scanned PDFs are refused, not OCR'd.
- **US and USD only.** The vehicle costs assume the actual-expense method. With the standard mileage rate, fuel and repairs are not separately deductible, and the summary says so.
- **Sessions and "always" rules live in memory.** A backend restart clears them. Idle sessions expire after 2 hours, and at most 100 are kept. Both are configurable. The store sits behind a small interface in `store.py` so a database can replace it.
- **No user accounts.** One driver at a time.
- **The tax-form summary is informational.** It groups the category totals by the line of the US self-employment form (IRS Schedule C) for the accountant. It is not tax advice. The form is set in `backend/app/rules/tax_form.yaml`, not in code.
