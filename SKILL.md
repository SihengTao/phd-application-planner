---
name: phd-application-planner
description: >-
  Research and compare PhD or doctoral programs and fitting advisors, then build an
  evidence-aware marimo dashboard plus a concise application tracker (Excel or Google Docs)
  and/or a full evidence workbook. Use for program shortlists, advisor or committee fit,
  funding and application rules, humanities/social-science or lab-based doctoral planning,
  international-student and placement questions, campus-anchored Chinese restaurant research,
  claim-level source checking, application ranking, and application/outreach trackers.
  Triggers include "find PhD programs", "grad school shortlist", "PhD advisor finder",
  "compare stipends", "writing sample or language requirements", "nearby Chinese food",
  "PhD application tracker", and "PhD application dashboard". Always completes progressive
  intake before research.
---

# PhD Application Planner

Turn a confirmed intake into a researched, source-traceable PhD application dataset, an
interactive marimo dashboard, and the result version the user chose. One executable spec for
Claude Code and Codex; it hard-codes no applicant identity.

## At a glance

| # | Stage | Command / action | Writes | Gate |
|---|---|---|---|---|
| 0 | Run directory | create or reuse `<out>` | — | returning user if `_config.json` exists |
| 1 | Intake | adaptive questions → [intake.md](reference/intake.md) | `_config.json` | user confirms; `intake_complete: true` |
| 2 | Research | Workflow or parallel research → [research.md](reference/research.md) | `_wf_result.json` | v2 schema, failures kept |
| 3 | Check | `check_data.py` | `_quality_report.json` | no errors |
| 4 | Build | `build_data.py` | `_research_data.json`, `_rows.json` | quality gate reruns |
| 5 | Launch | `launch.py` | `phd_explorer.py` | ready URL reached |
| 6 | Deliver | `summary_export.py` / `excel_export.py` → [outputs.md](reference/outputs.md) | tracker / workbook | version + destination from config |

`<skill>` is the installed skill directory and `<out>` the run directory; never assume the
current directory is the skill root.

References — read before executing:

| File | Covers |
|---|---|
| [reference/intake.md](reference/intake.md) | first-time and returning-user intake, config example |
| [reference/research.md](reference/research.md) | research fan-out and required research behavior |
| [reference/schema.md](reference/schema.md) | canonical v2 data contract |
| [reference/source_policy.md](reference/source_policy.md) | source precedence, claims, conflicts, food evidence, privacy |
| [reference/honesty.md](reference/honesty.md) | non-fabrication and verification rules |
| [reference/outputs.md](reference/outputs.md) | concise tracker vs full workbook, Excel vs Google Docs |

## Runtime differences

| | Claude Code | Codex |
|---|---|---|
| Questions | structured question tool | input tool, else concise plain-language questions |
| Research | bundled Workflow (`assets/research_workflow.js`) | web research + independent subagents / parallel calls |

The research contract, data files, and quality gate are identical in both.

## Stage 0 — Run directory

| File | Kind | Rule |
|---|---|---|
| `_config.json` | intake result | rewritten only through intake |
| `_wf_result.json` | research | replaced on refresh |
| `_quality_report.json` | checker | rewritten by check and build |
| `_research_data.json`, `_rows.json` | derived | rewritten by build |
| `phd_explorer.py`, `excel_export.py`, `summary_export.py` | app | copied from `<skill>/assets` |
| `_pi_notes.json`, `_pi_hidden.json` | private dashboard state | **never overwrite on refresh** |

## Stage 1 — Intake (required gate)

Follow [intake.md](reference/intake.md): 5–8 adaptive rounds for a first-time user, a delta review
for a returning user, then a confirmed summary. The last round covers ranking, privacy, and
**result delivery** (concise / full / both; Excel or Google Docs).

Keep `intake_complete: false` while collecting. **Do not discover programs, launch research,
call the Workflow, or reuse old results as current until the user confirms and
`<out>/_config.json` has `intake_complete: true`.**

`discipline_mode` is `lab_based`, `faculty_based`, or `hybrid`. Generate interest buckets and
ranking dimensions for that discipline; never apply biomedical labels or h-index/lab-size priors
to humanities and social sciences.

## Stage 2 — Research

Follow [research.md](reference/research.md) and write `<out>/_wf_result.json` in the shape of
[schema.md](reference/schema.md). Essentials:

- official, current-cycle sources mapped to exact `claimPaths`;
- closed enums for application policy, retrieval status, and check status;
- an independent evidence pass; nothing is called verified just because a source exists;
- tracker fields (`degreeType`, `applicationDeadline`, `programUrl`, `applicationPortalUrl`)
  from official pages, or `null`;
- food research only when opted in.

## Stage 3 — Check

```bash
python3 "<skill>/assets/check_data.py" "<out>/_wf_result.json" \
  --output "<out>/_quality_report.json" [--online] [--strict]
```

Default mode validates structure, IDs, enums, types, claim/source links, critical-claim
coverage, and conflicts. `--online` also probes URL reachability; `--strict` fails on warnings.
Fix data errors and rerun. Unresolved evidence may stay unresolved but must not be presented as
verified. Keep `_quality_report.json` beside the dashboard.

## Stage 4 — Build

```bash
python3 "<skill>/assets/build_data.py" "<out>/_wf_result.json" "<out>" [--strict] [--online]
```

Preserves stable program/advisor IDs, v2 provenance, nearby-food records, and unknown/conflict
states. The build reruns the quality gate, rewrites `_quality_report.json`, and blocks on errors.

## Stage 5 — Launch

```bash
cp "<skill>/assets/dashboard_template.py" "<out>/phd_explorer.py"
python3 "<skill>/assets/launch.py" "<out>/phd_explorer.py"
```

Use the Python environment that has the dependencies. The launcher copies both exporters next to
the dashboard, waits for marimo readiness, and reports startup errors from
`<out>/_marimo_run.log`.

## Stage 6 — Deliver results

Read `_config.json.export` and produce what the user chose. Details in
[outputs.md](reference/outputs.md).

| `export.version` | `export.destination` | Command |
|---|---|---|
| `concise` | `excel` / `google_sheets` | `python3 "<skill>/assets/summary_export.py" "<out>" "<out>/phd_application_tracker.xlsx"` |
| `concise` | `google_doc` | `python3 "<skill>/assets/summary_export.py" "<out>" "<out>/phd_application_tracker.html" --format gdoc` |
| `full` | `excel` | `python3 "<skill>/assets/excel_export.py" "<out>" "<out>/phd_application_plan.xlsx"` |
| `both` | any | run the concise and full commands |

- The **concise** result is an application tracker: program overview, application status, and
  faculty outreach tables, with deadlines marked `(TBC)` unless independently confirmed.
- For Google destinations, create the doc/sheet with a Google connector when one is available
  (confirm before uploading); otherwise give the file plus the Drive "Open with" steps.
- Add `--include-notes` only after the user explicitly opts in to private notes.
- The dashboard's Export panel offers the same choices interactively.

## Delivery checklist

1. Intake confirmed; `_config.json.intake_complete` is `true`.
2. `_wf_result.json` follows v2 and preserves failures/conflicts.
3. Checker ran; `_quality_report.json` is present.
4. No unconditional "verified" statement in the dashboard, exports, or handoff.
5. Build completed; stable IDs survived into derived data.
6. Dashboard reached a ready URL.
7. The chosen result version was produced in the chosen destination, and note privacy explained.
8. No generated file contains applicant identity unless the user provided and requested it.

## Dependencies

```bash
python3 -m pip install -r "<skill>/requirements.txt"
```
