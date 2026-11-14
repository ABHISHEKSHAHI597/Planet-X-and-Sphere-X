"""F12 (owner D, pair P): which FrameSource meets the budgets from where we run, and what concurrency IRSA
tolerates (workflow.md §5; implementation.md §3.4, §3.7, §10.3).

  1. Timed single reads: S3 row sections and stream-aborted IRSA cutouts of the same frames and box
     (6′ view → `cutout_size_deg(6)`), sequential, then S3 at concurrency 8.
  2. Soak: 4 concurrent IRSA cutout requests, back to back, for 10 minutes (§10.3), retries OFF so every
     raw failure is visible: HTTP status, truncation (EOFError), corrupt body, transport errors.

Every request is logged (requests.json next to the record). The record states the host it ran from; a
run that is not from the deployment region (AWS us-east-1 VM, owner P) answers F12 only for that network.

Usage: python scripts/verify/f12_framesource_bench.py [--soak-seconds 600] [--concurrency 4] [--where TEXT]
"""
import argparse
import asyncio
import json
import platform
import random
import socket
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))

import httpx  # noqa: E402

from spherex.access.fitsstream import IrsaCutoutSource, cutout_url, read_hdus  # noqa: E402
from spherex.access.frames import FrameBox, cutout_size_deg  # noqa: E402
from spherex.access.http import IBE_PREFIX, HostLimiter, Timer, make_client  # noqa: E402
from spherex.access.s3sections import S3SectionSource  # noqa: E402
from spherex.types import FrameRef  # noqa: E402

FIX = ROOT / "backend/tests/data/real/frames_5targets.json"
BARNARD = (269.4461, 4.7707)          # 2026.0 position used for the committed coverage fixture


def frames(n, seed=1):
    d = json.loads(FIX.read_text())
    c = d["columns"]
    rows = [dict(zip(c, r)) for r in d["rows"] if r[0] == "barnard"]
    random.Random(seed).shuffle(rows)
    return [FrameRef(IBE_PREFIX + r["s3_key"], r["s3_key"], r["collection"], r["obs_id"], int(r["DETECTOR"]),
                     float(r["t_min_mjd"])) for r in rows[:n]]


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q / 100 * (len(xs) - 1))))] if xs else None


def summary(log):
    ok = [r for r in log if r["ok"]]
    tot = [r["total_s"] for r in ok]
    ttfb = [r["ttfb_s"] for r in ok if r.get("ttfb_s") is not None]
    by = {}
    for r in log:
        if not r["ok"]:
            by[r["error"]] = by.get(r["error"], 0) + 1
    return dict(requests=len(log), ok=len(ok), failures=len(log) - len(ok), failure_kinds=by,
                total_p50_s=pct(tot, 50), total_p95_s=pct(tot, 95), total_max_s=max(tot) if tot else None,
                ttfb_p50_s=pct(ttfb, 50), ttfb_p95_s=pct(ttfb, 95),
                bytes_mean=statistics.mean(r["bytes"] for r in ok) if ok else None,
                bytes_total=sum(r["bytes"] for r in log))


def classify(e):
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP {e.response.status_code}"
    return type(e).__name__


async def one_cutout(client, lim, ref, box):
    url = cutout_url(ref.access_url, box)
    t = Timer()
    rec = dict(frame=ref.id, t0=time.time())
    try:
        async with lim.slot(url):
            async with client.stream("GET", url, timeout=120) as resp:
                rec["status"] = resp.status_code
                resp.raise_for_status()
                hdus, _, n = await read_hdus(resp.aiter_bytes(), timer=t)
        rec.update(ok=True, ttfb_s=t.ttfb, total_s=t.elapsed, bytes=n, shape=list(hdus["IMAGE"][1].shape))
    except Exception as e:  # noqa: BLE001 — every failure is recorded, not raised
        rec.update(ok=False, error=classify(e), detail=str(e)[:200], total_s=t.elapsed, ttfb_s=t.ttfb, bytes=0)
    return rec


