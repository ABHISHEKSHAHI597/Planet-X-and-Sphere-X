# F14 — Viewer orientation (golden half) — INCONCLUSIVE (L2, real-field half pending)

**Question (workflow.md §5):** are both viewers north-up, east-left?

**Method.** The contract golden `frontend/fixtures/golden/stack_F_121x121.f16` (encoded by I's
`render.golden_F` / `to_f16`; an "F" in the north-east of a row-0-south grid, sentinels in the south-west
corner and at the centre, a ramp brightening westward along the south edge) was:
1. decoded in TypeScript and compared with the layout the encoder test asserts (`tests/golden.test.ts`);
2. rendered by the CPU/PNG path (`renderRGBA`, the only place rows are flipped) and checked pixel by pixel;
3. mapped through the shader's uv→pixel algebra (`px = u_center + (v_uv − 0.5)·u_span`, `v_uv` = (0,0) at the
   canvas bottom-left) and through the overlay/loupe mapping (`lib/viewport.ts`), which must agree;
4. drawn by the real WebGL2 viewer and the CPU path side by side on `/f14` in Chrome (Linux).

**Result.** All four agree: F upright in the top-left, purple no-data tint bottom-right and at the centre,
ramp brightening to the right. No flip in the WebGL path (R16F upload, `UNPACK_FLIP_Y_WEBGL = false`);
exactly one flip in the CPU path. implementation.md §6.3's orientation rule is **confirmed** for the golden.

**Bug found on the way.** The first browser run showed a blank WebGL panel: `BlinkRenderer.dispose()` called
`WEBGL_lose_context.loseContext()`, and React StrictMode's mount→unmount→mount then received the dead context
of the same canvas. `dispose()` now frees textures/program only.

**Open (why inconclusive).** F14 also asks for a real field blinked beside Aladin's 2MASS HiPS. That needs
P's `/views` and D's pins. Run it on staging with the Barnard 12′ pin; it supersedes this record.

**Reproduce.** `cd frontend && npm test -- golden` · `npm run dev:mock` → open `/f14`.

git 7d55ed1 (dirty) · binary f16le-row0south-nodata-65504@1 · author F · reviewer pending (P)
