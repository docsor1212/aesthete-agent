# aesthete-agent

**Mechanically validated frontend aesthetics for AI agents.** An agent skill (and MCP server) that plans, validates, and exports color systems — so your agent stops shipping purple-gradient AI slop and starts shipping palettes that pass WCAG, survive color-blindness, and read as designed.

[![install](https://img.shields.io/badge/install-npx%20skills%20add%20docsor1212%2Faesthete-agent-blue)](https://github.com/docsor1212/aesthete-agent)
[![license](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![palette library](https://img.shields.io/badge/palette%20library-89%20crowd%2Dendorsed-orange)](#the-evidence-library)
[![tests](https://img.shields.io/badge/tests-27%20passing-brightgreen)](tests/)

## Why

LLMs choose colors badly for measurable reasons: they treat hex codes as text, they regress to the median of their training data (the frontend-tutorial median is purple/indigo), and they cannot see the colors they emit. `aesthete-agent` fixes this the engineering way — **outsource taste to process**:

- an **evidence library** of 89 palettes harvested from community "most-endorsed" charts, filtered by objective quality gates (flat lightness → rejected; no readable text pair → rejected; color-blind collisions / slop signatures → flagged),
- **mechanical gates** on every decision: a 5-dimension scorecard, exact WCAG 2.2 boundaries, three color-blindness simulations, AI-slop signature detection, and an HTML delivery linter,
- a **six-step method** (manifesto → register check → source → roles → validate → five-lens review) that turns "make it pretty" into a reproducible pipeline,
- a **preference profile** (`profile.json`) that learns from every accept/reject verdict and mechanically down-ranks what the user rejects — e.g. dark grounds, banned hex families.

## Install

**Agent skills CLI** (Claude Code, ZCode, Codex, Cursor, Gemini CLI, and any `skills`-compatible agent):

```bash
npx skills add docsor1212/aesthete-agent
```

**MCP server** (Claude Desktop, Cursor, any MCP client) — expose the engine as tools:

```bash
uvx aesthete-agent-mcp
```

**SkillHub** (中文站): search `aesthete-agent` or `前端美学`.

Pure Python stdlib in the core engine (offline, zero keys, zero telemetry); Pillow optional for image extraction; FastMCP optional for the MCP server.

## 30-second agent quickstart

```bash
S="scripts/palette_forge.py"   # inside the installed skill directory
python "$S" match --brief "pediatric clinical teaching page" --limit 6   # rank the evidence library by register
python "$S" score --palette 264653,2A9D8F,E9C46A,F4A261,E76F51           # 5-dim scorecard /20
python "$S" matrix --palette ... --method apca --recommend               # full contrast matrix (APCA = WCAG 3 draft)
python "$S" semantic --count 8 --base 2A9D8F                             # color-blind-safe categorical colors
python "$S" theme "Golden Window Suya" --format css                      # named theme pack → CSS tokens
python "$S" export --palette ... --format w3c                            # W3C Design Tokens JSON
python "$S" export --palette ... --format context                        # paste-ready color context for any LLM
python "$S" doctor                                                       # environment health check
```

Full method (manifesto → register → source → roles → validate → five-lens review) lives in [SKILL.md](SKILL.md). References carry a 30-second routing table per task.

## What's inside

| Area | Highlights |
|---|---|
| Engine (23 subcommands) | match/search/harmony/ramp/mutate/roles/score/contrast/blind/matrix/semantic/slop/themes/theme/export(w3c·context·css·tailwind)/card/showcase/visualize/critique/doctor/selftest/house |
| Evidence library | 89 palettes with likes tiers, computed style tags, gate flags, sources |
| Theme packs | 8 named packs (colors + fonts + voice + use-when), all with dogfood provenance |
| Quality gates | exit-code enforced: scorecard, contrast, blind collisions, slop, HTML lint, candidate discipline |
| Learning | `profile.json` preferences consumed by match/score/lint; verdict write-back is an iron rule |
| Tests | 27 automated tests incl. WCAG boundary values (#767676=4.54 pass / #777777=4.48 fail), APCA, W3C export |

## The evidence library

Nobody can know "beautiful" a priori — so the library is built from three filters, each doing only what it can: **crowd signal** (community-endorsed charts, like tiers, cross-page recurrence), **objective gates** (reject only objectively broken architecture: flat lightness, no readable pair; flag CB collisions and slop), and **in-context review** (the final verdict happens in real layouts, with the user). Rejections are recorded with reasons — 29 of the first 116 candidates were rejected, all with measured causes.

## MCP server

`mcp/` wraps the engine as MCP tools (JSON-RPC over stdio, FastMCP). Zero keys, zero telemetry; the engine itself has no FastMCP dependency.

| Tool | Wraps |
|---|---|
| `palette_match` | evidence-library ranking by brief |
| `palette_harmony` | OKLCH harmony generation |
| `palette_score` | 5-dim scorecard |
| `palette_contrast` | WCAG / APCA pair check |
| `palette_matrix` | full pair matrix |
| `palette_semantic` | CB-safe categorical colors |
| `palette_themes` / `palette_theme` | named theme packs |
| `palette_export` | css / tailwind / w3c / context tokens |

## Platform availability

| Platform | Handle | Install |
|---|---|---|
| GitHub (source of truth) | [docsor1212/aesthete-agent](https://github.com/docsor1212/aesthete-agent) | `npx skills add docsor1212/aesthete-agent` |
| ClawHub (international) | `aesthete-agent` | via ClawHub CLI |
| SkillHub (中文站) | `aesthete-agent` | search `前端美学` |
| MCP | `aesthete-agent-mcp` | `uvx aesthete-agent-mcp` |

## License

MIT
