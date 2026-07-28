#!/usr/bin/env python3
"""Validate a workflow result and emit a machine-readable JSON report.

Usage:
  python3 assets/check_data.py [_wf_result.json] [-o REPORT.json] [--online] [--strict]

The default is offline.  Exit status is 1 for validation errors, or also for
warnings when --strict is used.  Input/JSON/output failures use exit status 2.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, Optional, Sequence

try:
    from .data_quality import validate_result
except ImportError:  # Direct script execution: python3 assets/check_data.py
    from data_quality import validate_result


def _failure_report(code: str, path: str, message: str) -> Dict[str, Any]:
    issue = {
        "severity": "error",
        "code": code,
        "path": path,
        "message": message,
    }
    return {
        "schema_version": "2.0",
        "ok": False,
        "valid": False,
        "summary": {
            "programs": 0,
            "advisors": 0,
            "restaurants": 0,
            "sources": 0,
            "claims": 0,
            "errors": 1,
            "warnings": 0,
            "info": 0,
            "online": False,
        },
        "errors": [issue],
        "warnings": [],
        "info": [],
        "issues": [issue],
    }


def _write_report(report: Dict[str, Any], output: Optional[str]) -> None:
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    if output:
        destination = Path(output)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".{}.".format(destination.name),
            suffix=".tmp",
            dir=str(destination.parent),
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, destination)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
    else:
        sys.stdout.write(text)


def _apply_gate(report: Dict[str, Any], strict: bool) -> bool:
    summary = report.get("summary") or {}
    has_errors = bool(summary.get("errors"))
    has_warnings = bool(summary.get("warnings"))
    passed = not has_errors and not (strict and has_warnings)
    report["gate"] = {
        "strict": bool(strict),
        "passed": passed,
    }
    return passed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input",
        nargs="?",
        default="_wf_result.json",
        help="workflow result JSON (default: _wf_result.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="write the JSON report to this file (stdout when omitted)",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="also check recorded URLs over the network using urllib",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return a non-zero status for warnings as well as errors",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with Path(args.input).open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        report = _failure_report("input_error", "$", str(exc))
        _apply_gate(report, args.strict)
        try:
            _write_report(report, args.output)
        except OSError as output_exc:
            print("error writing report: {}".format(output_exc), file=sys.stderr)
        return 2

    report = validate_result(data, online=args.online)
    gate_passed = _apply_gate(report, args.strict)
    try:
        _write_report(report, args.output)
    except OSError as exc:
        print("error writing report: {}".format(exc), file=sys.stderr)
        return 2

    return 0 if gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
