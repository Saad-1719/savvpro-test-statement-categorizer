# SRS: Driver Statement Categorizer

Oct 26, 2026 · @Saad

## 1. Introduction

**Purpose.** This document specifies what the Driver Statement Categorizer must do. It is the contract for the build due 26 October 2026, 23:59.

**Product.** A web app that reads a rideshare or delivery driver's bank and card statements (CSV), sorts every transaction into a tax category using deterministic rules, flags what it is not sure about, and produces tax-time totals the driver can hand to an accountant.

**Persona.** Ali (fictional) drives for Uber and DoorDash in the US as an independent contractor. One checking account receives platform payouts; one credit card pays for fuel, tolls, repairs and his phone. At tax time he needs his business income and deductible expenses sorted, and he must not over-claim.

**The one big rule.** No large AI model decides a category. All decisions are made by our own code: rules, lookups and an explicit confidence policy. A wrong guess is worse than asking.

**In scope**

- CSV upload from 3 bank layouts, detected automatically
- Text-based PDF statements with the same table layouts (read with `pdfplumber`)
- Rule-based categorization with a reason per row
- Needs Review queue, user fixes, and learned user rules
- Category totals, a tax-form summary, and CSV export
- Evaluation of precision and coverage on fake labeled data

**Delivery phases.** Scope follows `TASK.md`: a working product first, extras second. Phase 2 starts only once Phase 1 is complete and green.

| Phase | Contents | Done when |
| --- | --- | --- |
| **1 — Working core** | One CSV layout (`first_federal_checking`: Date, Description, Amount, Balance), one file per upload; the full brain (type, user, merchant, keyword layers); Needs Review queue, user fixes and "always" rules; Phone & Data business %; totals with Draft/Final; CSV export; tests for every messy case except E16; evaluation script; GitHub Actions running Ruff and pytest; `make test`; README, DESIGN, AI_USAGE | A user can upload, fix every Needs Review row, see final totals and export |
| **2 — Extras** | `metro_bank_checking` (Debit/Credit, E16) and `nova_card` (bank category as weak evidence) layouts; multi-file upload; Schedule C view; strictness setting; eval gate in CI; `docker compose` | Each item ships with its tests |

Requirements below that fall in Phase 2: FR-02 (layouts 2 and 3), FR-01 (more than one file), FR-31, E16, NFR-09 (`docker compose` only).

**Out of scope**

- Scanned PDF statements and OCR (a scanned PDF is refused with a clear message), bank connections (Plaid)
- User accounts and multi-user storage
- Filing taxes or giving tax advice

**Definitions**

| Term | Meaning |
| --- | --- |
| Transaction | One normalized statement row: date, description, amount, account |
| Merchant key | Cleaned description used for matching, e.g. `SHELL OIL 57442` → `SHELL` |
| Rule | A pattern that maps a merchant key or row to a category with a strength |
| Auto | Row categorized by the app with high confidence |
| Needs Review | Row the app will not categorize on its own; the user decides |
| Excluded | Row that is not income or spending, e.g. transfers, card payments |
| Precision | Share of Auto rows whose category is correct |
| Coverage | Share of all rows that are Auto |

## 2. Overall description

**Users**

| User | Needs |
| --- | --- |
| Driver (primary) | Upload statements, see what each row is, fix the unsure ones fast, get totals |
| Accountant (secondary) | Receive a clean export with categories, reasons and review status |
| Reviewer of this submission | Run it in one command, see the brain's logic, tests and measured results |

**User journey**

1. Upload one or more CSV statements.
2. The app detects the bank layout, reads and validates rows, and shows any problems.
3. The brain categorizes each row as Auto, Needs Review or Excluded, with a reason.
4. The driver works through Needs Review, grouped by merchant, and optionally saves "always" rules.
5. The driver sees category totals, the tax-form summary and exports a CSV.

**Constraints**

- Backend in Python; frontend in React or Next.js.
- No large AI model in the decision path.
- Fake data only; no real people or real statements in the repo.
- No keys, passwords or tokens committed.
- Tests required.
- Delivered as a pull request by 23:59 today.

**Assumptions**

- US driver, amounts in USD; foreign currency appears only as fee rows.
- Vehicle costs use the actual-expense method. If the driver uses the standard mileage rate, fuel and repairs are not separately deductible; the app shows this as a setting note, not a decision.
- Statements cover one tax year; rows outside it are flagged.
- The tax-form summary is informational, for review with an accountant.

## 3. Category taxonomy

Every row ends in exactly one category. The tax line is the usual IRS Schedule C placement for a sole proprietor; it is shown for the accountant and is configurable.

