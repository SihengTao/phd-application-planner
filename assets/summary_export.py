#!/usr/bin/env python3
"""Export a concise application tracker (the "summary" result).

Usage:
  python3 assets/summary_export.py OUT_DIR OUTPUT [--format xlsx|gdoc]
                                   [--include-hidden] [--include-notes]

The full workbook (``excel_export.py``) keeps every evidence column. This
exporter keeps only what an applicant tracks day to day, in three tables:

* Application overall — one row per program: region, degree, school, program,
  deadline, match level, program website, application portal;
* Application status — the same programs plus Status / # of Interviews / Notes
  for the applicant to fill in;
* Reach out status — one row per advisor: school, name, lab website, email
  status, notes, meeting.

``--format xlsx`` writes an Excel workbook (also opens in Google Sheets).
``--format gdoc`` writes an ``.html`` file with the same tables; uploading it to
Google Drive and choosing "Open with Google Docs" converts it to a Google Doc.

Programs and advisors hidden in the dashboard (``_pi_hidden.json``) are left
out unless ``--include-hidden`` is given. Private advisor notes are excluded
unless ``--include-notes`` is given.
"""

from __future__ import annotations

import argparse
import html
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

SUMMARY_API_VERSION = 1

FORMULA_PREFIXES = ("=", "+", "-", "@")
STATUS_OPTIONS = [
    "Not started",
    "In progress",
    "Submitted",
    "Interview Invitation",
    "On-site Campus Tour",
    "Admitted",
    "Waitlisted",
    "Rejected",
    "Withdraw",
]
EMAIL_OPTIONS = ["Not sent", "Sent", "Replied", "Follow-up sent", "No reply", "Declined"]
MATCH_FILLS = {"High": "#F4CCCC", "Medium": "#FFF2CC"}
LEGEND = "Red: High match · Yellow: Medium match · Deadline marked (TBC) is not independently confirmed"

OVERVIEW_COLUMNS = [
    ("No.", 6),
    ("Country", 10),
    ("Degree Type", 12),
    ("School Name", 30),
    ("Program", 45),
    ("Deadline", 22),
    ("Match Level", 12),
    ("Program Website", 40),
    ("Application Portal", 40),
]
STATUS_COLUMNS = [
    ("No.", 6),
    ("Country", 10),
    ("Degree Type", 12),
    ("School Name", 30),
    ("Program", 45),
    ("App. Deadline", 22),
    ("Match Level", 12),
    ("Status", 20),
    ("# of Interviews", 15),
    ("Notes", 40),
]
REACH_OUT_COLUMNS = [
    ("No.", 6),
    ("School", 30),
    ("Professor", 24),
    ("Lab Website", 40),
    ("Email Status", 16),
    ("Notes", 48),
    ("Meeting?", 12),
]

_ISO_DATE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_TEXT_DATE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(20\d{2})\b",
    re.IGNORECASE,
)
_MONTHS = {
    name: index
    for index, name in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"],
        start=1,
    )
}


# ---------- record → tracker rows ----------


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _http_url(value: Any) -> str:
    text = _text(value)
    return text if text.lower().startswith(("http://", "https://")) else ""


def match_level(fit: Any) -> str:
    """Map the 0–10 fit score to the tracker's coarse match level."""

    if isinstance(fit, bool) or not isinstance(fit, (int, float)):
        return ""
    if fit >= 7.5:
        return "High"
    if fit >= 5:
        return "Medium"
    return "Low"


def _deadline_date(facts: Mapping[str, Any]) -> str:
    explicit = _text(facts.get("applicationDeadline"))
    if _ISO_DATE.fullmatch(explicit):
        return explicit
    text = _text(facts.get("deadlineAndTests"))
    iso = _ISO_DATE.search(text)
    if iso:
        return iso.group(0)
    written = _TEXT_DATE.search(text)
    if written:
        month = _MONTHS[written.group(1)[:3].lower()]
        return f"{written.group(3)}-{month:02d}-{int(written.group(2)):02d}"
    return ""


def _deadline_confirmed(record: Mapping[str, Any]) -> bool:
    provenance = record.get("provenance")
    checks = provenance.get("checks") if isinstance(provenance, Mapping) else None
    for check in checks or []:
        if (
            isinstance(check, Mapping)
            and check.get("claimPath") == "facts.deadlineAndTests"
        ):
            return check.get("status") in {"confirmed", "corrected"}
    return False


