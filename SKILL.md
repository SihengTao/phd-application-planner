---
name: phd-application-planner
description: >-
  Find and compare PhD / doctoral programs and fitting faculty (PIs / advisors), then
  build an interactive marimo dashboard to decide where to apply. Use when the user wants
  to find PhD programs, graduate schools, doctoral programs, or research advisors matching
  their field, region, funding/stipend needs, and PI preferences; to compare programs on
  stipend, fit, application restrictions, international-student friendliness, or career
  outcomes; to build a PhD application shortlist, tracker, or decision dashboard; or to
  surface rising-star / direction-fit PIs per program. Triggers: "find PhD programs",
  "grad school shortlist", "which programs should I apply to", "PhD advisor / PI finder",
  "compare stipends / funding", "PhD application dashboard". Starts by interactively asking
  what the user cares about, researches in parallel, and delivers a marimo dashboard.
---

# PhD Application Planner — program & PI finder → marimo dashboard

Turns a short intake conversation into a researched, interactive **marimo** decision
dashboard: browse programs and their fitting PIs, filter, annotate, hide, rank by weighted
priority, and read stats-based recommendations. Everything is driven by the user's own
criteria — **this skill hard-codes no personal data.**

Pipeline: **① intake (interactive)** → **② write `_config.json`** → **③ parallel research
or equivalent web-researched `_wf_result.json`** → **④ build data** → **⑤ launch marimo**.

Assets (in `assets/`): `dashboard_template.py` (the marimo app — all features),
`research_workflow.js` (parallel research), `build_data.py`, `launch.py`.
Reference: `reference/intake.md`, `reference/schema.md`, `reference/honesty.md`.

Runtime compatibility:

- In **Claude Code**, use structured question tools when available and run
  `assets/research_workflow.js` with the Workflow tool.
- In **Codex**, use `request_user_input` only when that tool is available; otherwise ask concise
  plain-language questions. If no Workflow tool exists, perform the same research with web search
  and/or subagents, then save the final object directly as `<out>/_wf_result.json` using the schema
  in `reference/schema.md`. Continue with the same build and launch steps.

---

## Step 0 — Pick a working directory

Create/choose an output folder for this run (e.g. `./phd_compass/` or a user-named path).
All generated files land there: `_config.json`, `_research_data.json`, `_rows.json`,
`_wf_result.json`, `phd_explorer.py`, plus the user's `_pi_notes.json` / `_pi_hidden.json`.

## Step 1 — Interactive intake (REQUIRED, do this first)

Before any research, **have a short conversation to learn what the user cares about.** Use a
structured question tool when the host provides one; otherwise ask concise plain follow-up
questions. Collect (see `reference/intake.md` for the full question bank + option sets):

1. **Research field / subfields** (free text) — the discipline and the specific topics/methods they want.
2. **Regions / countries** — where they'll apply (and any "partial" regions). Capture a short label + color per region.
3. **Funding** — the hard minimum stipend floor + currency (a firm filter).
4. **Scope** — roughly how many programs, and how many fitting PIs per program.
5. **PI preferences** — rising-star vs established, lab size (small/young vs large), wet/dry balance, specific methods/topics, mechanism-vs-descriptive leanings.
6. **Rising-star bias** — how strongly to favor junior/rising PIs over famous ones.
7. **Application constraints they care about** — e.g. can-apply-to-multiple-programs hedging, deadlines.
8. **Lifestyle / other** — city-size preference, international-student concerns, academia-vs-industry outcome interest.

Keep it to ~3–5 short question rounds; don't over-interrogate. Confirm the summary back to the
user before researching.

## Step 2 — Write `_config.json`

From the intake answers, write `<out>/_config.json`. Fields the dashboard reads:

```json
{
  "title": "PhD Application Planner — <field> program & PI dashboard",
  "subtitle": "powered by marimo · <regions> · <field>",
  "stipend_floor": 35000,
  "currency": "USD",
  "current_year": 2026,
  "regions": [
    {"key": "US", "label": "United States", "short": "US", "color": "#0F4D92", "order": 0}
  ],
  "region_order": {"US": 0},
  "interest_areas": { "<Bucket>": ["keyword", "..."] },
  "col_index": { "new york": 187 }
}
```

