# Sample statements (all fake)

Every file here is made up. No real people, accounts or bank statements.
Rebuild the generated ones with `make samples` (or `make sample-pdf` for the first PDF).

## Statements that should work

| File | Layout | What to try |
| --- | --- | --- |
| `first_federal_checking_2025.csv` | Date, Description, Amount, Balance | The main demo: 30 rows covering the SRS messy cases (Uber payout vs trip, refund, transfer, duplicate, last-year row, Walmart, PayPal, big gas purchase, phone bill). Hand-written. |
| `first_federal_checking_2025.pdf` | same, as a PDF with grid lines | Same rows and same results as the CSV. |
| `metro_bank_checking_2025.csv` | Posting Date, Details, Debit, Credit | Separate Debit/Credit columns (both positive). Lyft income, Amazon, Costco, a $412 tire purchase, Zelle money in, a $131 gas purchase. |
| `metro_bank_checking_2025.pdf` | same, as a PDF **without** grid lines | Like most real bank PDFs. Same results as the CSV. |
| `driver_full_year_2025.csv` | Date, Description, Amount, Balance | 300 rows for a whole year from the seeded generator. Good for the review queue and totals. |
| `driver_full_year_2025.pdf` | same, as a multi-page PDF | Header repeats on each page; rows still read once. |

## Files that must be refused (`broken/`)

The frontend does not copy these. Upload them by hand; each should show a clear message.

| File | Expected error |
| --- | --- |
| `broken/unknown_layout.csv` | `unrecognized_layout`: lists the supported layouts |
| `broken/header_only.csv` | `no_transactions` |
| `broken/too_many_bad_rows.csv` | `too_many_bad_rows`: 4 of 10 rows unreadable (limit 10%) |
| `broken/empty.csv` | `empty_file` |
| `broken/scanned_statement.pdf` | `pdf_no_text`: a picture-only PDF; asks for the CSV instead |
| `broken/renamed_text.pdf` | `unsupported_file`: a CSV renamed to .pdf |
