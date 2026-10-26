# Frontend

Next.js 14 (App Router, TypeScript, Tailwind). It is one page: upload a statement (CSV, or a text-based PDF), check the file summary, clear the Needs Review queue, fix any row, then read the totals and export a CSV. The page makes no categorization decisions. It only shows and edits what the API returns, and it reloads from the API after every change.

## Run

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, default http://localhost:8000
npm install
npm run dev                  # http://localhost:3000 (start the backend first)
```

`npm run dev` and `npm run build` first copy the `.csv` and `.pdf` files from `../sample_data/` into `public/samples/`. The sample buttons on the start screen load them from there.

Run only one `next dev` or `next build` at a time in this folder. They share `.next/`, and a second one corrupts it.

## Tests and checks

```bash
npm run lint        # ESLint (next/core-web-vitals)
npm run typecheck   # tsc --noEmit
npm test            # Vitest + Testing Library: helpers, components and the whole page against a fake API
npm run test:e2e    # Playwright: a real browser against the real backend (starts both servers if needed)
npm run build
```

| Layer | Where | Covers |
| --- | --- | --- |
| Unit | `tests/format.test.ts`, `tests/api.test.ts` | Money formatting, sorting, filters, the API client and its errors |
| Component | `tests/components/` | Review queue, table (decision details, locked rows, business %), totals, upload checks |
| Page | `tests/page.test.tsx` | Upload → fix a group with one bulk request → Final totals; refused upload; failed save; expired session |
| End-to-end | `e2e/review-flow.spec.ts` | The demo statement from upload to Final totals and the CSV download; PDF gives the same rows; a broken file is refused; keyboard access |

For the end-to-end tests, Playwright needs a browser. Either run `npx playwright install chromium` once, or use an installed Chrome with `PLAYWRIGHT_CHANNEL=chrome npm run test:e2e`.

## Docker

The build copies `../sample_data`, so build from the repo root:

```bash
docker build -f frontend/Dockerfile --build-arg NEXT_PUBLIC_API_URL=http://localhost:8000 -t statement-frontend .
docker run -p 3000:3000 statement-frontend
```

The image is multi-stage. It runs the Next.js standalone server as a non-root user. `NEXT_PUBLIC_API_URL` is the backend address *as the browser sees it*, and it is fixed at build time, so rebuild the image to point it somewhere else.

## Layout

| Path | What |
| --- | --- |
| `app/page.tsx` | Page layout only |
| `app/error.tsx` | Error boundary: shown instead of a blank page if a component crashes |
| `lib/useStatementSession.ts` | All data for the uploaded statement and the actions that change it (upload, fix a row, fix a group, start over) |
| `lib/api.ts` | One function per API endpoint; turns `{error: {code, message}}` into `ApiError` |
| `lib/types.ts` | API response shapes |
| `lib/format.ts` | Display helpers: money, row order (Needs Review first), filters |
| `components/` | `UploadZone`, `FileSummaryCard`, `SummaryCards`, `ReviewQueue`, `TransactionsSection` (filters + `StatusBar` + `TxTable`), `Totals`, `CategorySelect`, `icons` |

## Accessibility

- Every control has a label. Filters and view switches are toggle buttons (`aria-pressed`).
- Each row's status badge is a button that opens the decision details (rule, merchant key, evidence) inline, so the "why" is reachable by keyboard and screen readers, not only on hover.
- Saving, errors and filter results are announced through live regions.

## Known limitations

- One statement per upload, and one change is saved at a time. Controls are disabled while saving.
- The "Always" rule and the business % are two requests when both are used. If the second fails, the rule stays saved and the error says what happened.
- Sessions live in the backend's memory. After a restart or expiry the page asks you to upload again.
- No dark mode, and only US English and USD.
