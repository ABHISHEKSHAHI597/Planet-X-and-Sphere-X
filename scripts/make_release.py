"""Release candidate manifest (workflow.md §12.2; owner P, release manager).

  python scripts/make_release.py RC0 --image-digest api=ghcr.io/...@sha256:... --image-digest web=...@sha256:...
  python scripts/make_release.py RC0 --check        refuse unless check_flags is green and the tree is clean

Writes release/<RC>/release.json: git sha, image digests, contract versions, calibration lock hash, pins,
effective feature flags for production, the validation status digest, and a link to the STATUS.md generated for
that sha (release/<RC>/STATUS.md). The tag itself is created by .github/workflows/release.yml (or by hand:
`git tag -a <RC> -m "<RC>" && git push origin <RC>`) after the G6 go/no-go (scripts/go_no_go.py)."""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))


def git(*a: str) -> str:
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()


def build(rc: str, digests: dict[str, str]) -> dict:
    import validate

    from app.settings import API_VERSION, effective_features, load_features
    from spherex.types import CONTRACT_VERSION
    lock = yaml.safe_load((ROOT / "config/calibration.lock").read_text(encoding="utf-8"))
    pins_idx = json.loads((ROOT / "config/pins/index.json").read_text(encoding="utf-8")) \
        if (ROOT / "config/pins/index.json").exists() else {}
    status = validate.status_md()
    feats = dict(effective_features(load_features(ROOT / "config/features.yaml"), "production"))
    sha = git("rev-parse", "HEAD")
    return {
        "schema": "parallax-release@1", "rc": rc, "git_sha": sha, "git_dirty": bool(git("status", "--porcelain")),
        "created": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "image_digests": digests,
        "contract_versions": {"http-api": API_VERSION, "spherex.types": CONTRACT_VERSION,
                              "features": "parallax-features@1", "evidence": validate.SCHEMA_V},
        "calibration_lock": lock.get("lock_hash"),
        "pins": pins_idx,
        "features_production": feats,
        "validation": {"status_sha256": hashlib.sha256(status.encode()).hexdigest(),
                       "report": f"release/{rc}/STATUS.md"},
        "demo_views": yaml.safe_load((ROOT / "config/demo_views.yaml").read_text(encoding="utf-8"))["views"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rc", help="RC0, RC1, final")
    ap.add_argument("--image-digest", action="append", default=[], help="name=ref@sha256:...")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    digests = dict(x.split("=", 1) for x in a.image_digest)
    if a.check:
        if subprocess.call([sys.executable, str(ROOT / "scripts/check_flags.py")]) != 0:
            print("refused: check_flags.py is not green")
            return 1
        if git("status", "--porcelain"):
            print("refused: working tree is dirty")
            return 1
        if not digests:
            print("refused: no --image-digest given (images must be pushed by digest, workflow.md §9.5)")
            return 1
    rel = build(a.rc, digests)
    out = ROOT / "release" / a.rc
    out.mkdir(parents=True, exist_ok=True)
    import validate
    (out / "STATUS.md").write_text(validate.status_md(), encoding="utf-8", newline="\n")
    (out / "release.json").write_text(json.dumps(rel, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    print(f"wrote release/{a.rc}/release.json (sha {rel['git_sha'][:10]}, {len(digests)} images, "
          f"{sum(v == 'on' for v in rel['features_production'].values())} flags on)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
