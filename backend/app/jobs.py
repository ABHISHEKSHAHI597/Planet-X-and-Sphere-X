"""In-process job registry (implementation.md §2.2, §9): asyncio tasks for I/O, the API's process pool for
CPU work, one uvicorn worker. Jobs are keyed by view key, so two users asking for the same cold view share
one job. Every job has a hard time-out (5 min by default); its events are kept so a late SSE subscriber
replays them from the start (`planned`, `fetched`, `stack_ready`, `diff_ready`, `warning`, `done`, `error`).

Scale-out later: the same API on arq + Redis (implementation.md §9); routes would not change."""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("parallax.jobs")
Emit = Callable[[dict[str, Any]], None]
TERMINAL = ("done", "error")


@dataclass
class Job:
    id: str
    key: str
    created: float = field(default_factory=time.time)
    finished: float | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    status: str = "running"            # running | done | error
    task: asyncio.Task[Any] | None = None
    _cond: asyncio.Condition = field(default_factory=asyncio.Condition)
    stats: dict[str, Any] = field(default_factory=dict)

    def emit(self, ev: dict[str, Any]) -> None:
        if self.status != "running":
            return
        self.events.append(ev)
        if ev["type"] in TERMINAL:
            self.status = ev["type"]
        loop_task = asyncio.ensure_future(self._notify())   # must be called on the event-loop thread
        loop_task.add_done_callback(lambda t: None if t.cancelled() else t.exception())

    async def _notify(self) -> None:
        async with self._cond:
            self._cond.notify_all()

    async def stream(self, heartbeat_s: float = 15.0) -> AsyncIterator[dict[str, Any] | None]:
        """Yield every event from the first; None = heartbeat. Ends after done/error."""
        i = 0
        while True:
            while i < len(self.events):
                ev = self.events[i]
                i += 1
                yield ev
                if ev["type"] in TERMINAL:
                    return
            if self.status != "running":
                return
            async with self._cond:
                try:
                    await asyncio.wait_for(self._cond.wait(), heartbeat_s)
                except TimeoutError:
                    yield None


def sse(ev: dict[str, Any] | None) -> str:
    """Event name = type; data = JSON of the other fields (CONTRACTS.md HTTP API 0.1.0)."""
    if ev is None:
        return ": keep-alive\n\n"
    data = {k: v for k, v in ev.items() if k != "type"}
    return f"event: {ev['type']}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


class JobRegistry:
    def __init__(self, timeout_s: float = 300.0, keep_s: float = 3600.0) -> None:
        self.timeout_s, self.keep_s = timeout_s, keep_s
        self.jobs: dict[str, Job] = {}
        self.by_key: dict[str, str] = {}
        self.counters = {"started": 0, "done": 0, "error": 0, "timeout": 0, "deduplicated": 0}

    def get(self, job_id: str) -> Job | None:
        return self.jobs.get(job_id)

    def running(self) -> int:
        return sum(1 for j in self.jobs.values() if j.status == "running")

    def active(self, key: str) -> Job | None:
        """The running job building this view key, if any (a second request shares it)."""
        jid = self.by_key.get(key)
        job = self.jobs.get(jid) if jid else None
        return job if job is not None and job.status == "running" else None

    def start(self, key: str, work: Callable[[Job], Awaitable[None]], timeout_s: float | None = None) -> Job:
        self._gc()
        jid = self.by_key.get(key)
        if jid and jid in self.jobs and self.jobs[jid].status == "running":
            self.counters["deduplicated"] += 1
            return self.jobs[jid]
        job = Job(id="job_" + secrets.token_hex(8), key=key)
        self.jobs[job.id], self.by_key[key] = job, job.id
        self.counters["started"] += 1
        job.task = asyncio.create_task(self._run(job, work, timeout_s or self.timeout_s))
        return job

    async def _run(self, job: Job, work: Callable[[Job], Awaitable[None]], timeout_s: float) -> None:
        t0 = time.perf_counter()
        try:
            await asyncio.wait_for(work(job), timeout_s)
            if job.status == "running":
                job.emit({"type": "done", "key": job.key})
        except TimeoutError:
            self.counters["timeout"] += 1
            job.emit({"type": "error", "message": f"job timed out after {timeout_s:.0f} s; stacks finished so "
                                                  "far stay available and the view resumes on the next request"})
        except Exception as e:                                       # never leave a subscriber hanging
            log.exception("job %s failed", job.id)
            job.emit({"type": "error", "message": f"{type(e).__name__}: {e}"[:300]})
        finally:
            job.finished = time.time()
            self.counters[job.status if job.status in ("done", "error") else "error"] += 1
            job.stats["seconds"] = round(time.perf_counter() - t0, 3)
            log.info(json.dumps({"event": "job_end", "job": job.id, "key": job.key, "status": job.status,
                                 **job.stats}, default=str))

    def _gc(self) -> None:
        now = time.time()
        for jid, j in list(self.jobs.items()):
            if j.status != "running" and now - (j.finished or j.created) > self.keep_s:
                del self.jobs[jid]
                if self.by_key.get(j.key) == jid:
                    del self.by_key[j.key]
