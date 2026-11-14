"""Release watcher (implementation.md §3.6, workflow.md §12.4).

New data appears as new planning-period prefixes under <release>/level2/ in S3; a new release appears
as a new top-level prefix (dr1/). One delimiter listing per release finds both. Periods are sorted by
their parsed fields (year, ISO week, sequence, letter), never by string, and listings follow every
continuation token.

Effects: `release_state` refreshes cached coverage (cache.CoverageCache) and the freshness badge. It
never changes pins and never edits config/releases.yaml: a new release prefix (DR1) is reported as
"detected, not adopted" and goes through the manual §12.4 procedure (docs/data-refresh.md)."""
from __future__ import annotations

import datetime
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .releases import Registry
from .s3list import list_s3

PP = re.compile(r"(\d{4})W(\d{2})_(\d)([A-Z])")
KNOWN_NON_RELEASE = {"index/"}           # non-release top-level prefixes, if any appear


def pp_key(prefix: str) -> tuple[int, int, int, str]:
    m = PP.search(prefix)
    if m is None:
        raise ValueError(f"not a planning period: {prefix!r}")
    y, w, n, s = m.groups()
    return int(y), int(w), int(n), s


def period_of(prefix: str) -> str:
    m = PP.search(prefix)
    if m is None:
        raise ValueError(prefix)
    return m.group(0)


def period_week_start(period: str) -> datetime.date:
    """Monday of the planning period's ISO week (the badge says "≈early Oct 2026", not an exact date)."""
    y, w, _, _ = pp_key(period)
    return datetime.date.fromisocalendar(y, w, 1)


@dataclass
class ReleaseState:
    latest: dict[str, str] = field(default_factory=dict)      # release id → newest planning period
    periods: dict[str, int] = field(default_factory=dict)     # release id → number of periods
    top_prefixes: list[str] = field(default_factory=list)
    checked: str = ""

    def token(self) -> str:
        """Compact string for coverage-cache invalidation."""
        return ";".join(f"{k}={v}" for k, v in sorted(self.latest.items())) + "|" + ",".join(sorted(self.top_prefixes))

    @classmethod
    def load(cls, path: Path) -> ReleaseState:
        if not path.exists():
            return cls()
        return cls(**json.loads(path.read_text()))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=1))
        tmp.replace(path)


async def current_state(client: httpx.AsyncClient, registry: Registry) -> ReleaseState:
    top = await list_s3(client, "", "/")
    st = ReleaseState(top_prefixes=sorted(top.prefixes),
                      checked=datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"))
    for rel in registry.releases:
        if rel.s3_prefix not in top.prefixes:
            continue
        lst = await list_s3(client, rel.s3_prefix + "level2/", "/")
        periods = sorted((p for p in lst.prefixes if PP.search(p)), key=pp_key)
        if periods:
            st.latest[rel.id] = period_of(periods[-1])
            st.periods[rel.id] = len(periods)
    return st


def compare(old: ReleaseState, new: ReleaseState, registry: Registry) -> dict[str, Any]:
    known = set(registry.s3_prefixes().values()) | {f"{n}/" for n in registry.never_use} | KNOWN_NON_RELEASE
    unknown = sorted(p for p in new.top_prefixes if p not in known)
    baseline = not old.latest and not old.top_prefixes            # first run: no periods are "new"
    new_periods = {} if baseline else {r: (old.latest.get(r), p) for r, p in new.latest.items()
                                       if old.latest.get(r) is None or pp_key(p) > pp_key(old.latest[r])}
    regress = {r: (old.latest[r], p) for r, p in new.latest.items()
               if r in old.latest and pp_key(p) < pp_key(old.latest[r])}
    events = ["baseline release state recorded"] if baseline else []
    for r, (a, b) in new_periods.items():
        events.append(f"{r}: new planning period {b} (was {a}); refresh coverage caches; pins unchanged")
    for p in unknown:
        events.append(f"NEW RELEASE PREFIX {p}: detected, NOT adopted. Follow docs/data-refresh.md (§12.4): "
                      "add it to config/releases.yaml by reviewed PR only after candidate pins pass")
    for r, (a, b) in regress.items():
        events.append(f"{r}: newest period went backwards {a} → {b} (listing problem?); state not trusted")
    return dict(changed=bool(new_periods or unknown), baseline=baseline, new_periods=new_periods,
                unknown_release_prefixes=unknown,
                dr1_detected=any(p.startswith("dr1") for p in unknown), regressions=regress, events=events,
                adopted=[], release_state=new.token(),
                freshness={r: {"period": p, "week_of": period_week_start(p).isoformat()} for r, p in new.latest.items()})


async def check(client: httpx.AsyncClient, registry: Registry, state_path: Path) -> dict[str, Any]:
    """One hourly run: list, compare with the stored state, store the new state, report. Never writes
    the registry or pins."""
    old = ReleaseState.load(state_path)
    new = await current_state(client, registry)
    rep = compare(old, new, registry)
    if not rep["regressions"]:
        new.save(state_path)
    return rep