async def soak(client, refs, box, seconds, conc):
    lim = HostLimiter({"irsa.ipac.caltech.edu": conc})
    log, stop = [], time.time() + seconds
    it = iter(range(10 ** 9))

    async def worker():
        while time.time() < stop:
            ref = refs[next(it) % len(refs)]
            log.append(await one_cutout(client, lim, ref, box))

    await asyncio.gather(*(worker() for _ in range(conc)))
    return log, lim.peak.get("irsa.ipac.caltech.edu", 0)


async def singles(client, refs, box):
    out = {"s3": [], "cutout": [], "s3_conc8": []}
    s3 = S3SectionSource(client, tries=1)
    cut = IrsaCutoutSource(client, tries=1)
    for ref in refs:
        for name, src in (("s3", s3), ("cutout", cut)):
            t = Timer()
            b0 = src.stats.bytes
            try:
                f = await src.fetch(ref, box)
                out[name].append(dict(frame=ref.id, ok=True, total_s=t.elapsed, ttfb_s=None,
                                      bytes=src.stats.bytes - b0, shape=list(f.hdus["IMAGE"][1].shape),
                                      origin=list(f.origin)))
            except Exception as e:  # noqa: BLE001
                out[name].append(dict(frame=ref.id, ok=False, error=classify(e), detail=str(e)[:200],
                                      total_s=t.elapsed, bytes=src.stats.bytes - b0))
    s3b = S3SectionSource(client, limiter=HostLimiter({"nasa-irsa-spherex.s3.amazonaws.com": 8}), tries=1)

    async def s3one(ref):
        t = Timer()
        try:
            await s3b.fetch(ref, box)
            return dict(frame=ref.id, ok=True, total_s=t.elapsed, bytes=0)
        except Exception as e:  # noqa: BLE001
            return dict(frame=ref.id, ok=False, error=classify(e), total_s=t.elapsed, bytes=0)
    t = Timer()
    out["s3_conc8"] = await asyncio.gather(*(s3one(r) for r in refs))
    out["s3_conc8_wall_s"] = t.elapsed
    out["s3_conc8_bytes"] = s3b.stats.bytes
    return out


