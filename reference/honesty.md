# Honesty and verification rules

Applicants make expensive, high-impact decisions from this data. Accuracy, traceability, and
clear uncertainty are more important than filling every field. These rules apply equally to
Claude Code and Codex.

1. **Never fabricate.** Do not invent a stipend, deadline, cohort size, application rule,
   advisor, advising availability, publication metric, placement result, language requirement,
   writing-sample rule, restaurant, route, or review. Use `null`, `unknown`, `unresolved`, or an
   explicit access error when evidence is insufficient.

2. **Attach evidence to claims.** A general source list is not enough. Decision-relevant values
   need structured source records with `claimPaths`, access dates, applicable cycles, retrieval
   status, and official/secondary classification. First-pass section observations belong in
   `evidenceChecks`; they are not independent-verification results. Follow
   [source_policy.md](source_policy.md).

3. **Check independently.** The evidence-checking research pass retrieves evidence before
   comparing it with the first-pass answer. It records `confirmed`, `corrected`, `conflict`, or
   `unresolved` in `verification.claimChecks` and `provenance.checks`; it never silently
   overwrites a disputed value. Then run the local structural/provenance checker:

   ```bash
   python3 assets/check_data.py <out>/_wf_result.json \
     --output <out>/_quality_report.json
   ```

   `--online` adds URL reachability checks, and `--strict` treats warnings as gate failures.
   Neither flag proves that a page semantically supports a claim.

4. **Do not claim blanket verification.** A non-empty source array, a successful checker
   process, or an official-looking URL is not enough. Only current, applicable evidence plus a
   `confirmed` or `corrected` independent check can support a verified claim. Dashboard and
   export summaries must derive their labels from the recorded checks.

5. **Funding requires scope and units.** Distinguish 9-month from 12-month funding, stipend from
   salary, guaranteed from typical support, tuition remission from take-home pay, and
   department minimum from actual awards. Record local amount/currency, conversion rate/source/
   date when converted, summer funding, duration, fees, and health insurance where available.
   Use dedicated fields when present and otherwise preserve these details in `stipend_basis` or
   `stipendNotes`. `meetsFloor` is `null` when the comparable amount is unknown.

6. **Application policy uses a closed enum.** Record only
   `multiple_allowed | single_only | unknown | conflict`. Verify whether the rule is
   institution-wide, graduate-school-wide, school/college-specific, or program-specific and
   whether it applies to the current cycle. Do not infer it from a keyword.

7. **Respect official conflicts.** Prefer current-cycle and correctly scoped sources, but never
   choose whichever value is more favorable. When current applicable official sources disagree,
   preserve both values, add a conflict record, and use `conflict` or `unresolved` as appropriate.

8. **Advisor fit is discipline-specific.** For lab-based programs, lab model, recruitment,
   methods, and research fit may be relevant. For humanities and social sciences, prioritize
   advising eligibility, committee coverage, intellectual/method fit, language or archive
   alignment, writing-sample expectations, and placement. Do not substitute h-index, lab age,
   wet/dry labels, or fame when they are not meaningful.

9. **Bibliometrics are snapshots.** Google Scholar h-index and citation totals drift and may
   conflate authors. Record the access date and use `null` when identity cannot be resolved.
   Never classify a senior faculty member as a rising star merely to match a preference.

10. **Nearby food is a researched shortlist, not a promise.** Anchor distance to the relevant
    campus or department. Separate official menu/location evidence from review-based taste,
    authenticity, price, and spice impressions. Opening hours, status, routes, and travel times
    are volatile. Record the source `accessedAt` (and `lastVerified` when available), travel mode,
    and evidence basis, and tell the user to re-check before visiting.

11. **Access failure is not negative evidence.** A blocked page, timeout, removed PDF, search
    miss, or parser failure does not prove that a policy, advisor, outcome, or restaurant does
    not exist. Preserve the retrieval state and retry or flag it.

12. **Use stable identities.** Program, advisor, and source IDs must survive refreshes. Never
    join or persist notes solely by display name; same-named programs and faculty are common.

13. **Protect private user data.** Do not place the applicant's name, identity, application
    secrets, or private notes in research records. Excel export excludes notes by default. If
    notes are explicitly included, warn the user. Escape untrusted values that begin with `=`,
    `+`, `-`, or `@` so spreadsheet applications cannot execute them as formulas.

When uncertain, expose the uncertainty in the record and quality report instead of projecting
confidence.
