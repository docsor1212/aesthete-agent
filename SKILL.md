---
version: 0.3.0
name: aesthete-agent
description: Color palette generation, frontend aesthetics, UI color schemes — mechanically validated color output for UI/HTML, SVG slides, video covers, charts and posters. An 87-palette evidence library matched by register, OKLCH harmony generation, luminance ramps and image extraction; 60-30-10 role mapping with semantic colors; a 5-dimension scorecard plus WCAG contrast, color-blind simulation and AI-slop detection as four mechanical gates; card and six-scene visualizer previews; a preference-learning profile that evolves with every verdict. Named theme packs, full contrast matrices, CB-safe data-viz palettes, five-lens critique reports, and APCA (WCAG 3 draft) perceptual contrast included. Pure stdlib, offline. Skip when pure text layout, translation or polishing, copywriting, or any task unrelated to color and frontend aesthetics. Trigger words — color palette, color scheme, palette generation, frontend aesthetics, UI color, design aesthetics, hex, contrast, WCAG, color blind, visual taste, aesthete-agent.
---

# aesthete-agent — Frontend Aesthetics Engine

Why LLM color output is bad, with evidence: models treat hex codes as text, regress to the median of training data (the frontend-tutorial median is purple/indigo), and cannot actually see color. The fix is not a better model — it is **outsourcing taste to process**: manifesto first, role mapping, mechanical validation, in-context self-review.

⛔ Iron rules:
1. **No bare palette writing.** Every color task goes through the six-step method; step 6 (five-lens review) is not skippable.
2. **No runtime access to coolors.co** — no public API, direct connections hit Cloudflare 403; all data ships offline.
3. **The brief is law**: colors and aesthetics pinned by the user are binding constraints. Already-shipped brand systems are out of scope for re-paletteing.
4. **Bounded verification**: build fully → one batched review → one batched fix round → at most one more confirmation → **stop polishing**.
5. **Candidate discipline**: user verdicts require ≥2 full-page candidates (`make_variants.py` builds the comparison sheet); a single proposal is not sent for review.
6. **Verdict write-back**: every accept/reject lands in `profile.json` (machine-read) and `critique.md` necropsies (failure modes) — no write-back, no growth.

## Capability × Boundary Quick Reference

