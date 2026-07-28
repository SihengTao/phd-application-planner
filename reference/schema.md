# Data schema

`_wf_result.json` is the canonical research record. `assets/check_data.py` validates it and
writes `_quality_report.json`; `assets/build_data.py` then derives the dashboard files. Claude
Code and Codex must produce the same v2 contract.

## Conventions

- Use JSON `null` for unknown values. Do not use `-1`, `false`, or an empty string to mean
  "not researched."
- Use ISO 8601 dates/timestamps and absolute application-cycle labels.
- Keep `program_id`, `advisor_id`, and `source.id` stable across refreshes.
- Canonical IDs are based on normalized institutional identity, not list order or display name
  alone. Once assigned, persist them even if a label changes.
- Do not key notes, hidden state, joins, or exports by a program/advisor display name alone.
- Every important claim should be referenced by one or more `claimPaths` in a source and checked
  independently. See [source_policy.md](source_policy.md).

## `_wf_result.json`

```json
{
  "schema_version": "2.0",
  "generatedAt": "2026-07-27T18:30:00-04:00",
  "field": "History",
  "discipline_mode": "faculty_based",
  "regions": [{"key": "US", "label": "United States"}],
  "floor": 35000,
  "currency": "USD",
  "programs": [
    {
      "program_id": "program_1d6ddfa298189e3d",
      "region": "US",
      "school": "Example University",
      "program": "History PhD",
      "city": "Example City",
      "researchStatus": "complete",
      "facts": {
        "applicationPolicy": "unknown",
        "sources": [],
        "evidenceChecks": [],
        "errors": []
      },
      "pis": {
        "pis": [],
        "sources": [],
        "evidenceChecks": [],
        "errors": []
      },
      "out": {
        "sources": [],
        "evidenceChecks": [],
        "errors": []
      },
      "nearbyFood": {
        "enabled": false,
        "researchStatus": "not_requested",
        "campusAnchor": {
          "name": "Humanities Building",
          "address": "1 College Way, Example City",
          "sourceUrl": "https://example.edu/campus"
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
        "resolution": "No critical claim has yet been resolved.",
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
        "researchStatus": "complete"
      }
    }
  ],
  "workflowStatus": "complete",
  "errors": []
}
```

Readers may accept `schemaVersion` and `disciplineMode` as compatibility aliases; v2 writers
emit the canonical snake-case keys and may include both aliases.

`discipline_mode` is one of:

- `lab_based`: PI/lab-centered advising;
- `faculty_based`: advisor/committee-centered humanities or social-science advising;
- `hybrid`: both models materially affect fit.

`pis` is retained as the compatibility container name; in `faculty_based` mode its members are
faculty/advisor records, and the UI uses the configured advisor label rather than forcing lab
terminology.

## Program identity and core record

Every item in `programs` has:

- `program_id` (required): stable opaque ID, unique across the dataset;
- `region`, `school`, `program`, `city`;
- `facts`: program, admission, funding, and discipline-specific facts;
- `pis: {"pis": [...]}`: advisor/faculty records;
- `out`: placement, admission-background, and international-student information;
- `nearbyFood`: campus-anchored restaurant research;
- `verification`: independent critical-claim comparison and reconciliation;
- `provenance`: claim-level source, check, conflict, and collection-status records.

The program root also carries `researchStatus`. The `facts`, `pis`, and `out` wrappers each
carry their own `sources`, `evidenceChecks`, and `errors` arrays so evidence and access failures
remain attached to the research slice that produced them. `evidenceChecks` contains first-pass
collection checks; it is distinct from final independent `claimChecks`.

For backward-compatible readers, a program may also expose `restaurants` as an alias for
`nearbyFood.restaurants`, `faculty` as the richer alias of `pis`, and `outcomes` as the richer
alias of `out`; new writers should retain the canonical `pis`, `out`, and `nearbyFood` fields.

## `facts`

Common fields:

