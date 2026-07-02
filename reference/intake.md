# Intake question bank

Run this as a short conversation (about 3–5 structured or plain-language question rounds plus a
couple of open follow-ups). Adapt wording to the user's field. Goal: fill the
`args`/`_config.json` fields. Do **not** ask for or store the user's name or identity.

## A. Field & topics (open)
- "What field is your PhD in, and which specific subfields / methods / systems do you care about most?"
- Capture → `field`, `subfields`. Use these to also generate `interest_areas` buckets.

## B. Regions (structured multi-select if available) → `regions`
- "Where do you want to apply?" Options e.g.: United States · Europe (broadly) · United Kingdom ·
  Canada · Hong Kong / Singapore · China · Australia · Other.
- For each chosen region set `{key, label, short, color, order}`. Assign distinct colors
  (palette: #0F4D92 #42949E #B64342 #8B5CF6 #E2A52C #3775BA). Ask if any region is "partial"
  (only if funded / only certain programs).

## C. Funding (structured choices or open) → `stipend_floor`, `currency`
- "What's your minimum acceptable annual stipend, and in what currency?" This is a hard filter.
- Common presets: $35,000 · $30,000 · $40,000 · no minimum.

## D. Scope (structured choices or open) → `n_programs`, `n_pis_per_program`
- "How many programs should I research?" (e.g. ~10 / ~20 / ~30)
- "How many fitting PIs per program?" (e.g. 6 / 10 / 12)

## E. PI preferences (structured multi-select if available) → `pi_preferences`, `rising_star_bias`
- "What kind of advisors do you want?" Options e.g.:
  - Rising stars (junior, lab started ~recently, actively recruiting)
  - Small / young labs over big established ones
  - Strong direction-fit / mid-career specialists
  - Novel-method / interesting labs
  - Compute-first / dry vs wet-lab balance (ask which)
  - Mechanism-oriented vs descriptive/association
- "How strongly should I favor rising stars over famous names?" → `rising_star_bias`: strong / moderate / neutral.

## F. Application constraints (open) → `notes`
- "Any application mechanics you care about? e.g. can you apply to multiple programs at one
  school (hedging), deadlines, GRE, fee waivers?"

## G. Lifestyle / other (open) → `notes`
- City size preference; international-student funding/visa concerns; academia-vs-industry
  outcome interest; anything else that defines 'fit'.

## Wrap-up
Summarize the collected criteria back to the user in 4–6 bullets and confirm before launching
the research workflow or Codex-equivalent web research. Write everything into `_config.json`
(branding, regions, floor, interest_areas, col_index) and pass the research params as Workflow
`args` when Workflow is available.
