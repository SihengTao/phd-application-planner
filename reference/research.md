# Research contract

Applies to both runtimes. The output is `<out>/_wf_result.json` in the v2 shape defined in
[schema.md](schema.md).

## Claude Code: Workflow path

Run `<skill>/assets/research_workflow.js` with the Workflow tool and the confirmed config values:

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

Save the returned object to `<out>/_wf_result.json`.

## Codex or no-Workflow path

Fan out independent tasks when available:

1. program discovery by region, retaining discovery failures;
2. per-program facts, admissions, funding, and tracker fields (degree type, main deadline,
   program page, application portal);
3. eligible advisors and fit evidence;
4. outcomes, placement, and international-student evidence;
5. campus anchor and nearby food, when enabled;
6. a checker that retrieves evidence independently before reading/comparing first-pass values.

Deduplicate by normalized institutional identity and assign stable IDs. Never use array order,
program title alone, or faculty name alone as an identity key.

## Required behavior

**Sources**

- Use current, applicable official sources for funding, deadlines, application rules, program
  requirements, advisor eligibility, and placement when available.
- Map each important source to exact `claimPaths`; a loose URL list is insufficient.
- Preserve source `retrievalStatus` as `retrieved | partial | blocked | not_found | stale |
  error`. Record finer causes such as `timeout` or `parse_error` in `errors[].code`. Never drop a
  program silently because one subtask failed.

**Enums and checks**

- Application policy is exactly `multiple_allowed | single_only | unknown | conflict`.
- First-pass collection records go in `evidenceChecks` with `supported | unresolved | conflict`;
  they do not imply independent verification.
- The independent checker records final reconciliation in `verification.claimChecks` and
  `provenance.checks` as `confirmed | corrected | conflict | unresolved`, with `initialValue`,
  `independentValue`, and `finalValue`. Corrections keep the first-pass value and the new
  evidence; conflicts keep both claims.
- Never label a claim or program verified merely because a source exists or a checker ran.

**Discipline mode**

- `faculty_based` / `hybrid`: research advising eligibility, committee structure, writing sample,
  language/field requirements, methods training, teaching load, time to degree, and placement.
  Advisor fit covers intellectual, method, language, and archive coverage and selected work.
- Lab metrics (h-index, lab size, wet/dry) stay optional and never become silent ranking
  defaults outside `lab_based`.

**Nearby food (opt-in)**

- Missing `food_preferences` means disabled: emit `nearbyFood.enabled: false` and
  `researchStatus: "not_requested"`.
- When enabled, anchor to the relevant campus/department address and prioritize Sichuan,
  Cantonese, and Hunan. Set `researchStatus` to `complete`, `partial`, or `failed` by the actual
  outcome. Keep official location/menu evidence separate from review summaries and volatile
  hours, price, spice, and route claims. See [source_policy.md](source_policy.md).

The Workflow also emits `schemaVersion` / `disciplineMode` aliases and the program-level
`faculty`, `outcomes`, and `restaurants` display aliases; preserve them if present.
