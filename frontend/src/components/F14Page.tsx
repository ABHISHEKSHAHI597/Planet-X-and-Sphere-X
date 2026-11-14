/**
 * F14 orientation check (workflow.md §5 F14, §7.3): the golden payload
 * frontend/fixtures/golden/stack_F_121x121.f16 (encoded by backend render.golden_F) drawn by BOTH
 * viewers. Pass = in each panel the "F" is upright in the TOP-LEFT (north-east), the purple no-data
 * tint is in the BOTTOM-RIGHT corner (south-west) and at the centre pixel, and the bottom-row ramp
 * brightens to the RIGHT (west). The second half of F14 (a real field beside Aladin's 2MASS) needs real
 * data and is run on staging.
 */
import { useEffect, useRef, useState } from "react";
import goldenUrl from "../../fixtures/golden/stack_F_121x121.f16?url";
import goldenMeta from "../../fixtures/golden/stack_F_121x121.json";
import { FORMAT_F16, assertFormat } from "../api/formats";
import { webgl2Available } from "../gl/renderer";
import { decodeF16, f16Bits } from "../lib/half";
import { renderRGBA } from "../lib/stretch";
import { GLCanvas } from "./GLCanvas";

const N = 121;

export function F14Page() {
  const [bits, setBits] = useState<Uint16Array | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const cpu = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    (async () => {
      try {
        assertFormat(goldenMeta.format, FORMAT_F16);
        const b = f16Bits(await (await fetch(goldenUrl)).arrayBuffer());
        if (b.length !== N * N) throw new Error(`golden has ${b.length} px, expected ${N * N}`);
        setBits(b);
      } catch (e) { setErr((e as Error).message); }
    })();
  }, []);
  useEffect(() => {
    const c = cpu.current;
    if (!c || !bits) return;
    const rgba = renderRGBA(decodeF16(bits), N, N, 0, 100, { mode: "lin", beta: 1 }, "gray");
    c.getContext("2d")!.putImageData(new ImageData(rgba, N, N), 0, 0);
  }, [bits]);
  const gl = webgl2Available();
  return (
    <main className="f14">
      <h1>F14 — orientation check</h1>
      <p>{goldenMeta.decoder_check}</p>
      {err && <p className="error" role="alert">{err}</p>}
      <div className="f14-grid">
        <figure>
          <figcaption>WebGL2 viewer (R16F, no flip){gl ? "" : " — WebGL2 unavailable here"}</figcaption>
          <div className="f14-box">{bits && gl && <GLCanvas bits={bits} nx={N} ny={N} lo={0} hi={100} stretch={{ mode: "lin", beta: 1 }}
            cmap="gray" transform={null} label="Golden F in the WebGL viewer" />}</div>
        </figure>
        <figure>
          <figcaption>CPU / PNG path (row 0 flipped to the bottom)</figcaption>
          <div className="f14-box"><canvas ref={cpu} width={N} height={N} className="pixelated" aria-label="Golden F, CPU render" role="img" /></div>
        </figure>
      </div>
      <p className="small">Expected in both: <b>F upright, top-left</b> · <b>purple corner bottom-right</b> and a purple centre pixel ·
        <b> ramp brighter to the right</b> along the bottom edge. North is up, east is left.</p>
    </main>
  );
}
