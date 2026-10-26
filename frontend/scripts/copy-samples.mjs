// Copies the fake statements (CSV and PDF) from ../sample_data into public/samples so "Try sample data" can fetch them.
import { copyFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const src = join(root, "..", "sample_data");
const dest = join(root, "public", "samples");

if (!existsSync(src)) {
  console.warn(`copy-samples: ${src} not found, skipping`);
  process.exit(0);
}
mkdirSync(dest, { recursive: true });
for (const name of readdirSync(src).filter((f) => f.endsWith(".csv") || f.endsWith(".pdf"))) {
  copyFileSync(join(src, name), join(dest, name));
}
