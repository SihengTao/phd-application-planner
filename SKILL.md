---
name: phd-application-planner
description: >-
  Research and compare PhD or doctoral programs and fitting advisors, then build an
  evidence-aware marimo dashboard and optional Excel workbook. Use for program shortlists,
  advisor or committee fit, funding and application rules, humanities/social-science or
  lab-based doctoral planning, international-student and placement questions, campus-anchored
  Chinese restaurant research, claim-level source checking, and application ranking. Triggers
  include "find PhD programs", "grad school shortlist", "PhD advisor finder", "compare
  stipends", "writing sample or language requirements", "nearby Chinese food", and "PhD
  application dashboard". Always completes progressive intake before research.
---

# PhD Application Planner

Turn a confirmed user intake into a researched, source-traceable PhD application dataset,
interactive marimo dashboard, and optional Excel export. This skill is one executable
specification for both Claude Code and Codex. It hard-codes no applicant identity.

Pipeline:

**intake gate → config → parallel research → independent check → build → launch → optional
Excel export**

Read these references before executing:

- `reference/intake.md`: first-time and returning-user intake;
- `reference/schema.md`: canonical v2 data contract;
- `reference/source_policy.md`: source precedence, claims, conflicts, food evidence, and privacy;
- `reference/honesty.md`: non-fabrication and verification rules.

Resolve the installed skill directory first. Commands below use `<skill>` for that directory and
`<out>` for the run directory; do not assume the caller's current directory is the skill root.

## Runtime paths

- **Claude Code:** use structured questions and the bundled Workflow tool when available.
- **Codex:** use its input tool when available, otherwise ask concise plain-language questions.
  If Workflow is unavailable, use web research plus independent subagents/parallel calls and
  write the same v2 JSON.

The research contract and quality gate are identical in both runtimes.

## Step 0 — Select or resume a run directory

Create or select `<out>`. Generated research files live there:

`_config.json, _wf_result.json, _quality_report.json, _research_data.json, _rows.json,
phd_explorer.py`

The dashboard may also create private runtime state:

`_pi_notes.json, _pi_hidden.json`

Never overwrite note/hidden-state files during a refresh. If `_config.json` already exists, this
is a returning-user run.

## Step 1 — Complete progressive intake (required gate)

Follow `reference/intake.md`.

- First-time user: conduct 5–8 adaptive rounds. Cover field, `discipline_mode`, geography,
  funding/application constraints, advisor fit, discipline-specific requirements/outcomes,
  campus food, and ranking/export preferences.
- Returning user: show the prior summary and ask only what changed. Ask follow-ups only for
  changed, missing, inconsistent, or new-cycle values.
- Confirm the final summary with the user.

Set `intake_complete: false` while collecting or changing answers. **Do not discover programs,
launch research, call the Workflow, or reuse old results as current until the user confirms and
`<out>/_config.json` exists with `intake_complete: true`.**

Required config core:

```json
{
  "schema_version": "2.0",
  "intake_version": 2,
  "intake_complete": true,
  "field": "History",
  "subfields": ["modern East Asia"],
  "discipline_mode": "faculty_based",
  "advisor_label": "faculty/advisor",
  "application_cycle": "2027 admission",
  "stipend_floor": 35000,
  "currency": "USD",
  "regions": [
    {
      "key": "US",
      "label": "United States",
      "short": "US",
      "color": "#0F4D92",
      "order": 0
    }
  ],
  "region_order": {"US": 0},
  "interest_areas": {"Archives": ["archive", "manuscript"]},
  "food_preferences": {
    "enabled": true,
    "priority_cuisines": ["Sichuan", "Cantonese", "Hunan"],
    "max_distance": "30 minutes",
    "travel_modes": ["walk", "transit"],
    "budget": "any",
    "spice": "very spicy",
    "dietary_needs": []
  },
  "export": {"excel": true, "include_private_notes": false}
}
```

`discipline_mode` is `lab_based`, `faculty_based`, or `hybrid`. Generate interest buckets and
ranking dimensions for the chosen discipline; do not apply biomedical labels or h-index/lab-size
priors to humanities and social sciences.

## Step 2 — Research into `_wf_result.json`

### Claude Code Workflow path

Run `<skill>/assets/research_workflow.js` using the Workflow tool. Pass the confirmed config
values, including the discipline mode and food preferences:

```text
Workflow({
  scriptPath: "<skill>/assets/research_workflow.js",
  args: {
    field, subfields, discipline_mode, regions, stipend_floor, currency,
    n_programs, n_pis_per_program, pi_preferences, rising_star_bias,
    application_constraints, outcome_preferences, food_preferences,
    notes, seed_programs
  }
})
```

Save the result object to `<out>/_wf_result.json`.

### Codex or no-Workflow path

Fan out independent tasks when available:

1. program discovery by region, retaining discovery failures;
2. per-program facts/admissions/funding;
3. eligible advisors and fit evidence;
4. outcomes, placement, and international-student evidence;
5. campus anchor and nearby food, when enabled;
6. a checker that retrieves evidence independently before reading/comparing first-pass values.

Deduplicate by normalized institutional identity and assign stable IDs. Do not use array order,
program title alone, or faculty name alone as an identity key.

Write the canonical structure from `reference/schema.md`:

```json
{
  "schema_version": "2.0",
  "field": "<field>",
  "discipline_mode": "faculty_based",
  "regions": [{"key": "US", "label": "United States"}],
  "floor": 35000,
  "currency": "USD",
  "programs": [
    {
      "program_id": "program_<stable-id>",
      "region": "US",
      "school": "...",
      "program": "...",
      "city": "...",
      "researchStatus": "partial",
      "facts": {"sources": [], "evidenceChecks": [], "errors": []},
      "pis": {
        "pis": [],
        "sources": [],
        "evidenceChecks": [],
        "errors": []
      },
      "out": {"sources": [], "evidenceChecks": [], "errors": []},
      "nearbyFood": {
        "enabled": false,
        "researchStatus": "not_requested",
        "campusAnchor": {
          "name": "...",
          "address": "...",
          "sourceUrl": "https://..."
        },
        "restaurants": [],
        "sources": [],
        "evidenceChecks": [],
        "errors": []
      },
      "verification": {
        "status": "unresolved",
        "checkedAt": "2026-07-27T18:45:00-04:00",
        "initial": {},
        "independent": {},
        "final": {},
        "conflict": false,
        "resolution": "...",
        "sources": [],
        "evidenceChecks": [],
        "claimChecks": [],
        "errors": []
      },
      "provenance": {
        "applicationCycle": "2027 admission",
        "sources": [],
        "evidenceChecks": [],
        "checks": [],
        "conflicts": [],
        "errors": [],
        "researchStatus": "partial"
      }
    }
  ],
  "workflowStatus": "partial",
  "errors": []
}
```

The Workflow also emits `schemaVersion` and `disciplineMode` compatibility aliases and the
program-level `faculty`, `outcomes`, and `restaurants` display aliases. Preserve them if present.
For collection output, `facts`, `pis`, `out`, and `nearbyFood` use `evidenceChecks` with
`supported | unresolved | conflict` and one observed `value`. Only final independent
reconciliation uses `verification.claimChecks` and `provenance.checks`, with
`confirmed | corrected | conflict | unresolved` plus `initialValue`, `independentValue`, and
`finalValue`.

### Required research behavior

- Use current, applicable official sources for funding, deadlines, application rules, program
  requirements, advisor eligibility, and placement when available.
- Map each important source to exact `claimPaths`; a loose URL list is insufficient.
- Record application policy only as
  `multiple_allowed | single_only | unknown | conflict`.
- Preserve source `retrievalStatus` as
  `retrieved | partial | blocked | not_found | stale | error`. Record finer causes such as
  `timeout` or `parse_error` in `errors[].code`; do not silently drop a program because one
  subtask failed.
- First-pass section collection records go in `evidenceChecks` and use `supported`,
  `unresolved`, or `conflict`; they do not imply independent verification.
- The independent checker records final reconciliation in `verification.claimChecks` and
  `provenance.checks` as `confirmed`, `corrected`, `conflict`, or `unresolved`. Corrections
  retain the first-pass value and new evidence; conflicts retain both claims.
- Never label a claim or program verified merely because a source exists or a checker ran.

For `faculty_based` or `hybrid` work, research advising eligibility, committee structure,
writing sample, language/field requirements, methods training, teaching load, time to degree,
and placement. Advisor fit should include intellectual/method/language/archive coverage and
selected work as relevant. Lab metrics remain optional and must not become silent ranking
defaults.

