"""25-year blink, data side (owner D; implementation.md §4.13, §10.2; workflow.md G5.25yr "D (data)").

For Barnard's Star, ε Indi B and WISE 0855: find each target's own 2MASS epoch (fp_psc.jdate, with a
brightness-checked match), the overlapping 2MASS Ks Atlas images, AllWISE W1/W2 tiles and NEOWISE W2
epochs; size the FOV to ≥ 1.5 × the expected jump; download one archival cutout per target and check it
is valid FITS that contains both the archival and the 2026 position. Writes plans to
backend/tests/data/real/blink25/ and an evidence record `G5.25yr-data`.

What this does NOT establish: the image-measured jump (I normalises, M measures, F displays). The jumps
reported here are catalogue-based: the 2MASS PSC position at its epoch → pos(2026.63).
pos(t) here is the TEMPORARY linear adapter `blink25.linear_pos` (constants.TEST_TARGETS) until M's
targets.pos(t) lands.
"""
import asyncio
import datetime
import gzip
import hashlib
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts/verify"))

from astropy.io import fits  # noqa: E402
from astropy.wcs import WCS  # noqa: E402

from spherex.access.blink25 import plan
from spherex.targets import Target
from astropy.time import Time  # noqa: E402
from spherex.access.http import make_client  # noqa: E402
from spherex.constants import TEST_TARGETS  # noqa: E402
from spherex.external.twomass import TwoMassClient  # noqa: E402
from spherex.external.wise import WiseClient  # noqa: E402

OUT = ROOT / "backend/tests/data/real/blink25"
CACHE = Path(os.environ.get("PARALLAX_CACHE", Path.home() / ".cache/parallax")) / "blink25"
NOW = 2026.63                       # Aug 2026, the latest full SPHEREx visit of Barnard (understanding.md §8.2)
TARGETS = {  # name: (constants key, catalogue Ks for the 2MASS match, expected jump ′, tolerance ′, which jump)
    "barnard": ("Barnard's Star", 4.52, 4.55, 0.1, "2MASS"),
    "epsindb": ("eps Ind B", 11.21, 2.1, 0.1, "2MASS"),
    "wise0855": ("WISE 0855-0714", 23.0, 2.2, 0.1, "AllWISE"),
}


def fits_bytes(raw):
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


async def get_fits(c, url):
    """Archival cutout with the same retry policy as the clients; a body that is not FITS (an error page,
    seen once from IRSA on 2026-11-07) is a retryable CorruptResponse."""
    from spherex.access.fitsio import CorruptResponse
    from spherex.access.retry import with_retry

    async def once():
        r = await c.get(url, timeout=300)
        r.raise_for_status()
        data = fits_bytes(r.content)
        if not data.startswith(b"SIMPLE  ="):
            raise CorruptResponse(f"not FITS ({len(r.content)} B): {r.content[:60]!r}")
        return r.content
    return await with_retry(once)


