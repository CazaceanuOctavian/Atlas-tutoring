"""
This code is ran on the cloud VM responsable for running student code

runner.py — Pre-warmed ephemeral Docker container pool for code execution.

Architecture
------------
                        ┌──────────────────────────────────────┐
  submit_batch()        │           CodeRunner                 │
  enqueues a Job        │                                      │
  (one job = one        │  queue: Queue[Job]                   │
  submission, with      │                                      │
  N runs — one per      │  slots: list[ContainerSlot]  (N)     │
  test case) and        │    each slot has a "home" language   │
  awaits its result     │    it is warmed to and recycled to   │
  Future.               │                                      │
                        │  dispatcher thread                   │
  The dispatcher        │    └─ pulls Job from queue           │
  thread picks a free   │    └─ prefers a slot already on      │
  slot (preferring one  │       the job's language (no swap)   │
  already on the job's  │    └─ writes + compiles ONCE         │
  language), writes     │    └─ runs each stdin variant        │
  the code once,        │    └─ recycles container ONCE to     │
  compiles once (C++),  │       the slot's home language       │
  runs once per stdin,  └───────────────────────────────────── ┘
  then recycles.

Usage
-----
    # In lifespan — 2 C++ slots + 2 Python slots kept warm:
    runner = CodeRunner(warm={"cpp": 2, "python": 2})
    runner.start()
    app.state.runner = runner
    yield
    runner.stop()

    # (Legacy) uniform pool of one language:
    runner = CodeRunner(pool_size=4)   # 4 python slots

    # Single run (no test cases):
    result = await app.state.runner.submit(code, language, timeout=10)

    # Batch run (one execution per test case, same container):
    results = await app.state.runner.submit_batch(
        code, language, stdin_list=["1\n", "2\n", "15\n"], timeout=10,
    )
"""

import asyncio
import base64
import logging
import queue
import threading
import time
import uuid
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import docker
from docker.errors import DockerException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-language configuration.
#
# `compile` is an argv LIST (no shell) — g++ diagnostics go to stderr, which
# exec_run captures in the combined output by default, so we do NOT need a
# `2>&1` redirect (which was the source of the `ld: cannot find 2>&1` bug —
# docker-py shlex-splits string commands, turning the redirect into a bogus
# filename argument to g++).
#
# `run` is a shell command string, executed via `sh -c` because it uses a
# stdin redirect. `compile=None` means an interpreted language.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LangSpec:
    image:       str
    source_file: str
    run:         str
    compile:     Optional[list[str]] = None


LANGS: dict[str, LangSpec] = {
    "python": LangSpec(
        image="python:3.12-slim",
        source_file="/tmp/solution.py",
        run="python3 /tmp/solution.py",
    ),
    "cpp": LangSpec(
        image="gcc:13",
        source_file="/tmp/solution.cpp",
        compile=["g++", "-std=c++17", "/tmp/solution.cpp", "-o", "/tmp/solution"],
        run="/tmp/solution",
    ),
}

DEFAULT_LANGUAGE = "python"

# Hard ceiling on execution time (seconds), applied PER RUN.
MAX_TIMEOUT = 30

# Per-container resource limits.
# NOTE: g++ can spike well past 128 MB on non-trivial programs; if you see
# compiles killed with no diagnostics (OOM), raise this for the C++ image.
CONTAINER_MEM_LIMIT = "128m"
CONTAINER_CPU_QUOTA = 50_000   # 50% of one core (period is 100_000)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    stdout:    str  = ""
    stderr:    str  = ""
    exit_code: str  = "0"
    timed_out: bool = False


@dataclass
class Job:
    """
    One Job = one submission through the pool exactly once.
    `stdin_list` holds one entry per run:
      - [""]            → single run, no stdin
      - ["1\\n", "2\\n"] → one run per test case, same container/compile
    """
    code:       str
    language:   str
    timeout:    int
    stdin_list: list[str] = field(default_factory=lambda: [""])
    future:     Future    = field(default_factory=Future)
    job_id:     str       = field(default_factory=lambda: str(uuid.uuid4()))


class SlotStatus(str, Enum):
    idle = "idle"
    busy = "busy"


@dataclass
class ContainerSlot:
    slot_id:       int
    home_language: str                      # language this slot is warmed/recycled to
    status:        SlotStatus     = SlotStatus.idle
    container:     object         = None    # docker Container
    language:      str            = ""       # language of the currently live container
    lock:          threading.Lock = field(default_factory=threading.Lock)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64(text: str) -> str:
    return base64.b64encode(text.encode()).decode()


# ---------------------------------------------------------------------------
# CodeRunner
# ---------------------------------------------------------------------------

