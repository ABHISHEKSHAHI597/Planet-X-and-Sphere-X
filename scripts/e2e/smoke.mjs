// End-to-end smoke test (workflow.md §9.5 "frontend smoke test in a headless browser against mock mode, with and
// without WebGL"; G2 "PNG fallback works with WebGL disabled"). Owner P (CI); the UI is F's.
//
//   1. backend:  cd backend && MOCK=1 uv run uvicorn app.main:app --port 8000
//   2. frontend: cd frontend && npm run build && PARALLAX_API=http://localhost:8000 npx vite preview --port 4173
//   3. node scripts/e2e/smoke.mjs http://localhost:4173
//
// Passes when, for both runs, the pinned-style URL loads, a manifest arrives from the API, the viewer shows a
// stack (WebGL canvas, or PNG <img> served by the API's /png route when WebGL is off) and no page error occurs.
import { chromium } from "playwright";

const BASE = process.argv[2] ?? "http://localhost:4173";
const PAGE = `${BASE}/?q=${encodeURIComponent("Barnard's Star")}&bands=6`;

async function run(label, args) {
  const browser = await chromium.launch({ args });
  const page = await browser.newPage();
  const errors = [];
  const apiCalls = [];
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
  page.on("response", (r) => { if (r.url().includes("/api/v1/")) apiCalls.push(`${r.status()} ${new URL(r.url()).pathname}`); });
  await page.goto(PAGE, { waitUntil: "domcontentloaded" });
  const webgl2 = await page.evaluate(() => !!document.createElement("canvas").getContext("webgl2"));
  let shown;
  try {
    const el = await page.waitForSelector(".gl-canvas, .png-viewer img", { timeout: 45000 });
    shown = await el.evaluate((n) => n.tagName.toLowerCase() + "." + n.className);
    if (shown.startsWith("img")) {
      await page.waitForFunction(() => {
        const i = document.querySelector(".png-viewer img");
        return i && i.complete && i.naturalWidth > 0;
      }, null, { timeout: 30000 });
    }
  } catch (e) {
    errors.push(`no stack shown: ${e.message}`);
  }
  const manifest = apiCalls.some((c) => c.startsWith("200") && (c.includes("/manifest") || c.endsWith("/views")));
  if (!manifest) errors.push(`no manifest from the API; calls: ${apiCalls.slice(0, 10).join(", ")}`);
  if (!webgl2 && shown && !shown.startsWith("img")) errors.push(`WebGL unavailable but viewer did not fall back to PNG (${shown})`);
  await browser.close();
  console.log(`${errors.length ? "FAIL" : "ok  "} ${label}: webgl2=${webgl2} shown=${shown} api=${apiCalls.length} calls`);
  errors.forEach((e) => console.log("     " + e));
  return errors.length === 0;
}

const ok1 = await run("default (WebGL if available)", ["--use-gl=swiftshader", "--enable-unsafe-swiftshader"]);
const ok2 = await run("WebGL disabled → PNG fallback", ["--disable-webgl", "--disable-webgl2", "--disable-3d-apis"]);
process.exit(ok1 && ok2 ? 0 : 1);
