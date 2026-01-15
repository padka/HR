#!/usr/bin/env python3
"""
Self-healing development server for the admin UI.

Usage:
    python scripts/dev_server.py

The wrapper launches Uvicorn, restarts it whenever Python files change, and
brings the server back up automatically if it crashes for any reason. Command
and watch paths can be customised via CLI flags or environment variables:

    DEVSERVER_CMD="uvicorn backend.apps.bot.app:app --port 8100" \
        python scripts/dev_server.py --watch backend apps
"""

from __future__ import annotations

import argparse
import asyncio
import errno
import os
import shlex
import signal
import socket
import sys
import time
from collections import deque
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

try:
    from watchfiles import awatch
except ImportError as exc:  # pragma: no cover - dev helper dependency
    raise SystemExit(
        "watchfiles is required for scripts/dev_server.py. "
        "Install development dependencies with `pip install -e \".[dev]\"`."
    ) from exc

DEFAULT_CMD = os.environ.get(
    "DEVSERVER_CMD",
    "uvicorn backend.apps.admin_ui.app:app --host 127.0.0.1 --port 8000",
)
DEFAULT_WATCH = tuple(
    filter(
        None,
        os.environ.get(
            "DEVSERVER_WATCH",
            "backend backend/apps scripts tests docs",
        ).split(),
    )
)
DEFAULT_DELAY = float(os.environ.get("DEVSERVER_RESTART_DELAY", "1.5"))
RESTART_WINDOW_SECONDS = 10.0
RESTART_LIMIT = 3
CONFIG_ERROR_HINTS = {
    "asyncpg": {
        "needles": [
            "database_url uses postgresql+asyncpg but asyncpg is not installed",
            "asyncpg is not installed",
        ],
        "message": (
            "[devserver] DATABASE_URL uses postgresql+asyncpg but asyncpg is not installed.\n\n"
            "SQLite fallback:\n"
            "  DATABASE_URL='' make dev-sqlite\n"
            "Postgres setup:\n"
            "  python -m pip install asyncpg\n"
            "  docker compose up -d postgres\n"
            "  DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db make dev\n"
        ),
    },
}


class DevServerFatalError(RuntimeError):
    """Raised when the supervisor decides to stop instead of restarting."""


