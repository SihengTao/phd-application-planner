#!/usr/bin/env python3
"""phd-application-planner · launch.py — start the marimo dashboard, detached and persistent.

Usage:
  python3 launch.py [dashboard.py] [--port N] [--edit] [--no-open]

- Runs `marimo run` (app mode) by default, or `marimo edit` with --edit.
- Detaches into a new process session so the server survives across shells / tool turns.
- Waits for the port to answer, then opens the default browser (unless --no-open).
- Must be run with a Python that has marimo installed (the same interpreter that
  runs this script is reused for `-m marimo`).
"""
import argparse
import os
import signal
import sys
import time
import socket
import subprocess
import shutil
import urllib.request
import webbrowser
from pathlib import Path


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        if port_available(port):
            return port
    raise RuntimeError(f"no free port found in {start}..{start + 49}")


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dashboard",
        nargs="?",
        default="phd_explorer.py",
        help="generated marimo dashboard (default: phd_explorer.py)",
    )
    parser.add_argument("--port", type=_port, help="port to use (default: first free 2740..2789)")
    parser.add_argument("--edit", action="store_true", help="launch marimo edit instead of run")
    parser.add_argument("--no-open", action="store_true", help="do not open the browser")
    return parser


def stop_process_group(proc: subprocess.Popen) -> None:
    """Stop only the detached process group created by this launcher."""

    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        proc.wait(timeout=5)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    app = str(Path(args.dashboard).resolve())
    if not Path(app).exists():
        print(f"error: {app} not found", file=sys.stderr)
        return 1
    # The dashboard imports the Excel exporter lazily. Keep the generated app
    # self-contained even when users followed an older copy-only command.
    for helper in ("excel_export.py", "summary_export.py"):
        helper_src = Path(__file__).resolve().parent / helper
        helper_dst = Path(app).parent / helper
        if helper_src.exists() and helper_src != helper_dst:
            try:
                shutil.copy2(helper_src, helper_dst)
            except OSError as exc:
                print(f"error: could not copy exporter to {helper_dst}: {exc}", file=sys.stderr)
                return 1
    try:
        port = args.port if args.port is not None else free_port(2740)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.port is not None and not port_available(port):
        print(f"error: port {port} is already in use", file=sys.stderr)
        return 1

    mode = "edit" if args.edit else "run"
    py = sys.executable
    # Detached launch so the server persists across shells / tool turns.
    # start_new_session=True puts it in its own session+process group (survives parent exit);
    # do NOT also call os.setsid() — that would double-create the session and fail.
    cmd = [py, "-m", "marimo", mode, app, "--headless", "--no-token", "--port", str(port)]
    log = Path(app).parent / "_marimo_run.log"
    with open(log, "w") as lf:
        proc = subprocess.Popen(cmd, stdout=lf, stderr=lf, start_new_session=True, close_fds=True)

    url = f"http://localhost:{port}"
    ready = False
    for _ in range(60):
        if proc.poll() is not None:
            detail = log.read_text(errors="replace")[-4000:] if log.exists() else ""
            print(f"error: marimo exited before startup (code {proc.returncode}).\n{detail}", file=sys.stderr)
            return proc.returncode or 1
        try:
            with urllib.request.urlopen(url, timeout=1):
                pass
            time.sleep(0.05)
            if proc.poll() is not None:
                continue
            ready = True
            break
        except Exception:
            time.sleep(1)
    if not ready:
        detail = log.read_text(errors="replace")[-4000:] if log.exists() else ""
        stop_process_group(proc)
        print(f"error: dashboard did not become ready at {url} within 60 seconds.\n{detail}", file=sys.stderr)
        return 1
    print(f"dashboard: {url}  (mode={mode}, log={log})")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
