# Source and claim policy

This policy applies to every Claude Code and Codex run. A source list alone is not enough:
each decision-relevant claim must be traceable to evidence, and a second pass must check the
claim independently.

## Source hierarchy

Use the narrowest current source that actually governs the claim:

1. Current-cycle program, department, graduate-school, or university pages and official PDFs.
2. Official faculty profiles, CVs, lab/group pages, placement lists, campus maps, and restaurant
   websites or menus.
3. Government, accreditor, or other authoritative primary records.
4. Reputable secondary sources only when primary evidence is unavailable or when the claim is
   inherently review-based, such as restaurant reception.

Search snippets, model memory, directory aggregators, crowd-edited pages, and map/review platforms
are discovery aids, not automatic confirmation. A URL being reachable does not prove the page is
current or supports the recorded claim.

## Claim-level provenance

Every decision-relevant field should name one or more source records through `claimPaths`.
Examples include:

- `facts.stipendLocal`, `facts.deadlineAndTests`, and `facts.applicationPolicy`;
- `facts.writingSampleRequirements`, `facts.languageRequirements`, and
  `out.placementTransparency` (or the retained `outcomes.placementTransparency` alias);
- `pis.pis[0].recruiting` (or the retained `faculty.faculty[0].recruiting` alias);
- `nearbyFood.restaurants[0].address` and `nearbyFood.restaurants[0].operatingStatus`.

Each source record stores, when available:

- a stable source ID, URL, title, publisher, and source type;
- whether the publisher is official for the claim;
- the application cycle or other effective period;
- the page update date and access date;
- retrieval status and the exact `claimPaths` it supports.

Do not mark a source `official: true` merely because it is hosted on an `.edu` domain. It must be
official for the institution, program, person, policy, campus, or restaurant represented by the
claim.

Each research section (`facts`, `pis`, `out`, and `nearbyFood`) stores its first-pass
source-to-claim observations in `evidenceChecks`. These records use
`supported | unresolved | conflict` plus one observed `value`. The combined copies live in
`provenance.evidenceChecks`. Do not put final independent-verification statuses in these arrays.

## Independent checking

The first-pass researcher and evidence-checking researcher are separate roles. The latter must
retrieve evidence independently before comparing it with the first-pass value. For each critical
claim, record one of:

- `confirmed`: independent evidence supports the value;
- `corrected`: independent evidence supports a replacement value, with both the old and new
  values retained in the audit record;
- `conflict`: current, applicable sources disagree and the conflict cannot be safely resolved;
- `unresolved`: evidence is missing, inaccessible, stale, out of scope, or insufficient.

Store these final reconciliation records in `verification.claimChecks` and
`provenance.checks`, with `initialValue`, `independentValue`, and `finalValue`. Reserve
`claimChecks` for these four-state final checks; do not use it as the section-level collection
array in new v2 data.

Only `confirmed` and `corrected` checks may contribute to a `verified` summary. A checker run,
an official-looking URL, or a non-empty source array does not by itself make a claim verified.
The dashboard must derive its wording from the recorded checks and must never state that all data
is verified unconditionally.

After that research pass, run the local structural/provenance checker before building:

```bash
python3 assets/check_data.py <out>/_wf_result.json \
  --output <out>/_quality_report.json
```

Use `--online` to re-check retrievable URLs and `--strict` when warnings should fail the quality
gate. Online checks still cannot establish that a page semantically supports a claim; the
claim-level audit record remains required.

## Conflict and time handling

- Prefer the current application cycle over an older page. Record both if the older page remains
  live and could mislead.
- Match scope before choosing precedence: an institution-wide limit, a graduate-school rule, and
  a department exception may all be valid for different applicants.
- Never silently select the more favorable stipend, deadline, application rule, or advising
  status when official sources conflict. Store the competing values and use `conflict`.
- Preserve access failures as access failures. Source `retrievalStatus` is
  `retrieved | partial | blocked | not_found | stale | error`; finer causes such as `timeout`
  and `parse_error` belong in `errors[].code`. None of these failures proves that the underlying
  program, policy, advisor, or restaurant does not exist.
- Use absolute dates and record the application cycle, exchange-rate date, and restaurant check
  date where applicable.

## Nearby-food evidence boundary

Nearby-food research is anchored to the relevant campus or department location, not merely the
university's city. Prioritize Sichuan, Cantonese, and Hunan candidates, while allowing other
Chinese cuisines when useful.

Run it only when the user opted in. Missing food preferences mean disabled; retain
`nearbyFood.enabled: false` and `researchStatus: "not_requested"`. For an enabled search, report
`complete`, `partial`, or `failed` rather than hiding access failures.

Treat the following as different claims:

- address, menu, and self-described cuisine: prefer an official restaurant source;
- distance or travel time: a dated route estimate from the campus anchor, with travel mode;
- opening status and hours: volatile, so retain the source `accessedAt` (and `lastVerified` when
  available) and label uncertainty;
- `priceLevel`, `spiceFit`, recommended dishes, and dietary options: cite the menu or explain the
  review basis in `whyRecommended`;
- "delicious," "authentic," or "best": subjective review summaries, never official facts or
  guaranteed experiences.

Do not claim that a restaurant is open now, genuinely regional, suitably spicy, or objectively
good unless the evidence supports that narrower statement. Recommendations are a researched
shortlist for the user to re-check before visiting.

## Privacy and exports

Provenance is internal audit metadata and should not contain the applicant's identity. Excel
exports omit private notes by default. If a user explicitly includes notes, warn them that the
workbook now contains private content. All exported text that begins with `=`, `+`, `-`, or `@`
must be escaped so spreadsheet software cannot interpret untrusted web text as a formula.