`city, campusAnchor, disciplineMode, stipendUSD (number|null), stipendLocal,
stipendCurrency, stipend_basis, stipend_confidence (high|medium|low|unknown|conflict),
stipend_foundOfficial (bool|null), stipendNotes, meetsFloor (bool|null), cohortSize,
degreeStructure, applicationRoute, deadlineAndTests, applicationRestrictions,
applicationPolicy, researchFocus, fitScore (number 0-10), fitRationale, siblingPrograms`

`applicationPolicy` is exactly one of:

- `multiple_allowed`: the applicable current-cycle rule permits multiple applications;
- `single_only`: the applicable current-cycle rule permits only one;
- `unknown`: the rule could not be established;
- `conflict`: current applicable sources disagree.

Never infer this enum only from a keyword such as "multiple." Preserve the governing scope and
wording in `applicationRestrictions` and provenance.

Lab/hybrid fields:

`wetDryIntegration, gwasOrMechanistic`

Faculty/hybrid fields:

`admissionsModel, advisorSelection, writingSampleRequirements, languageRequirements,
methodsOrTheoryTraining, qualifyingOrFieldExamStructure, dissertationFormat,
archiveFieldworkSupport, teachingRequirements`

Readers may accept the display-oriented aliases `facultyModel`, `advisorAssignment`,
`writingSample`, `methodsTraining`, `fieldRequirements`, and `teachingLoad`, but v2 writers
should prefer the canonical fields above.

Fields that do not apply to a discipline remain `null` or absent; do not invent a lab analogue
for a humanities requirement.

## Advisor/faculty record

Each member of `pis.pis` has:

`advisor_id, name, category, roleType, rank, disciplinaryHome, research, whyFit, advisingFit,
recruiting, contactGuidance, url, sourceIds`

Optional lab/hybrid fields:

`hIndex (number|null), citations (number|null), scholarUrl, startedApprox, labSize,
wetDry (dry|wet|both|not_applicable|unknown)`

Optional faculty/hybrid fields:

`theoreticalApproaches, methodologicalApproaches, languagesArchivesOrFieldwork, recentWork`

Readers may accept the older/display aliases `role`, `departmentAffiliations`, `methods`,
`archivesLanguages`, `intellectualTradition`, and `selectedWorks`.

`category` may use the legacy values `rising_star`, `direction_fit`,
`interesting`, and `famous_but_fits`; use `roleType` to distinguish `primary_advisor`,
`potential_supervisor`, `program_faculty`, `committee_member`, `lab_pi`, and `other` roles.
Never require h-index, lab age, lab size, or wet/dry labels for humanities and social-science
ranking.

`advisor_id` is required for v2 data and must remain stable across program refreshes. If the same
person is eligible through two programs, each program/advisor relationship may have its own ID
so notes and fit evidence cannot leak across records accidentally.

## Outcomes (`out`)

Common fields:

`careerOutcomes, placementTransparency, namedPlacements, admitBackgrounds, intlNotes,
timeToDegree, teachingPreparation, nonAcademicCareerSupport,
publicHumanitiesOrPolicyOpportunities, extraIntel`

Readers may accept `placement` as a compact display alias.

The legacy strings `stipendVerified` and `restrictionsVerified` may be retained for display, but
they are not authoritative verification flags. Verification status is derived from
`provenance.checks`.

## `nearbyFood`

```json
{
  "enabled": true,
  "researchStatus": "complete",
  "campusAnchor": {
    "name": "Humanities Building",
    "address": "1 College Way, Example City",
    "sourceUrl": "https://example.edu/campus"
  },
  "restaurants": [
    {
      "name": "Example Kitchen",
      "cuisine": "sichuan",
      "cuisineLabel": "川菜",
      "spiceFit": "menu has explicitly spicy dishes",
      "priceLevel": "$$",
      "distanceFromCampus": "1.2 km / about 17 minutes walking",
      "distanceKm": 1.2,
      "transitMode": "walk",
      "address": "2 Main Street, Example City",
      "rating": 4.4,
      "ratingScale": 5,
      "reviewCount": 240,
      "operatingStatus": "open",
      "whyRecommended": "Official menu plus a dated review-platform summary; taste is subjective.",
      "url": "https://example.org/menu",
      "sourceIds": []
    }
  ],
  "sources": [],
  "evidenceChecks": [],
  "errors": []
}
```