async def main():
    from _evidence import record
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    metrics, plans, ok_all = {}, {}, True
    async with make_client(timeout=300) as c:
        tm, wi = TwoMassClient(c), WiseClient(c)
        for name, (key, kexp, jump_exp, tol, which) in TARGETS.items():
            ra, dec, ep, pmra, pmdec = TEST_TARGETS[key][:5]
            t=Target('', 'star', key, *TEST_TARGETS[key][:7])
            def pos(year):
                a,d=t.pos([float(Time(year,format='jyear').mjd)])
                return float(a[0]),float(d[0])
            p = await plan(name, pos, NOW, tm, wi, "spherex.targets.Target.pos (catalogue epoch + PM + parallax)", k_expected=kexp)
            d = p.as_dict()
            jkey = next(k for k in p.expected_jumps_arcmin if k.startswith(which))
            jump = p.expected_jumps_arcmin[jkey]
            ep0 = next(e for e in p.epochs if e.label.startswith("2MASS" if which == "2MASS" else "AllWISE W2"))
            dl = dict(ok=False, cutouts=[])
            old = (p.twomass_source["ra"], p.twomass_source["dec"]) if which == "2MASS" else pos(2010.5)
            inside_any = {"archival": False, "now": False}
            for im in ep0.images[:3]:                            # union of up to 3 images (mosaic case)
                url = im["cutout"]
                try:
                    raw = await get_fits(c, url)
                    data = fits_bytes(raw)
                    with fits.open(io.BytesIO(data)) as hl:
                        h = next(x for x in hl if x.data is not None and x.data.ndim == 2)
                        w = WCS(h.header)
                        ny, nx = h.data.shape
                        inside = {}
                        for lab, (r, dd) in (("archival", old), ("now", p.now_pos)):
                            x, y = (float(v) for v in w.all_world2pix(r, dd, 0))
                            inside[lab] = bool(0 <= x < nx and 0 <= y < ny)
                            inside_any[lab] |= inside[lab]
                    f = CACHE / f"{name}_{ep0.label.replace(' ', '_')}_{len(dl['cutouts'])}.fits"
                    f.write_bytes(data)
                    dl["cutouts"].append(dict(url=url, bytes=len(raw), sha256=hashlib.sha256(data).hexdigest(),
                                              shape=[ny, nx], contains=inside, cached=str(f)))
                except Exception as e:  # noqa: BLE001
                    dl["cutouts"].append(dict(url=url, error=repr(e)[:200]))
                if all(inside_any.values()):
                    break
            dl.update(ok=all(inside_any.values()), contains=inside_any,
                      mosaic=len([x for x in dl["cutouts"] if "contains" in x]) > 1)
            d["sample_download"] = dl
            plans[name] = d
            (OUT / f"{name}_plan.json.gz").write_bytes(gzip.compress(json.dumps(d, indent=1, default=str).encode(), 9, mtime=0))
            jok = abs(jump - jump_exp) <= tol
            ok = jok and dl["ok"] and (which != "2MASS" or p.twomass_source is not None)
            ok_all &= ok
            metrics[f"{name}_jump_arcmin"] = {"value": round(jump, 3), "threshold": f"{jump_exp} ± {tol} ({jkey})", "pass": jok}
            metrics[f"{name}_2mass_epoch"] = {"value": (p.twomass_source or {}).get("date") or "not detected",
                                              "threshold": "per-target fp_psc.jdate" if which == "2MASS" else "not detected (J≈25)",
                                              "pass": (p.twomass_source is not None) == (which == "2MASS")}
            metrics[f"{name}_fov_arcmin"] = {"value": round(p.fov_arcmin, 2), "threshold": "≥ 1.5 × jump", "pass": p.fov_arcmin >= 1.5 * jump - 1e-9}
            metrics[f"{name}_sample_cutout"] = {"value": dict(contains=dl.get("contains"), mosaic=dl.get("mosaic"),
                                                              cutouts=[{k: x.get(k) for k in ("bytes", "shape", "contains", "error") if k in x}
                                                                       for x in dl["cutouts"]]),
                                                "threshold": "valid FITS; archival and 2026 positions inside (one image or a mosaic)",
                                                "pass": dl["ok"]}
            metrics[f"{name}_epochs"] = {"value": {e.label: len(e.images) for e in p.epochs if not e.label.startswith("NEOWISE")} |
                                         {"NEOWISE W2 epochs": sum(e.label.startswith("NEOWISE") for e in p.epochs)},
                                         "threshold": "reported", "pass": None}
            print(name, round(jump, 3), (p.twomass_source or {}).get("date"), dl.get("contains"), flush=True)
    rows = "\n".join(f"| {n} | {(p['twomass_source'] or {}).get('date', '—')} | "
                     f"{', '.join(f'{k}: {v:.3f}′' for k, v in p['expected_jumps_arcmin'].items())} | {p['fov_arcmin']:.1f}′ | "
                     f"{sum(e['label'].startswith('NEOWISE') for e in p['epochs'])} | {p['sample_download'].get('contains')} |"
                     for n, p in plans.items())
    report = f"""
**Scope.** The data half of G5.25yr (workflow.md §6: "D (data), I (normalisation), F"). Archival epochs are
found and fetched server-side; the jumps below are **catalogue-based** (2MASS PSC position at the target's
own epoch → pos(2026.63)), not image measurements, and pos(t) is a temporary linear-PM adapter until M's
`targets.pos(t)` exists. The image-measured jumps of implementation.md §10.2 remain I's/M's/F's.

| target | 2MASS epoch (fp_psc) | jumps | FOV | NEOWISE W2 epochs | sample cutout contains (archival, 2026) |
|---|---|---|---|---|---|
{rows}

WISE 0855 has no 2MASS epoch: 2MASS 08551654-0714457 (K = 15.8) lies 3.6″ from its J2000 position but is a
different star (WISE 0855: J ≈ 25); the client's brightness check rejects it.
"""
    record("G5.25yr-data", "L3", "pass" if ok_all else "fail", metrics, report,
           inputs={"plans": str(OUT.relative_to(ROOT)), "now_year": NOW}, n_frames=0,
           code_paths=["backend/spherex/access/blink25.py", "backend/spherex/external/twomass.py",
                       "backend/spherex/external/wise.py"],
           caveats=["pos(t) is a temporary linear-PM adapter (no parallax): ≲1″ error, far below the 0.1′ tolerance",
                    "catalogue-based jumps only; image-measured jumps belong to I/M/F"], author="D")
    (OUT / "README.provenance.json").write_text(json.dumps(dict(
        source="IRSA fp_psc (TAP), IBE 2MASS image search, SIA2 wise_allwise/neowiser; sample cutouts in the cache only",
        retrieved=datetime.date.today().isoformat(), collected_by="D (scripts/blink25_acquire.py)",
        needed_by="I (25-year-blink normalisation), F (display), P (API)"), indent=1))


if __name__ == "__main__":
    asyncio.run(main())
