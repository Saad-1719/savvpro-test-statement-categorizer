# Design

## 1. The use case

**Who:** Ali (fictional) drives for Uber and DoorDash in the US as an independent contractor. Platform payouts land in his checking account. Fuel, tolls, repairs and his phone bill go out of the same account.

**The job:** at tax time Ali needs his business income and his deductible expenses, grouped by the lines of the US form for self-employed income (IRS Schedule C), the way his accountant files them. He must not over-claim. Counting a grocery run as fuel, or a refund as income, is worse than leaving a row for him to check.

**Why this persona is a good test:** driver statements are full of traps that simple keyword matching gets wrong:

- **"UBER" means three different things.** It can be income (payout), personal spending (a ride he took) or food (Uber Eats).
- **A $142 gas station charge is probably fuel plus snacks.**
- **Walmart could be a phone mount or groceries.**
- **Money in is not always income.** It can be a refund, a transfer from savings, or a friend paying him back.

## 2. The rule behind every decision

> **If we are not sure, we ask.** A row is only decided automatically when a strong rule matches and nothing disagrees. Everything else goes to Needs Review, with a reason and, where we have one, a suggestion.

That is why the results table shows 100% precision but only 60% coverage. We give up coverage on purpose. The driver clears the rest in a few clicks, because review rows are grouped by merchant and one "Always" rule fixes the whole group, now and in future uploads.

No AI model makes any decision. The brain is plain Python plus rules in YAML, so every decision can be traced and tested, and the same input always gives the same output.

## 3. How a row flows through the system

```
 statement.csv / .pdf
        │
        ▼
 ingest/parser.py      find the header, read rows, parse dates and amounts,
                       flag duplicates and rows outside the tax year
        │  Transaction(date, description, amount, flags)
        ▼
 brain/merchant_key.py "SHELL OIL 57442 TX"  →  "SHELL OIL"
        │
        ▼
 brain/layers.py       each layer returns at most one piece of evidence:
                       type → user rules → merchant dictionary → keywords
        │
        ▼
 brain/decide.py       the 10-step policy  →  auto / review / excluded + reason + rule_id
        │
        ▼
 reports/              totals, tax-form lines, review groups, CSV export
```

The brain (`app/brain/`) does no I/O and imports nothing from the API. The tests and the evaluation call it directly, the same way the API does.

## 4. The brain, step by step

### 4.1 Merchant key: [merchant_key.py](backend/app/brain/merchant_key.py)

Bank descriptions carry noise. We clean them into a short key that rules can match:

| Raw description | Key | Also recorded |
| --- | --- | --- |
| `SHELL OIL 57442 TX` | `SHELL OIL` | store number and state code dropped |
| `JIFFY LUBE #1402` | `JIFFY LUBE` | |
| `SQ *JOES CAR WASH` | `JOES CAR WASH` | processor: Square |
| `PAYPAL *XYZ123` | `XYZ123` | processor: PayPal |
| `SHELL OIL REFUND` | `SHELL OIL` | refund marker: yes |
| `uber*eats` | `UBER *EATS` | the `*EATS` is kept because it changes the meaning |

Rule: we never clean a key down to nothing. If a step would leave it empty, we keep what we had.

### 4.2 Evidence layers: [layers.py](backend/app/brain/layers.py)

Each layer looks through its own rule file and returns **at most one** piece of evidence: its most specific match.

| Order | Layer | Rule file | Matches against | Example |
| --- | --- | --- | --- | --- |
| 0 | Type | `types.yaml` (9 rules) | full description | `TRANSFER TO SAVINGS` → Transfer |
| 1 | User | your saved "Always" rules | exact merchant key | `JOES CAFE` → Personal |
| 2 | Merchant | `merchants.yaml` (62 rules) | merchant key, aware of debit/credit | `SHELL` + money out → Fuel |
| 3 | Keyword | `keywords.yaml` (14 rules) | whole words in the key | `CAR WASH` → Vehicle Maintenance |

Every rule has a **strength**. `strong` can decide. `medium` can only suggest (e.g. the word `GAS`).

Rules can be sign-aware: `UBER … PAYOUT` only matches money **in**, and `UBER *TRIP` only matches money **out**. That is how one company maps to income and to personal spending.

