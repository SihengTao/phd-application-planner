#!/usr/bin/env python3
"""Create a privacy-safe Excel workbook from built planner data.

Usage:
  python3 assets/excel_export.py OUT_DIR OUTPUT.xlsx [--include-notes]

The dashboard imports :func:`build_excel_bytes` directly. The CLI reads the
derived JSON files in ``OUT_DIR``. Private advisor notes are excluded unless
``--include-notes`` is explicitly supplied.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence

import pandas as pd


FORMULA_PREFIXES = ("=", "+", "-", "@")
PRIVATE_ADVISOR_COLUMNS = {
    "note",
    "notes",
    "my_note",
    "private_note",
    "my_private_note",
}
SHEET_COLORS = {
    "Programs": "#2563EB",
    "Advisors": "#7C3AED",
    "Restaurants": "#DC2626",
    "Sources": "#059669",
    "Quality": "#D97706",
    "Priority": "#0891B2",
    "Metadata": "#64748B",
}
EXPORTER_API_VERSION = 2


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value) or math.isinf(value)
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    return bool(missing) if isinstance(missing, bool) else False


def _safe_cell(value: Any) -> Any:
    """Return a scalar that Excel will store as data, never as a formula."""

    if _is_missing(value):
        return None
    if isinstance(value, (dict, list, tuple, set)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    elif isinstance(value, (datetime, pd.Timestamp)):
        value = value.isoformat()
    elif not isinstance(value, (str, int, float, bool)):
        value = str(value)
    if isinstance(value, str) and value.lstrip().startswith(FORMULA_PREFIXES):
        return "'" + value
    return value


def _frame(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value.copy()
    if isinstance(value, Mapping):
        return pd.DataFrame([dict(value)])
    return pd.DataFrame(value).copy()


def _safe_frame(value: Any, *, drop_private_notes: bool = False) -> pd.DataFrame:
    frame = _frame(value)
    if drop_private_notes:
        to_drop = [
            column
            for column in frame.columns
            if str(column).strip().casefold() in PRIVATE_ADVISOR_COLUMNS
        ]
        frame = frame.drop(columns=to_drop, errors="ignore")
    frame.columns = [_safe_cell(str(column)) for column in frame.columns]
    for column in frame.columns:
        frame[column] = frame[column].map(_safe_cell)
    return frame


def _safe_metadata(metadata: Optional[Mapping[str, Any]]) -> pd.DataFrame:
    records = []
    for key, value in (metadata or {}).items():
        key_text = str(key)
        lowered = key_text.casefold()
        if "path" in lowered or "directory" in lowered:
            continue
        if isinstance(value, str):
            try:
                if Path(value).expanduser().is_absolute():
                    continue
            except (OSError, RuntimeError, ValueError):
                pass
        records.append({"key": _safe_cell(key_text), "value": _safe_cell(value)})
    return pd.DataFrame(records, columns=["key", "value"])


def _format_sheet(writer: pd.ExcelWriter, sheet_name: str, frame: pd.DataFrame) -> None:
    workbook = writer.book
    worksheet = writer.sheets[sheet_name]
    header = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": SHEET_COLORS[sheet_name],
            "border": 0,
            "align": "left",
            "valign": "vcenter",
        }
    )
    body = workbook.add_format({"valign": "top"})
    wrapped = workbook.add_format({"valign": "top", "text_wrap": True})
    worksheet.hide_gridlines(2)
    worksheet.set_tab_color(SHEET_COLORS[sheet_name])
    worksheet.freeze_panes(1, 0)
    worksheet.set_row(0, 24)

    for index, column in enumerate(frame.columns):
        worksheet.write(0, index, str(column), header)
        sample = [str(column)]
        if not frame.empty:
            sample.extend(
                "" if value is None else str(value)
                for value in frame[column].head(250)
            )
        longest = max((len(text) for text in sample), default=8)
        lowered = str(column).casefold()
        should_wrap = (
            longest > 35
            or any(
                token in lowered
                for token in (
                    "rationale",
                    "research",
                    "require",
                    "evidence",
                    "message",
                    "note",
                    "source",
                    "outcome",
                    "placement",
                    "address",
                    "url",
                )
            )
        )
        width = min(52, max(11, longest + 2))
        worksheet.set_column(index, index, width, wrapped if should_wrap else body)

    if len(frame.columns):
        last_row = max(1, len(frame))
        worksheet.autofilter(0, 0, last_row, len(frame.columns) - 1)
    if sheet_name == "Quality" and "severity" in frame.columns and len(frame):
        severity_col = frame.columns.get_loc("severity")
        worksheet.conditional_format(
            1,
            severity_col,
            len(frame),
            severity_col,
            {
                "type": "text",
                "criteria": "containing",
                "value": "error",
                "format": workbook.add_format(
                    {"bg_color": "#FEE2E2", "font_color": "#991B1B"}
                ),
            },
        )
        worksheet.conditional_format(
            1,
            severity_col,
            len(frame),
            severity_col,
            {
                "type": "text",
                "criteria": "containing",
                "value": "warning",
                "format": workbook.add_format(
                    {"bg_color": "#FEF3C7", "font_color": "#92400E"}
                ),
            },
        )


def build_excel_bytes(
    programs_df: Any,
    advisors_df: Any,
    restaurants_df: Any,
    sources_df: Any,
    quality_df: Any,
    metadata: Optional[Mapping[str, Any]],
    *,
    priority_df: Any = None,
    include_notes: bool = False,
) -> bytes:
    """Build and return an in-memory ``.xlsx`` workbook."""

    sheets = [
        ("Programs", _safe_frame(programs_df)),
        (
            "Advisors",
            _safe_frame(advisors_df, drop_private_notes=not include_notes),
        ),
        ("Restaurants", _safe_frame(restaurants_df)),
        ("Sources", _safe_frame(sources_df)),
        ("Quality", _safe_frame(quality_df)),
        ("Priority", _safe_frame(priority_df)),
    ]
    metadata_frame = _safe_metadata(metadata)
    buffer = io.BytesIO()
    try:
        with pd.ExcelWriter(
            buffer,
            engine="xlsxwriter",
            engine_kwargs={
                "options": {
                    "strings_to_formulas": False,
                    "strings_to_urls": False,
                    "nan_inf_to_errors": False,
                }
            },
        ) as writer:
            for sheet_name, frame in sheets:
                if frame.empty and not len(frame.columns):
                    continue
                frame.to_excel(writer, sheet_name=sheet_name, index=False)
                _format_sheet(writer, sheet_name, frame)
            metadata_frame.to_excel(writer, sheet_name="Metadata", index=False)
            _format_sheet(writer, "Metadata", metadata_frame)
            writer.book.set_properties(
                {
                    "title": "PhD Application Planner export",
                    "subject": "Evidence-aware application research snapshot",
                    "comments": (
                        "Time-sensitive claims must be rechecked against linked "
                        "official sources."
                    ),
                }
            )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Excel export requires XlsxWriter; install requirements.txt"
        ) from exc
    return buffer.getvalue()


def _load_json(path: Path, *, required: bool, default: Any) -> Any:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"required input not found: {path}")
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc


def _as_text(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return value


def _verification_summary(record: Mapping[str, Any]) -> Dict[str, Any]:
    provenance = record.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    verification = record.get("verification")
    verification = verification if isinstance(verification, Mapping) else {}

    checks = provenance.get("checks")
    if not isinstance(checks, list):
        checks = verification.get("claimChecks")
    checks = checks if isinstance(checks, list) else []
    conflicts = provenance.get("conflicts")
    conflicts = conflicts if isinstance(conflicts, list) else []
    statuses = [
        check.get("status")
        for check in checks
        if isinstance(check, Mapping) and isinstance(check.get("status"), str)
    ]
    verification_status = verification.get("status")
    if not verification_status:
        verification_status = next(
            (
                status
                for status in ("conflict", "unresolved", "corrected", "confirmed")
                if status in statuses
            ),
            "unknown",
        )
    return {
        "verification_status": verification_status,
        "verification_checked_at": verification.get("checkedAt"),
        "verification_conflict": bool(
            verification.get("conflict")
            or conflicts
            or "conflict" in statuses
        ),
        "provenance_research_status": provenance.get("researchStatus"),
        "check_count": len(checks),
        "conflict_count": len(conflicts),
        "unresolved_check_count": statuses.count("unresolved"),
        "corrected_check_count": statuses.count("corrected"),
    }


def _records(research: Mapping[str, Any]) -> Iterable[Dict[str, Any]]:
    for school, values in research.items():
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, Mapping):
                record = dict(value)
                record.setdefault("school", school)
                yield record


def _advisor_values(record: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    block = record.get("pis")
    if isinstance(block, Mapping):
        values = block.get("pis") or block.get("advisors") or block.get("faculty")
    elif isinstance(block, list):
        values = block
    else:
        faculty = record.get("faculty")
        values = faculty.get("faculty") if isinstance(faculty, Mapping) else faculty
    for value in values or []:
        if isinstance(value, Mapping):
            yield value


def _source_values(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, Mapping):
        for source_id, source in value.items():
            if isinstance(source, Mapping):
                item = dict(source)
                item.setdefault("id", str(source_id))
                yield item
            elif isinstance(source, str):
                yield {"id": str(source_id), "url": source}
        return
    for source in value or []:
        if isinstance(source, Mapping):
            yield dict(source)
        elif isinstance(source, str):
            yield {"url": source}


def _flatten_cli(out_dir: Path, *, include_notes: bool) -> Dict[str, Any]:
    research = _load_json(
        out_dir / "_research_data.json", required=True, default={}
    )
    rows = _load_json(out_dir / "_rows.json", required=True, default=[])
    config = _load_json(out_dir / "_config.json", required=False, default={})
    quality = _load_json(
        out_dir / "_quality_report.json", required=False, default={}
    )
    if not isinstance(research, Mapping):
        raise ValueError("_research_data.json must contain an object")
    if not isinstance(rows, list):
        raise ValueError("_rows.json must contain an array")
    if not isinstance(config, Mapping):
        raise ValueError("_config.json must contain an object")
    if not isinstance(quality, Mapping):
        raise ValueError("_quality_report.json must contain an object")

    row_by_id = {
        row.get("program_id"): row
        for row in rows
        if isinstance(row, Mapping) and row.get("program_id")
    }
    programs = []
    advisors = []
    restaurants = []
    sources = []
    seen_sources = set()
    for record in _records(research):
        program_id = record.get("program_id")
        base = {
            "program_id": program_id,
            "region": record.get("region"),
            "school": record.get("school"),
            "program": record.get("program"),
            "city": record.get("city"),
            "research_status": record.get("researchStatus"),
            **_verification_summary(record),
        }
        base.update(dict(row_by_id.get(program_id) or {}))
        for prefix, block in (
            ("facts", record.get("facts")),
            ("outcomes", record.get("out") or record.get("outcomes")),
        ):
            if isinstance(block, Mapping):
                for key, value in block.items():
                    if key not in {"sources", "claimChecks", "evidenceChecks", "errors"}:
                        base[f"{prefix}.{key}"] = _as_text(value)
        programs.append(base)

        advisor_records = list(_advisor_values(record))
        for advisor in advisor_records:
            advisors.append(
                {
                    "program_id": program_id,
                    "region": record.get("region"),
                    "school": record.get("school"),
                    "program": record.get("program"),
                    **{key: _as_text(value) for key, value in advisor.items()},
                }
            )

        food = record.get("nearbyFood")
        food_values = (
            food.get("restaurants", [])
            if isinstance(food, Mapping)
            else record.get("restaurants", [])
        )
        for restaurant in food_values or []:
            if isinstance(restaurant, Mapping):
                restaurants.append(
                    {
                        "program_id": program_id,
                        "school": record.get("school"),
                        "program": record.get("program"),
                        **{
                            key: _as_text(value)
                            for key, value in restaurant.items()
                        },
                    }
                )

        source_blocks = []
        provenance = record.get("provenance")
        if isinstance(provenance, Mapping):
            source_blocks.append(("program", provenance.get("sources", [])))
        facts = record.get("facts")
        if isinstance(facts, Mapping):
            for key in ("sourceRecords", "source_records", "sources", "stipend_sources"):
                source_blocks.append((f"facts:{key}", facts.get(key, [])))
        outcomes = record.get("out") or record.get("outcomes")
        if isinstance(outcomes, Mapping):
            for key in ("sourceRecords", "source_records", "sources"):
                source_blocks.append((f"outcomes:{key}", outcomes.get(key, [])))
        pis_block = record.get("pis")
        if isinstance(pis_block, Mapping):
            for key in ("sourceRecords", "source_records", "sources"):
                source_blocks.append((f"advisors:{key}", pis_block.get(key, [])))
        for advisor in advisor_records:
            advisor_scope = f"advisor:{advisor.get('advisor_id') or advisor.get('name') or ''}"
            for key in ("sourceRecords", "source_records", "sources"):
                source_blocks.append((advisor_scope, advisor.get(key, [])))
        if isinstance(food, Mapping):
            source_blocks.append(("nearbyFood", food.get("sources", [])))
        for scope, block in source_blocks:
            for source in _source_values(block):
                identity = (
                    program_id,
                    source.get("id") or "",
                    source.get("url") or "",
                    scope,
                )
                if identity in seen_sources:
                    continue
                seen_sources.add(identity)
                sources.append(
                    {
                        "program_id": program_id,
                        "school": record.get("school"),
                        "program": record.get("program"),
                        "scope": scope,
                        **{
                            key: _as_text(value)
                            for key, value in source.items()
                        },
                    }
                )

    if include_notes:
        notes = _load_json(out_dir / "_pi_notes.json", required=False, default={})
        if not isinstance(notes, Mapping):
            raise ValueError("_pi_notes.json must contain an advisor_id-to-text object")
        for advisor in advisors:
            advisor["my_private_note"] = notes.get(advisor.get("advisor_id"), "")

    issues = quality.get("issues") or []
    if not isinstance(issues, list):
        issues = [{"severity": "error", "message": "quality issues is not an array"}]
    metadata = {
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "all",
        "field": config.get("field") or "",
        "discipline_mode": config.get("discipline_mode")
        or config.get("disciplineMode")
        or "",
        "application_cycle": config.get("application_cycle") or "",
        "currency": config.get("currency") or "",
        "stipend_floor": config.get("stipend_floor"),
        "includes_private_notes": include_notes,
        "warning": (
            "Web-research snapshot. Re-check time-sensitive claims on linked "
            "official pages."
        ),
    }
    return {
        "programs": pd.DataFrame(programs),
        "advisors": pd.DataFrame(advisors),
        "restaurants": pd.DataFrame(restaurants),
        "sources": pd.DataFrame(sources),
        "quality": pd.DataFrame(
            [value for value in issues if isinstance(value, Mapping)]
        ),
        "metadata": metadata,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path, help="built planner output directory")
    parser.add_argument("output", type=Path, help="destination .xlsx file")
    parser.add_argument(
        "--include-notes",
        action="store_true",
        help="include private advisor notes by stable advisor_id",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        frames = _flatten_cli(args.out_dir, include_notes=args.include_notes)
        payload = build_excel_bytes(
            frames["programs"],
            frames["advisors"],
            frames["restaurants"],
            frames["sources"],
            frames["quality"],
            frames["metadata"],
            include_notes=args.include_notes,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f".{args.output.name}.",
            suffix=".tmp",
            dir=args.output.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        os.replace(temporary, args.output)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        try:
            if "temporary" in locals() and temporary.exists():
                temporary.unlink()
        except OSError:
            pass
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"wrote {args.output} "
        f"(private notes {'included' if args.include_notes else 'excluded'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