def _deadline(record: Mapping[str, Any], facts: Mapping[str, Any]) -> str:
    date = _deadline_date(facts)
    if not date:
        return "TBC"
    return date if _deadline_confirmed(record) else f"{date} (TBC)"


def _advisors(record: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    block = record.get("pis")
    values = block.get("pis") if isinstance(block, Mapping) else block
    for value in values or []:
        if isinstance(value, Mapping):
            yield value


def _records(research: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(research, Mapping):
        for school, values in research.items():
            for value in values if isinstance(values, list) else []:
                if isinstance(value, Mapping):
                    yield {"school": school, **value}


def summary_tables(
    research: Any,
    *,
    region_order: Optional[Mapping[str, int]] = None,
    program_ids: Optional[Iterable[str]] = None,
    hidden: Optional[Mapping[str, Any]] = None,
    notes: Optional[Mapping[str, str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Return ``{"programs": [...], "advisors": [...]}`` tracker rows.

    ``research`` is the built ``_research_data.json`` object. ``program_ids``
    restricts the export (e.g. to the dashboard's current filter); ``hidden``
    is the dashboard hidden state; ``notes`` maps advisor_id to private text and
    is only passed when the user opted in.
    """

    order = dict(region_order or {})
    wanted = set(program_ids) if program_ids is not None else None
    hidden = hidden or {}
    hidden_programs = set(hidden.get("programs") or [])
    hidden_advisors = set(hidden.get("pis") or [])

    records = [
        record
        for record in _records(research)
        if record.get("program_id") not in hidden_programs
        and (wanted is None or record.get("program_id") in wanted)
    ]
    records.sort(
        key=lambda r: (
            order.get(r.get("region"), len(order)),
            _text(r.get("region")),
            _text(r.get("school")).casefold(),
            -(r.get("facts", {}).get("fitScore") or 0)
            if isinstance(r.get("facts", {}).get("fitScore"), (int, float))
            else 0,
            _text(r.get("program")).casefold(),
        )
    )

    programs: List[Dict[str, Any]] = []
    advisors: List[Dict[str, Any]] = []
    for record in records:
        facts = record.get("facts") if isinstance(record.get("facts"), Mapping) else {}
        programs.append(
            {
                "program_id": record.get("program_id"),
                "country": _text(record.get("region")),
                "degree_type": _text(facts.get("degreeType")) or "PhD",
                "school": _text(record.get("school")),
                "program": _text(record.get("program")),
                "deadline": _deadline(record, facts),
                "match_level": match_level(facts.get("fitScore")),
                "program_url": _http_url(facts.get("programUrl")),
                "portal_url": _http_url(facts.get("applicationPortalUrl")),
            }
        )
        for advisor in _advisors(record):
            advisor_id = advisor.get("advisor_id")
            if advisor_id in hidden_advisors:
                continue
            advisors.append(
                {
                    "advisor_id": advisor_id,
                    "program_id": record.get("program_id"),
                    "school": _text(record.get("school")),
                    "name": _text(advisor.get("name")),
                    "url": _http_url(advisor.get("url")),
                    "notes": _text((notes or {}).get(advisor_id)),
                }
            )

    # One outreach row per person per school, even if they sit in two programs.
    seen = set()
    unique_advisors = []
    for advisor in sorted(advisors, key=lambda a: (a["school"].casefold(), a["name"].casefold())):
        key = (advisor["school"].casefold(), advisor["name"].casefold())
        if advisor["name"] and key not in seen:
            seen.add(key)
            unique_advisors.append(advisor)
    return {"programs": programs, "advisors": unique_advisors}


def _row_values(table: str, rows: List[Dict[str, Any]]) -> List[List[str]]:
    if table == "overview":
        return [
            [str(i), r["country"], r["degree_type"], r["school"], r["program"],
             r["deadline"], r["match_level"], r["program_url"], r["portal_url"]]
            for i, r in enumerate(rows, start=1)
        ]
    if table == "status":
        return [
            [str(i), r["country"], r["degree_type"], r["school"], r["program"],
             r["deadline"], r["match_level"], "", "", ""]
            for i, r in enumerate(rows, start=1)
        ]
    return [
        [str(i), r["school"], r["name"], r["url"], "", r["notes"], ""]
        for i, r in enumerate(rows, start=1)
    ]


def _school_runs(rows: List[Dict[str, Any]]) -> List[tuple]:
    """Return ``(start, length)`` runs of consecutive rows with the same school."""

    runs = []
    start = 0
    for index in range(1, len(rows) + 1):
        if index == len(rows) or rows[index]["school"] != rows[start]["school"]:
            runs.append((start, index - start))
            start = index
    return runs


SHEETS = [
    ("Application overall", "PhD Programs", "overview", "programs", OVERVIEW_COLUMNS),
    ("Application status", "PhD Programs", "status", "programs", STATUS_COLUMNS),
    ("Reach out status", "Faculty outreach", "reach", "advisors", REACH_OUT_COLUMNS),
]


# ---------- writers ----------


def _excel_text(value: str) -> str:
    return "'" + value if value.lstrip().startswith(FORMULA_PREFIXES) else value


def build_summary_xlsx(tables: Mapping[str, List[Dict[str, Any]]]) -> bytes:
    """Render the tracker tables as a template-style ``.xlsx`` workbook."""

    try:
        import xlsxwriter
    except ModuleNotFoundError as exc:
        raise RuntimeError("summary export requires XlsxWriter; install requirements.txt") from exc

    buffer = io.BytesIO()
    workbook = xlsxwriter.Workbook(
        buffer,
        {"in_memory": True, "strings_to_formulas": False, "strings_to_urls": False},
    )
    base = {"border": 1, "text_wrap": True, "valign": "vcenter", "font_name": "Calibri", "font_size": 11}
    title_fmt = workbook.add_format({**base, "bold": True, "align": "center"})
    header_fmt = workbook.add_format({**base, "bold": True, "align": "center"})
    cell_fmt = workbook.add_format(base)
    link_fmt = workbook.add_format({**base, "font_color": "#1155CC", "underline": 1})
    match_fmts = {
        level: workbook.add_format({**base, "bg_color": color})
        for level, color in MATCH_FILLS.items()
    }
    legend_fmt = workbook.add_format({"italic": True, "font_color": "#555555"})

    for sheet_name, title, kind, source, columns in SHEETS:
        rows = tables.get(source) or []
        values = _row_values(kind, rows)
        sheet = workbook.add_worksheet(sheet_name)
        last_col = len(columns) - 1
        sheet.merge_range(0, 0, 0, last_col, title, title_fmt)
        sheet.set_row(0, 22)
        for col, (name, width) in enumerate(columns):
            sheet.set_column(col, col, width)
            sheet.write_string(1, col, name, header_fmt)
        sheet.freeze_panes(2, 0)

        school_col = 3 if kind != "reach" else 1
        for offset, row_values in enumerate(values):
            row = offset + 2
            fill = match_fmts.get(rows[offset].get("match_level")) if kind != "reach" else None
            for col, value in enumerate(row_values):
                fmt = fill if fill and col in (school_col, school_col + 1) else cell_fmt
                if value.startswith(("http://", "https://")):
                    sheet.write_url(row, col, value, link_fmt, string=value)
                else:
                    sheet.write_string(row, col, _excel_text(value), fmt)
        # Merge the school cell across that school's consecutive rows, like the template.
        for start, length in _school_runs(rows):
            if length > 1:
                first = rows[start]
                fill = (
                    match_fmts.get(first.get("match_level"))
                    if kind != "reach"
                    else None
                )
                sheet.merge_range(
                    start + 2, school_col, start + 1 + length, school_col,
                    _excel_text(first["school"]), fill or cell_fmt,
                )

        if rows and kind == "status":
            sheet.data_validation(2, 7, len(rows) + 1, 7, {"validate": "list", "source": STATUS_OPTIONS})
            sheet.data_validation(2, 8, len(rows) + 1, 8, {"validate": "integer", "criteria": ">=", "value": 0})
        if rows and kind == "reach":
            sheet.data_validation(2, 4, len(rows) + 1, 4, {"validate": "list", "source": EMAIL_OPTIONS})
            sheet.data_validation(2, 6, len(rows) + 1, 6, {"validate": "list", "source": ["Yes", "No", "Scheduled"]})
        if kind != "reach":
            sheet.write_string(len(rows) + 3, 0, LEGEND, legend_fmt)

    workbook.set_properties({"title": "PhD application tracker"})
    workbook.close()
    return buffer.getvalue()


def build_summary_html(tables: Mapping[str, List[Dict[str, Any]]]) -> str:
    """Render the tracker tables as HTML that Google Docs imports as tables."""

    cell = "border:1px solid #999;padding:4px 6px;vertical-align:middle;font-family:Calibri,Arial;font-size:11pt"
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>PhD application tracker</title></head><body>",
    ]
    for sheet_name, title, kind, source, columns in SHEETS:
        rows = tables.get(source) or []
        values = _row_values(kind, rows)
        school_col = 3 if kind != "reach" else 1
        span_at = {start: length for start, length in _school_runs(rows)}
        parts.append(f"<h2>{html.escape(sheet_name)}</h2>")
        parts.append("<table style='border-collapse:collapse'>")
        parts.append(
            f"<tr><th colspan='{len(columns)}' style='{cell}'>{html.escape(title)}</th></tr><tr>"
            + "".join(f"<th style='{cell}'>{html.escape(name)}</th>" for name, _ in columns)
            + "</tr>"
        )
        for offset, row_values in enumerate(values):
            fill = MATCH_FILLS.get(rows[offset].get("match_level")) if kind != "reach" else None
            tds = []
            for col, value in enumerate(row_values):
                if col == school_col:
                    if offset not in span_at:
                        continue  # covered by the rowspan above
                    span = f" rowspan='{span_at[offset]}'" if span_at[offset] > 1 else ""
                else:
                    span = ""
                style = cell + (f";background:{fill}" if fill and col in (school_col, school_col + 1) else "")
                text = html.escape(value)
                if value.startswith(("http://", "https://")):
                    text = f"<a href='{html.escape(value, quote=True)}'>{text}</a>"
                tds.append(f"<td{span} style='{style}'>{text}</td>")
            parts.append("<tr>" + "".join(tds) + "</tr>")
        parts.append("</table>")
        if kind == "status":
            parts.append(f"<p><i>Status options: {html.escape(', '.join(STATUS_OPTIONS))}</i></p>")
        if kind != "reach":
            parts.append(f"<p><i>{html.escape(LEGEND)}</i></p>")
    parts.append("</body></html>")
    return "\n".join(parts)


# ---------- CLI ----------


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def tables_from_out_dir(
    out_dir: Path,
    *,
    include_hidden: bool = False,
    include_notes: bool = False,
    program_ids: Optional[Iterable[str]] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    research_path = out_dir / "_research_data.json"
    if not research_path.exists():
        raise FileNotFoundError(f"required input not found: {research_path}")
    config = _load_json(out_dir / "_config.json", {})
    return summary_tables(
        _load_json(research_path, {}),
        region_order=config.get("region_order") if isinstance(config, Mapping) else None,
        program_ids=program_ids,
        hidden=None if include_hidden else _load_json(out_dir / "_pi_hidden.json", {}),
        notes=_load_json(out_dir / "_pi_notes.json", {}) if include_notes else None,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", type=Path, help="built planner output directory")
    parser.add_argument("output", type=Path, help="destination .xlsx or .html file")
    parser.add_argument("--format", choices=["xlsx", "gdoc"], default=None,
                        help="xlsx (Excel / Google Sheets) or gdoc (HTML for Google Docs); default from the output suffix")
    parser.add_argument("--include-hidden", action="store_true", help="keep programs/advisors hidden in the dashboard")
    parser.add_argument("--include-notes", action="store_true", help="copy private advisor notes into Reach out status")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    fmt = args.format or ("gdoc" if args.output.suffix.lower() in {".html", ".htm"} else "xlsx")
    temporary = None
    try:
        tables = tables_from_out_dir(
            args.out_dir, include_hidden=args.include_hidden, include_notes=args.include_notes
        )
        payload = (
            build_summary_xlsx(tables)
            if fmt == "xlsx"
            else build_summary_html(tables).encode("utf-8")
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f".{args.output.name}.", suffix=".tmp", dir=args.output.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
        os.replace(temporary, args.output)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        if temporary is not None and temporary.exists():
            temporary.unlink()
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(
        f"wrote {args.output} ({fmt}; {len(tables['programs'])} programs / "
        f"{len(tables['advisors'])} advisors; private notes "
        f"{'included' if args.include_notes else 'excluded'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
