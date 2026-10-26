# Frontend

Next.js 14 (App Router, TypeScript, Tailwind). It is one page: upload a statement (CSV, or a text-based PDF), check the file summary, clear the Needs Review queue, fix any row, then read the totals and export a CSV. The page makes no categorization decisions; it only shows and edits what the API returns.

## Run

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, default http://localhost:8000
npm install
npm run dev                  # http://localhost:3000 (start the backend first)
```

`npm run dev` and `npm run build` first copy the `.csv` and `.pdf` files from `../sample_data/` into `public/samples/`, which is what the **Try sample CSV** and **Try sample PDF** buttons load.

## Checks

```bash
npm run lint        # ESLint (next/core-web-vitals)
npm run typecheck   # tsc --noEmit
npm test            # Vitest unit tests for lib/
npm run build
```

## Layout

| Path | What |
| --- | --- |
| `app/page.tsx` | Page state and the calls that tie the components together |
| `components/` | `UploadZone`, `FileSummaryCard`, `ReviewQueue`, `StatusBar`, `TxTable`, `Totals`, `CategorySelect` |
| `lib/api.ts` | One function per API endpoint; turns `{error: {code, message}}` into `ApiError` |
| `lib/types.ts` | API response shapes |
| `lib/format.ts` | Display helpers: money, row order (Needs Review first), filters, tooltips |
| `tests/` | Vitest tests |