- **`interest_areas`** — YOU generate this: 6–10 buckets of lowercase keyword substrings that
  auto-tag each PI's research by subfield **for the user's field** (e.g. for immunology:
  "T-cell", "innate immunity", "autoimmunity"…). These power the interest heatmap + priority
  ranker. If unsure, omit and a broad default is used.
- **`regions`** — one entry per region the user chose (assign distinct colors; `short` is the
  badge label). `region_order` sets sort order.
- **`col_index`** — optional cost-of-living index by lowercase city substring (avg=100); enables
  the "real purchasing power" chart. Seed major target cities or omit.

## Step 3 — Parallel research

Preferred Claude Code path: run `assets/research_workflow.js` via the **Workflow** tool, passing
the intake config as `args`. It runs fully in parallel: per-region program discovery → per-program
(facts ‖ PIs ‖ outcomes) → adversarial stipend/restriction verification.

```
Workflow({
  scriptPath: "<abs path>/assets/research_workflow.js",
  args: { field, subfields, regions, stipend_floor, currency,
          n_programs, n_pis_per_program, pi_preferences, rising_star_bias,
          notes, seed_programs: [] }
})
```

- If the user already named specific schools/programs, pass them as `seed_programs`
  (`[{school, program, region, city}]`); otherwise discovery fills the list.
- When it completes, **save the workflow's `result` object to `<out>/_wf_result.json`.**
- Follow `reference/honesty.md`: never fabricate stipends/PIs; keep "not found" honest.

Codex or no-Workflow path: run the same phases manually with web search and/or subagents. Use the
prompts and JSON schemas inside `assets/research_workflow.js` as the contract, then write:

```json
{
  "field": "<field>",
  "regions": [{"key": "US", "label": "United States"}],
  "floor": 35000,
  "currency": "USD",
  "programs": [
    {
      "region": "US",
      "school": "...",
      "program": "...",
      "city": "...",
      "facts": {},
      "pis": {"pis": []},
      "out": {}
    }
  ]
}
```

Save that object as `<out>/_wf_result.json`; `assets/build_data.py` accepts the same shape.

## Step 4 — Build the dashboard data

```
python3 assets/build_data.py <out>/_wf_result.json <out>
```

Writes `<out>/_research_data.json` and `<out>/_rows.json` in the exact shape the dashboard
reads (see `reference/schema.md`).

## Step 5 — Launch marimo

Copy the app next to the data, then launch (persistent + auto-opens the browser):

```
cp assets/dashboard_template.py <out>/phd_explorer.py
python3 assets/launch.py <out>/phd_explorer.py
```

Use the **same Python that has marimo installed** (install with `pip install marimo pandas
matplotlib scipy scikit-learn` if needed). The dashboard reads the JSON from its own folder.

## What the dashboard gives the user (all included)

KPIs · ⭐ top-fit picks · 🔎 **program browser** (region/fit/stipend/hedge filters, aligned
table rows, per-row ✕ to hide + restore) · 🏫 program detail cards · 🔬 **PI browser**
(category/wet-dry/region/min-h/keyword filters, per-row ✕ hide, **editable persistent notes
per PI**, Scholar links) · 🎯 **weighted priority ranker** (5 sliders + interest picks) · 💰
cost-of-living-adjusted real stipend · 📊 **statistics** (Spearman, Kruskal–Wallis, Pareto
frontier, K-means clustering + PCA) with stats-based recommendations. Notes/hidden lists
persist across restarts. Footer: *powered by marimo*.

## Notes

- Re-running research overwrites `_research_data.json` / `_rows.json` but **not** the user's
  `_pi_notes.json` / `_pi_hidden.json` (those are theirs).
- The dashboard UI strings are in Chinese by default (from the reference implementation);
  translate labels in `phd_explorer.py` if the user prefers another language.
- Never write the user's personal identity into any generated file — the dashboard is about
  programs and PIs, not the applicant.