async def main(a):
    from _evidence import record
    box = FrameBox(*BARNARD, cutout_size_deg(6.0))
    refs = frames(400)
    async with make_client() as client:
        print("singles…", flush=True)
        sg = await singles(client, refs[:a.singles], box)
        print("soak…", flush=True)
        log, peak = await soak(client, refs, box, a.soak_seconds, a.concurrency)
    s_s3, s_cut = summary(sg["s3"]), summary(sg["cutout"])
    s_soak = summary(log)
    span = (max(r["t0"] for r in log) - min(r["t0"] for r in log)) if log else 0
    n503 = s_soak["failure_kinds"].get("HTTP 503", 0)
    where = a.where
    deploy = a.deployment
    metrics = {
        "host": {"value": f"{socket.gethostname()} ({platform.system()}); {where}", "threshold": "deployment VM (us-east-1)", "pass": deploy},
        "box_deg": {"value": round(box.size_deg, 5), "threshold": "cutout_size_deg(6′)", "pass": None},
        "s3_single_p50_s": {"value": s_s3["total_p50_s"], "threshold": "reported", "pass": None},
        "s3_single_bytes_mean": {"value": s_s3["bytes_mean"], "threshold": "reported (≈ rows × 8160 B × 3 + FLAGS)", "pass": None},
        "s3_single_failures": {"value": s_s3["failures"], "threshold": "0", "pass": s_s3["failures"] == 0},
        "cutout_single_p50_s": {"value": s_cut["total_p50_s"], "threshold": "reported", "pass": None},
        "cutout_single_bytes_mean": {"value": s_cut["bytes_mean"], "threshold": "≈190 KB for 6′ (implementation.md §3.4)", "pass": None},
        "cutout_single_failures": {"value": s_cut["failures"], "threshold": "0", "pass": s_cut["failures"] == 0},
        "s3_conc8_frames_per_s": {"value": round(len(sg["s3_conc8"]) / sg["s3_conc8_wall_s"], 3), "threshold": "reported", "pass": None},
        "soak_seconds": {"value": round(span, 1), "threshold": f">= {max(a.soak_seconds - 30, 0)}", "pass": span >= a.soak_seconds - 30},
        "soak_concurrency_peak": {"value": peak, "threshold": f"== {a.concurrency}", "pass": peak == a.concurrency},
        "soak_requests": {"value": s_soak["requests"], "threshold": "reported", "pass": None},
        "soak_failures": {"value": s_soak["failures"], "threshold": "reported", "pass": None},
        "soak_503": {"value": n503, "threshold": "0 (§10.3: no 503s before raising concurrency)", "pass": n503 == 0},
        "soak_failure_kinds": {"value": s_soak["failure_kinds"], "threshold": "reported", "pass": None},
        "soak_total_p50_s": {"value": s_soak["total_p50_s"], "threshold": "reported", "pass": None},
        "soak_total_p95_s": {"value": s_soak["total_p95_s"], "threshold": "reported", "pass": None},
        "soak_ttfb_p50_s": {"value": s_soak["ttfb_p50_s"], "threshold": "reported", "pass": None},
        "soak_ttfb_p95_s": {"value": s_soak["ttfb_p95_s"], "threshold": "reported", "pass": None},
        "soak_bytes_mean": {"value": s_soak["bytes_mean"], "threshold": "reported", "pass": None},
        "soak_bytes_total": {"value": s_soak["bytes_total"], "threshold": "reported", "pass": None},
    }
    local_pass = n503 == 0 and s_soak["failures"] == 0
    verdict = "inconclusive" if not deploy else ("pass" if local_pass else "fail")
    report = f"""
**Question (F12).** From the deployment region, which FrameSource meets the budgets, and what concurrency
does IRSA tolerate? **Run from:** {where}.

**Method.** Barnard's Star field, 6′ view (box {box.size_deg:.4f}°, `cutout_size_deg`). (1) {a.singles}
frames read once by each source, sequentially, no retries; then S3 at concurrency 8. (2) Soak: {a.concurrency}
workers issuing stream-aborted cutouts back to back over {len(refs)} distinct Barnard frames for
{a.soak_seconds} s, retries off, every request logged in `requests.json`.

**Results.** S3 section p50 {s_s3['total_p50_s']} s, {s_s3['bytes_mean']} B/frame mean; cutout p50
{s_cut['total_p50_s']} s, {s_cut['bytes_mean']} B/frame. Soak: {s_soak['requests']} requests in {span:.0f} s,
{s_soak['failures']} failures {s_soak['failure_kinds']}, total p50/p95 {s_soak['total_p50_s']}/{s_soak['total_p95_s']} s,
TTFB p50/p95 {s_soak['ttfb_p50_s']}/{s_soak['ttfb_p95_s']} s.

**Verdict.** {'Deployment-region run.' if deploy else 'NOT the deployment region: this answers F12 only for this network. F12 stays open until the same script runs on the us-east-1 VM (owner P provides the VM; D runs it).'}
"""
    d = record(a.check_id, "L3", verdict, metrics, report,
               inputs={"frames": [r.id for r in refs], "box": box.key(), "fixture": str(FIX.relative_to(ROOT))},
               n_frames=len(refs), code_paths=["backend/spherex/access/fitsstream.py",
                                                "backend/spherex/access/s3sections.py",
                                                "backend/spherex/access/http.py"],
               caveats=[] if deploy else ["run from a non-deployment network; latency and throughput are not the VM's"],
               author="D")
    (d / "requests.json").write_text(json.dumps({"singles": sg, "soak": log}, indent=0, default=str))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--soak-seconds", type=int, default=600)
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--singles", type=int, default=6)
    p.add_argument("--where", default="developer laptop, residential network (not us-east-1)")
    p.add_argument("--check-id", default="F12", help="e.g. F12-c2 for a supplementary run")
    p.add_argument("--deployment", action="store_true", help="this host IS the deployment VM (us-east-1)")
    asyncio.run(main(p.parse_args()))
