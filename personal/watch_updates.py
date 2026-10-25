"""Refresh a clean local main checkout and supervise only services we launch.

Run ``python -m personal.watch_updates --voice`` for foreground supervision.
Run ``python -m personal.watch_updates --once`` to refresh without starting
services. Stop existing services yourself before using --once. This supervisor
does not register an OS service and runs only while its foreground process lives.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


class UpdateFailure(RuntimeError):
    """An update could not be completed; operator attention is required."""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    # Never echo a remote URL, credential-bearing stderr, or Git configuration.
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateFailure("Git operation failed or timed out") from exc


def _required(root: Path, *args: str) -> str:
    result = _git(root, *args)
    if result.returncode:
        raise UpdateFailure(f"Git {args[0]} failed; no changes were discarded")
    return result.stdout.strip()


def refresh(
    root: Path = ROOT,
    *,
    stop: Callable[[], None] = lambda: None,
    start: Callable[[], None] = lambda: None,
    emit: Callable[[str], None] = print,
) -> bool:
    """Fast-forward clean main only; install and restart only after a change."""
    branch = _required(root, "symbolic-ref", "--short", "HEAD")
    if branch != "main":
        emit("Update skipped: check out main to enable local automatic updates.")
        return False
    if _required(root, "status", "--porcelain", "--untracked-files=all"):
        emit("Update skipped: local changes or untracked files must be preserved.")
        return False
    _required(root, "fetch", "--quiet", "origin", "main")
    head = _required(root, "rev-parse", "HEAD")
    # FETCH_HEAD identifies the branch fetched even with a narrow remote refspec.
    target = _required(root, "rev-parse", "FETCH_HEAD")
    if head == target:
        emit("Local Jarvis already matches origin/main.")
        return False
    ancestor = _git(root, "merge-base", "--is-ancestor", head, target)
    if ancestor.returncode == 1:
        emit("Update skipped: main has local commits or diverges from origin/main.")
        return False
    if ancestor.returncode:
        raise UpdateFailure("Could not verify fast-forward ancestry")
    if _required(root, "symbolic-ref", "--short", "HEAD") != "main":
        emit("Update skipped: branch changed during the update check.")
        return False
    if _required(root, "status", "--porcelain", "--untracked-files=all"):
        emit("Update skipped: files changed during the update check.")
        return False
    stop()
    _required(root, "merge", "--ff-only", target)
    emit("Fast-forward applied; refreshing pinned dependencies and frontend.")
    try:
        result = subprocess.run(["bash", "personal/setup.sh"], cwd=root, check=False)
    except OSError as exc:
        raise UpdateFailure("Setup could not start; services remain stopped") from exc
    if result.returncode:
        raise UpdateFailure(
            "Setup failed after the fast-forward; services remain stopped. "
            "Fix setup and restart manually. No Git reset was performed."
        )
    start()
    emit("Local Jarvis updated successfully.")
    return True


class Services:
    """Own child process groups, never discover or kill unrelated servers."""

    def __init__(self, root: Path, voice: bool):
        self.root = root
        self.voice = voice
        self.children: list[subprocess.Popen] = []

    def start(self) -> None:
        commands = [["bash", "personal/start.sh"]]
        if self.voice:
            commands.append([sys.executable, "-m", "personal.voice"])
        try:
            for command in commands:
                self.children.append(
                    subprocess.Popen(
                        command,
                        cwd=self.root,
                        start_new_session=True,
                    )
                )
        except OSError as exc:
            self.stop()
            raise UpdateFailure("A Jarvis service could not start") from exc

    def check(self) -> None:
        for child in self.children:
            code = child.poll()
            if code is not None:
                raise UpdateFailure(
                    f"A supervised Jarvis service exited (status {code}); "
                    "inspect its output and restart manually."
                )

    def stop(self) -> None:
        for child in self.children:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for child in self.children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=10)
        self.children.clear()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interval", type=int, default=3600, metavar="SECONDS")
    parser.add_argument("--voice", action="store_true", help="also supervise voice UI")
    parser.add_argument("--once", action="store_true", help="refresh only; no services")
    args = parser.parse_args(argv)
    if args.interval < 60:
        parser.error("--interval must be at least 60 seconds")
    services = Services(ROOT, args.voice)
    stopped = threading.Event()

    def shutdown(_signum: int, _frame: object) -> None:
        stopped.set()

    previous = {
        sig: signal.signal(sig, shutdown) for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        if args.once:
            refresh()
            return 0
        services.start()
        deadline = time.monotonic() + args.interval
        print("Automatic local updates active while this process runs.", flush=True)
        while not stopped.wait(1):
            services.check()
            if time.monotonic() >= deadline:
                refresh(stop=services.stop, start=services.start)
                deadline = time.monotonic() + args.interval
        return 0
    except UpdateFailure as exc:
        print(f"Jarvis updater stopped: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        services.stop()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