Anchor search to the relevant campus/department location. Prioritize Sichuan, Cantonese, and
Hunan, then other Chinese cuisines if useful. A restaurant recommendation is not a guarantee of
taste, authenticity, spice, price, operating status, or current travel time. Record evidence and
retrieval limitations using the rules in [source_policy.md](source_policy.md).

`enabled` records the confirmed user opt-in. If the config omits food preferences, the Workflow
defaults this feature to disabled and emits `enabled: false` with
`researchStatus: "not_requested"` rather than silently running a restaurant search.
`researchStatus` is `not_requested | complete | partial | failed`.

`cuisine` is `sichuan | cantonese | hunan | other_chinese`; `operatingStatus` is
`open | temporarily_closed | permanently_closed | unknown`. Readers may accept the display
aliases `regionalStyle`, `spiceLevel`, `price`, `travelMode`, `openStatus`, `reviewBasis`, and
`lastVerified`. `restaurants` at the program root is accepted as a legacy/convenience alias of
this array.

## `provenance`

```json
{
  "sources": [
    {
      "id": "source_0d398d00c7b15ac1",
      "url": "https://example.edu/graduate/funding",
      "title": "Doctoral funding",
      "publisher": "Example University Graduate School",
      "sourceType": "official_program",
      "official": true,
      "claimPaths": ["facts.stipendLocal", "facts.stipend_basis"],
      "effectiveCycle": "2027 admission",
      "updatedAt": "2026-06-15",
      "accessedAt": "2026-07-27T18:30:00-04:00",
      "retrievalStatus": "retrieved"
    }
  ],
  "checks": [
    {
      "claimPath": "facts.stipendLocal",
      "status": "confirmed",
      "sourceIds": ["source_0d398d00c7b15ac1"],
      "initialValue": "$42,000 for 12 months",
      "independentValue": "$42,000 for 12 months",
      "finalValue": "$42,000 for 12 months",
      "checkedAt": "2026-07-27T18:45:00-04:00",
      "conflict": false,
      "resolution": "Current-cycle graduate-school page agrees."
    }
  ],
  "conflicts": [],
  "errors": [],
  "applicationCycle": "2027 admission",
  "researchStatus": "complete"
}
```

Source `retrievalStatus` values should distinguish at least:

`retrieved | partial | blocked | not_found | stale | error`

Each research section stores first-pass collection checks in `evidenceChecks`. Their fields are
`claimPath, status, value, sourceIds, checkedAt, conflict, note`, and `status` is:

`supported | unresolved | conflict`

Final independent critical-claim reconciliation records are stored in
`verification.claimChecks` and `provenance.checks`. Their fields are
`claimPath, status, initialValue, independentValue, finalValue, sourceIds, checkedAt, conflict,
resolution`, and `status` is:

`confirmed | corrected | conflict | unresolved`

The local checker also accepts `confirmed`, `corrected`, `not_found`, and `error` in imported
legacy collection records, and may accept the old section key `claimChecks`; new Workflow writers
must use `evidenceChecks` for collection records and reserve `claimChecks` for final
reconciliation.
`independentValue` belongs to the critical-claim reconciliation records; ordinary collection
checks use `value` instead.

`verified` is a derived display summary, not a permitted check status. A critical claim is
verified only when a current, applicable source supports it and an independent check is
`confirmed` or `corrected`. One unresolved or conflicting critical claim prevents an
unqualified program-level "verified" label.

`researchStatus` is `complete | partial | conflict | failed`. Structured research errors use
`{stage, code, message, url, occurredAt, retryable}`; access and subtask failures remain in the
record instead of causing the program to disappear.

## `verification`

Each program has a structured independent-verification result:

`status, checkedAt, initial, independent, final, conflict, resolution, sources,
evidenceChecks, claimChecks, errors`