class CodeRunner:
    def __init__(
        self,
        pool_size: int = 4,
        warm: Optional[dict[str, int]] = None,
    ):
        """
        `warm` declares how many slots to pre-warm per language, e.g.
        {"cpp": 2, "python": 2}. Each slot is warmed to that language and
        recycled back to it after every job, so the balance is preserved.

        If `warm` is omitted, all `pool_size` slots are warmed to
        DEFAULT_LANGUAGE (legacy behaviour).
        """
        if warm is None:
            warm = {DEFAULT_LANGUAGE: pool_size}

        # Flatten into a per-slot plan: one home-language entry per slot.
        self._warm_plan: list[str] = []
        for language, count in warm.items():
            if language not in LANGS:
                raise ValueError(f"Unsupported language in warm plan: {language!r}")
            if count < 0:
                raise ValueError(f"warm count for {language!r} must be >= 0")
            self._warm_plan.extend([language] * count)

        if not self._warm_plan:
            raise ValueError("warm plan is empty — nothing to pre-warm")

        self.pool_size = len(self._warm_plan)
        self._queue: queue.Queue[Optional[Job]] = queue.Queue()
        self._slots: list[ContainerSlot] = []
        self._client: Optional[docker.DockerClient] = None
        self._dispatcher_thread: Optional[threading.Thread] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Connect to Docker, warm up the pool, start the dispatcher."""
        logger.info("CodeRunner: connecting to Docker...")
        try:
            self._client = docker.from_env()
            self._client.ping()
        except DockerException as e:
            raise RuntimeError(f"CodeRunner: cannot connect to Docker: {e}") from e

        logger.info(
            "CodeRunner: pre-warming %d slots: %s",
            self.pool_size,
            ", ".join(f"{n}×{lang}" for lang, n in self._warm_counts().items()),
        )
        for i, language in enumerate(self._warm_plan):
            slot = ContainerSlot(slot_id=i, home_language=language)
            slot.container = self._start_container(language)
            slot.language = language
            self._slots.append(slot)
            logger.info("  slot %d ready (%s, container %s)", i, language, slot.container.short_id)

        self._running = True
        self._dispatcher_thread = threading.Thread(
            target=self._dispatcher_loop, name="runner-dispatcher", daemon=True,
        )
        self._dispatcher_thread.start()
        logger.info("CodeRunner: dispatcher started.")

    def stop(self) -> None:
        """Gracefully shut down — stop all containers."""
        logger.info("CodeRunner: shutting down...")
        self._running = False
        self._queue.put(None)
        if self._dispatcher_thread:
            self._dispatcher_thread.join(timeout=5)
        for slot in self._slots:
            self._stop_container(slot.container)
        logger.info("CodeRunner: stopped.")

    def _warm_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for lang in self._warm_plan:
            counts[lang] = counts.get(lang, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(
        self, code: str, language: str, timeout: int = 10, stdin: str = "",
    ) -> ExecutionResult:
        """Run the code once. Convenience wrapper around submit_batch()."""
        results = await self.submit_batch(code, language, [stdin], timeout)
        return results[0]

    async def submit_batch(
        self, code: str, language: str, stdin_list: list[str], timeout: int = 10,
    ) -> list[ExecutionResult]:
        """
        Enqueue ONE job that runs the code once per entry in `stdin_list`,
        all against the same compiled/loaded container. Returns a list of
        ExecutionResult in the same order as stdin_list.
        """
        if language not in LANGS:
            raise ValueError(f"Unsupported language: {language!r}")

        timeout = min(timeout, MAX_TIMEOUT)
        stdin_list = stdin_list or [""]

        job = Job(code=code, language=language, timeout=timeout, stdin_list=stdin_list)
        self._queue.put(job)
        logger.info(
            "CodeRunner: job %s enqueued (lang=%s, runs=%d)",
            job.job_id, language, len(stdin_list),
        )

        loop = asyncio.get_running_loop()
        total_budget = timeout * len(stdin_list) + 20   # + container overhead
        return await loop.run_in_executor(
            None, lambda: job.future.result(timeout=total_budget),
        )

    # ------------------------------------------------------------------
    # Dispatcher
    # ------------------------------------------------------------------

    def _dispatcher_loop(self) -> None:
        while self._running:
            job = self._queue.get()
            if job is None:
                break   # shutdown signal

            slot = self._acquire_free_slot(job.language)
            if slot is None:
                job.future.set_exception(RuntimeError("Runner stopped"))
                continue

            threading.Thread(
                target=self._run_job, args=(slot, job),
                name=f"runner-slot-{slot.slot_id}", daemon=True,
            ).start()

    def _acquire_free_slot(self, language: str) -> Optional[ContainerSlot]:
        """
        Block until a free slot is available, then claim it.

        Pass 1 prefers an idle slot already running `language` (no swap needed).
        Pass 2 falls back to any idle slot, which will be swapped to `language`
        before use. Only the dispatcher thread acquires, so the two passes are
        race-free against each other; the lock guards against a worker flipping
        a slot back to idle concurrently.
        """
        while self._running:
            for require_match in (True, False):
                for slot in self._slots:
                    with slot.lock:
                        if slot.status != SlotStatus.idle:
                            continue
                        if require_match and slot.language != language:
                            continue
                        slot.status = SlotStatus.busy
                        return slot
            time.sleep(0.05)
        return None

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _run_job(self, slot: ContainerSlot, job: Job) -> None:
        try:
            # Ensure the live container matches the job's language BEFORE we
            # compile/run — otherwise a C++ job on a python container has no g++.
            if slot.language != job.language:
                logger.info(
                    "slot %d: swapping container %s -> %s",
                    slot.slot_id, slot.language, job.language,
                )
                self._swap_container(slot, job.language)

            results = self._execute_batch(slot.container, job)
            job.future.set_result(results)
        except Exception as exc:
            logger.exception("slot %d job %s failed", slot.slot_id, job.job_id)
            job.future.set_exception(exc)
        finally:
            # Recycle once, after the whole batch: a fresh container of the
            # slot's HOME language. This both isolates submissions from each
            # other and restores the declared warm balance (e.g. 2 cpp + 2 py).
            self._swap_container(slot, slot.home_language)
            with slot.lock:
                slot.status = SlotStatus.idle
            logger.info("slot %d ready again (%s)", slot.slot_id, slot.language)

    def _execute_batch(self, container, job: Job) -> list[ExecutionResult]:
        """Write the source once, compile once (if needed), run once per stdin."""
        spec = LANGS[job.language]

        # --- Write source (once) ---
        ec, out = self._sh(container, f"echo {_b64(job.code)} | base64 -d > {spec.source_file}")
        if ec != 0:
            fail = ExecutionResult(stderr=f"Failed to write source: {out}", exit_code=str(ec))
            return [fail for _ in job.stdin_list]

        # --- Compile (once, compiled languages only) ---
        if spec.compile is not None:
            ec, out = self._exec(container, spec.compile)
            if ec != 0:
                fail = ExecutionResult(stderr=f"Compilation error:\n{out}", exit_code=str(ec))
                return [fail for _ in job.stdin_list]

        # --- Run once per stdin entry, reusing the same binary ---
        return [self._run_once(container, spec.run, stdin, job.timeout)
                for stdin in job.stdin_list]

    def _run_once(self, container, run_cmd: str, stdin: str, timeout: int) -> ExecutionResult:
        """Run the already-written/compiled program once with the given stdin."""
        ec, out = self._sh(container, f"echo {_b64(stdin or '')} | base64 -d > /tmp/stdin.txt")
        if ec != 0:
            return ExecutionResult(stderr=f"Failed to write stdin: {out}", exit_code=str(ec))

        ec, out = self._sh(container, f"timeout {timeout} {run_cmd} < /tmp/stdin.txt")
        timed_out = ec == 124   # coreutils `timeout` exit code

        return ExecutionResult(
            stdout=out if ec == 0 else "",
            stderr=out if (ec != 0 and not timed_out) else "",
            exit_code=str(ec),
            timed_out=timed_out,
        )

    # ------------------------------------------------------------------
    # Container helpers
    # ------------------------------------------------------------------

    def _exec(self, container, argv: list[str]) -> tuple[int, str]:
        """Run an argv list directly (no shell). Combined stdout+stderr."""
        ec, output = container.exec_run(argv)
        return ec, (output.decode(errors="replace") if output else "")

    def _sh(self, container, script: str) -> tuple[int, str]:
        """
        Run a shell script inside the container. Combined stdout+stderr.

        Passing ["sh", "-c", script] as a LIST is deliberate: docker-py runs
        shlex.split() on *string* commands, which mangles shell syntax like
        redirects (`<`), pipes (`|`) and `2>&1`. A list is passed through
        untouched, so the real shell interprets them.
        """
        ec, output = container.exec_run(["sh", "-c", script])
        return ec, (output.decode(errors="replace") if output else "")

    def _start_container(self, language: str):
        """Start a long-running idle container for the given language."""
        spec = LANGS.get(language, LANGS[DEFAULT_LANGUAGE])
        return self._client.containers.run(
            spec.image,
            command="sleep infinity",       # keep alive until we exec into it
            detach=True,
            remove=True,                     # auto-remove on stop
            mem_limit=CONTAINER_MEM_LIMIT,
            cpu_quota=CONTAINER_CPU_QUOTA,
            network_disabled=True,           # no outbound network access
            security_opt=["no-new-privileges"],
        )

    def _stop_container(self, container) -> None:
        if container is None:
            return
        try:
            container.stop(timeout=2)
        except Exception:
            pass

    def _swap_container(self, slot: ContainerSlot, language: str) -> None:
        """Stop the slot's current container and start a fresh one for `language`."""
        self._stop_container(slot.container)
        slot.container = self._start_container(language)
        slot.language = language