// Writes the frontend LUTs to fixtures/colormaps.json so P's PNG renderer uses byte-identical colours
// (CONTRACTS.md "Colormaps"). Run: npx vite-node scripts/export_colormaps.mjs
import { writeFileSync } from "node:fs";
import { lut, NODATA_RGB } from "../src/gl/colormaps.ts";

const out = { format: "rgba8-256@1", nodata_rgb: NODATA_RGB, index: "round(t*255)", maps: {} };
for (const n of ["gray", "magma", "cividis", "diverging"]) out.maps[n] = Array.from(lut(n));
writeFileSync(new URL("../fixtures/colormaps.json", import.meta.url), JSON.stringify(out) + "\n");
console.log("wrote fixtures/colormaps.json");