| Category | Kind | Typical merchants | Schedule C line |
| --- | --- | --- | --- |
| Platform Income | Income | UBER payout, DOORDASH DASHER, LYFT payout | 1 (gross receipts) |
| Tips & Bonuses | Income | Platform tip or incentive payouts | 1 |
| Fuel | Expense | SHELL, CHEVRON, EXXONMOBIL, BP | 9 (car and truck) |
| Vehicle Maintenance | Expense | JIFFY LUBE, AUTOZONE, car wash | 9 |
| Tolls & Parking | Expense | E-ZPASS, FASTRAK, city parking | 9 |
| Vehicle Insurance | Expense | GEICO, PROGRESSIVE | 9 |
| Platform Fees | Expense | Service fees charged by the platform | 10 (commissions and fees) |
| Phone & Data | Expense (mixed use) | VERIZON, T-MOBILE, AT&T | 25 (utilities), business share only |
| Supplies | Expense | Phone mounts, chargers, insulated bags | 22 (supplies) |
| Bank Fees | Expense | Foreign transaction fee, monthly fee | 27a (other) |
| Refund | Contra | Credit from a merchant | Reduces the original category |
| Personal | Not deductible | Groceries, personal Uber rides, Uber Eats | — |
| Transfer | Excluded | Transfer to savings, Zelle to self | — |
| Card Payment | Excluded | PAYMENT THANK YOU, AUTOPAY | — |
| Needs Review | Status | Anything the brain is not sure about | — |

Needs Review is a status, not a final category: it must be resolved before totals are marked final.

## 4. Functional requirements

Priority: **M** = must ship today, **S** = should, **C** = could.

| ID | Requirement | Priority |
| --- | --- | --- |
| **Ingestion** |  |  |
| FR-01 | Accept one or more `.csv` files up to 5 MB each via drag-and-drop or file picker. | M |
| FR-02 | Detect the bank layout from the header row (3 layouts: single signed amount, separate Debit/Credit columns, card export with Category column). | M |
| FR-03 | Skip junk rows before the header and summary rows after the data. | M |
| FR-04 | Parse dates in `MM/DD/YYYY`, `YYYY-MM-DD` and `DD MMM YYYY`; reject a file whose dates cannot be parsed and say why. | M |
| FR-05 | Normalize amounts to signed decimals: negative = money out, positive = money in, handling `(12.50)`, `12.50-`, `$1,234.50`. | M |
| FR-06 | Flag exact duplicate rows (same date, description, amount, account) and keep only one in totals. | M |
| FR-07 | Show a file summary: rows read, rows skipped with reasons, date range, money in, money out. | M |
| **Categorization** |  |  |
| FR-10 | Clean each description into a merchant key: strip store numbers, card digits, dates, and processor prefixes (`SQ *`, `TST*`, `PAYPAL *`, `PP*`). | M |
| FR-11 | Categorize each row through ordered rule layers: transaction type, user rules, merchant dictionary, keyword rules. | M |
| FR-12 | Assign every row exactly one status: Auto, Needs Review or Excluded. | M |
| FR-13 | Auto only when a strong rule matches and no rule disagrees; otherwise Needs Review. | M |
| FR-14 | Store a human-readable reason for every row, including why it was sent to review. | M |
| FR-15 | Use amount sign in decisions: the same merchant can be income (credit) or expense (debit). | M |
| FR-16 | Keep a deny list of ambiguous merchants (e.g. WALMART, AMAZON, COSTCO) that always go to review unless a user rule exists. | M |
| FR-17 | Provide a suggested category on Needs Review rows when weak evidence exists, clearly marked as a suggestion. | S |
| **Review** |  |  |
| FR-20 | Show all rows in a table with date, description, amount, category, status and reason; filter by status and category. | M |
| FR-21 | Group Needs Review rows by merchant key so one fix applies to all rows in the group. | M |
| FR-22 | Let the user set or change any row's category, including Auto rows. | M |
| FR-23 | Offer "Always categorize MERCHANT as CATEGORY"; saving creates a user rule and re-runs categorization. | M |
| FR-24 | For Phone & Data rows, ask for a business-use percentage and apply it to the deductible total. | S |
| FR-25 | Allow splitting a row into business and personal amounts. | C |
| **Results** |  |  |
| FR-30 | Show totals per category, plus a separate Unreviewed amount; totals are labeled final only when Unreviewed is 0. | M |
| FR-31 | Show a tax-form summary grouping totals by Schedule C line, labeled informational. | S |
| FR-32 | Export all rows as CSV with category, status, reason and rule ID. | M |
| **Rules and evaluation** |  |  |
| FR-40 | Load the merchant dictionary, keywords and deny list from YAML files, not code. | M |
| FR-41 | Provide a command that runs the brain on a labeled CSV and reports precision, coverage and top confusions. | M |

