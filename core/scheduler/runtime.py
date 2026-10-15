"""Single in-process scheduler coordinator.

This coordinates threads inside one API process only. Separate API worker
processes each have their own scheduler; in-memory state does not synchronize
them. Use a database lock or a single worker process for cross-process safety.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class SchedulerRuntime:
    """Thread-safe lifecycle and heartbeat tracker for the background scheduler."""

    _shared: "SchedulerRuntime | None" = None
    _shared_lock = threading.Lock()

    def __init__(self, interval_seconds: int = 30) -> None:
        self.interval_seconds = max(1, int(interval_seconds))
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = "stopped"
        self.started_at: float | None = None
        self.stopped_at: float | None = None
        self.last_run_started_at: float | None = None
        self.last_run_finished_at: float | None = None
        self.last_heartbeat_at: float | None = None
        self.run_count = 0
        self.last_error: str | None = None
        self.last_run_duration_ms: float | None = None
        self._stop_timeout = 10.0

    @classmethod
    def shared(cls, interval_seconds: int = 30) -> "SchedulerRuntime":
        with cls._shared_lock:
            if cls._shared is None:
                cls._shared = cls(interval_seconds=interval_seconds)
            return cls._shared

    def _worker_wrapper(self, worker) -> None:
        self.state = "running"
        try:
            while not self._stop_event.is_set():
                self.last_run_started_at = time.time()
                started = time.monotonic()
                try:
                    worker(self)
                    self.last_run_finished_at = time.time()
                    self.run_count += 1
                    self.last_error = None
                    self.last_run_duration_ms = round((time.monotonic() - started) * 1000.0, 3)
                except Exception as exc:  # noqa: BLE001
                    self.last_run_finished_at = time.time()
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    self.last_run_duration_ms = round((time.monotonic() - started) * 1000.0, 3)
                self.last_heartbeat_at = time.time()
                self._stop_event.wait(self.interval_seconds)
        finally:
            self.state = "stopped"
            self.stopped_at = time.time()
            self.last_heartbeat_at = self.stopped_at

    def start(self, worker) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self.started_at = time.time()
            self.stopped_at = None
            self.last_heartbeat_at = self.started_at
            self.thread_name = "jarvis-scheduler"
            self._thread = threading.Thread(
                target=self._worker_wrapper,
                args=(worker,),
                daemon=True,
                name=self.thread_name,
            )
            self._thread.start()
            return True

    def stop(self, timeout: float | None = None) -> None:
        timeout = self._stop_timeout if timeout is None else timeout
        with self._lock:
            thread = self._thread
            self._stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            if thread is None or not thread.is_alive():
                self._thread = None
                self.state = "stopped"

    def should_stop(self) -> bool:
        return self._stop_event.is_set()

    def sleep(self, seconds: float) -> None:
        self._stop_event.wait(max(0.0, float(seconds)))

    def is_running(self) -> bool:
        with self._lock:
            return self.state in {"starting", "running"} and self._thread is not None and self._thread.is_alive()

    def status(self) -> dict[str, Any]:
        with self._lock:
            thread = self._thread
            alive = bool(thread is not None and thread.is_alive())
            return {
                "running": alive and self.state in {"starting", "running"},
                "state": self.state if alive else "stopped",
                "thread_name": thread.name if thread is not None else None,
                "interval_seconds": self.interval_seconds,
                "started_at": self.started_at,
                "stopped_at": self.stopped_at,
                "last_heartbeat_at": self.last_heartbeat_at,
                "last_run_started_at": self.last_run_started_at,
                "last_run_finished_at": self.last_run_finished_at,
                "last_run_duration_ms": self.last_run_duration_ms,
                "run_count": self.run_count,
                "last_error": self.last_error,
            }


def scheduler_runtime() -> SchedulerRuntime:
    return SchedulerRuntime.shared()


def scheduler_running() -> bool:
    return SchedulerRuntime.shared().is_running()
