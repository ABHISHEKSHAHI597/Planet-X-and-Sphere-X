import { describe, expect, it } from "vitest";
import { placeLoupe } from "../src/components/Loupe";

// Loupe box sizes seen in practice (desktop, tall when σ/flags wrap, narrow-width clamp) on plates from
// phone to desktop width. For EVERY cursor position on the plate the box must sit fully inside the
// plate, and must not cover the hovered pixel whenever some side has room for it.
const BOXES: [number, number][] = [[256, 116], [256, 160], [288, 200], [240, 140]];
const PLATES = [300, 360, 420, 560, 720, 900];
const PAD = 6, TIGHT = 4;

describe("placeLoupe", () => {
  for (const S of PLATES) for (const [bw, bh] of BOXES) {
    const w = Math.min(bw, S - 2 * PAD), h = Math.min(bh, S - 2 * PAD);   // CSS width / max-height clamps
    it(`fits every cursor position on a ${S}px plate (${w}×${h} box)`, () => {
      const bad: string[] = [];
      for (let y = 0; y <= S; y++) for (let x = 0; x <= S; x++) {
        const { left, top } = placeLoupe(x, y, w, h, S, S);
        if (left < 0 || top < 0 || left + w > S || top + h > S) bad.push(`clipped at (${x},${y})`);
        const roomy = Math.max(x - PAD, S - PAD - x) >= w + TIGHT || Math.max(y - PAD, S - PAD - y) >= h + TIGHT;
        if (roomy && x > left && x < left + w && y > top && y < top + h) bad.push(`covers cursor at (${x},${y})`);
        if (bad.length > 5) break;
      }
      expect(bad).toEqual([]);
    });
  }
});