## 5. Messy cases and required behaviour

Each case below must have at least one automated test. They also appear as an edge-case table in `DESIGN.md`.

| # | Case | Example row | Required result |
| --- | --- | --- | --- |
| E1 | Same merchant, income vs expense | `UBER TECHNOLOGIES PAYOUT +412.30` vs `UBER *TRIP -18.40` | Payout → Platform Income; trip → Personal (a passenger ride) |
| E2 | Uber Eats vs Uber ride | `UBER *EATS -24.10` | Personal, never Fuel or Travel |
| E3 | Ambiguous Uber debit | `UBER BV -9.99` | Needs Review: "Uber charge with no ride or eats marker" |
| E4 | Refund | `SHELL OIL REFUND +20.00` | Refund linked to Fuel; reduces Fuel total; not income |
| E5 | Transfer to own account | `TRANSFER TO SAVINGS -500.00` | Excluded: Transfer |
| E6 | Card bill payment | `PAYMENT THANK YOU +850.00` (card) | Excluded: Card Payment, not income |
| E7 | Large gas station purchase | `CHEVRON 0091 -142.00` | Needs Review: amount above fuel threshold may include store items |
| E8 | Mixed-use phone bill | `VERIZON WRLS -85.00` | Phone & Data, with business-use % required before it counts |
| E9 | Processor wrapper | `SQ *JOES CAR WASH -15.00` | Strip `SQ *`, match CAR WASH → Vehicle Maintenance |
| E10 | Wrapper with unknown merchant | `PAYPAL *XYZ123 -40.00` | Needs Review: "PayPal payment, merchant unknown" |
| E11 | Deny-listed merchant | `WALMART SUPERCENTER -63.20` | Needs Review unless a user rule exists |
| E12 | Unknown merchant | `JOES CAFE 9921 -8.75` | Needs Review, no guess |
| E13 | Conflicting rules | Keyword says Fuel, dictionary says Personal | Needs Review: both reasons shown |
| E14 | Foreign transaction fee | `FOREIGN TRANSACTION FEE -1.20` | Bank Fees |
| E15 | Duplicate row | Same row twice in a file | Flagged; counted once |
| E16 | Debit/Credit columns | Separate columns, both positive | Signed correctly by layout rules |
| E17 | Junk header and footer | Account info above header; totals below | Skipped and reported in file summary |
| E18 | Row outside tax year | Date in previous year | Flagged in file summary; excluded from totals |
| E19 | Platform fee shown as a debit | `DOORDASH FEE -2.00` | Platform Fees |
| E20 | User correction | User sets `JOES CAFE` → Personal with "always" | All JOES CAFE rows update now and in future uploads |

## 6. Non-functional requirements

| ID | Area | Requirement |
| --- | --- | --- |
| NFR-01 | Accuracy | Precision of Auto rows ≥ 98% on the held-out fake test set; coverage reported, not forced. |
| NFR-02 | Determinism | The same input and rules always produce the same output. No randomness, no network calls in the brain. |
| NFR-03 | Explainability | Every row's decision traces to a rule ID and reason string. |
| NFR-04 | Performance | Categorize 5,000 rows in under 2 seconds on a laptop. |
| NFR-05 | Security | No secrets in the repo; `.env.example` only. Uploaded files are processed in memory and never written to the repo. |
| NFR-06 | Privacy | All sample data is generated and fake. |
| NFR-07 | Maintainability | Rules live in YAML; the brain is a pure module separate from the API and UI. Lint with Ruff and ESLint. |
| NFR-08 | Testability | Unit tests per rule layer, tests per messy case, an API test, and the evaluation run in CI. |
| NFR-09 | Operability | `docker compose up` starts backend and frontend; `make test` runs all tests. |
| NFR-10 | Usability | A first-time user can upload, review and export without instructions; Needs Review is visible at a glance. |
| NFR-11 | Robustness | Malformed files return a clear error, never a crash or a silent partial result. |

## 7. Acceptance criteria

The submission is accepted when all of these hold:

- [ ] The four example behaviours work on the driver persona: a known merchant is categorized, an Uber trip is told apart from an Uber payout, a transfer is excluded, and an unknown merchant goes to Needs Review.
- [ ] All M requirements in section 4 are implemented.
- [ ] All 20 messy cases in section 5 have passing tests.
- [ ] Precision on the held-out test set is ≥ 98% and is reported in the README with coverage.
- [ ] A user can upload, fix every Needs Review row, see final totals and export a CSV.
- [ ] `README.md`, `DESIGN.md` and `AI_USAGE.md` exist and are complete, with token logs or screenshots.
- [ ] No keys or real data in the repo; CI passes on the pull request.
