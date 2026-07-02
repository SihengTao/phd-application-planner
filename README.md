# PhD Application Planner

A **Claude Code / Codex skill** that turns a short conversation into a researched,
interactive **[marimo](https://marimo.io) dashboard** for planning PhD applications:
find programs, surface fitting advisors (PIs), compare stipends and application rules,
and decide where to apply.

It works for **any field, any region**. You tell it what you care about; it researches in
parallel when the host supports workflow/subagent tools, then hands you a dashboard you can
filter, annotate, and rank.

> No personal data is baked in. Every run is driven entirely by your own intake answers.

---

## What you get

A single-page marimo app with:

- **KPIs** and a **top-fit picks** grid
- **Program browser**: filter by region / fit / stipend / application-hedge; aligned table
  rows; click **x** on any row to hide it and restore later
- **Program detail cards**: stipend with verification basis, cohort, deadlines, application
  restrictions, career outcomes, international-student notes
- **PI browser**: filter by category / wet-dry / region / min-h-index / keyword; per-row
  hide; editable notes per advisor that persist across restarts; Google Scholar links
- **Weighted priority ranker**: 5 sliders plus interest picks, live re-ranking
- **Cost-of-living-adjusted real stipend** chart
- **Statistics**: Spearman correlation, Kruskal-Wallis, Pareto frontier, K-means clustering
  plus PCA, with plain-language, stats-based recommendations

Your notes and hidden lists are saved next to the data, so they survive restarts.

---

## Requirements

- **Claude Code** or **Codex with local Skills enabled**
- **Python 3.9+** with:
  ```bash
  pip install marimo pandas matplotlib scipy scikit-learn
  ```
- Web access for the research step

Claude Code can use the bundled `assets/research_workflow.js` Workflow template. Codex can use
the same `SKILL.md`, `reference/`, and `assets/` package; when a Workflow tool is unavailable,
the skill performs equivalent web research and writes the same `_wf_result.json` schema before
building the dashboard.

---

## Install

### Claude Code

Clone into your Claude Code skills directory:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/SihengTao/phd-application-planner \
  ~/.claude/skills/phd-application-planner
```

Claude Code auto-discovers skills in `~/.claude/skills/`.

### Codex

Clone into your Codex skills directory:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/SihengTao/phd-application-planner \
  "${CODEX_HOME:-$HOME/.codex}/skills/phd-application-planner"
```

Codex discovers local skills from `${CODEX_HOME:-$HOME/.codex}/skills/`. The included
`agents/openai.yaml` provides Codex-facing display metadata; the root `SKILL.md` is the
shared execution guide.

---

## Usage (tutorial)

Ask Claude Code or Codex, in any project:

> "Help me find PhD programs in *<your field>* and build me a dashboard."

You can also invoke it explicitly:

- Claude Code: `/phd-application-planner`
- Codex: `Use $phd-application-planner to help me build a PhD application dashboard.`

### The 5 steps it runs

1. **Interactive intake.** It asks what you care about: research field and subfields, target
   regions/countries, minimum stipend and currency, how many programs and advisors per program,
   PI preferences, rising-star bias, application constraints, and lifestyle/outcome concerns.
   This is usually 3-5 quick question rounds.

2. **Config.** It writes a `_config.json` with dashboard branding, regions, stipend floor, and
   an auto-generated interest-tag taxonomy for your field.

3. **Research.** In Claude Code, it can run the bundled Workflow template for parallel research.
   In Codex, or in any host without Workflow, it performs the same program / PI / outcome /
   verification research path and saves the final object as `_wf_result.json`. Stipends and PIs
   should be verified against official pages and Google Scholar; "not found" stays honest.

4. **Build data.** It assembles the results into the dashboard's data files.

5. **Launch.** It copies the marimo app next to the data and starts it, opening it in your
   browser.

### After it launches

- Browse programs and advisors; hide the ones you're not interested in.
- Write notes on each advisor as you meet/read about them; notes persist.
- Use the priority ranker sliders to weight fit / stipend / city / advisor-density / topics.
- Read the statistics section for data-driven strategy tips.

Re-running the research refreshes the program/PI data but keeps your notes and hidden lists.

---

## Repository layout

```text
phd-application-planner/
├── SKILL.md                    # shared Claude Code / Codex skill instructions
├── agents/
│   └── openai.yaml             # Codex skill display metadata
├── assets/
│   ├── dashboard_template.py   # the marimo app
│   ├── research_workflow.js    # Claude Workflow research template
│   ├── build_data.py           # research output -> dashboard data files
│   └── launch.py               # detached marimo launcher
├── reference/
│   ├── intake.md               # intake question bank
│   ├── schema.md               # data schema
│   └── honesty.md              # verification / no-fabrication rules
├── README.md
└── LICENSE
```

### Configuration notes

- **Regions are arbitrary**: US, EU, UK, Canada, Singapore, China, etc. Each gets a color and
  short label in `_config.json`; the whole dashboard adapts.
- **Seed programs**: if you already have a target list, it is passed straight into the research
  step instead of auto-discovery.
- **Language**: the dashboard UI labels ship in Chinese; translate strings in
  `dashboard_template.py` if you prefer another language. Titles/subtitles are configurable per
  run via `_config.json`.

---

## A note on accuracy

Stipends, deadlines, cohort sizes, application rules, and h-indexes are **web-research
snapshots**. They can be wrong or out of date. Always confirm the numbers that matter on the
program's official pages before deciding. See `reference/honesty.md` for the verification rules
the skill follows.

---

## License

[MIT](LICENSE), powered by [marimo](https://marimo.io).

---

# 博士申请规划器

这是一个同时适用于 **Claude Code / Codex 的 skill**。它会把一段简短对话转成一个经过调研的
交互式 **[marimo](https://marimo.io) 仪表盘**，用来规划博士申请：寻找项目、筛选匹配的导师
（PI）、比较 stipend 和申请规则，并帮助你决定申请哪些项目。

它适用于**任何领域、任何地区**。你只需要说明自己在意什么；如果运行环境支持 workflow 或
subagent，它会并行调研，然后交付一个可以筛选、做笔记、隐藏、排序的仪表盘。

> 仓库里不内置任何个人信息。每次运行都完全由你当次回答的 intake 信息驱动。

---

## 你会得到什么

一个单页 marimo 应用，包含：

- **关键指标**和**最匹配项目**列表
- **项目浏览器**：按地区、匹配度、stipend、申请 hedging 过滤；可以隐藏/恢复单行
- **项目详情卡**：stipend 及验证依据、cohort、deadline、申请限制、career outcome、
  国际学生相关备注
- **PI 浏览器**：按类别、wet/dry、地区、最低 h-index、关键词过滤；可以隐藏 PI；可以给每个
  PI 写持久化笔记；带 Google Scholar 链接
- **加权优先级排序器**：5 个滑块加兴趣方向选择，实时重新排序
- **生活成本调整后的实际 stipend** 图
- **统计分析**：Spearman 相关、Kruskal-Wallis、Pareto frontier、K-means clustering 和 PCA，
  并给出易读的策略建议

笔记和隐藏列表会保存在数据旁边，重启后仍然保留。

---

## 环境要求

- **Claude Code** 或 **开启本地 Skills 的 Codex**
- **Python 3.9+**，并安装：
  ```bash
  pip install marimo pandas matplotlib scipy scikit-learn
  ```
- 调研阶段需要联网

Claude Code 可以使用仓库里的 `assets/research_workflow.js` Workflow 模板。Codex 可以使用同一个
`SKILL.md`、`reference/` 和 `assets/` 包；如果没有 Workflow 工具，skill 会执行等价的网页调研，
写出同样结构的 `_wf_result.json`，再继续构建仪表盘。

---

## 安装

### Claude Code

克隆到 Claude Code 的 skills 目录：

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/SihengTao/phd-application-planner \
  ~/.claude/skills/phd-application-planner
```

Claude Code 会自动发现 `~/.claude/skills/` 下的 skills。

### Codex

克隆到 Codex 的 skills 目录：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/SihengTao/phd-application-planner \
  "${CODEX_HOME:-$HOME/.codex}/skills/phd-application-planner"
```

Codex 会从 `${CODEX_HOME:-$HOME/.codex}/skills/` 发现本地 skills。仓库中的
`agents/openai.yaml` 提供 Codex 侧的展示元数据；根目录的 `SKILL.md` 是 Claude Code 和 Codex
共用的执行说明。

---

## 使用方式

在 Claude Code 或 Codex 的任意项目里直接说：

> “Help me find PhD programs in *<your field>* and build me a dashboard.”

也可以显式调用：

- Claude Code：`/phd-application-planner`
- Codex：`Use $phd-application-planner to help me build a PhD application dashboard.`

### 它会执行的 5 步

1. **交互式 intake。** 它会询问你的研究领域/子方向、目标地区、最低 stipend 和币种、想调研的
   项目数量和每个项目的 PI 数量、PI 偏好、是否偏好 rising-star、申请机制限制，以及城市/就业
   等考虑。通常是 3-5 轮简短问题。

2. **写配置。** 它会生成 `_config.json`，包含仪表盘标题、地区、stipend floor，以及根据你领域
   自动生成的兴趣标签体系。

3. **调研。** 在 Claude Code 里，它可以运行内置 Workflow 模板进行并行调研。在 Codex 或没有
   Workflow 的环境里，它会执行同样的项目 / PI / outcome / 验证流程，并把最终结果保存为
   `_wf_result.json`。Stipend 和 PI 应该根据官方页面和 Google Scholar 验证；找不到就诚实标注
   “not found”。

4. **构建数据。** 它会把调研结果整理成仪表盘读取的数据文件。

5. **启动。** 它会把 marimo app 复制到数据旁边并启动，在浏览器中打开。

### 启动之后

- 浏览项目和 PI；隐藏不感兴趣的条目。
- 给每个 PI 写笔记，之后重启也会保留。
- 用优先级排序器调整 fit / stipend / city / advisor density / topics 的权重。
- 阅读统计部分，辅助形成申请策略。

重新调研会刷新项目和 PI 数据，但保留你的笔记和隐藏列表。

---

## 仓库结构

```text
phd-application-planner/
├── SKILL.md                    # Claude Code / Codex 共用 skill 说明
├── agents/
│   └── openai.yaml             # Codex skill 展示元数据
├── assets/
│   ├── dashboard_template.py   # marimo 应用
│   ├── research_workflow.js    # Claude Workflow 调研模板
│   ├── build_data.py           # 调研输出 -> 仪表盘数据文件
│   └── launch.py               # 后台 marimo 启动器
├── reference/
│   ├── intake.md               # intake 问题库
│   ├── schema.md               # 数据 schema
│   └── honesty.md              # 验证 / 不编造规则
├── README.md
└── LICENSE
```

### 配置说明

- **地区是任意的**：美国、欧盟、英国、加拿大、新加坡、中国等都可以。每个地区在
  `_config.json` 里有颜色和短标签，仪表盘会自动适配。
- **Seed programs**：如果你已经有目标项目列表，会直接传入调研步骤，而不是从头自动发现。
- **语言**：仪表盘 UI 默认是中文；如果想换语言，可以修改 `dashboard_template.py` 中的字符串。
  标题和副标题也可以在每次运行的 `_config.json` 里配置。

---

## 准确性说明

Stipend、deadline、cohort size、申请规则和 h-index 都是**网页调研快照**，可能错误或过期。决定前
务必到项目官方页面确认关键数字。`reference/honesty.md` 里记录了这个 skill 使用的验证规则。

---

## License

[MIT](LICENSE)，powered by [marimo](https://marimo.io)。
