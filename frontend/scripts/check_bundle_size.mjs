// implementation.md §6.7: JS bundle ≤ 400 KB gzipped WITHOUT Aladin (Aladin is lazy-loaded in its own chunk).
import { readdirSync, readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { join } from "node:path";

const dir = process.argv[2] ?? "dist/assets";
const LIMIT = 400 * 1024;
let total = 0;
const rows = [];
for (const f of readdirSync(dir).filter((x) => x.endsWith(".js"))) {
  const gz = gzipSync(readFileSync(join(dir, f))).length;
  const aladin = /^aladin-/i.test(f);          // the lazy Aladin Lite chunk
  rows.push({ f, kb: (gz / 1024).toFixed(1), aladin });
  if (!aladin) total += gz;
}
console.table(rows);
console.log(`total without Aladin: ${(total / 1024).toFixed(1)} KB gz (budget ${LIMIT / 1024} KB)`);
if (total > LIMIT) { console.error("bundle budget exceeded"); process.exit(1); }
