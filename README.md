# PhD Application Planner

An evidence-aware **Claude Code / Codex skill** that turns a progressive intake conversation
into a researched **[marimo](https://marimo.io) dashboard** and optional Excel workbook for PhD
application planning.

It supports lab-based fields, humanities, social sciences, and hybrid programs. It compares
programs and advisors, funding, application policies, discipline-specific requirements,
placement, international-student information, and campus-anchored Chinese food—with internal
claim-level sources, an independent evidence pass, and a local data checker.

> No applicant identity is built into the repository. Private dashboard notes are excluded from
> Excel by default.

---

## What it adds

- **Progressive onboarding:** first-time users get 5–8 adaptive question rounds rather than one
  large form; returning users review the prior config and answer only what changed.
- **Humanities and social-science mode:** advisor/committee fit, faculty model, writing sample,
  language and field requirements, methods training, teaching load, time to degree, and
  placement replace inappropriate lab-only assumptions.
- **Campus food research 🌶️🌶️🌶️:** searches from the relevant campus or department anchor,
  prioritizing Sichuan, Cantonese, and Hunan restaurants. Menu/location evidence is kept
  separate from subjective reviews and volatile hours, prices, spice, and travel estimates.
- **Claim-level provenance and checking:** critical facts retain source-to-field links, cycle and
  access dates, retrieval status, independent check results, and unresolved conflicts. The
  dashboard never claims that everything is verified unconditionally.
- **Excel export:** export all programs or the current filtered view from the dashboard or CLI.
  Notes are opt-in, and cells are escaped against spreadsheet formula injection.
- **Stable identities:** `program_id` and `advisor_id` prevent same-named programs or faculty
  from mixing data, notes, hidden state, and exports.

The dashboard also includes program/advisor browsers, persistent notes and hidden lists, weighted
ranking, cost-of-living-adjusted stipend views, and guarded statistical summaries.

---

## Evidence states

The checker records each critical claim as:

- `confirmed`: independent evidence agrees;
- `corrected`: independent evidence supports a replacement value;
- `conflict`: current applicable sources disagree;
- `unresolved`: evidence is missing, inaccessible, stale, or insufficient.

Only `confirmed` and `corrected` claims can contribute to a `verified` summary. A source URL or
successful checker process alone does not prove a claim. See
[`reference/source_policy.md`](reference/source_policy.md) and
[`reference/honesty.md`](reference/honesty.md).

---

## Requirements

- **Claude Code** or **Codex with local Skills enabled**
- **Python 3.10+**
- Web access for research and optional online source checks

Install runtime dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Claude Code may run the bundled `assets/research_workflow.js`. Codex or another host without
Workflow performs the same phases with web research and parallel subagents/calls, then writes the
same v2 `_wf_result.json`.

---

## Install

### Claude Code

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/SihengTao/phd-application-planner \
  ~/.claude/skills/phd-application-planner
```

### Codex

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/SihengTao/phd-application-planner \
  "${CODEX_HOME:-$HOME/.codex}/skills/phd-application-planner"
```

`SKILL.md` is the shared execution specification. `agents/openai.yaml` supplies Codex display
metadata.

---

## Use

Ask in either runtime:

> Help me research PhD programs in my field and build an evidence-aware application dashboard.

Or invoke it explicitly:

- Claude Code: `/phd-application-planner`
- Codex: `Use $phd-application-planner to build my PhD application plan.`

### 1. Complete intake

Research is blocked until the user confirms `_config.json` with `intake_complete: true`.

- **First run:** 5–8 progressive rounds cover field, advising model, geography, funding,
  application constraints, advisor fit, discipline-specific requirements/outcomes, nearby food,
  ranking, and export privacy.
- **Returning run:** the skill shows the prior summary, asks what changed, and follows up only on
  changed, missing, inconsistent, or cycle-sensitive items.

The selected `discipline_mode` is:

- `lab_based` for PI/lab-centered advising;
- `faculty_based` for advisor/committee-centered programs;
- `hybrid` when both models matter.

See [`reference/intake.md`](reference/intake.md).

### 2. Research

The skill discovers programs, gathers facts/advisors/outcomes, optionally researches nearby food,
and runs an independent evidence pass. Claude Code can use the bundled Workflow; Codex can run
equivalent parallel research. Both produce `<out>/_wf_result.json`.

For humanities and social sciences, fit research covers advising eligibility, committee breadth,
intellectual and method alignment, languages/archives, writing sample, requirements, teaching
load, and placement. Bibliometrics and lab attributes are optional rather than default ranking
axes.

Nearby-food research is opt-in; missing food preferences leave it disabled. When enabled, it uses
the relevant campus or department address and prioritizes Sichuan, Cantonese, and Hunan while
clearly labeling the evidence basis. "Delicious," "authentic," opening status, spice, price, and
travel time are not guaranteed; re-check before visiting.

### 3. Check, build, and launch

From the repository root, with `OUT` set to the run directory:

```bash
OUT="./phd_compass"

python3 assets/check_data.py "$OUT/_wf_result.json" \
  --output "$OUT/_quality_report.json"

python3 assets/build_data.py "$OUT/_wf_result.json" "$OUT"

cp assets/dashboard_template.py "$OUT/phd_explorer.py"
python3 assets/launch.py "$OUT/phd_explorer.py"
```

Add `--online` to probe source URLs and `--strict` to make warnings fail the checker:

```bash
python3 assets/check_data.py "$OUT/_wf_result.json" \
  --output "$OUT/_quality_report.json" --online --strict
```

The local checker validates schema, stable IDs, closed enums, types, claim/source links,
critical-claim coverage, and conflict handling. An online reachability check cannot establish
that a page semantically supports a claim. `build_data.py` runs the same offline quality gate
again, always writes `_quality_report.json`, blocks on errors, and accepts `--strict` and
`--online` when the build itself should use those modes.

### 4. Export Excel

Use the dashboard's **Excel** panel to export all programs or the current filtered view. Private
advisor notes are off by default and require explicit opt-in.

For command-line export, use the exporter after building data:

```bash
python3 assets/excel_export.py "$OUT" "$OUT/phd_application_plan.xlsx"
```

The CLI exports the complete built dataset. To include private advisor notes, the user must opt in
explicitly:

```bash
python3 assets/excel_export.py "$OUT" "$OUT/phd_application_plan_with_notes.xlsx" \
  --include-notes
```

The generated workbook includes Metadata, Programs, Advisors, Restaurants, Sources, Quality, and
Priority sheets when data is available; requirements and outcomes remain explicit program/
advisor columns. Stable IDs are retained for safe joins. Any exported value beginning with `=`,
`+`, `-`, or `@` is neutralized so untrusted web text cannot become a spreadsheet formula.

---

## Data contract

`_wf_result.json` is the canonical v2 record. Each program contains:

- stable `program_id` and stable advisor `advisor_id` values;
- `facts`, `pis`, and `out`;
- `nearbyFood = {enabled, researchStatus, campusAnchor, restaurants, sources, evidenceChecks,
  errors}`;
- `provenance = {sources, evidenceChecks, checks, conflicts, errors, researchStatus}`.

Section-level `evidenceChecks` are first-pass source observations
(`supported | unresolved | conflict`). Final independent reconciliation is recorded only in
`verification.claimChecks` and `provenance.checks`
(`confirmed | corrected | conflict | unresolved`).

`applicationPolicy` is exactly:

`multiple_allowed | single_only | unknown | conflict`

See [`reference/schema.md`](reference/schema.md) for fields and examples.

---

## Repository layout

```text
phd-application-planner/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   ├── research_workflow.js
│   ├── check_data.py
│   ├── data_quality.py
│   ├── build_data.py
│   ├── dashboard_template.py
│   ├── excel_export.py
│   └── launch.py
├── reference/
│   ├── intake.md
│   ├── schema.md
│   ├── source_policy.md
│   └── honesty.md
├── tests/
├── requirements.txt
├── README.md
└── LICENSE
```

Generated run files:

```text
<out>/
├── _config.json
├── _wf_result.json
├── _quality_report.json
├── _research_data.json
├── _rows.json
├── phd_explorer.py
├── _pi_notes.json       # private runtime state; not exported by default
└── _pi_hidden.json
```

Refreshes replace derived research data but preserve stable IDs, notes, and hidden state.

---

## Accuracy and privacy

Funding, deadlines, application rules, advisor availability, placement, restaurant details, and
routes are time-sensitive research snapshots. The skill exposes sources, conflicts, and missing
evidence, but the applicant should still confirm high-impact facts on the applicable official
pages before acting.

Do not put applicant identity or secrets in generated research files. Excel notes remain
excluded unless explicitly requested.

---

## License

[MIT](LICENSE), powered by [marimo](https://marimo.io).

---

# 博士申请规划器

这是一个同时适用于 **Claude Code / Codex 的、重视证据的 skill**。它会通过渐进式询问了解需求，
然后生成经过调研的 **[marimo](https://marimo.io) 仪表盘**，也可以导出 Excel，用于规划博士申请。

它支持实验室型学科、人文学科、社会科学和混合型项目。除了项目、导师、funding 和申请规则，
它还会比较学科特定要求、placement、国际学生信息，以及以校区为锚点的中餐馆；关键消息在内部
保留字段级来源，并经过独立证据复核和本地 checker 检查。

> 仓库不内置申请者身份信息。仪表盘里的私人笔记默认不会导出到 Excel。

---

## 新增能力

- **渐进式首次询问：** 第一次使用会分 5–8 轮自适应提问，而不是一次抛出大表单；返回用户先
  查看旧配置，只补充发生变化的内容。
- **人文社科模式：** 关注 advisor/committee 契合度、faculty model、writing sample、语言和
  field requirement、method training、teaching load、毕业时间和 placement，不再强行套用
  实验室指标。
- **学校周边中餐 🌶️🌶️🌶️：** 从真正相关的校区或院系位置出发，优先查询川菜、粤菜和湘菜。
  官方菜单/地址证据会与主观评价，以及容易变化的营业时间、价格、辣度和通勤估计分开。
- **字段级来源与独立检查：** 关键事实记录来源所支持的具体字段、申请周期、访问日期、抓取
  状态、独立核验结果和未解决冲突。仪表盘不会无条件声称所有消息都“已核验”。
- **Excel 导出：** 可以从仪表盘或 CLI 导出全部项目或当前筛选结果。笔记需要主动选择才会
  导出；所有单元格都会防止 spreadsheet formula injection。
- **稳定 ID：** `program_id` 和 `advisor_id` 避免同名项目或教师错误地共享数据、笔记、
  隐藏状态和导出记录。

仪表盘还包括项目/导师浏览器、持久化笔记和隐藏列表、加权排序、生活成本调整后的 stipend
视图，以及带保护条件的统计总结。

---

## 证据状态

checker 会把每项关键消息标为：

- `confirmed`：独立证据与首轮结果一致；
- `corrected`：独立证据支持修正后的值；
- `conflict`：当前且适用的来源相互冲突；
- `unresolved`：证据缺失、无法访问、过期或不足。

只有 `confirmed` 和 `corrected` 才能计入 `verified` 汇总。仅仅存在一个 URL 或 checker 成功
运行，并不能证明内容正确。详见
[`reference/source_policy.md`](reference/source_policy.md) 和
[`reference/honesty.md`](reference/honesty.md)。

---

## 环境要求

- **Claude Code** 或 **开启本地 Skills 的 Codex**
- **Python 3.10+**
- 调研和可选在线来源检查需要联网

安装运行依赖：

```bash
python3 -m pip install -r requirements.txt
```

Claude Code 可以运行内置的 `assets/research_workflow.js`。Codex 或没有 Workflow 的环境会用
网页调研和并行 subagent/tool call 执行同样阶段，并生成同样的 v2 `_wf_result.json`。

---

## 安装

### Claude Code

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/SihengTao/phd-application-planner \
  ~/.claude/skills/phd-application-planner
```

### Codex

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/SihengTao/phd-application-planner \
  "${CODEX_HOME:-$HOME/.codex}/skills/phd-application-planner"
```

`SKILL.md` 是两种运行环境共用的执行规范；`agents/openai.yaml` 提供 Codex 展示元数据。

---

## 使用

在任意一种环境中直接说：

> 帮我调研适合我的博士项目，并生成一个带来源检查的申请仪表盘。

也可以显式调用：

- Claude Code：`/phd-application-planner`
- Codex：`Use $phd-application-planner to build my PhD application plan.`

### 1. 完成 intake

在用户确认 `_config.json` 且 `intake_complete: true` 之前，禁止开始调研。

- **第一次运行：** 分 5–8 轮渐进询问领域、指导模式、地区、funding、申请限制、导师契合度、
  学科特定要求/结果、周边中餐、排序和导出隐私。
- **再次运行：** 先展示已有配置，只询问发生的变化；只有内容改变、缺失、相互矛盾或随申请
  周期变化时才继续追问。

`discipline_mode` 有三种：

- `lab_based`：以 PI/实验室为中心；
- `faculty_based`：以 advisor/committee 为中心；
- `hybrid`：两种模式都重要。

详见 [`reference/intake.md`](reference/intake.md)。

### 2. 调研

skill 会发现项目，调研项目事实、导师和 outcome，并运行独立证据检查。附近中餐查询需要
用户明确选择；若配置中没有 food preferences，默认关闭。Claude Code 可以使用内置
Workflow；Codex 可以执行等价的并行调研。两者都会生成 `<out>/_wf_result.json`。

对人文社科，契合度会覆盖导师资格、committee 广度、思想/方法匹配、语言/档案、writing
sample、培养要求、teaching load 和 placement。h-index 和实验室属性只是可选信息，不会成为
默认排序标准。

附近餐馆以相关校区或院系地址为锚点，优先川菜、粤菜和湘菜，并明确标注证据依据。“好吃”、
“正宗”、当前营业、辣度、价格和通勤时间都不是保证；前往前请再次确认。

### 3. 检查、构建和启动

在仓库根目录运行，并让 `OUT` 指向本次输出目录：

```bash
OUT="./phd_compass"

python3 assets/check_data.py "$OUT/_wf_result.json" \
  --output "$OUT/_quality_report.json"

python3 assets/build_data.py "$OUT/_wf_result.json" "$OUT"

cp assets/dashboard_template.py "$OUT/phd_explorer.py"
python3 assets/launch.py "$OUT/phd_explorer.py"
```

`--online` 会探测来源 URL；`--strict` 会让 warning 也导致 checker 失败：

```bash
python3 assets/check_data.py "$OUT/_wf_result.json" \
  --output "$OUT/_quality_report.json" --online --strict
```

本地 checker 会检查 schema、稳定 ID、封闭枚举、类型、claim/source 关联、关键 claim 覆盖和
冲突处理。在线可访问性检查仍不能证明网页内容确实支持该字段。`build_data.py` 会再次运行同一
套离线质量门、始终写出 `_quality_report.json`，并在出现 error 时阻止构建；如果希望构建阶段
本身使用严格或在线模式，也可以给它添加 `--strict` 和 `--online`。

### 4. 导出 Excel

在仪表盘的 **Excel** 区域中，可以导出全部项目或当前筛选结果。导师私人笔记默认关闭，只有
用户主动选择后才会加入。

构建数据后也可以使用命令行导出器：

```bash
python3 assets/excel_export.py "$OUT" "$OUT/phd_application_plan.xlsx"
```

CLI 会导出完整的已构建数据。只有在用户明确同意后，才可以加入私人导师笔记：

```bash
python3 assets/excel_export.py "$OUT" "$OUT/phd_application_plan_with_notes.xlsx" \
  --include-notes
```

工作簿会在存在数据时包含 Metadata、Programs、Advisors、Restaurants、Sources、Quality 和
Priority 工作表；requirements 和 outcomes 会保留为明确的 program/advisor 列。工作簿会保留
稳定 ID 以便安全关联。任何以 `=`, `+`, `-`, `@` 开头的内容都会被中和，避免网页文本被
Excel 当成公式执行。

---

## 数据契约

`_wf_result.json` 是 canonical v2 记录。每个项目包含：

- 稳定的 `program_id`，以及稳定的导师 `advisor_id`；
- `facts`、`pis` 和 `out`；
- `nearbyFood = {enabled, researchStatus, campusAnchor, restaurants, sources, evidenceChecks,
  errors}`；
- `provenance = {sources, evidenceChecks, checks, conflicts, errors, researchStatus}`。

各分区的 `evidenceChecks` 是第一次资料收集记录
（`supported | unresolved | conflict`）。最终独立核验只写入
`verification.claimChecks` 和 `provenance.checks`
（`confirmed | corrected | conflict | unresolved`）。

`applicationPolicy` 只能是：

`multiple_allowed | single_only | unknown | conflict`

字段和示例详见 [`reference/schema.md`](reference/schema.md)。

---

## 仓库结构

```text
phd-application-planner/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── assets/
│   ├── research_workflow.js
│   ├── check_data.py
│   ├── data_quality.py
│   ├── build_data.py
│   ├── dashboard_template.py
│   ├── excel_export.py
│   └── launch.py
├── reference/
│   ├── intake.md
│   ├── schema.md
│   ├── source_policy.md
│   └── honesty.md
├── tests/
├── requirements.txt
├── README.md
└── LICENSE
```

每次运行的输出：

```text
<out>/
├── _config.json
├── _wf_result.json
├── _quality_report.json
├── _research_data.json
├── _rows.json
├── phd_explorer.py
├── _pi_notes.json       # 私人运行状态；默认不导出
└── _pi_hidden.json
```

刷新会替换派生调研数据，但保留稳定 ID、笔记和隐藏状态。

---

## 准确性与隐私

Funding、deadline、申请规则、导师招生状态、placement、餐馆消息和路线都是时效性快照。
skill 会暴露来源、冲突和证据缺口，但申请者在做高影响决定前仍应到适用的官方页面确认。

不要把申请者身份或秘密写进调研文件。除非用户明确要求，Excel 不会包含私人笔记。

---

## License

[MIT](LICENSE)，powered by [marimo](https://marimo.io)。
