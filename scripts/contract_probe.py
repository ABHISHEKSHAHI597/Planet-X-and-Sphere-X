"""Contract probe against a running server (workflow.md §7.3: "nightly against staging"). Owner P.

  python scripts/contract_probe.py --api https://staging.example [--build]

Checks that the server's /openapi.json equals the committed frontend/src/api/openapi.json (same contract as the
code on main), then validates live responses of /releases, /resolve, /coverage, /healthz and — with --build —
one pinned view (POST /views, every SSE event, manifest) against the components of that schema. Exit 1 on any
mismatch; the nightly workflow opens an issue."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SSE = {"planned": "EvPlanned", "fetched": "EvFetched", "stack_ready": "EvStackReady", "diff_ready": "EvDiffReady",
       "warning": "EvWarning", "done": "EvDone", "error": "EvError"}


def validator(oa: dict, name: str) -> jsonschema.Draft202012Validator:
    schema = {"$ref": f"#/components/schemas/{name}", "components": oa["components"]}
    return jsonschema.Draft202012Validator(schema)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api", required=True)
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--pin", default="21a7689afc4b")
    a = ap.parse_args()
    errs: list[str] = []
    with httpx.Client(base_url=a.api, timeout=60) as c:
        oa = c.get("/openapi.json").raise_for_status().json()
        committed = json.loads((ROOT / "frontend/src/api/openapi.json").read_text(encoding="utf-8"))
        if oa != committed:
            errs.append("server /openapi.json differs from committed frontend/src/api/openapi.json (deployed sha ≠ main?)")

        def check(name: str, obj: object, where: str) -> None:
            for e in validator(oa, name).iter_errors(obj):
                errs.append(f"{where}: {name}: {e.message[:200]}")

        check("ReleasesResponse", c.get("/api/v1/releases").json(), "/releases")
        check("ResolveResult", c.get("/api/v1/resolve", params={"q": "WISE 0855-0714"}).json(), "/resolve name")
        check("ResolveResult", c.get("/api/v1/resolve", params={"q": "08:55:10.831 -07:14:42.53"}).json(), "/resolve coords")
        cov = c.get("/api/v1/coverage", params={"ra": 269.4461, "dec": 4.7707, "fov": 6})
        if cov.status_code == 200:
            check("Coverage", cov.json(), "/coverage")
        else:
            errs.append(f"/coverage HTTP {cov.status_code}: {cov.text[:200]}")
        check("Health", c.get("/healthz").json(), "/healthz")
        if a.build:
            r = c.post("/api/v1/views", json={"q": "Barnard's Star", "pin": a.pin})
            d = r.json()
            if d.get("status") == "queued":
                check("ViewQueued", d, "/views")
                with c.stream("GET", f"/api/v1/jobs/{d['job_id']}/events", timeout=900) as s:
                    name = None
                    for line in s.iter_lines():
                        if line.startswith("event: "):
                            name = line[7:]
                        elif line.startswith("data: ") and name:
                            check(SSE[name], {"type": name, **json.loads(line[6:])}, f"SSE {name}")
                            if name in ("done", "error"):
                                break
                key = d["key"]
            else:
                check("ViewReady", d, "/views")
                key = d["manifest"]["key"]
            check("ViewManifest", c.get(f"/api/v1/views/{key}/manifest").json(), "/manifest")
    for e in errs:
        print("FAIL", e)
    print(f"contract probe {a.api}: {len(errs)} problems")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
