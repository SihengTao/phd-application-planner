# Result outputs

Every run ends with the marimo dashboard. On top of it the user chooses a **result version**
and a **destination** during intake (`_config.json.export`), and can change both later in the
dashboard's Export panel.

| Version | What it contains | Destinations | Producer |
|---|---|---|---|
| `concise` (default) | Application tracker: program overview, application status, faculty outreach | Excel `.xlsx` (also opens in Google Sheets) or Google Docs | `assets/summary_export.py` |
| `full` | Every evidence column: Programs, Advisors, Restaurants, Sources, Quality, Priority, Metadata | Excel `.xlsx` | `assets/excel_export.py` |
| `both` | Both of the above | as above | both |

## Concise tracker layout

Three tables, each with a merged title row, a header row, thin borders, wrapped text, and the
school cell merged across that school's consecutive rows.

1. **Application overall** — `No. · Country · Degree Type · School Name · Program · Deadline ·
   Match Level · Program Website · Application Portal`
2. **Application status** — `No. · Country · Degree Type · School Name · Program · App. Deadline ·
   Match Level · Status · # of Interviews · Notes`. Status is a dropdown (Not started, In progress,
   Submitted, Interview Invitation, On-site Campus Tour, Admitted, Waitlisted, Rejected,
   Withdraw); the last three columns are left for the applicant.
3. **Reach out status** — `No. · School · Professor · Lab Website · Email Status · Notes ·
   Meeting?`. One row per person per school; Email Status and Meeting? are dropdowns.

Field derivation:

| Column | Source | Rule |
|---|---|---|
| Country | `region` | region key from the config |
| Degree Type | `facts.degreeType` | defaults to `PhD` |
| Deadline | `facts.applicationDeadline`, else the first date in `facts.deadlineAndTests` | suffix `(TBC)` unless the independent check of `facts.deadlineAndTests` is `confirmed` or `corrected`; `TBC` if no date |
| Match Level | `facts.fitScore` | ≥ 7.5 `High` (red fill), ≥ 5 `Medium` (yellow fill), else `Low`; blank if unscored |
| Program Website / Application Portal | `facts.programUrl` / `facts.applicationPortalUrl` | `http(s)` only, otherwise blank |
| Professor / Lab Website | advisor `name` / `url` | advisors hidden in the dashboard are skipped |
| Notes (outreach) | `_pi_notes.json` | only with explicit private-notes opt-in |

Programs and advisors the user hid in the dashboard (`_pi_hidden.json`) are excluded unless
`--include-hidden` is passed.

## Commands

```bash
# concise → Excel / Google Sheets
python3 "<skill>/assets/summary_export.py" "<out>" "<out>/phd_application_tracker.xlsx"

# concise → Google Docs (HTML that Google Docs converts on import)
python3 "<skill>/assets/summary_export.py" "<out>" "<out>/phd_application_tracker.html" --format gdoc

# full evidence workbook
python3 "<skill>/assets/excel_export.py" "<out>" "<out>/phd_application_plan.xlsx"
```

Add `--include-notes` to either exporter only after the user explicitly opts in.

## Delivering to Google

1. If the runtime has a Google Drive / Docs / Sheets connector, create the document there from
   the generated file (the `.html` for Docs, the `.xlsx` for Sheets) and give the user the link.
   Uploading is publishing to an external service: confirm with the user first.
2. Otherwise hand over the file with the import steps:
   - Google Docs: upload the `.html` to Google Drive → right-click → **Open with → Google Docs**;
   - Google Sheets: upload the `.xlsx` → **Open with → Google Sheets** (dropdowns are kept).

## Rules for every export

- Text beginning with `=`, `+`, `-`, or `@` is written as plain text, never as a formula.
- Only `http(s)` URLs become links.
- No applicant identity, absolute local paths, or private notes unless explicitly requested.
- A deadline or fact that is not independently confirmed is never presented as confirmed.