class DevServer:
    """Supervise a child process and restart it on crashes or file changes."""

    def __init__(
        self,
        command: Sequence[str],
        watch_paths: Sequence[str],
        restart_delay: float = DEFAULT_DELAY,
    ) -> None:
        self.command = list(command)
        self.watch_paths = self._resolve_watch_paths(watch_paths)
        self.restart_delay = max(0.5, restart_delay)
        self._process: asyncio.subprocess.Process | None = None
        self._stop = False
        self._restart_requested = False
        self._stop_event = asyncio.Event()
        self._host_port = self._extract_host_port()
        self._fatal_message: str | None = None
        self._crash_times: deque[float] = deque()
        if any("--reload" in token for token in self.command):
            print(
                "[devserver] warning: command already contains --reload. "
                "The dev server already restarts on changes; double reload can spawn "
                "extra processes and block the port.",
                flush=True,
            )

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self.stop(s)))
            except NotImplementedError:  # pragma: no cover - Windows fallback
                pass

        runner = asyncio.create_task(self._process_loop(), name="devserver-runner")
        watcher = asyncio.create_task(self._watch_loop(), name="devserver-watch")

        finished, pending = await asyncio.wait(
            {runner, watcher},
            return_when=asyncio.FIRST_COMPLETED,
        )
        try:
            for task in finished:
                if task.exception():
                    raise task.exception()
        finally:
            await self.stop()
            for task in pending:
                task.cancel()

    async def stop(self, _sig: signal.Signals | None = None) -> None:
        if self._stop:
            return
        self._stop = True
        self._stop_event.set()
        await self._terminate()

    async def restart(self, reason: str) -> None:
        if self._stop:
            return
        print(f"[devserver] restart requested ({reason})", flush=True)
        self._restart_requested = True
        await self._terminate()

    async def _process_loop(self) -> None:
        while not self._stop:
            config_error_event = asyncio.Event()
            self._fatal_message = None
            while not await self._wait_for_port():
                if self._stop:
                    return
            print(f"[devserver] starting: {' '.join(self.command)}", flush=True)
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_task = asyncio.create_task(
                self._stream_output(self._process.stdout, is_stderr=False),
                name="devserver-stdout",
            )
            stderr_task = asyncio.create_task(
                self._stream_output(
                    self._process.stderr,
                    is_stderr=True,
                    config_event=config_error_event,
                ),
                name="devserver-stderr",
            )
            returncode = await self._process.wait()
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)
            self._process = None

            if self._stop:
                break

            if config_error_event.is_set():
                message = self._fatal_message or "[devserver] configuration error detected, aborting."
                raise DevServerFatalError(message)

            if self._restart_requested:
                self._restart_requested = False
                self._crash_times.clear()
                continue

            if returncode == 0:
                self._crash_times.clear()
            else:
                if self._register_crash_and_should_abort():
                    message = self._fatal_message or self._default_crash_loop_hint()
                    raise DevServerFatalError(message)

            print(
                f"[devserver] process exited with code {returncode}, "
                f"restarting in {self.restart_delay:.1f}s",
                flush=True,
            )
            await asyncio.sleep(self.restart_delay)

    async def _watch_loop(self) -> None:
        async for changes in awatch(*self.watch_paths, stop_event=self._stop_event):
            if self._stop:
                break
            if not changes:
                continue
            await self.restart(f"{len(changes)} file change(s)")

    async def _terminate(self) -> None:
        if not self._process or self._process.returncode is not None:
            return
        self._process.terminate()
        try:
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except asyncio.TimeoutError:
            print("[devserver] process did not exit in time, killing...", flush=True)
            self._process.kill()
            await self._process.wait()
        finally:
            self._process = None

    @staticmethod
    def _resolve_watch_paths(paths: Iterable[str]) -> list[str]:
        resolved: list[str] = []
        missing: list[str] = []
        for path in paths:
            candidate = Path(path).resolve()
            if candidate.exists():
                resolved.append(str(candidate))
            else:
                missing.append(path)
        if missing:
            print(
                "[devserver] warning: skipping non-existent paths:",
                ", ".join(missing),
                flush=True,
            )
        if not resolved:
            resolved.append(str(Path.cwd()))
        return resolved

    def _extract_host_port(self) -> Optional[Tuple[str, int]]:
        host = "0.0.0.0"
        port: Optional[int] = None
        tokens = self.command
        for idx, token in enumerate(tokens):
            if token in {"--port", "-p"} and idx + 1 < len(tokens):
                try:
                    port = int(tokens[idx + 1])
                except ValueError:
                    pass
            elif token.startswith("--port="):
                try:
                    port = int(token.split("=", 1)[1])
                except ValueError:
                    pass
            elif token == "--host" and idx + 1 < len(tokens):
                host = tokens[idx + 1]
            elif token.startswith("--host="):
                host = token.split("=", 1)[1]
        if port is None:
            return None
        if not host:
            host = "0.0.0.0"
        return host, port

    async def _wait_for_port(self) -> bool:
        target = self._host_port
        if target is None:
            return True
        host, port = target
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            sock.close()
            return True
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                return True
            print(
                f"[devserver] port {port} is already in use. "
                f"Use `lsof -ti :{port}` to inspect or kill the blocking process.",
                flush=True,
            )
            await asyncio.sleep(self.restart_delay)
            return False

    def _register_crash_and_should_abort(self) -> bool:
        now = time.monotonic()
        self._crash_times.append(now)
        while self._crash_times and now - self._crash_times[0] > RESTART_WINDOW_SECONDS:
            self._crash_times.popleft()
        if len(self._crash_times) >= RESTART_LIMIT:
            if not self._fatal_message:
                self._fatal_message = self._default_crash_loop_hint()
            return True
        return False

    @staticmethod
    def _default_crash_loop_hint() -> str:
        return (
            f"[devserver] child process crashed {RESTART_LIMIT} times within "
            f"{int(RESTART_WINDOW_SECONDS)}s. Check the traceback above or run "
            "the safe default via `DATABASE_URL='' make dev-sqlite`."
        )

    def _detect_config_error_hint(self, text: str) -> Optional[str]:
        lowered = text.strip().lower()
        if not lowered:
            return None
        for info in CONFIG_ERROR_HINTS.values():
            if any(needle in lowered for needle in info["needles"]):
                return info["message"]
        return None

    async def _stream_output(
        self,
        stream: asyncio.StreamReader | None,
        *,
        is_stderr: bool,
        config_event: asyncio.Event | None = None,
    ) -> None:
        if stream is None:
            return
        target = sys.stderr if is_stderr else sys.stdout
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode(errors="ignore")
            target.write(text)
            target.flush()
            if is_stderr and config_event and not config_event.is_set():
                hint = self._detect_config_error_hint(text)
                if hint:
                    self._fatal_message = hint
                    config_event.set()
                    if self._process and self._process.returncode is None:
                        self._process.terminate()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resilient dev server with auto-restart")
    parser.add_argument(
        "--cmd",
        default=DEFAULT_CMD,
        help=f"Command to run (default: '{DEFAULT_CMD}')",
    )
    parser.add_argument(
        "--watch",
        action="append",
        dest="watch",
        help="Paths to watch for changes (can be provided multiple times)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help=f"Delay before restarting crashed process (default: {DEFAULT_DELAY}s)",
    )
    return parser.parse_args(argv)


async def amain(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    command = shlex.split(args.cmd)
    watch_paths = args.watch or DEFAULT_WATCH
    server = DevServer(command=command, watch_paths=watch_paths, restart_delay=args.delay)
    try:
        await server.run()
    finally:
        await server.stop()


def main() -> None:
    try:
        asyncio.run(amain())
    except DevServerFatalError as exc:
        print(str(exc), flush=True)
        raise SystemExit(1)
    except KeyboardInterrupt:  # pragma: no cover - interactive helper
        print("\n[devserver] stopped by user", flush=True)


if __name__ == "__main__":
    main()
