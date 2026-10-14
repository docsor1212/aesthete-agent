#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""palette_forge.py — offline palette engine distilled from coolors.co mechanics.

Commands:
  harmony   generate a palette from a seed color using a harmony rule (OKLCH)
  mutate    coolors-style adjust transforms (shade/saturation/hue/temperature/luminance)
  contrast  WCAG contrast ratio + AA/AAA verdict for fg/bg pair
  roles     assign 60-30-10 role architecture + emit CSS variables
  blind     color-blindness simulation (protanopia/deuteranopia/tritanopia)
  slop      AI-slop lint (Tailwind-default family, flat lightness, purple gradient, all-vivid)
  extract   pull dominant colors from an image (needs Pillow)
  search    search the curated harvested library (palettes/palettes.json)
  card      render a self-contained HTML palette card + UI mockup for self-review
  export    emit tokens (css / tailwind / json / svg)

Core is stdlib-only. `extract` needs Pillow; everything else runs anywhere.

Color math: OKLab (Bjorn Ottosson, public domain) for perceptual operations;
WCAG 2.x relative-luminance formula for contrast; Machado et al. 2009 matrices
for color-blindness simulation (approximate, severity 1.0).
"""
import argparse
import colorsys
import json
import math
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

LIBRARY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "palettes", "palettes.json")
PROFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profile.json")


def load_profile():
    """用户偏好档案——机制化消费;不存在则返回空档(不猜)。"""
    try:
        with open(PROFILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# ---------------------------------------------------------------- color core

def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def parse_hex(s):
    s = str(s).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise ValueError(f"bad hex: {s!r}")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(rgb):
    return "%02X%02X%02X" % tuple(int(round(clamp(c) * 255)) for c in rgb)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def oklab_from_srgb(rgb):
    r, g, b = (srgb_to_linear(c) for c in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (
        0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_,
    )


def srgb_from_oklab(L, a, b):
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    return (
        clamp(linear_to_srgb(4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s)),
        clamp(linear_to_srgb(-1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s)),
        clamp(linear_to_srgb(-0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s)),
    )


def oklch_from_hex(h):
    L, a, b = oklab_from_srgb(tuple(c / 255 for c in parse_hex(h)))
    C = math.hypot(a, b)
    H = math.degrees(math.atan2(b, a)) % 360
    return L, C, H


def hex_from_oklch(L, C, H):
    rad = math.radians(H)
    rgb = srgb_from_oklab(L, C * math.cos(rad), C * math.sin(rad))
    return to_hex(rgb)


def gamut_fit(L, C, H):
    """Reduce chroma until (L,C,H) fits sRGB. Returns fitted C."""
    rad = math.radians(H)
    for step in range(33):
        c = C * (1 - step / 32)
        a, b = c * math.cos(rad), c * math.sin(rad)
        l_ = L + 0.3963377774 * a + 0.2158037573 * b
        m_ = L - 0.1055613458 * a - 0.0638541728 * b
        s_ = L - 0.0894841775 * a - 1.2914855480 * b
        l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
        vals = (
            4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
            -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
            -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
        )
        if all(-0.002 <= v <= 1.002 for v in vals):
            return c
    return 0.0


def hsl(h):
    r, g, b = (c / 255 for c in parse_hex(h))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return hh * 360, ll, ss


# ------------------------------------------------------------ WCAG contrast

def rel_luminance(h):
    r, g, b = (srgb_to_linear(c / 255) for c in parse_hex(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg, bg):
    l1, l2 = sorted((rel_luminance(fg), rel_luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def wcag_verdict(ratio, large=False):
    aa = 3.0 if large else 4.5
    aaa = 4.5 if large else 7.0
    verdicts = []
    verdicts.append("AA PASS" if ratio >= aa else "AA FAIL")
    verdicts.append("AAA PASS" if ratio >= aaa else "AAA FAIL")
    return verdicts


def readable_text(bg):
    """coolors is-light equivalent: pick black or white text per WCAG."""
    if contrast_ratio("000000", bg) >= contrast_ratio("FFFFFF", bg):
        return "000000"
    return "FFFFFF"


# --------------------------------------------------- color-blind simulation
# Machado, Oliveira & Fernandes 2009, severity 1.0 (RGB-space matrices)

CB_MATRICES = {
    "protanopia": (
        0.152286, 1.052583, -0.204868,
        0.114503, 0.786281, 0.099216,
        -0.003882, -0.048116, 1.051998,
    ),
    "deuteranopia": (
        0.367322, 0.860646, -0.227968,
        0.280085, 0.672501, 0.047413,
        -0.011820, 0.042940, 0.968881,
    ),
    "tritanopia": (
        1.255528, -0.076749, -0.178779,
        -0.078411, 0.930809, 0.147602,
        0.004733, 0.691367, 0.303900,
    ),
}


def simulate_cb(h, kind):
    r, g, b = (c / 255 for c in parse_hex(h))
    m = CB_MATRICES[kind]
    out = (
        m[0] * r + m[1] * g + m[2] * b,
        m[3] * r + m[4] * g + m[5] * b,
        m[6] * r + m[7] * g + m[8] * b,
    )
    return to_hex(tuple(clamp(c) for c in out))


# ------------------------------------------------------------- AI-slop lint

TAILWIND_DEFAULTS = {
    "3B82F6": "blue-500", "6366F1": "indigo-500", "8B5CF6": "violet-500",
    "A855F7": "purple-500", "EC4899": "pink-500", "6D28D9": "violet-700",
    "4F46E5": "indigo-600", "0EA5E9": "sky-500", "22D3EE": "cyan-400",
}


def slop_lint(hexes):
    findings = []
    upper = [h.upper() for h in hexes]
    hits = [(h, TAILWIND_DEFAULTS[h]) for h in upper if h in TAILWIND_DEFAULTS]
    if hits:
        findings.append(f"MEDIAN-TRAP: Tailwind tutorial defaults present: "
                        f"{', '.join(f'#{h} ({n})' for h, n in hits)} — this is the "
                        f"'median of training data' look; pick another route")
    Ls = [oklch_from_hex(h)[0] for h in upper]
    if max(Ls) - min(Ls) < 0.25:
        findings.append(f"FLAT-LIGHTNESS: L range {max(Ls)-min(Ls):.2f} < 0.25 — no light/dark "
                        f"architecture; text/bg roles will fail contrast")
    purpleish = [oklch_from_hex(h) for h in upper
                 if 275 <= oklch_from_hex(h)[2] <= 330 and oklch_from_hex(h)[1] > 0.12]
    if len(purpleish) >= 2 and abs(purpleish[0][0] - purpleish[1][0]) < 0.2:
        findings.append("PURPLE-GRADIENT: two mid-light chromatic purples — the #1 AI-slop signature")
    if Ls and all(oklch_from_hex(h)[1] > 0.16 and oklch_from_hex(h)[0] > 0.45 for h in upper):
        findings.append("ALL-VIVID: every color loud — no quiet surface for content to rest on")
    if not findings:
        findings.append("CLEAN: no known slop signature detected (taste is still yours)")
    return findings


# ------------------------------------------------------------ subcommands

def palette_list(s):
    return [h for h in (x.strip() for x in s.replace("#", ",").split(",")) if h]


def cmd_harmony(args):
    L, C, H = oklch_from_hex(args.base)
    modes = {
        "monochromatic": [0], "analogous": [-30, 0, 30],
        "complementary": [0, 180], "split-complementary": [0, 150, 210],
        "triadic": [0, 120, 240], "tetradic": [0, 90, 180, 270],
        "square": [0, 90, 180, 270],
    }
    hues = [(H + d) % 360 for d in modes[args.mode]]
    dark = args.theme == "dark"
    # role scaffold: quiet bg, dark text, chromatic body from harmony hues
    bg_L, text_L = (0.97, 0.22) if not dark else (0.23, 0.95)
    surf_C = 0.012
    palette = [
        hex_from_oklch(bg_L, surf_C, H),                       # background
        hex_from_oklch((bg_L - 0.06) if not dark else (bg_L + 0.05), surf_C, (H + 20) % 360),  # surface
    ]
    for h in hues:
        c = gamut_fit(0.55 if not dark else 0.68, min(0.19, max(C, 0.11)), h)
        palette.append(hex_from_oklch(0.55 if not dark else 0.68, c, h))
    palette.append(hex_from_oklch(text_L, 0.008, H))          # text
    if args.count:
        palette = palette[:args.count]
    print(" ".join(palette))
    print("roles: bg surface primary... text (assign with `roles`)")
    print("contrast bg/text: %.2f:1 (%s)" % (
        (lambda r: r)(contrast_ratio(palette[0], palette[-1])),
        wcag_verdict(contrast_ratio(palette[0], palette[-1]))[0]))
    for f in slop_lint(palette):
        print("lint:", f)


def cmd_mutate(args):
    hexes = palette_list(args.palette)
    out = []
    for h in hexes:
        L, C, H = oklch_from_hex(h)
        L += args.lum / 100
        C = max(0.0, C + args.sat / 100)
        H = (H + args.hue) % 360
        C = gamut_fit(L, C, H)
        # temperature: rotate toward warm (+) or cool (-) without wrecking hue identity
        if args.temp:
            target = 60 if args.temp > 0 else 260
            delta = args.temp / 100 * 15
            dist = (target - H) % 360
            H = (H + delta * (1 if dist < 180 else -1)) % 360
        if args.shade:
            L += args.shade / 100 * 0.5
            C = gamut_fit(L, C, H)
        out.append(hex_from_oklch(clamp(L), C, H))
    print(" ".join(out))


def cmd_contrast(args):
    ratio = contrast_ratio(args.fg, args.bg)
    verdicts = wcag_verdict(ratio, args.large)
    best = readable_text(args.bg)
    print(f"#{args.fg.upper()} on #{args.bg.upper()} = {ratio:.2f}:1  {' '.join(verdicts)}")
    if ratio < (3.0 if args.large else 4.5):
        # suggest fix: nudge fg lightness away from bg
        L, C, H = oklch_from_hex(args.fg)
        bg_L = oklch_from_hex(args.bg)[0]
        step = 0.05 if bg_L > L else -0.05
        for _ in range(16):
            L += step
            c = gamut_fit(L, C, H)
            cand = hex_from_oklch(clamp(L), c, H)
            if contrast_ratio(cand, args.bg) >= (3.0 if args.large else 4.5):
                print(f"suggestion: #{cand} ({contrast_ratio(cand, args.bg):.2f}:1)")
                break
    print(f"auto text for bg: #{best}")


def cmd_roles(args):
    hexes = palette_list(args.palette)
    info = sorted(((oklch_from_hex(h), h) for h in hexes), reverse=True)
    light_theme = args.theme != "dark"
    bg = max(info, key=lambda t: t[0][0]) if light_theme else min(info, key=lambda t: t[0][0])
    text = min(info, key=lambda t: t[0][0]) if light_theme else max(info, key=lambda t: t[0][0])
    rest = [t for t in info if t[1] not in (bg[1], text[1])]
    accent = max(rest, key=lambda t: t[0][1]) if rest else bg
    primary = max([t for t in rest if t[1] != accent[1]],
                  key=lambda t: abs(t[0][0] - 0.55)) if len(rest) > 1 else (accent if accent is not bg else bg)
    surface = min([t for t in rest if t[1] not in (accent[1], primary[1])],
                  key=lambda t: abs(t[0][0] - bg[0][0]), default=None) if rest else None
    roles = {"bg": bg[1], "text": text[1], "accent": accent[1], "primary": primary[1]}
    if surface:
        roles["surface"] = surface[1]
    if args.semantic:
        # semantic states derived from the accent hue (impeccable "roles, not swatch bags"):
        # success/warning/error/info keep the accent's lightness & chroma character
        L, C, H = oklch_from_hex(accent[1])
        C = max(C, 0.10)
        for name, hue in (("success", 145), ("warning", 85), ("error", 25), ("info", 250)):
            roles[name] = hex_from_oklch(clamp(L), gamut_fit(L, C, hue), hue)
    checks = [
        ("text/bg", contrast_ratio(roles["text"], roles["bg"]), False),
        ("primary/bg", contrast_ratio(roles["primary"], roles["bg"]), True),
        ("accent/bg", contrast_ratio(roles["accent"], roles["bg"]), True),
    ]
    if args.css:
        print(":root {")
        for k, v in roles.items():
            print(f"  --color-{k}: #{v};")
        print("}")
    else:
        for k, v in roles.items():
            t = readable_text(v)
            print(f"{k:8s} #{v}  (text: #{t})")
    ok = True
    for name, r, large in checks:
        v = wcag_verdict(r, large)[0]
        if "FAIL" in v:
            ok = False
        print(f"check {name}: {r:.2f}:1 {v}")
    usage = ("60-30-10 mapping: %s dominates ~60%% (bg), %s+%s ~30%% (structure), "
             "%s ~10%% (accent)" % (roles["bg"], roles.get("surface", roles["primary"]),
                                    roles["primary"], roles["accent"]))
    print(usage)
    sys.exit(0 if ok else 1)


def cmd_ramp(args):
    """OKLCH lightness ramp from a base hue — chroma falls off near white/black
    (impeccable ramp rule: don't keep high chroma at extreme lightness)."""
    L, C, H = oklch_from_hex(args.base)
    C = max(C, 0.08)
    out = []
    lo, hi = (0.25, 0.97) if args.direction != "dark" else (0.97, 0.25)
    for i in range(args.steps):
        t = i / max(1, args.steps - 1)
        L_i = lo + (hi - lo) * t
        # chroma falloff near the extremes
        c_scale = clamp(min((L_i - 0.02) / 0.30, (0.98 - L_i) / 0.30, 1.0))
        c = gamut_fit(L_i, C * c_scale, H)
        out.append(hex_from_oklch(L_i, c, H))
    print(" ".join(out))


def cmd_score(args):
    """Audit-style palette scorecard: deterministic checks only, 0-4 anchors,
    P0-P3 findings. Mechanical gate for step 4; taste stays with the model/user."""
    hexes = palette_list(args.palette)
    findings = []

    def dim(name, score, note):
        print(f"{name:12s} {'#'*score}{'.'*(4-score)} {score}/4  {note}")
        return score

    # 1 architecture: lightness span + quiet surface presence
    Ls = [oklch_from_hex(h)[0] for h in hexes]
    span = max(Ls) - min(Ls)
    a = 4 if span >= 0.45 else 3 if span >= 0.30 else 2 if span >= 0.20 else 1 if span >= 0.12 else 0
    dim("ARCHITECTURE", a, f"L span {span:.2f} (need >=0.25 for role architecture)")
    if span < 0.25:
        findings.append(("P1", f"flat lightness (span {span:.2f} < 0.25): no quiet surface for content"))

    # 2 readability: best text/bg pair + accent visibility
    best = max(((contrast_ratio(x, y), x, y) for i, x in enumerate(hexes) for y in hexes[i+1:]), default=(0, None, None))
    r, x, y = best
    b = 4 if r >= 7 else 3 if r >= 4.5 else 2 if r >= 3 else 1 if r >= 2 else 0
    dim("READABILITY", b, f"best pair {x}/{y} = {r:.2f}:1")
    if r < 4.5:
        findings.append(("P0" if r < 3 else "P1", f"no AA-readable text/bg pair (best {r:.2f}:1)"))

    # 3 CB safety: min pairwise separation under deuteranopia
    def lab_orig(h):
        return oklab_from_srgb(tuple(c / 255 for c in parse_hex(h)))
    def d_cb(h):
        rgbs = [c / 255 for c in parse_hex(h)]
        m = CB_MATRICES["deuteranopia"]
        o = tuple(clamp(m[i]*rgbs[0] + m[i+1]*rgbs[1] + m[i+2]*rgbs[2]) for i in (0, 3, 6))
        return oklab_from_srgb(o)
    pairs = [(i, j) for i in range(len(hexes)) for j in range(i+1, len(hexes))]
    cb = min(min(math.dist(lab_orig(hexes[i]), lab_orig(hexes[j])),
                 math.dist(d_cb(hexes[i]), d_cb(hexes[j]))) for i, j in pairs)
    c = 4 if cb >= 0.12 else 3 if cb >= 0.08 else 2 if cb >= 0.05 else 1 if cb >= 0.03 else 0
    dim("CB-SAFETY", c, f"min pair separation under deuteranopia {cb:.3f} (>=0.08 good)")
    if cb < 0.05:
        findings.append(("P1", "two colors collide under red-green blindness; rely on lightness or add labels"))

    # 4 saturation discipline
    Cs = [oklch_from_hex(h)[1] for h in hexes]
    mean_c = sum(Cs) / len(Cs)
    loud = sum(1 for c_, l_ in zip(Cs, Ls) if c_ > 0.16 and l_ > 0.45)
    d = 4 if loud == 0 and mean_c <= 0.14 else 3 if loud <= 1 else 2 if loud <= 2 else 1 if loud < len(hexes) else 0
    dim("SAT-DISCIPLINE", d, f"mean C {mean_c:.3f}, {loud}/{len(hexes)} loud colors (quiet surfaces needed)")
    if loud == len(hexes):
        findings.append(("P2", "every color is loud; add a quiet neutral surface"))

    # 5 uniqueness vs the median (anti-slop)
    slop_f = [f for f in slop_lint(hexes) if not f.startswith("CLEAN")]
    e = 4 if not slop_f else 2 if len(slop_f) == 1 else 0
    dim("UNIQUENESS", e, "; ".join(slop_f) if slop_f else "no median-trap signature")
    for f in slop_f:
        findings.append(("P1" if "MEDIAN-TRAP" in f else "P2", f))

    total = a + b + c + d + e
    band = ("Excellent" if total >= 18 else "Good" if total >= 14 else
            "Acceptable" if total >= 10 else "Poor" if total >= 6 else "Critical")
    print("-" * 56)
    print(f"TOTAL {total}/20  {band}")
    # 档案机制:偏好违例=机械发现(不是建议)
    prof = load_profile()
    reg = prof.get("registers", {}).get(prof.get("default_register", ""), {})
    dark_share = sum(1 for l_ in Ls if l_ < 0.35) / len(Ls) if Ls else 0
    if reg.get("theme") == "light" and dark_share >= 0.4:
        findings.append(("P1", f"PROFILE: 档案默认语域要求浅底,当前 {int(dark_share*100)}% 色为深底(dark_penalty={prof.get('theme_bias', {}).get('dark_penalty', 0)})——除非 brief 明示深色,否则换板"))
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    for sev, msg in sorted(findings, key=lambda t: order[t[0]]):
        print(f"[{sev}] {msg}")
    if not findings:
        print("[OK] no mechanical findings; taste judgment happens in context (card step)")
    sys.exit(1 if any(s == "P0" for s, _ in findings) or total < 10 else 0)


def cmd_showcase(args):
    """Contact sheet of library candidates for user selection (theme-factory pattern)."""
    with open(LIBRARY, encoding="utf-8") as f:
        lib = json.load(f)
    pals = lib["palettes"]
    if args.style:
        want = set(args.style.split(","))
        pals = [p for p in pals if want & set(p["computed_styles"])]
    if args.min_likes:
        pals = [p for p in pals if p["likes"] >= args.min_likes]
    pals = pals[: args.limit]
    cards = []
    for p in pals:
        stars = "*" * p["tier"] or "new"
        flags = " ".join(p["flags"])
        sw = "".join(f'<div style="background:#{h};flex:1;padding:26px 0 6px;text-align:center">'
                     f'<span style="font:600 11px monospace;color:#{readable_text(h)};opacity:.75">{h}</span></div>'
                     for h in p["hexes"])
        cards.append(f"""
      <div style="border:1px solid #e5e5e5;border-radius:10px;overflow:hidden">
        <div style="display:flex">{sw}</div>
        <div style="padding:8px 12px;font:500 13px system-ui;display:flex;justify-content:space-between;gap:8px">
          <span>{p['name']} <span style="color:#999">{stars} {p['likes']:,}</span></span>
          <span style="color:#b33">{flags}</span>
        </div>
      </div>""")
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>Palette showcase</title></head>
<body style="margin:0;background:#fafafa;font-family:system-ui">
  <div style="max-width:960px;margin:0 auto;padding:28px">
    <h1 style="font:700 20px system-ui">Palette showcase — pick one by name</h1>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">{''.join(cards)}</div>
  </div>
</body></html>"""
    out = args.out or "palette_showcase.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"showcase written: {out} ({len(pals)} palettes)")
    print("present to user for explicit selection, then build with the chosen palette")


def cmd_blind(args):
    hexes = palette_list(args.palette)
    kinds = ["protanopia", "deuteranopia", "tritanopia"] if not args.kind else [args.kind]
    row = " ".join(h.upper() for h in hexes)
    print("original : " + row)
    for k in kinds:
        sim = [simulate_cb(h, k) for h in hexes]
        # distinctness loss: min pairwise delta-E (oklab) original vs simulated
        def mindiff(cols):
            labs = [oklab_from_srgb(tuple(c / 255 for c in parse_hex(x))) for x in cols]
            m = 9e9
            for i in range(len(labs)):
                for j in range(i + 1, len(labs)):
                    d = math.dist(labs[i], labs[j])
                    m = min(m, d)
            return m
        loss = mindiff(hexes) - mindiff(sim)
        warn = "  <- COLLISION RISK" if mindiff(sim) < 0.07 else ""
        print(f"{k:12s}: " + " ".join(s.upper() for s in sim) + f"  (min-separation drop {loss:+.3f}){warn}")


def cmd_slop(args):
    for f in slop_lint(palette_list(args.palette)):
        print(f)


def cmd_extract(args):
    try:
        from PIL import Image
    except ImportError:
        print("Pillow required: pip install pillow", file=sys.stderr)
        sys.exit(2)
    img = Image.open(args.image).convert("RGB")
    img.thumbnail((200, 200))
    q = img.quantize(colors=args.n, method=Image.Quantize.MEDIANCUT).convert("RGB")
    counts = sorted(q.getcolors(img.width * img.height) or [], reverse=True)
    total = img.width * img.height
    picked = []
    for cnt, rgb in counts:
        h = to_hex(tuple(c / 255 for c in rgb))
        L, C, _ = oklch_from_hex(h)
        if C < 0.008 and picked:  # collapse near-gray duplicates, keep one
            continue
        picked.append((h, cnt / total, L, C))
        if len(picked) >= args.n:
            break
    for h, share, L, C in picked:
        print(f"#{h}  {share*100:5.1f}%  L={L:.2f} C={C:.3f}  text:#{readable_text(h)}")


def cmd_search(args):
    with open(LIBRARY, encoding="utf-8") as f:
        lib = json.load(f)
    pals = lib["palettes"]
    if args.style:
        want = set(args.style.split(","))
        pals = [p for p in pals if want & set(p["computed_styles"])]
    if args.min_likes:
        pals = [p for p in pals if p["likes"] >= args.min_likes]
    if args.no_flags:
        pals = [p for p in pals if not p["flags"]]
    pals = pals[: args.limit]
    for p in pals:
        stars = "*" * p["tier"] if p["tier"] else "new"
        flags = " !" + "!".join(p["flags"]) if p["flags"] else ""
        print(f"{stars:4s}{p['likes']:>7,}  {p['name']}  [{' '.join(p['computed_styles'])}]{flags}")
        print(f"           {' '.join(p['hexes'])}")


BRIEF_KEYWORDS = {
    # 词 → 语域。机械映射,不靠临场发挥;新领域=加词条,不是加散文。
    "medical_teaching": ["教学", "临床", "查房", "医学", "医疗", "指南", "解读", "儿科", "病例", "文献", "患教"],
    "pediatric_cover": ["封面", "儿童", "母婴"],
}
REGISTER_TAGS = {
    "medical_teaching": ["light", "mid", "warm", "cool", "pastel"],
    "pediatric_cover": ["warm", "vivid", "mid", "pastel"],
}


def cmd_match(args):
    """brief → 语域 → 库内排序。机制:关键词映射 + 档案惩罚;候选 ≥2 才许往下走。"""
    prof = load_profile()
    with open(LIBRARY, encoding="utf-8") as f:
        lib = json.load(f)
    pals = lib["palettes"]
    reg = args.register
    if not reg:
        hits = {r: sum(1 for k in kws if k in args.brief) for r, kws in BRIEF_KEYWORDS.items()}
        reg = max(hits, key=hits.get) if max(hits.values()) > 0 else prof.get("default_register", "medical_teaching")
    want_tags = set(REGISTER_TAGS.get(reg, []))
    pen = prof.get("theme_bias", {}).get("dark_penalty", 0)
    banned = set(prof.get("banned_hex_families", {}).get("tailwind_defaults", []))
    loved = prof.get("loved_palette_ids", [])

    def rank(p):
        tag_hits = len(want_tags & set(p["computed_styles"]))
        dark = 1 if ({'dark', 'deep'} & set(p["computed_styles"])) else 0
        slop = 1 if set(p["hexes"]) & banned else 0
        return (tag_hits + (2 if p["name"] in loved else 0) - dark * pen - slop * 4,
                p["tier"], p["likes"])

    pals.sort(key=rank, reverse=True)
    if args.no_flags:
        pals = [p for p in pals if not p["flags"]]
    print(f"register={reg}  theme_penalty_dark={pen}  candidates={len(pals)}")
    for p in pals[: args.limit]:
        stars = "*" * p["tier"] if p["tier"] else "new"
        fl = " !" + "!".join(p["flags"]) if p["flags"] else ""
        print(f"{stars:4s}{p['likes']:>7,}  {p['name']}  [{' '.join(p['computed_styles'])}]{fl}")
        print(f"           {' '.join(p['hexes'])}")
    print("纪律:取 ≥2 候选走 card/showcase 对比后定;被否决的裁决写回 profile.json(机制,不是记忆)。")


def cmd_card(args):
    hexes = palette_list(args.palette)
    name = args.name or "Palette"
    roles_css = ""
    try:
        rs = sorted(((oklch_from_hex(h), h) for h in hexes), reverse=True)
        roles_css = "--c-bg:#%s;--c-text:#%s;" % (rs[0][1], rs[-1][1])
    except Exception:
        pass
    swatches = []
    for h in hexes:
        t = readable_text(h)
        swatches.append(f"""
        <div style="background:#{h};color:#{t};flex:1;display:flex;flex-direction:column;
             justify-content:flex-end;padding:18px 14px;min-height:220px">
          <div style="font:600 15px/1.4 system-ui;opacity:.55">#{h.upper()}</div>
        </div>""")
    mock = f"""
    <div style="background:#F7F7F5;padding:26px;border-radius:10px;margin-top:22px">
      <div style="display:flex;gap:12px;align-items:center;margin-bottom:16px">
        <div style="width:34px;height:34px;border-radius:8px;background:#{hexes[-1] if len(hexes)>3 else hexes[0]}"></div>
        <div style="font:700 17px system-ui;color:#222">Acme</div>
        <div style="margin-left:auto;display:flex;gap:8px">
          <span style="padding:7px 14px;border-radius:6px;background:#{hexes[0]};font:500 13px system-ui;color:#{readable_text(hexes[0])}">Ghost</span>
          <span style="padding:7px 14px;border-radius:6px;background:#{hexes[min(3,len(hexes)-1)]};font:500 13px system-ui;color:#{readable_text(hexes[min(3,len(hexes)-1)])}">CTA</span>
        </div>
      </div>
      <div style="display:flex;gap:10px;align-items:flex-end;height:90px;margin-top:8px">
        {"".join(f'<div style="flex:1;height:{25+((i*37)%70)}%;background:#{h};border-radius:4px 4px 0 0"></div>' for i, h in enumerate(hexes))}
      </div>
      <div style="margin-top:14px;height:10px;border-radius:5px;background:linear-gradient(90deg,{",".join("#"+h for h in hexes)})"></div>
    </div>"""
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{name}</title></head>
<body style="margin:0;background:#fff;font-family:system-ui">
  <div style="max-width:860px;margin:0 auto;padding:28px">
    <div style="display:flex;justify-content:space-between;align-items:baseline">
      <h1 style="font:700 22px system-ui;margin:0 0 14px">{name}</h1>
      <span style="font:500 13px system-ui;color:#888">palette-forge card</span>
    </div>
    <div style="display:flex;border-radius:10px;overflow:hidden;border:1px solid #eee">
      {''.join(swatches)}
    </div>
    {mock}
  </div>
</body></html>"""
    out = args.out or "palette_card.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"card written: {out}")
    print("self-review: screenshot/emitImage this file, then judge roles+contrast in context")


def cmd_export(args):
    hexes = palette_list(args.palette)
    if args.format == "css":
        print(":root{")
        for i, h in enumerate(hexes):
            print(f"  --color-{i+1}: #{h.upper()};")
        print("}")
    elif args.format == "tailwind":
        print("// tailwind.config extend.colors")
        names = ["primary", "secondary", "accent", "muted", "base", "extra"]
        print("colors: {")
        for i, h in enumerate(hexes):
            print(f"  '{names[i] if i < len(names) else f'shade{i}'}': '#{h.upper()}',")
        print("}")
    elif args.format == "json":
        print(json.dumps(hexes))
    elif args.format == "svg":
        w = 120 * len(hexes)
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="120">']
        for i, h in enumerate(hexes):
            t = readable_text(h)
            parts.append(f'<rect x="{i*120}" y="0" width="120" height="120" fill="#{h}"/>')
            parts.append(f'<text x="{i*120+12}" y="108" font-family="monospace" font-size="14" fill="#{t}">#{h.upper()}</text>')
        parts.append("</svg>")
        print("".join(parts))


def main():
    p = argparse.ArgumentParser(description="aesthete-agent: offline frontend-aesthetics & palette engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("harmony")
    s.add_argument("--base", required=True)
    s.add_argument("--mode", default="analogous",
                   choices=["monochromatic", "analogous", "complementary",
                            "split-complementary", "triadic", "tetradic", "square"])
    s.add_argument("--theme", default="light", choices=["light", "dark"])
    s.add_argument("--count", type=int)
    s.set_defaults(fn=cmd_harmony)

    s = sub.add_parser("mutate")
    s.add_argument("--palette", required=True)
    s.add_argument("--shade", type=float, default=0, help="-100..100 darken/lighten")
    s.add_argument("--sat", type=float, default=0, help="-100..100 chroma delta")
    s.add_argument("--hue", type=float, default=0, help="hue rotate degrees")
    s.add_argument("--temp", type=float, default=0, help="-100..100 cool..warm")
    s.add_argument("--lum", type=float, default=0, help="-100..100 lightness delta")
    s.set_defaults(fn=cmd_mutate)

    s = sub.add_parser("contrast")
    s.add_argument("--fg", required=True)
    s.add_argument("--bg", required=True)
    s.add_argument("--large", action="store_true", help="large text threshold 3:1")
    s.set_defaults(fn=cmd_contrast)

    s = sub.add_parser("roles")
    s.add_argument("--palette", required=True)
    s.add_argument("--theme", default="light", choices=["light", "dark"])
    s.add_argument("--css", action="store_true")
    s.add_argument("--semantic", action="store_true", help="derive success/warning/error/info from accent hue")
    s.set_defaults(fn=cmd_roles)

    s = sub.add_parser("ramp")
    s.add_argument("--base", required=True, help="seed hue/lightness source")
    s.add_argument("--steps", type=int, default=7)
    s.add_argument("--direction", default="light", choices=["light", "dark"], help="light: dark->light ramp; dark: light->dark")
    s.set_defaults(fn=cmd_ramp)

    s = sub.add_parser("score")
    s.add_argument("--palette", required=True)
    s.set_defaults(fn=cmd_score)

    s = sub.add_parser("showcase")
    s.add_argument("--style", help="comma list of style tags")
    s.add_argument("--min-likes", type=int, default=0)
    s.add_argument("--limit", type=int, default=8)
    s.add_argument("--out", default=None)
    s.set_defaults(fn=cmd_showcase)

    s = sub.add_parser("blind")
    s.add_argument("--palette", required=True)
    s.add_argument("--kind", choices=["protanopia", "deuteranopia", "tritanopia"])
    s.set_defaults(fn=cmd_blind)

    s = sub.add_parser("slop")
    s.add_argument("--palette", required=True)
    s.set_defaults(fn=cmd_slop)

    s = sub.add_parser("extract")
    s.add_argument("image")
    s.add_argument("--n", type=int, default=6)
    s.set_defaults(fn=cmd_extract)

    s = sub.add_parser("search")
    s.add_argument("--style", help="comma list: warm,cool,dark,light,mid,pastel,vivid,monochromatic,multihue,deep")
    s.add_argument("--min-likes", type=int, default=0)
    s.add_argument("--no-flags", action="store_true", help="exclude palettes carrying any gate flag")
    s.add_argument("--limit", type=int, default=8)
    s.set_defaults(fn=cmd_search)

    s = sub.add_parser("match")
    s.add_argument("--brief", required=True, help="需求自然语言,如:儿科教学页/母婴封面/文献解读课件")
    s.add_argument("--register", choices=list(BRIEF_KEYWORDS.keys()), default=None)
    s.add_argument("--no-flags", action="store_true")
    s.add_argument("--limit", type=int, default=6)
    s.set_defaults(fn=cmd_match)

    s = sub.add_parser("card")
    s.add_argument("--palette", required=True)
    s.add_argument("--name", default=None)
    s.add_argument("--out", default=None)
    s.set_defaults(fn=cmd_card)

    s = sub.add_parser("export")
    s.add_argument("--palette", required=True)
    s.add_argument("--format", default="css", choices=["css", "tailwind", "json", "svg"])
    s.set_defaults(fn=cmd_export)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
