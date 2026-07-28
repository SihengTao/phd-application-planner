# Progressive intake

Intake is a required gate for both Claude Code and Codex. Do not start program discovery,
research, checking, building, or launch until the user has confirmed a complete config and
`_config.json.intake_complete` is `true`.

Do not ask for or store the user's name or identity. Ask only questions that can materially
change the shortlist, evidence search, ranking, or export.

## First-time user: 5–8 adaptive rounds

Use one focused question or a small coherent group per round. Reflect the answer briefly, explain
what it changes when useful, and then ask the next most informative question. Do not dump the
whole questionnaire at once.

1. **Goal and field.** What discipline, subfields, questions, populations/periods/regions, and
   methods define fit? Capture `field`, `subfields`, and a field-specific `interest_areas`
   taxonomy.

2. **Advising model.** Determine `discipline_mode`:

   - `lab_based`: PI/lab-centered;
   - `faculty_based`: advisor/committee-centered humanities or social science;
   - `hybrid`: both matter.

   Let the user correct the mode. Do not infer that all STEM is lab-based or all social science
   is faculty-based.

3. **Geography and scope.** Ask for target regions/countries, exclusions, any "partial" region,
   seed programs, approximate program count, and desired advisors per program. For each region,
   prepare `{key,label,short,color,order}`.

4. **Funding and application constraints.** Ask for the annual floor and currency, whether zero
   means no hard minimum, and which mechanics matter: deadlines, tests, fee waivers, international
   eligibility, and whether multiple programs at one institution may be applied to.

5. **Advisor/faculty fit.** Adapt to the mode:

   - lab-based: topics, methods, recruitment, rising vs established, lab size, and wet/dry mix;
   - faculty-based: primary advisor eligibility, committee breadth, intellectual tradition,
     periods/regions, archives/languages, qualitative/quantitative methods, and selected work;
   - hybrid: ask only the relevant parts of both.

6. **Discipline-specific requirements and outcomes.** For humanities/social sciences, explicitly
   ask about writing-sample fit, language requirements, methods training, field requirements,
   teaching load, advisor assignment/contact expectations, time to degree, and academic/
   non-academic placement. For lab-based fields, ask the corresponding training, rotation,
   placement, and career-outcome priorities.

7. **Campus life and nearby food.** Ask whether to research Chinese food near the relevant
   campus/department anchor. Default cuisine priorities are Sichuan, Cantonese, and Hunan
   (🌶️🌶️🌶️); capture max distance/travel time, travel modes, budget, spice, dietary needs, and
   whether the user wants other Chinese cuisines included. Explain that taste/authenticity and
   current opening status have evidence limits. This is an explicit opt-in: if the user does not
   request it, store `food_preferences.enabled: false`; a missing food config also defaults to
   disabled.

8. **Ranking, privacy, and delivery.** Ask about city/lifestyle, relative ranking weights,
   dashboard language, Excel need, and whether private notes must remain dashboard-only. Excel
   notes are excluded by default and require an explicit opt-in.

Five rounds is the minimum: combine low-impact topics when answers are already clear. Use up to
eight when the discipline, advising model, constraints, or food/export preferences need
separation. Skip redundant questions; never silently substitute defaults for a decision that
would materially change the result.

## Returning user: delta intake only

If `_config.json` exists:

1. Read it and summarize the current field/mode, regions, funding floor, scope, advisor criteria,
   food preferences, ranking priorities, and export privacy in a compact review.
2. Ask **what changed since the prior run**. Do not repeat unchanged questions.
3. Ask a targeted follow-up only for a changed value, a missing required field, a detected
   inconsistency, or a time-sensitive cycle update.
4. Preserve all unchanged values and stable IDs. Set `intake_complete: false` while editing.
5. Show the delta and the resulting config, obtain confirmation, then set
   `intake_complete: true`.

If a legacy config lacks v2 fields, ask only the minimum migration questions (usually
`discipline_mode`, current cycle, food opt-in, and export privacy), rather than restarting the
full first-time interview.

## Required completion checklist

Before confirmation, ensure the config states:

- `schema_version`, `intake_version`, and `intake_complete`;
- field, subfields, `discipline_mode`, and discipline-specific interest areas;
- regions, seed programs, program/advisor scope;
- stipend floor/currency and application constraints;
- advisor/faculty and outcome priorities;
- nearby-food opt-in and campus/distance preferences;
- ranking/lifestyle preferences and export privacy.

Summarize the criteria in 6–10 concise bullets. Clearly label assumptions and unresolved choices.
Only after the user confirms may the runtime write `intake_complete: true` and begin research.

## Config-oriented example

```json
{
  "schema_version": "2.0",
  "intake_version": 2,
  "intake_complete": true,
  "field": "Sociology",
  "subfields": ["political sociology", "organizations"],
  "discipline_mode": "faculty_based",
  "advisor_label": "faculty/advisor",
  "application_cycle": "2027 admission",
  "regions": [
    {
      "key": "US",
      "label": "United States",
      "short": "US",
      "color": "#0F4D92",
      "order": 0
    }
  ],
  "stipend_floor": 35000,
  "currency": "USD",
  "n_programs": 20,
  "n_pis_per_program": 8,
  "seed_programs": [],
  "interest_areas": {
    "Organizations": ["organization", "institution"],
    "Methods": ["ethnograph", "causal inference"]
  },
  "food_preferences": {
    "enabled": true,
    "priority_cuisines": ["Sichuan", "Cantonese", "Hunan"],
    "max_distance": "30 minutes",
    "travel_modes": ["walk", "transit"],
    "budget": "any",
    "spice": "very spicy",
    "dietary_needs": []
  },
  "export": {
    "excel": true,
    "include_private_notes": false
  }
}
```