Food research is opt-in. If `food_preferences` is missing, treat it as disabled and emit
`nearbyFood.enabled: false` plus `researchStatus: "not_requested"`. When enabled, anchor to the
relevant campus/department address and prioritize Sichuan, Cantonese, and Hunan restaurants.
Set `nearbyFood.researchStatus` to `complete`, `partial`, or `failed` according to the actual
search outcome. Keep official location/menu evidence separate from subjective review summaries
and volatile opening, price, spice, and route claims. Follow `reference/source_policy.md`.

## Step 3 — Run the local data checker

The independent evidence pass is part of Step 2. Now run the local structural/provenance checker
before building:

```bash
python3 "<skill>/assets/check_data.py" "<out>/_wf_result.json" \
  --output "<out>/_quality_report.json"
```

Optional modes:

```bash
python3 "<skill>/assets/check_data.py" "<out>/_wf_result.json" \
  --output "<out>/_quality_report.json" --online

python3 "<skill>/assets/check_data.py" "<out>/_wf_result.json" \
  --output "<out>/_quality_report.json" --online --strict
```

Default checking validates structure, IDs, enums, types, claim/source links, critical-claim
coverage, and conflicts. `--online` additionally probes source reachability. `--strict` makes
warnings fail the gate.

Fix data errors and rerun the checker. Unresolved evidence may remain explicitly unresolved, but
it must not be presented as verified. Preserve `_quality_report.json` beside the dashboard so the
user can inspect errors, warnings, sources, and verification status.

## Step 4 — Build dashboard data

```bash
python3 "<skill>/assets/build_data.py" "<out>/_wf_result.json" "<out>"
```

This writes `<out>/_research_data.json` and `<out>/_rows.json`, preserving stable program/advisor
IDs, v2 provenance, nearby-food records, and unknown/conflict states. The builder always reruns
the shared quality gate and rewrites `<out>/_quality_report.json`; errors block the build. Add
`--strict` to block on warnings too and `--online` to include URL reachability checks:

```bash
python3 "<skill>/assets/build_data.py" "<out>/_wf_result.json" "<out>" \
  --strict --online
```

## Step 5 — Launch marimo

Copy the dashboard next to its data and launch it:

```bash
cp "<skill>/assets/dashboard_template.py" "<out>/phd_explorer.py"
python3 "<skill>/assets/launch.py" "<out>/phd_explorer.py"
```

Use the same Python environment that has the runtime dependencies. The launcher copies required
export helpers when present, waits for marimo readiness, and reports startup errors from
`<out>/_marimo_run.log`.

The dashboard loads data from its own directory, displays claim sources and checker issues,
adapts terminology/fields to the discipline mode, shows campus-anchored Chinese-food candidates,
uses stable IDs for notes/hiding, and offers Excel export.

## Step 6 — Excel export

The dashboard export panel can export all programs or the current filtered view. Private advisor
notes are excluded by default; include them only after the user explicitly opts in and
acknowledges that the workbook contains private content.

The command-line exporter exports the complete built dataset:

```bash
python3 "<skill>/assets/excel_export.py" "<out>" \
  "<out>/phd_application_plan.xlsx"
```

Include private notes only after explicit user opt-in:

```bash
python3 "<skill>/assets/excel_export.py" "<out>" \
  "<out>/phd_application_plan_with_notes.xlsx" --include-notes
```

Every workbook must:

- include Metadata, Programs, Advisors, Restaurants, Sources, Quality, and Priority sheets when
  data exists, with requirements/outcomes retained as explicit columns;
- retain stable IDs so records can be joined safely;
- include provenance/verification status without turning `unresolved` into `verified`;
- escape cells beginning with `=`, `+`, `-`, or `@` to prevent formula injection;
- exclude `_pi_notes.json` unless notes were explicitly requested.

## Delivery checklist

Before claiming completion:

1. intake was confirmed and `_config.json.intake_complete` is `true`;
2. `_wf_result.json` follows the v2 schema and preserves failures/conflicts;
3. checker ran and `_quality_report.json` is present;
4. no unconditional "verified" statement appears in the dashboard or handoff;
5. build completed and stable IDs survived into derived data;
6. dashboard reached a ready URL;
7. Excel behavior and note privacy were explained if export was requested;
8. generated research/config/export files contain no applicant identity unless the user
   explicitly provided and requested that content.

## Dependencies

Install the libraries needed by the dashboard and Excel export:

```bash
python3 -m pip install -r "<skill>/requirements.txt"
```
