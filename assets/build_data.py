#!/usr/bin/env python3
"""Build dashboard JSON files from a researched workflow result.

Usage:
  python3 assets/build_data.py INPUT_JSON OUT_DIR [--strict] [--online]

The input may be either the canonical object with a ``programs`` array or a
legacy root-level program array.  A quality report is always written before
the derived dashboard files.  Errors block the build; ``--strict`` also makes
warnings blocking.
"""

import argparse
import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple


APPLICATION_POLICIES = {
    "multiple_allowed",
    "single_only",
    "unknown",
    "conflict",
}


class BuildBlocked(RuntimeError):
    """Raised when the pre-build quality gate does not pass."""


class BuildOperationalError(RuntimeError):
    """Raised when the checker or filesystem cannot complete the build."""


def _quality_api() -> Tuple[Callable[..., str], Callable[..., str], Callable[..., Dict[str, Any]]]:
    """Load the shared quality/identity API in module and script contexts."""

    if __package__:
        from .data_quality import advisor_id, program_id, validate_result
    else:
        from data_quality import advisor_id, program_id, validate_result
    return program_id, advisor_id, validate_result


def _clean_policy_value(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    cleaned = value.strip().lower()
    return cleaned if cleaned in APPLICATION_POLICIES else None


def legacy_application_policy(restriction: Any) -> str:
    """Conservatively map legacy prose to the v2 application-policy enum."""

    if not isinstance(restriction, str) or not restriction.strip():
        return "unknown"
    text = " ".join(restriction.casefold().split())

    # An absence of a published rule is not evidence that multiple applications
    # are permitted.
    unknown_phrases = (
        "no restriction is published",
        "no published restriction",
        "restriction is not published",
        "policy is not published",
        "could not confirm",
        "could not verify",
        "not found",
        "unknown",
        "unclear",
    )
    if any(phrase in text for phrase in unknown_phrases):
        return "unknown"
    if any(word in text for word in ("conflict", "contradict", "disagree")):
        return "conflict"

    # Check prohibitions before permissions so "cannot apply to multiple" can
    # never be captured by a positive "multiple" heuristic.
    single_phrases = (
        "cannot apply to multiple",
        "cannot apply to more than one",
        "may not apply to multiple",
        "may not apply to more than one",
        "only one program",
        "one program only",
        "only one application",
        "one application only",
        "single program",
        "one per cycle",
        "1 program",
        "⛔",
    )
    if any(phrase in text for phrase in single_phrases):
        return "single_only"

    multiple_phrases = (
        "can apply to multiple",
        "may apply to multiple",
        "can apply to more than one",
        "may apply to more than one",
        "multiple applications are allowed",
        "multiple applications allowed",
        "apply to both",
        "no restriction on the number",
        "no restriction on number",
        "✅",
    )
    if any(phrase in text for phrase in multiple_phrases):
        return "multiple_allowed"
    return "unknown"


def application_policy(facts: Mapping[str, Any], program: Mapping[str, Any]) -> str:
    """Return the canonical policy, preferring a structured enum over prose."""

    for container, key in (
        (facts, "applicationPolicy"),
        (facts, "application_policy"),
        (program, "applicationPolicy"),
        (program, "application_policy"),
    ):
        if key not in container:
            continue
        raw = container.get(key)
        cleaned = _clean_policy_value(raw)
        if cleaned is not None:
            return cleaned
        # A non-empty but invalid structured value must not be "repaired" from
        # potentially contradictory prose.
        if raw not in (None, ""):
            return "unknown"
    return legacy_application_policy(facts.get("applicationRestrictions"))


def multi_flag(restriction: Any = "", policy: Optional[str] = None) -> str:
    """Return the legacy dashboard label for a canonical policy."""

    canonical = _clean_policy_value(policy) or legacy_application_policy(restriction)
    if canonical == "multiple_allowed":
        return "✅ multi"
    if canonical == "single_only":
        return "⛔ 1 only"
    return ""


def _nonnegative_number(value: Any) -> Optional[Any]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < 0:
        return None
    return value


def _tri_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        cleaned = value.strip().casefold()
        if cleaned in {"true", "yes", "1"}:
            return True
        if cleaned in {"false", "no", "0"}:
            return False
    return None


def _currency(value: Any) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip().upper()


def _floor_state(
    raw_amount: Any,
    amount: Optional[Any],
    reported: Any,
    floor: Any,
    amount_currency: Any,
    floor_currency: Any,
) -> Optional[bool]:
    # The legacy -1 sentinel means "not found", never "below the floor."
    if (
        isinstance(raw_amount, (int, float))
        and not isinstance(raw_amount, bool)
        and math.isfinite(raw_amount)
        and raw_amount < 0
    ):
        return None

    comparable_floor = _nonnegative_number(floor)
    amount_ccy = _currency(amount_currency)
    floor_ccy = _currency(floor_currency)
    if (
        amount is not None
        and comparable_floor is not None
        and amount_ccy is not None
        and floor_ccy is not None
        and amount_ccy == floor_ccy
    ):
        return bool(amount >= comparable_floor)
    return _tri_bool(reported)


def _json_safe(value: Any) -> Any:
    """Replace non-finite floats recursively so emitted JSON stays standard."""

    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _programs(result: Any) -> List[Any]:
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        programs = result.get("programs", [])
        if programs is None:
            return []
        if isinstance(programs, list):
            return programs
        raise ValueError("input field 'programs' must be a list")
    raise ValueError("input root must be an object or a list")


def _workflow_payload(result: Any) -> Any:
    """Mirror the validator's one-level workflow-envelope compatibility."""

    if isinstance(result, dict) and "programs" not in result:
        nested = result.get("result")
        if isinstance(nested, (dict, list)):
            return nested
    return result


def _advisor_container(program: Mapping[str, Any]) -> Tuple[Dict[str, Any], List[Any]]:
    raw = program.get("pis")
    if isinstance(raw, dict):
        container = copy.deepcopy(raw)
        candidates = raw.get("pis")
        if candidates is None:
            candidates = raw.get("advisors")
        if candidates is None:
            candidates = raw.get("faculty")
    elif isinstance(raw, list):
        container = {}
        candidates = raw
    elif raw is None:
        container = {}
        candidates = program.get("advisors")
        faculty = program.get("faculty")
        if candidates is None:
            if isinstance(faculty, dict):
                candidates = faculty.get("faculty")
            elif isinstance(faculty, list):
                candidates = faculty
    else:
        raise ValueError("program 'pis' must be an object, a list, or null")

    if candidates is None:
        candidates = []
    if not isinstance(candidates, list):
        raise ValueError("program advisor collection must be a list")
    return container, candidates


def _report_entries(report: Mapping[str, Any], severity: str) -> List[Any]:
    direct = report.get("errors" if severity == "error" else "warnings") or []
    if not isinstance(direct, list):
        direct = [direct]
    if direct:
        return list(direct)
    return [
        issue
        for issue in (report.get("issues") or [])
        if isinstance(issue, dict)
        and str(issue.get("severity") or "").casefold() == severity
    ]


def _dump_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            value,
            handle,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        handle.write("\n")


def _write_json(path: Path, value: Any) -> None:
    """Atomically write one JSON file through a uniquely named sibling."""

    temporary: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            handle.write("\n")
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _write_derived_pair(
    destination: Path,
    research: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    """Commit both derived JSON files as one rollback-protected generation."""

    targets = (
        destination / "_research_data.json",
        destination / "_rows.json",
    )
    values = (research, rows)

    # A unique directory prevents concurrent builders from sharing stage or
    # backup names.  Both JSON documents are fully materialized before either
    # visible output is replaced.
    with tempfile.TemporaryDirectory(
        dir=destination,
        prefix=".build-data-",
    ) as temporary_name:
        temporary = Path(temporary_name)
        staged = (
            temporary / "staged-research.json",
            temporary / "staged-rows.json",
        )
        backups = (
            temporary / "backup-research.json",
            temporary / "backup-rows.json",
        )
        for stage_path, value in zip(staged, values):
            _dump_json(stage_path, value)

        had_existing = []
        for target, backup in zip(targets, backups):
            exists = target.exists()
            had_existing.append(exists)
            if exists:
                shutil.copy2(target, backup)

        try:
            for stage_path, target in zip(staged, targets):
                os.replace(stage_path, target)
        except Exception as commit_error:
            rollback_errors = []
            for target, backup, existed in zip(targets, backups, had_existing):
                try:
                    if existed:
                        os.replace(backup, target)
                    elif target.exists():
                        target.unlink()
                except Exception as rollback_error:
                    rollback_errors.append(f"{target.name}: {rollback_error}")
            if rollback_errors:
                detail = "; ".join(rollback_errors)
                raise BuildOperationalError(
                    f"derived-file commit failed ({commit_error}); "
                    f"rollback also failed ({detail})"
                ) from commit_error
            raise


def _checker_failure(exc: Exception) -> Dict[str, Any]:
    message = f"Quality checker failed: {exc}"
    return {
        "schema_version": "2.0",
        "ok": False,
        "errors": [message],
        "warnings": [],
        "issues": [
            {
                "severity": "error",
                "code": "checker_failure",
                "path": "$",
                "message": message,
                "suggestion": "Fix the checker or input before rebuilding.",
            }
        ],
    }


def build_outputs(
    result: Any,
    out_dir: Any,
    *,
    strict: bool = False,
    online: bool = False,
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    """Validate and build ``_research_data.json`` plus ``_rows.json``."""

    destination = Path(out_dir)
    destination.mkdir(parents=True, exist_ok=True)
    report_path = destination / "_quality_report.json"

    try:
        make_program_id, make_advisor_id, validate_result = _quality_api()
        report = validate_result(result, online=online)
        if not isinstance(report, dict):
            raise TypeError("validate_result() must return a report object")
    except Exception as exc:
        report = _checker_failure(exc)
        _write_json(report_path, report)
        raise BuildOperationalError(report["errors"][0]) from exc

    _write_json(report_path, report)
    errors = _report_entries(report, "error")
    warnings = _report_entries(report, "warning")
    if errors:
        raise BuildBlocked(f"quality gate found {len(errors)} error(s); see {report_path}")
    if strict and warnings:
        raise BuildBlocked(
            f"strict quality gate found {len(warnings)} warning(s); see {report_path}"
        )

    payload = _workflow_payload(result)
    if isinstance(payload, dict):
        root_floor = payload.get("floor", payload.get("stipend_floor"))
        root_currency = payload.get("currency")
    else:
        root_floor = None
        root_currency = None

    research: Dict[str, List[Dict[str, Any]]] = {}
    rows: List[Dict[str, Any]] = []

    for index, raw_program in enumerate(_programs(payload)):
        if raw_program is None:
            continue
        if not isinstance(raw_program, dict):
            raise ValueError(f"programs[{index}] must be an object")

        record = copy.deepcopy(raw_program)
        facts_raw = record.get("facts")
        if facts_raw is None:
            facts: Dict[str, Any] = {}
        elif isinstance(facts_raw, dict):
            facts = copy.deepcopy(facts_raw)
        else:
            raise ValueError(f"programs[{index}].facts must be an object or null")

        region = record.get("region") or ""
        school = record.get("school") or "Unknown"
        program_name = record.get("program")
        # Canonical program identity intentionally excludes list order and other
        # mutable display metadata.  The shared helper owns the exact hash format.
        pid = make_program_id(region, school, program_name)

        raw_amount = facts.get("stipendUSD")
        amount = _nonnegative_number(raw_amount)
        program_floor = record.get("floor", root_floor)
        floor_currency = record.get("currency", root_currency)
        amount_currency = facts.get("stipendCurrency") or floor_currency
        meets_floor = _floor_state(
            raw_amount,
            amount,
            facts.get("meetsFloor"),
            program_floor,
            amount_currency,
            floor_currency,
        )
        policy = application_policy(facts, record)
        facts["stipendUSD"] = amount
        facts["meetsFloor"] = meets_floor
        facts["applicationPolicy"] = policy

        pis_container, raw_advisors = _advisor_container(record)
        advisors: List[Dict[str, Any]] = []
        for advisor_index, raw_advisor in enumerate(raw_advisors):
            if not isinstance(raw_advisor, dict):
                raise ValueError(
                    f"programs[{index}].pis.pis[{advisor_index}] must be an object"
                )
            advisor = copy.deepcopy(raw_advisor)
            for metric in ("hIndex", "citations"):
                if metric in advisor:
                    advisor[metric] = _nonnegative_number(advisor.get(metric))
            aid = make_advisor_id(pid, advisor.get("name"))
            advisor["program_id"] = pid
            advisor["advisor_id"] = aid
            advisors.append(_json_safe(advisor))
        pis_container["pis"] = advisors

        outcomes = record.get("out")
        if outcomes is None:
            outcomes = record.get("outcomes")
        if outcomes is None:
            outcomes = {}
        if not isinstance(outcomes, dict):
            raise ValueError(f"programs[{index}].out must be an object or null")

        record["program_id"] = pid
        record["region"] = region
        record["school"] = school
        record["program"] = program_name
        record["facts"] = facts
        record["pis"] = pis_container
        record["out"] = copy.deepcopy(outcomes)
        record = _json_safe(record)

        research.setdefault(school, []).append(record)
        cohort = facts.get("cohortSize")
        rows.append(
            {
                "program_id": pid,
                "region": region,
                "school": school,
                "program": program_name,
                "city": record.get("city") or facts.get("city") or "",
                "usd": amount,
                "floor": meets_floor,
                "fit": _json_safe(facts.get("fitScore")),
                "application_policy": policy,
                "multi": multi_flag(facts.get("applicationRestrictions"), policy),
                "cohort": "" if cohort is None else cohort,
            }
        )

    _write_derived_pair(destination, research, rows)
    return research, rows


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_json", type=Path, help="workflow-result JSON object or list")
    parser.add_argument("out_dir", type=Path, help="directory for derived dashboard files")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="block the build when the checker reports warnings",
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="allow the checker to perform URL reachability checks",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        with args.input_json.open(encoding="utf-8") as handle:
            result = json.load(handle)
        research, rows = build_outputs(
            result,
            args.out_dir,
            strict=args.strict,
            online=args.online,
        )
    except BuildBlocked as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (
        BuildOperationalError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    n_advisors = sum(
        len((record.get("pis") or {}).get("pis") or [])
        for records in research.values()
        for record in records
    )
    print(
        "wrote _research_data.json "
        f"({len(rows)} programs / {n_advisors} advisors), _rows.json, "
        f"and _quality_report.json to {args.out_dir}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