`status` is `confirmed | corrected | conflict | unresolved`. `initial`, `independent`, and
`final` contain the critical values before checking, from the blind independent pass, and after
reconciliation. `claimChecks` contains the four-state reconciliation records; `evidenceChecks`
contains source-collection checks from the independent pass. Do not treat an empty or merely
present `verification` object as proof that claims were verified.

## `_quality_report.json`

The checker writes a machine-readable report such as:

```json
{
  "valid": false,
  "summary": {
    "programs": 1,
    "advisors": 4,
    "restaurants": 3,
    "sources": 12,
    "claims": 18,
    "errors": 1,
    "warnings": 0,
    "info": 0,
    "online": false
  },
  "errors": [
    {
      "severity": "error",
      "code": "application_policy_invalid",
      "path": "programs[0].facts.applicationPolicy",
      "message": "applicationPolicy must be one of conflict, multiple_allowed, single_only, unknown.",
      "value": "invalid_value"
    }
  ],
  "warnings": [],
  "info": [],
  "issues": [
    {
      "severity": "error",
      "code": "application_policy_invalid",
      "path": "programs[0].facts.applicationPolicy",
      "message": "applicationPolicy must be one of conflict, multiple_allowed, single_only, unknown.",
      "value": "invalid_value"
    }
  ]
}
```

Run:

```bash
python3 assets/check_data.py <out>/_wf_result.json \
  --output <out>/_quality_report.json
```

Add `--online` for URL reachability checks and `--strict` to make warnings fail. The dashboard
uses this report for quality messaging; report existence alone does not imply successful
verification.

## Derived dashboard files

`assets/build_data.py` writes:

- `_quality_report.json`: the shared pre-build quality gate report, always written first;
- `_research_data.json`: program records grouped by school, preserving v2 nested fields;
- `_rows.json`: compact one-row-per-program table with stable `program_id`.

Errors block derived output; `--strict` also blocks on warnings, and `--online` enables URL
reachability checks during the build.

Compact row fields include:

`program_id, region, school, program, city, usd (number|null), floor (bool|null), fit,
application_policy, multi, cohort`

`region` values must match `_config.json.regions[].key`. `multi` is a compatibility display
label; logic must use `application_policy`.

## `_config.json`

```json
{
  "schema_version": "2.0",
  "intake_complete": true,
  "intake_version": 2,
  "discipline_mode": "faculty_based",
  "advisor_label": "faculty/advisor",
  "application_cycle": "2027 admission",
  "title": "PhD Application Planner — History",
  "subtitle": "Evidence-aware application planning",
  "stipend_floor": 35000,
  "currency": "USD",
  "current_year": 2026,
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
  "col_index": {"example city": 100},
  "food_preferences": {
    "enabled": true,
    "priority_cuisines": ["Sichuan", "Cantonese", "Hunan"],
    "max_distance": "30 minutes",
    "travel_modes": ["walk", "transit"],
    "budget": "any",
    "spice": "very spicy",
    "dietary_needs": []
  }
}
```

Research must not begin unless `_config.json` exists and `intake_complete` is `true`. For a
returning user, retain the previous config, ask only what changed, update it, and reconfirm
before setting `intake_complete` back to `true`.

`interest_areas` is a discipline-specific mapping from display bucket to lowercase keyword
substrings. `col_index` uses 100 as the purchasing-power baseline. `food_preferences` is the
canonical config key, with `enabled`, `priority_cuisines`, `max_distance`, `travel_modes`,
`budget`, `spice`, and `dietary_needs`; readers may accept legacy `restaurant_preferences` and
its older aliases during migration.

## Persistent user state

The dashboard creates:

- `_pi_notes.json`: notes keyed by stable `advisor_id`;
- `_pi_hidden.json`: hidden `advisor_id` and `program_id` values.

Do not overwrite these files during refreshes. Excel export excludes private notes by default;
notes may be included only after explicit user choice. Exporters must neutralize cells beginning
with `=`, `+`, `-`, or `@` to prevent spreadsheet formula injection.