| Capability | Does | Does not | Deep dive |
|---|---|---|---|
| Library match/search | Rank an 87-palette evidence library by register + likes tiers + objective gates | Does not judge "subjective beauty" — final verdict is in-context | curation.md |
| Generate harmony / ramp / mutate | OKLCH harmony, luminance ramps, perceptual transforms with auto gamut fit | No illustration or gradient-image export | color-theory.md |
| Extract | Pull dominant colors + shares + readable-text hints from a reference image | No image redraw or matting | — |
| Roles | bg/text/accent/primary/surface + semantic colors, with contrast checks | Not a layout or type-selection system | craft-rules.md |
| Validate score/contrast/blind | 5-dim scorecard, exact WCAG boundaries, three color-blind simulations, fix suggestions on failure | Does not judge taste; contrast is necessary, not sufficient | color-theory.md |
| Anti-pattern slop + lint_page | Median-trap/purple-gradient/flat-lightness detection; HTML delivery audit | Does not cover every aesthetic failure — five-lens screenshots fill the gap | anti-slop.md |
| Preview card / showcase / make_variants | Palette cards + mockups; named showcase picks; ≥2-candidate comparison | Not a substitute for a real-environment smoke test | critique.md |
| Visualizer scenes + SVG recolor | 10 realistic scenes (mobile / landing / dashboard / branding / typography / pattern / chart / product card / email / editorial) with derived roles, legibility gates and a text ladder; SVG recolor via slot inventory (design's own colors mapped by rank, pure black/white kept), `--shuffle N` renders N permutations with a comparison grid | Scene mockups are decision aids, not production UI | critique.md |
| Learn house + profile.json | Accepted designs join the corpus; preferences (theme/bans/registers) apply mechanically | The learning file IS the config file — see "Verdict write-back" section | curation.md |

**Non-goals**: layout systems, image asset generation, print CMYK gamut, typeface selection — this skill only decides and validates color.

## Six-Step Method

Command variables (set once): `SDIR="<absolute path to this skill dir>"`, `S="$SDIR/scripts/palette_forge.py"`.

### Step 1: Name the aesthetic manifesto

Pick a **1-2 word movement name** + a one-line manifesto: "Herb garden ledger — pot brown, dried-herb green, mulberry-paper cream, all low saturation, sun-bleached". The manifesto includes:
- **Register check** (lens 0): who reads it / in what setting / what they take away in 3 seconds; visual register must match the content domain. **The user's existing aesthetic profile (e.g. light/understated/whitespace/ghost numerals) is the highest-priority constraint — check before writing; a fitting metaphor cannot rescue a register mismatch**;
- **Reference aesthetics**: "1970s ski lodge: burnt orange, avocado green, warm brown";
- **Lightness architecture**: light or dark ground; text is always the extreme;
- **Color dosage**: accent ≤10% of the page — "scarcity is force";
- **Negation list**: pick applicable items from `references/anti-slop.md` into the prompt (inference-time negation works);
- 60-30-10 is a **default scaffold, not law** — proportions follow the brief.

### Step 2: Source (four routes)

```bash
python "$S" match --brief "pediatric clinical teaching page" --limit 6   # A' brief match: auto register + profile down-rank (preferred)
python "$S" search --style warm,pastel --no-flags --limit 6   # A manual filter
python "$S" harmony --base 780000 --mode complementary --theme light  # B OKLCH harmony
python "$S" extract reference.png --n 6                  # C image extraction (needs Pillow)
python "$S" ramp --base 2A9D8F --steps 7                 # D luminance ramp (charts/heatmaps)
```

A' = natural-language brief → register detection + profile down-rank + tier ranking, **the preferred entry for new tasks**. **The spacebar-iteration equivalent**: re-roll seeds/modes/style words; generate ≥2 candidates before moving on. Many candidates → `showcase` renders named picks.

### Step 3: Roles, not a bag of swatches

```bash
python "$S" roles --palette 606C38,283618,FEFAE0,DDA15E,BC6C25 --semantic --css
```

Outputs bg/text/accent/primary/surface + derived semantic colors (success/warning/error/info), with three contrast checks — non-zero exit on failure. Key point: the strongest color **owns one deliberate region**, not scattered accents.

### Step 4: Mechanical validation (measurement vs taste, separated)

```bash
python "$S" score --palette ...     # 5-dim scorecard /20, P0-P3 findings, <10 exits non-zero
python "$S" contrast --fg ... --bg ... [--large]   # single-pair check with fix suggestions
python "$S" blind --palette ...     # three color-blind simulations; mandatory for charts/status colors
python "$S" slop --palette ...      # AI-slop signatures; non-zero exit on hit
```

Charts additionally: distinguish data by luminance ramps only (ramp), redundant encoding via shape/labels, never red+green as the sole distinction.

### Step 5: Export tokens

```bash
python "$S" export --palette ... --format css|tailwind|json|svg|w3c|context   # w3c=设计令牌标准;context=LLM 上下文块
python "$S" mutate --palette ... --shade -20 --sat +5 --hue 15 --temp +30
```

### Step 6: Five-lens self-review (mandatory gate)

```bash
python "$S" card --palette ... --name "Project" --out card.html   # palette card + mockup
python "$S" visualize --palette ... --name "Project" --out viz.html   # 10-scene visualizer; --variants N = same scenes under N palette orders
python "$S" visualize --palette ... --svg design.svg --shuffle 3      # slot-inventory recolor: 3 permutations + comparison grid
python "$S" critique --palette ... [--evidence evidence.json] --out report.md   # 五镜报告生成器(机械发现预填)
python "$S" doctor                                 # 环境体检
python "$SDIR/scripts/lint_page.py" page.html --palette <declared palette> --floor 12   # delivery audit
```

**Always** screenshot into the conversation and adjudicate with the **five lenses** from `references/critique.md` (intent/register → composition → information → color → type): every PASS/FAIL points at a concrete element + cites a principle + evidence; FAIL unfixed = not delivered; fixes are bounded. Before HTML delivery run lint_page.

Gate chain:

| Step | Tool | Guards |
|---|---|---|
| 1 palette | `score` | 5 dims + profile violations |
| 2 build | any | — |
| 3 HTML discipline | `lint_page` | drift/bans/font floor/dosage |
| 4 render evidence | `render_probe.js` + `lint_page --render` | measured theme/dosage/contrast/font |
| 5 candidates | `make_variants` | ≥2-candidate comparison sheet |
| 6 five-lens screenshots | human + agent | eye order/density/composition |

Render-probe fallback: without browser tooling skip step 4, keep five-lens screenshots as the floor, and note "render evidence not run" in the delivery.

On user rejection, run a **necropsy** first (write the transferable failure mode back to critique.md), then redesign. Formal deliverables follow the host environment's acceptance flow.

## Verdict write-back & customization

- **Accepted-design intake**: `python "$S" house --name "Project final" --hexes ... --from-proj project` — joins the library and gets match-boosted.
- **Custom registers**: edit `registers` in `profile.json` (key = register name, value with theme/style_tags/accent_max_area); `match --register` picks it up. A new domain = a new entry, not new code.
- **Self-test**: `python "$S" selftest` — WCAG boundaries/OKLCH round-trip/slop signatures; non-zero exit = engine untrustworthy.

## Reference docs (30-second routing)

| Task | Go to |
|---|---|
| Write negation lists / spot AI-slop | anti-slop.md (ban table + template) |
| Review a rendered page | critique.md (five lenses + verdict format) |
| Harmony rules / contrast formulas / color semantics | color-theory.md |
| Find a named rule fast | craft-rules.md (rule cards) |
| Grow the library / selection methodology | curation.md |
| Harvest more coolors data | harvest-coolors.md (5 field-tested traps) |

| File | Content |
|---|---|
| `references/critique.md` | Five-lens review + named failure modes + necropsy archive |
| `references/craft-rules.md` | Palette rule cards (five-lens quick reference) |
| `references/color-theory.md` | Harmony rules/OKLCH/lightness architecture/60-30-10/WCAG formulas/semantics |
| `references/anti-slop.md` | AI-slop bans and evidence chain |
| `references/curation.md` | Selection methodology + library-growth pipeline |
| `references/harvest-coolors.md` | coolors harvesting recipe (5 field-tested traps) |

## Selection methodology

Three filters: ① crowd signal (official coolors charts + likes tiers + cross-page recurrence) ② objective gates (reject only objectively broken: flat lightness / no readable pair; flag CB collisions / slop / narrow lightness) ③ in-context self-review (the final verdict). **Nobody can know "beautiful" a priori** — the library sets the starting line, the context decides. Details in `references/curation.md`.