**Which rule wins inside a layer** ([loader.py](backend/app/rules/loader.py), `most_specific_first`):

1. Higher `priority` first. This is used once: tips before payouts, so `UBER TIPS PAYOUT` is a tip.
2. Then match type: exact, prefix, regex, contains.
3. Then the longer pattern, so `UBER *EATS` beats the catch-all `UBER`.

The loader checks every rule file at startup. A bad regex, a duplicate ID or an unknown category stops the app from starting.

### 4.3 The decision policy: [decide.py](backend/app/brain/decide.py)

The steps run in order, and the first one that applies wins.

| Step | When | Result | Example |
| --- | --- | --- | --- |
| 1 | A **type** rule matched | Transfer and Card Payment → **excluded**; Bank Fees → auto | `TRANSFER TO SAVINGS` |
| 2 | A **user** "Always" rule matched | auto, shown as "you" | `JOES CAFE` after the user saved a rule |
| 3 | Money **in** from a shop we only know as an expense | auto **Refund**, linked to that category | `SHELL OIL REFUND +20` → reduces Fuel |
| 4 | The merchant is on the **deny list** | review | `WALMART SUPERCENTER` |
| 5 | A **review rule** matched (we know the merchant, and we know we can't tell) | review, with that rule's reason | `UBER BV` |
| 6 | The amount is **over the rule's limit** | review, suggesting the category | `CHEVRON -142.00` (fuel limit is $100) |
| 7 | **Strong** evidence and every layer agrees | **auto** | `SHELL OIL -48.15` |
| 8 | Two layers **disagree** | review, showing both reasons | `SAFEWAY FUEL` (Personal vs Fuel) |
| 9 | Only medium evidence | review, with a suggestion | `BOBS TIRE SHOP` → suggests Vehicle Maintenance |
| 10 | **Nothing** matched | review, no guess. Money in is "not assumed to be income"; a PayPal/Square payment gets "merchant unknown" | `JOES CAFE`, `VENMO CASHOUT`, `PAYPAL *XYZ123` |

Two small extras after the decision ([engine.py](backend/app/brain/engine.py)):

- A row decided by your own rule is marked `decided_by: user`.
- Phone & Data rows say "set a business-use % before it counts".

### 4.4 Totals: [totals.py](backend/app/reports/totals.py)

- **What counts:** only `auto` rows. Review rows are summed separately as **Unreviewed $**.
- **Refunds:** a refund is subtracted from the category it refunds, never added to income.
- **Phone & Data:** only the business share counts, and only once a % is set.
- **Final or Draft:** totals are **Final** only when nothing is left to review and every phone row has a %. Until then the UI shows **Draft**.
- **Tax-form view:** the same totals added up by the form line the accountant fills in. For example, Fuel + Tolls & Parking + Vehicle Insurance + Vehicle Maintenance all go on line 9, "Car and truck expenses". Each category's line is the `tax_line` field in `categories.yaml`. The form's name lives in `tax_form.yaml` (today the US IRS Schedule C), so the code never names a country's form, and another country is a data change.

## 5. Walkthrough: five rows from the sample statement

These are real outputs for [sample_data/first_federal_checking_2025.csv](sample_data/first_federal_checking_2025.csv).

**Row 1: `SHELL OIL 57442 TX, -48.15`**

1. `parser.parse_line` gives date 2025-01-04, amount −48.15 (money out).
2. `merchant_key` drops `57442` (a store number) and `TX` (a state code), leaving key `SHELL OIL`.
3. Layers:
   - Type: no match.
   - User: no rule.
   - Merchant: `merchant.shell` (prefix `SHELL`, money out only, strong, max $100) → Fuel.
   - Keyword: no match.
4. `decide`:
   - Steps 1–6 don't apply ($48.15 is under the limit).
   - Step 7: one strong rule, nothing disagrees → **auto Fuel**, reason "Known merchant SHELL is Fuel", rule `merchant.shell`.

**Row 2: `UBER *TRIP HELP.UBER.COM, -18.40`**

- **Key:** `UBER *TRIP HELP.UBER.COM`.
- **Candidate rules:** three merchant rules could match: `UBER *TRIP` (prefix), the review rule `^UBER\b` (regex) and the payout regex. The payout regex only matches money in, so it drops out.
- **Winner:** prefix beats regex, so `merchant.uber_trip` wins.
- **Result:** step 7 → **auto Personal**. It's a ride Ali took as a passenger, not a business cost.

**Row 3: `SHELL OIL REFUND, +20.00`**

1. The key is `SHELL OIL` with the refund marker set.
2. The merchant layer finds nothing: `merchant.shell` only matches money out.
3. Step 3: it's money in, and `find_refund_rule` finds that `SHELL OIL` matches an expense-only rule (ignoring the sign). Result: **auto Refund**, with `refund_of = Fuel`.
4. In the totals, +20.00 is subtracted from Fuel and never added to income.

**Row 4: `CHEVRON 0091, -142.00`**

- **Key and match:** the key is `CHEVRON`, which matches `merchant.chevron` → Fuel, strong, max $100.
- **Decision:** step 6 applies because $142 > $100. The row goes to **review**: "Amount above fuel limit of $100; may include store items (suggested: Fuel)".
- **What the driver sees:** a row already pre-filled with Fuel. One click accepts it, or they change it.

**Row 5: `JOES CAFE 9921, -8.75` (twice on 01/18, once on 02/14)**

1. **Parser:** the second 01/18 row is an exact duplicate. It's flagged and comes back **excluded**: "Duplicate of an earlier row; counted once".
2. **The other two rows:** the key is `JOES CAFE`, and no rule in any layer matches. Step 10 → **review**, "Unknown merchant", with no suggestion. We don't guess.
3. **The review queue:** both rows sit in one `JOES CAFE` group. The user picks Personal and ticks **Always**.
4. **Saving the rule:** `services.add_user_rule` saves the rule `JOES CAFE` → Personal and re-runs the brain on that merchant's rows. Step 2 now applies: **auto Personal**, "Your rule: always JOES CAFE as Personal", decided by **you**.
5. **Later uploads:** the next statement with a JOES CAFE row gets the same rule automatically (SRS case E20).

## 6. The 20 messy cases

Each case has a test in [test_edge_cases.py](backend/tests/test_edge_cases.py).

| # | Case | Example | Result |
| --- | --- | --- | --- |
| E1 | Same merchant, income vs expense | `UBER TECHNOLOGIES PAYOUT +412.30` / `UBER *TRIP -18.40` | Platform Income / Personal |
| E2 | Uber Eats vs Uber ride | `UBER *EATS -24.10` | Personal |
| E3 | Ambiguous Uber debit | `UBER BV -9.99` | Review: "Uber charge with no ride or eats marker" |
| E4 | Refund | `SHELL OIL REFUND +20.00` | Refund of Fuel; lowers Fuel; not income |
| E5 | Transfer to own account | `TRANSFER TO SAVINGS -500.00` | Excluded: Transfer |
| E6 | Card bill payment | `PAYMENT THANK YOU +850.00` | Excluded: Card Payment |
| E7 | Large gas station purchase | `CHEVRON 0091 -142.00` | Review, suggesting Fuel |
| E8 | Mixed-use phone bill | `VERIZON WRLS -85.00` | Phone & Data; counts only after a business % is set |
| E9 | Processor wrapper | `SQ *JOES CAR WASH -15.00` | `SQ *` stripped; Vehicle Maintenance |
| E10 | Wrapper, unknown merchant | `PAYPAL *XYZ123 -40.00` | Review: "PayPal payment, merchant unknown" |
| E11 | Deny-listed merchant | `WALMART SUPERCENTER -63.20` | Review unless the user has a rule |
| E12 | Unknown merchant | `JOES CAFE 9921 -8.75` | Review, no suggestion |
| E13 | Conflicting rules | `SAFEWAY FUEL 1187 -56.40` | Review, both reasons shown |
| E14 | Foreign transaction fee | `FOREIGN TRANSACTION FEE -1.20` | Bank Fees |
| E15 | Duplicate row | the same row twice | Flagged; counted once |
| E16 | Debit/Credit columns | separate columns, both positive | Signed correctly |
| E17 | Junk header and footer | account info above, totals below | Skipped and reported in the file summary |
| E18 | Row outside the tax year | a December 2024 row in a 2025 statement | Flagged; not in totals |
| E19 | Platform fee | `DOORDASH FEE -2.00` | Platform Fees |
| E20 | User correction | "Always JOES CAFE as Personal" | All JOES CAFE rows update, now and in later uploads |

Cases we found while building, each with a test:

- **A shop called `TOTAL WINE` was mistaken for the "Total" footer.** Only the first cell is now checked for footer words.
- **`--5` was read as +5.** An amount with two minus signs is now refused.
- **`UBER TIPS PAYOUT` was filed as a plain payout.** The tips rule now has priority.
- **PDF tables without grid lines cut long descriptions.** The PDF reader now places words using the column header positions.

## 7. Reading files

- **Layouts** ([layouts.py](backend/app/ingest/layouts.py)): a layout is recognised by its header line, which can sit under up to 15 lines of account info. There are two today: `Date, Description, Amount, Balance` (signed amounts) and `Posting Date, Details, Debit, Credit`. Adding a bank is one new entry plus a test.
- **Amounts** ([amounts.py](backend/app/ingest/amounts.py)): accepts `-18.40`, `(25.00)`, `15.00-`, `$1,234.50` and `-$850.00`. Anything else, including two minus signs, is refused rather than guessed.
- **Rows that can't be read:** they are skipped and listed in the file summary. If more than 10% of rows fail, the whole file is refused, because a half-read statement gives wrong totals.
- **PDFs** ([pdf_reader.py](backend/app/ingest/pdf_reader.py)): `pdfplumber` reads tables with grid lines directly. For tables without lines, each word is placed using where the column headers sit: text columns line up on the left, money columns on the right. After that, a PDF goes through exactly the same steps as a CSV. A test checks that every sample PDF gives the same rows and decisions as its CSV. Scanned PDFs have no text, so they are refused with a message asking for the CSV. We don't do OCR.

## 8. How we measure it

[eval/generate_data.py](backend/eval/generate_data.py) builds 500 labeled fake rows for one driver year (seeded, so they are identical every run):

- **Templates:** 23 transaction templates with realistic noise: store numbers, state codes, random casing and doubled spaces.
- **Traps:** ambiguous Uber charges, big gas purchases, deny-listed stores, PayPal payments, unknown merchants, unknown money in, conflicts, look-alikes (`SHELLYS SEAFOOD`, `UBERTI FURNITURE`) and duplicates. Every trap is labeled `review`.
- **The split:** 70% for writing rules (`dev.csv`) and 30% held out (`test.csv`). Only the evaluation reads the held-out 30%.

[eval/evaluate.py](backend/eval/evaluate.py) reports four numbers:

- **Precision:** correct Auto rows ÷ all Auto rows. This is the number that matters most, because a wrong Auto row is a wrong tax number nobody looked at.
- **Coverage:** Auto rows ÷ all rows.
- **Missed reviews:** traps that were decided automatically. This must be 0.
- **Top confusions:** which expected categories were predicted as which.

The CI test [test_eval_gate.py](backend/tests/test_eval_gate.py) fails the build below 98% precision or with any missed review.

**Honest caveat:** the same person wrote the generator and the rules, so 100% is an upper bound. On real statements, unknown merchants will mostly land in review (coverage drops) rather than be decided wrongly (precision holds). That is the trade-off the strict policy is built for.

## 9. Trade-offs and what I'd do next

- **Strict over helpful.** Medium evidence never decides on its own. A "balanced" mode that lets agreeing medium evidence decide would raise coverage. It's easy to add (one `if` in step 9), but I'd want real labeled data before turning it on.
- **Rules in YAML, not code.** Anyone can read what the brain knows in one place, and an accountant could review the rules. The cost is that the merchant list must be maintained by hand. User "Always" rules are the pressure valve.
- **One evidence per layer.** This keeps conflicts meaningful: only *different layers* disagreeing counts as a conflict. Inside a layer, the most specific rule simply wins.
- **Next:**
  - Split one row into business and personal amounts (SRS FR-25).
  - Persist user rules in a small database.
  - Use the card statement's own category column as weak evidence.
  - Add a labeled set written by someone other than the rule author, for a less biased precision number.
