#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""palette_forge.py — offline palette engine distilled from coolors.co mechanics.

Commands:
  harmony   generate a palette from a seed color using a harmony rule (OKLCH)
  mutate    classic adjust transforms (shade/saturation/hue/temperature/luminance)
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
import re
NL = chr(10)
import subprocess
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



def apca(txt, bg):
    """APCA 0.1.9 感知对比度(WCAG 3 草案方向):返回 Lc 值(0-108+,越大越清晰)。
    指南:正文 Lc>=75(理想 90)/大字 >=60/粗大字 >=45/非文字 >=30/低于 15 不可见。"""
    def ychan(h):
        c = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
        return tuple((x/12.92 if x <= 0.04045 else ((x+0.055)/1.055)**2.4) for x in c)
    def devY(c):
        y = 0.2126729*c[0]**2.4 + 0.7151522*c[1]**2.4 + 0.0721750*c[2]**2.4
        return y + (0.022 - y)**1.414 if y < 0.022 else y
    yt, yb = devY(ychan(txt)), devY(ychan(bg))
    if yb > yt:
        sapc = (yb**0.56 - yt**0.57) * 1.14
    else:
        sapc = (yb**0.65 - yt**0.62) * 1.14
    lc = abs(sapc) * 100
    return round(lc, 1) if abs(sapc) > 0.1 else 0.0


def apca_verdict(lc):
    if lc >= 90: return "正文理想"
    if lc >= 75: return "正文最低"
    if lc >= 60: return "大字/流畅"
    if lc >= 45: return "粗大字>=24px"
    if lc >= 30: return "非文字最低"
    if lc >= 15: return "不可见边缘"
    return "不可见"


def _export_w3c(hexes):
    toks = {"color": {}, "guideline": {"$type": "content",
            "$value": "WCAG 2.2 AA: body>=4.5:1, large/UI>=3:1; APCA Lc>=75 body"}}
    for i, h in enumerate(hexes):
        toks["color"][f"palette-{i+1}"] = {"$type": "color", "$value": f"#{h}"}
    return json.dumps(toks, ensure_ascii=False, indent=2)


def _export_context(hexes):
    rs = sorted(((oklch_from_hex(h), h) for h in hexes), key=lambda t: -t[0][0])
    bg, ink = rs[0][1], rs[-1][1]
    cands = [(oklch_from_hex(h)[1], h) for h in hexes if h not in (bg, ink)]
    accent = max(cands)[1] if cands else bg
    body_pair = contrast_ratio(ink, bg)
    best = max(((contrast_ratio(a, b), a, b) for i, a in enumerate(hexes) for b in hexes[i+1:]))
    ctx = []
    ctx.append("# Color System Context(可直接粘贴给任何 LLM 的配色上下文)")
    ctx.append("")
    ctx.append("## Tokens")
    for i, h in enumerate(hexes, 1):
        L, C, H = oklch_from_hex(h)
        ctx.append(f"- palette-{i}: #{h} (OKLCH {L:.2f} {C:.3f} {H:.0f}deg)")
    ctx.append("")
    ctx.append("## Roles(60-30-10)")
    ctx.append(f"- background: #{bg} (60%)")
    ctx.append(f"- text: #{ink} (contrast vs bg {body_pair:.2f}:1)")
    ctx.append(f"- accent: #{accent} (<=10%, 稀缺即力量)")
    ctx.append("")
    ctx.append("## Guardrails(硬规则)")
    ctx.append("- 正文对比 >=4.5:1,大字/非文字 >=3:1(APCA Lc>=75/60 为感知口径)")
    ctx.append("- accent 不超过全页 10%;最强色拥有一块完整区域")
    ctx.append("- 禁:Tailwind 默认族(#3B82F6/#6366F1/#8B5CF6)/紫渐变/全高饱和/平坦明度")
    ctx.append("- 红绿永不作唯一区分;图表用明度阶梯+冗余编码")
    ctx.append(f"- 已验证最优对: #{best[1]} on #{best[2]} = {best[0]:.2f}:1")
    return chr(10).join(ctx)


def _viz_roles(hexes, dark=None):
    """角色自动映射: bg/surface/ink/ink2/accent(+danger 若存在红系)。dark 缺省按明度均值自判。"""
    info = sorted(((oklch_from_hex(h)[0], h) for h in hexes), key=lambda t: -t[0])
    mL = sum(t[0] for t in info) / len(info)
    if dark is None:
        dark = mL < 0.5
    ordered = info if not dark else list(reversed(info))
    bg = ordered[0][1]
    ink = ordered[-1][1]
    rest = [t for t in ordered[1:-1]] or ordered[:1]
    accent = max(rest, key=lambda t: oklch_from_hex(t[1])[1])[1] if rest else bg
    # surface/ink2 派生而非挑选: 从 bg/ink 沿 OKLCH 插值, 保色相降饱和,
    # 避免把高饱和色(如暗红)当成中性面、或弱对比色当次级文字
    bL, bC, bH = oklch_from_hex(bg)
    iL, iC, iH = oklch_from_hex(ink)
    # 浅色主题 surface 近纸白(微降), 深色主题明显抬升 — 非对称
    sFrac = 0.06 if not dark else 0.16
    sL = bL + (iL - bL) * sFrac
    surface = hex_from_oklch(sL, gamut_fit(sL, bC * 0.9, bH), bH).upper()
    mL2 = bL + (iL - bL) * 0.52
    c2 = min(0.05, iC * 0.6 + 0.01)
    ink2 = hex_from_oklch(mL2, gamut_fit(mL2, c2, iH), iH).upper()
    _k = 0
    while contrast_ratio(ink2, bg) < 3.0 and _k < 10:
        _k += 1
        cL2 = mL2 + (iL - mL2) * _k / 10
        ink2 = hex_from_oklch(cL2, gamut_fit(cL2, c2, iH), iH).upper()
    reds = []
    for _, h in ordered:
        _, C, H = oklch_from_hex(h)
        if 8 <= H <= 35 and C > 0.08 and h not in (bg, ink, accent):
            reds.append(h)
    danger = None
    if reds:
        reds.sort(key=lambda h: -contrast_ratio(h, bg))
        if contrast_ratio(reds[0], bg) >= 3.0:
            danger = reds[0]
    if danger is None:
        danger = accent if contrast_ratio(accent, bg) >= 3.0 else ink
    # accent_text: accent 当文字用不达标时, 沿 OKLCH 向 ink 爬坡亮度直到 3:1
    atext = accent
    if contrast_ratio(accent, bg) < 3.0:
        aL, aC, aH = oklch_from_hex(accent)
        for k in range(1, 11):
            cL = aL + (iL - aL) * k / 10
            cand = hex_from_oklch(cL, gamut_fit(cL, aC, aH), aH).upper()
            atext = cand
            if contrast_ratio(cand, bg) >= 3.0:
                break
    return {"bg": bg, "surface": surface, "ink": ink, "ink2": ink2, "accent": accent,
            "danger": danger, "atext": atext, "dark": dark}


def _viz_render(ord_hexes, theme, label):
    """同场景换色渲染一个 variant(吸收 visualizer 空格洗牌循环:设计固定,色板变化)。"""
    hexes = ord_hexes
    R = _viz_roles(hexes, dark=theme)
    t_on = {k: readable_text(v) for k, v in R.items() if k != "dark"}
    # 辅助口声色(sage/honey 类): 文字用途须对 surface>=3:1, 从次高饱度色里挑, 兜底 ink2
    _cands = sorted((h for h in hexes if h not in (R["accent"], R["bg"], R["ink"])),
                    key=lambda h: -oklch_from_hex(h)[1])
    sage = next((h for h in _cands if contrast_ratio(h, R["surface"]) >= 3.0), R["ink2"])
    honey = (_cands[0] if _cands and contrast_ratio(_cands[0], R["surface"]) >= 1.6
             else R["ink2"])
    legend = NL.join(
        "<span class='chip' style='background:#" + R[k] + ";color:#" + t_on[k] + "'>" + k + ":#" + R[k] + "</span>"
        for k in ("bg", "surface", "ink", "ink2", "accent", "atext", "danger"))
    css = (NL.join([
        "body{margin:0;background:#23272E;font-family:system-ui,sans-serif;color:#E8EEF6}",
        "header{padding:16px 22px;border-bottom:1px solid rgba(255,255,255,.12)}",
        "header h1{font-size:16px;margin:0 0 10px}",
        "header h1 b{color:#F2CC8F}",
        ".chips{display:flex;gap:8px;flex-wrap:wrap}",
        ".chip{padding:4px 10px;border-radius:99px;font:600 11px monospace}",
        ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px;padding:16px}",
        ".scene{background:#fff;border-radius:10px;overflow:hidden}",
        ".scene h2{font-size:11px;letter-spacing:.14em;text-transform:uppercase;opacity:.85;",
        "  margin:0;padding:8px 14px;background:#F2F2F0;color:#444}",
        ".badge{float:right;font:700 10px monospace;color:#7CD992}",
        ".vsec{padding:6px 0 2px}",
        ".vhead{padding:10px 22px 0;font:700 13px system-ui;color:#F2CC8F;display:flex;gap:12px;align-items:center}",
        ".vhead .badge{float:none}",
        ".vhead .chips{padding:0}"
    ]))
    scenes = []

    # S1 Mobile App
    tpl = NL.join([
      "<div style='width:230px;margin:14px auto;border:1px solid #ddd;border-radius:18px;overflow:hidden;background:%(bg)s'>",
      "  <div style='padding:5px 12px;font:600 9px system-ui;color:%(tbg)s;display:flex;justify-content:space-between'><span>9:41</span><span>●●●</span></div>",
      "  <div style='padding:12px 14px 8px;color:%(ink)s;font:700 15px system-ui'>Wallet</div>",
      "  <div style='margin:0 12px;padding:14px;border-radius:12px;background:%(accent)s;color:%(tac)s'>",
      "    <div style='font:600 10px system-ui;opacity:.8'>Balance</div>",
      "    <div style='font:800 22px system-ui'>12,480</div></div>",
      "  <div style='margin:10px 12px;padding:10px 12px;border-radius:10px;background:%(surface)s;color:%(ink)s;display:flex;gap:10px;align-items:center'>",
      "    <div style='width:30px;height:30px;border-radius:8px;background:%(ink2)s'></div>",
      "    <div style='font:600 12px system-ui'>Coffee run<div style='font:400 10px;color:%(ink2)s'>Today 08:12</div></div>",
      "    <div style='margin-left:auto;font:700 12px;color:%(danger)s'>-28</div></div>",
      "  <div style='margin:10px 12px 14px;padding:10px 12px;border-radius:10px;background:%(surface)s;color:%(ink)s;display:flex;gap:10px;align-items:center'>",
      "    <div style='width:30px;height:30px;border-radius:8px;background:%(honey)s'></div>",
      "    <div style='font:600 12px system-ui'>Salary<div style='font:400 10px;color:%(ink2)s'>Mar 01</div></div>",
      "    <div style='margin-left:auto;font:700 12px;color:%(sage)s'>+9,500</div></div>",
      "  <div style='display:flex;justify-content:space-around;padding:8px 0 12px;border-top:1px solid rgba(0,0,0,.06)'>",
      "    <div style='width:18px;height:18px;border-radius:5px;background:%(accent)s'></div>",
      "    <div style='width:18px;height:18px;border-radius:5px;background:%(ink2)s;opacity:.4'></div>",
      "    <div style='width:18px;height:18px;border-radius:5px;background:%(ink2)s;opacity:.4'></div></div></div>",
    ])
    m = {"%(bg)s": R["bg"], "%(surface)s": R["surface"], "%(ink)s": R["ink"], "%(ink2)s": R["ink2"],
         "%(accent)s": R["accent"], "%(danger)s": R["danger"], "%(honey)s": hexes[2 % len(hexes)],
         "%(sage)s": sage, "%(tbg)s": t_on["bg"], "%(tac)s": t_on["accent"]}
    scenes.append(("Mobile App · 金融卡", _fill(tpl, m)))

    # S2 Landing
    tpl = NL.join([
      "<div style='background:%(bg)s;color:%(ink)s'>",
      "  <div style='display:flex;align-items:center;gap:10px;padding:12px 16px'>",
      "    <div style='width:22px;height:22px;border-radius:6px;background:%(accent)s'></div>",
      "    <b style='font:700 13px system-ui'>acme</b>",
      "    <span style='margin-left:auto;font:500 11px system-ui;color:%(ink2)s'>Docs&nbsp;&nbsp;Pricing</span>",
      "    <span style='padding:6px 12px;border-radius:6px;background:%(accent)s;color:%(tac)s;font:600 11px system-ui'>Sign up</span></div>",
      "  <div style='text-align:center;padding:26px 18px 20px'>",
      "    <div style='font:800 22px/1.25 system-ui'>Ship color systems<br>that pass review</div>",
      "    <div style='font:400 12px system-ui;color:%(ink2)s;margin:8px 0 14px'>Mechanically validated palettes for your product.</div>",
      "    <span style='padding:8px 16px;border-radius:7px;background:%(ink)s;color:%(tink)s;font:600 12px system-ui'>Get started</span>",
      "    <span style='padding:8px 16px;border-radius:7px;border:1px solid %(ink2)s;color:%(ink)s;font:600 12px system-ui;margin-left:6px'>Live demo</span></div>",
      "  <div style='display:flex;gap:8px;padding:0 16px 18px'>",
      "    <div style='flex:1;border:1px solid rgba(0,0,0,.08);border-radius:8px;padding:10px;background:%(surface)s'>",
      "      <div style='width:20px;height:20px;border-radius:5px;background:%(honey)s'></div>",
      "      <div style='font:700 11px system-ui;margin-top:6px'>Fast</div>",
      "      <div style='font:400 10px system-ui;color:%(ink2)s'>Instant checks</div></div>",
      "    <div style='flex:1;border:1px solid rgba(0,0,0,.08);border-radius:8px;padding:10px;background:%(surface)s'>",
      "      <div style='width:20px;height:20px;border-radius:5px;background:%(sage)s'></div>",
      "      <div style='font:700 11px system-ui;margin-top:6px'>Proven</div>",
      "      <div style='font:400 10px system-ui;color:%(ink2)s'>WCAG + APCA</div></div></div></div>",
    ])
    m = {"%(bg)s": R["bg"], "%(surface)s": R["surface"], "%(ink)s": R["ink"], "%(ink2)s": R["ink2"],
         "%(accent)s": R["accent"], "%(honey)s": hexes[2 % len(hexes)], "%(sage)s": sage,
         "%(tink)s": t_on["ink"], "%(tac)s": t_on["accent"]}
    scenes.append(("Landing · 落地页", _fill(tpl, m)))

    # S3 Dashboard
    bars = "".join(
        "<div style='flex:1;height:" + str(30 + ((i * 23) % 60)) + "%;background:#" +
        (R["accent"] if i == 3 else hexes[(i + 1) % len(hexes)]) +
        ";border-radius:3px 3px 0 0'></div>" for i in range(7))
    tpl = NL.join([
      "<div style='display:flex;min-height:210px;background:%(bg)s'>",
      "  <div style='width:52px;background:%(surface)s;padding:10px 0;display:flex;flex-direction:column;gap:10px;align-items:center'>",
      "    <div style='width:20px;height:20px;border-radius:6px;background:%(accent)s'></div>",
      "    <div style='width:16px;height:16px;border-radius:4px;background:%(ink2)s;opacity:.5'></div>",
      "    <div style='width:16px;height:16px;border-radius:4px;background:%(ink2)s;opacity:.5'></div>",
      "    <div style='width:16px;height:16px;border-radius:4px;background:%(ink2)s;opacity:.5'></div></div>",
      "  <div style='flex:1;padding:12px;color:%(ink)s'>",
      "    <div style='display:flex;gap:8px'>",
      "      <div style='flex:1;background:%(surface)s;border-radius:8px;padding:10px'><div style='font:500 9px system-ui;color:%(ink2)s'>MRR</div><div style='font:800 16px system-ui'>86k</div></div>",
      "      <div style='flex:1;background:%(surface)s;border-radius:8px;padding:10px'><div style='font:500 9px system-ui;color:%(ink2)s'>Active</div><div style='font:800 16px system-ui'>1,204</div></div>",
      "      <div style='flex:1;background:%(surface)s;border-radius:8px;padding:10px'><div style='font:500 9px system-ui;color:%(ink2)s'>Churn</div><div style='font:800 16px system-ui;color:%(danger)s'>1.9%</div></div></div>",
      "    <div style='display:flex;align-items:flex-end;gap:6px;height:70px;margin-top:10px;background:%(surface)s;border-radius:8px;padding:10px'>%(bars)s</div>",
      "    <div style='margin-top:8px;background:%(surface)s;border-radius:8px;overflow:hidden;font:500 10px system-ui'>",
      "      <div style='display:flex;justify-content:space-between;padding:6px 10px;border-bottom:1px solid rgba(0,0,0,.05)'><span>Acme Corp</span><b>12,400</b></div>",
      "      <div style='display:flex;justify-content:space-between;padding:6px 10px'><span>Globex</span><b>8,150</b></div></div></div></div>",
    ])
    m = {"%(bg)s": R["bg"], "%(surface)s": R["surface"], "%(ink)s": R["ink"], "%(ink2)s": R["ink2"],
         "%(accent)s": R["accent"], "%(danger)s": R["danger"], "%(bars)s": bars}
    scenes.append(("Dashboard · 仪表盘", _fill(tpl, m)))

    # S4 Branding
    tpl = NL.join([
      "<div style='padding:16px;background:%(bg)s'>",
      "  <div style='max-width:250px;margin:0 auto;background:%(surface)s;border-radius:8px;padding:16px;box-shadow:0 4px 14px rgba(0,0,0,.10)'>",
      "    <div style='display:flex;align-items:center;gap:8px'>",
      "      <div style='width:26px;height:26px;border-radius:50%;background:%(accent)s'></div>",
      "      <b style='font:800 13px system-ui;letter-spacing:.06em;color:%(ink)s'>STUDIO NOVA</b></div>",
      "    <div style='height:1px;background:rgba(0,0,0,.08);margin:10px 0'></div>",
      "    <div style='font:400 10px/1.7 system-ui;color:%(ink2)s'>Lin Zhang · Design Lead<br>studio.nova@example.com<br>+86 138 0000 0000</div>",
      "    <div style='margin-top:10px;display:flex;gap:5px'>",
      "      <div style='width:14px;height:14px;border-radius:3px;background:%(honey)s'></div>",
      "      <div style='width:14px;height:14px;border-radius:3px;background:%(sage)s'></div>",
      "      <div style='width:14px;height:14px;border-radius:3px;background:%(ink)s'></div></div></div>",
      "  <div style='max-width:250px;margin:10px auto 4px;border-radius:8px;overflow:hidden;display:flex;height:54px'>",
      "    <div style='flex:2;background:%(ink)s;color:%(tink)s;display:flex;align-items:center;justify-content:center;font:800 13px system-ui;letter-spacing:.2em'>NOVA</div>",
      "    <div style='flex:1;background:%(accent)s'></div>",
      "    <div style='flex:1;background:%(honey)s'></div>",
      "    <div style='flex:1;background:%(sage)s'></div></div></div>",
    ])
    m = {"%(bg)s": R["bg"], "%(surface)s": R["surface"], "%(ink)s": R["ink"], "%(ink2)s": R["ink2"],
         "%(accent)s": R["accent"], "%(honey)s": hexes[2 % len(hexes)], "%(sage)s": sage,
         "%(tink)s": t_on["ink"]}
    scenes.append(("Branding · 名片与色带", _fill(tpl, m)))

    # S5 Typography
    tpl = NL.join([
      "<div style='padding:16px 18px;background:%(bg)s;color:%(ink)s'>",
      "  <div style='font:800 30px/1.1 Georgia,serif'>Aa Palette in Type</div>",
      "  <div style='font:700 15px system-ui;margin-top:8px'>Heading 2 — structure speaks in the darkest ink</div>",
      "  <div style='font:400 12px/1.7 system-ui;color:%(ink2)s;margin-top:6px'>Body 12px — secondary ink at 1.7 line height. The quick brown fox jumps over the lazy dog 0123456789.</div>",
      "  <div style='font:600 10px system-ui;letter-spacing:.18em;color:%(atext)s;margin-top:8px'>EYEBROW LABEL — ACCENT VOICE</div>",
      "  <div style='font:400 10px monospace;color:%(ink2)s;margin-top:6px'>mono 10px — data: 1,204 · 86.4% · +3.2</div></div>",
    ])
    m = {"%(bg)s": R["bg"], "%(ink)s": R["ink"], "%(ink2)s": R["ink2"], "%(atext)s": R["atext"]}
    scenes.append(("Typography · 字阶标本", _fill(tpl, m)))

    # S6 Pattern
    tiles = ""
    for i in range(6):
        h = hexes[i % len(hexes)]
        tiles += ("<div style='aspect-ratio:1;border-radius:6px;display:flex;align-items:center;"
                  "justify-content:center;background:#" + h + "'>"
                  "<div style='width:55%;height:55%;border-radius:50%;background:#" +
                  readable_text(h) + ";opacity:.16'></div></div>")
    sc = ("<div style='padding:14px;background:#" + R["bg"] + "'>"
          "<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:8px'>" + tiles + "</div></div>")
    scenes.append(("Pattern · 图案节奏", sc))

    body = ""
    for title, inner in scenes:
        body += "<div class='scene'><h2>" + title + "</h2>" + inner + "</div>"
    badge_r = contrast_ratio(R["ink"], R["bg"])
    badge = "text/bg %.2f:1" % badge_r + (" AA" if badge_r >= 4.5 else "")
    head = ("<div class='vsec'><div class='vhead'><b>" + label + "</b>" +
            "<span class='badge'>" + badge + "</span></div>"
            "<div class='chips'>" + legend + "</div></div>")
    sec = head + "<div class='grid'>" + body + "</div>"
    return css, sec


def cmd_visualize(args):
    """Palette Visualizer: 色板套进 6 类真实 UI 场景自审;
    --svg 可对其额外做重着色(纯黑白保留,其余映射到角色)。"""
    hexes = [h.upper() for h in palette_list(args.palette)]
    if len(hexes) < 3:
        print("至少 3 色", file=sys.stderr); sys.exit(1)
    n_var = max(1, min(int(getattr(args, "variants", 1) or 1), 6))
    orders = [hexes[i:] + hexes[:i] for i in range(n_var)]
    if n_var >= 2:
        orders[1] = list(reversed(orders[1]))
    R = _viz_roles(hexes, dark=(args.theme == "dark"))
    if args.svg:
        if not os.path.exists(args.svg):
            print(f"文件不存在: {args.svg}", file=sys.stderr); sys.exit(2)
        raw = open(args.svg, encoding="utf-8", errors="ignore").read()
        def _nearest_role(hh):
            if hh in ("000000", "FFFFFF"):
                return "#" + hh
            L, C, H = oklch_from_hex(hh)
            if C < 0.04:
                return "#" + (R["ink"] if L < 0.5 else R["bg"])
            if 8 <= H <= 35 and C > 0.08:
                return "#" + R["danger"]
            if C >= 0.09:
                return "#" + R["accent"]
            return "#" + (R["ink"] if L < 0.5 else R["surface"])
        def _sub(m):
            hh = m.group(2).strip("#").upper()
            if len(hh) == 3:
                hh = "".join(c * 2 for c in hh)
            if len(hh) != 6 or m.group(2).lower().startswith(("url", "none")):
                return m.group(0)
            return m.group(1) + ":" + _nearest_role(hh)
        def _sub_attr(m):
            hh = m.group(2).strip("#").upper()
            if len(hh) == 3:
                hh = "".join(c * 2 for c in hh)
            if len(hh) != 6:
                return m.group(0)
            return m.group(1) + '="' + _nearest_role(hh) + '"'
        svg_out = re.sub(r"(fill|stroke):\s*(#[0-9a-fA-F]{3,6})", _sub, raw)
        svg_out = re.sub(r'(fill|stroke)="(#[0-9a-fA-F]{3,6})"', _sub_attr, svg_out)
        svg_out_path = os.path.splitext(args.svg)[0] + ".recolored.svg"
        open(svg_out_path, "w", encoding="utf-8").write(svg_out)
        print(f"SVG 重着色: {svg_out_path}(纯黑白保留,其余映射角色)")
    vcss = ""
    sections = []
    for vi, oh in enumerate(orders):
        label = ("Variant %d · %s" % (vi + 1, " ".join("#" + h for h in oh))) if n_var > 1 else ""
        css_v, sec = _viz_render(oh, (args.theme == "dark"), label)
        if not vcss:
            vcss = css_v
        sections.append(sec)
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>Visualizer - " + args.name + "</title>"
            "<style>" + vcss + "</style></head><body><header>"
            "<h1>Visualizer · <b>" + args.name + "</b></h1></header>"
            + "".join(sections) + "</body></html>")
    out = args.out or "visualizer.html"
    open(out, "w", encoding="utf-8").write(html)
    print("visualizer: " + out + " (6 场景; 角色 bg=#" + R["bg"] + " ink=#" + R["ink"] + " accent=#" + R["accent"] + ")")
    print("自审: 截图/emitImage 本文件, 按五镜判色在真实版式里是否成立")


def _fill(tpl, m):
    for k, v in m.items():
        if len(v) == 6 and all(c in "0123456789abcdefABCDEF" for c in v):
            v = "#" + v
        tpl = tpl.replace(k, v)
    return tpl


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
    if getattr(args, "method", "wcag") == "apca":
        lc = apca(args.fg, args.bg)
        print(f"APCA Lc={lc} ({apca_verdict(lc)})  #{args.fg.upper()} on #{args.bg.upper()}")
        print("指南: 正文>=75(理想90) / 大字>=60 / 粗大字>=45 / 非文字>=30 — WCAG 3 草案方向")
        return
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
        # semantic states derived from the accent hue (角色,不是色块袋):
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
    (端点降饱和法则:不为数学均匀在极端明度硬保高 chroma)。"""
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
    """Contact sheet of library candidates for user selection (样张点名)."""
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
    findings = slop_lint(palette_list(args.palette))
    for f in findings:
        print(f)
    sys.exit(0 if all(f.startswith("CLEAN") for f in findings) else 1)


def cmd_extract(args):
    try:
        from PIL import Image
    except ImportError:
        print("Pillow required: pip install pillow", file=sys.stderr)
        sys.exit(2)
    if not os.path.exists(args.image):
        print(f"文件不存在: {args.image}", file=sys.stderr)
        sys.exit(2)
    try:
        img = Image.open(args.image).convert("RGB")
    except Exception as e:
        print(f"无法打开图像({e}): 仅支持常见位图格式", file=sys.stderr)
        sys.exit(2)
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


def cmd_house(args):
    """已验收设计入库(origin=house):用户的接受裁决=最强味信号,直接进库参与 match。"""
    hexes = [h.upper() for h in palette_list(args.hexes)]
    assert 3 <= len(hexes) <= 10, "3-10 色"
    with open(LIBRARY, encoding="utf-8") as f:
        lib = json.load(f)
    key = "#".join(sorted(hexes))
    if any("#".join(sorted(p["hexes"])) == key for p in lib["palettes"]):
        print("已存在同色组合,跳过")
        return
    hues, lights, sats = [], [], []
    for h in hexes:
        hh, ll, ss = hsl(h)
        hues.append(hh); lights.append(ll); sats.append(ss)
    mean_l = sum(lights) / len(lights)
    mean_s = sum(sats) / len(sats)
    tags = ["warm" if sum(1 for x in hues if x >= 310 or x < 70) >= len(hues) / 2 else "cool"]
    tags.append("dark" if mean_l < 0.35 else "light" if mean_l > 0.65 else "mid")
    if mean_s < 0.40 and mean_l > 0.60: tags.append("pastel")
    if mean_s > 0.55: tags.append("vivid")
    best = max(contrast_ratio(a, b) for i, a in enumerate(hexes) for b in hexes[i+1:])
    lib["palettes"].insert(0, {
        "name": args.name, "hexes": hexes, "text_hint": [], "likes": 0, "tier": 3,
        "origin": "house", "computed_styles": sorted(set(tags)),
        "occurrences": 1, "flags": [],
        "metrics": {"lightness_span": round(max(lights) - min(lights), 3),
                    "max_contrast": round(best, 2), "cb_min_separation": None},
        "sources": [f"house:{args.from_proj or 'user_accepted'}"],
    })
    lib["_meta"]["counts"]["kept"] = len(lib["palettes"])
    json.dump(lib, open(LIBRARY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    prof = load_profile()
    prof.setdefault("loved_palette_ids", [])
    if args.name not in prof["loved_palette_ids"]:
        prof["loved_palette_ids"].append(args.name)
        json.dump(prof, open(PROFILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"house 入库: {args.name} [{' '.join(sorted(set(tags)))}] (loved+1, match 自动加权)")


def cmd_selftest(args):
    """机器金标:WCAG 边界/OKLCH 往返/slop 签名/对比函数。非零退出 = 引擎不可信。"""
    ok, fail = [], []
    def check(name, cond):
        (ok if cond else fail).append(name)
        print(("PASS  " if cond else "FAIL  ") + name)
    check("wcag边界-过(#767676/FFF=4.54)", 4.53 < contrast_ratio("767676", "FFFFFF") < 4.55)
    check("wcag边界-不过(#777777/FFF=4.48)", 4.47 < contrast_ratio("777777", "FFFFFF") < 4.49)
    check("wcag阈值方向", contrast_ratio("767676", "FFFFFF") > contrast_ratio("777777", "FFFFFF"))
    h = "2A9D8F"
    L1, C1, H1 = oklch_from_hex(h)
    check("oklch往返(L误差<0.003)", abs(oklch_from_hex(hex_from_oklch(L1, C1, H1))[0] - L1) < 0.003)
    check("oklch往返(色相误差<0.5deg)", abs((oklch_from_hex(hex_from_oklch(L1, C1, H1))[2] - H1 + 180) % 360 - 180) < 0.5)
    check("slop签名-tailwind", any("MEDIAN-TRAP" in f for f in slop_lint(["3B82F6", "8B5CF6", "EC4899", "6366F1", "A855F7"])))
    check("slop签名-干净板", all(f.startswith("CLEAN") for f in slop_lint(["264653", "2A9D8F", "E9C46A", "F4A261", "E76F51"])))
    check("自动文字-深底选白", readable_text("000814") == "FFFFFF")
    check("自动文字-浅底选黑", readable_text("FEFAE0") == "000000")
    check("色盲矩阵-有输出", len(simulate_cb("FF0000", "deuteranopia")) == 6)
    print(f"\n{len(ok)} PASS / {len(fail)} FAIL")
    sys.exit(0 if not fail else 1)


THEMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "palettes", "themes.json")

def load_themes():
    try:
        with open(THEMES_FILE, encoding="utf-8") as f:
            return json.load(f)["themes"]
    except Exception:
        return []


def cmd_themes(args):
    """列出命名主题包(配色+字体+语气+适用域)。"""
    themes = load_themes()
    if args.json:
        print(json.dumps(themes, ensure_ascii=False, indent=1))
        return
    for t in themes:
        print(f"{t['name']} ({t['name_en']})  —  {t['use_when']}")
        print(f"  色: {' '.join(t['colors'].values())}")
        print(f"  语气: {t['voice']}")
    print(f"\
共 {len(themes)} 包;theme apply <名> --format css 输出完整 token")


def cmd_theme(args):
    themes = load_themes()
    t = next((x for x in themes if x["name"] == args.name or x["name_en"] == args.name), None)
    if not t:
        print(f"主题不存在: {args.name};可用: " + ", ".join(x["name"] for x in themes))
        sys.exit(1)
    if args.format == "json":
        print(json.dumps(t, ensure_ascii=False, indent=1))
        return
    c = t["colors"]
    print(f"/* {t['name']} — {t['use_when']} */")
    print(":root {")
    for k, v in c.items():
        print(f"  --c-{k.replace('_','-')}: {v};")
    for k, v in t["fonts"].items():
        print(f"  --font-{k}: {v};")
    print("  --radius: 6px;")
    print("}")
    print(f"/* 语气: {t['voice']} */")


def cmd_matrix(args):
    """全对对比度矩阵 + 最优文字/背景配对推荐。"""
    hexes = [h.upper() for h in palette_list(args.palette)]
    n = len(hexes)
    print("| | " + " | ".join(f"#{h}" for h in hexes) + " |")
    print("|---|" + "---|" * n)
    best = []
    for i, a in enumerate(hexes):
        row = [f"#{a}"]
        for j, b in enumerate(hexes):
            if i == j:
                row.append("—")
                continue
            r = contrast_ratio(a, b)
            row.append(f"{r:.2f}")
            if i < j:
                best.append((r, a, b))
        print("| " + " | ".join(row) + " |")
    best.sort(reverse=True)
    pairs = ", ".join(f"#{a}/#{b}={r:.2f}:1" for r, a, b in best[:3])
    print("")
    print(f"最优文字对: {pairs}")
    print(f"过 AA 正文对(>=4.5): {sum(1 for r,_,_ in best if r >= 4.5)} 组;过 AAA 大字(>=3): {sum(1 for r,_,_ in best if r >= 3)} 组")
    if args.recommend:
        r, a, b = best[0]
        print(f"推荐: 文字 #{a} 于底 #{b}({r:.2f}:1)")


def cmd_semantic(args):
    """色盲安全分类色:明度阶梯交错+色相均布,内置去盲分离度验证(图表/数据可视化)。"""
    n = max(3, min(12, args.count))
    base_hue = oklch_from_hex(args.base)[2] if args.base else args.hue
    out, worst = [], 0
    for tries in range(60):
        cols = []
        for i in range(n):
            hue = (base_hue + i * (360 / max(3, n)) + (15 if i % 2 else 0)) % 360
            L = 0.82 if i % 2 == 0 else 0.52
            if i == n - 1 and n % 2:
                L = 0.30
            C = 0.13 if i % 2 == 0 else 0.15
            c = gamut_fit(L, C, hue)
            cols.append(hex_from_oklch(L, c, hue))
        def lab(h):
            return oklab_from_srgb(tuple(cc / 255 for cc in parse_hex(h)))
        def labd(h):
            m = CB_MATRICES["deuteranopia"]
            rgbs = [cc / 255 for cc in parse_hex(h)]
            o = tuple(clamp(m[i]*rgbs[0] + m[i+1]*rgbs[1] + m[i+2]*rgbs[2]) for i in (0, 3, 6))
            return oklab_from_srgb(o)
        labs = [lab(h) for h in cols]
        labd_ = [labd(h) for h in cols]
        worst = 9e9
        for i in range(n):
            for j in range(i+1, n):
                worst = min(worst, math.dist(labs[i], labs[j]), math.dist(labd_[i], labd_[j]))
        if worst >= 0.08:
            out = cols
            break
        base_hue = (base_hue + 7) % 360
    if not out:
        print("无法在 60 次内找到色盲安全组合——减少 --count 或放宽", file=sys.stderr)
        sys.exit(1)
    print(" ".join(out))
    for h in out:
        L, C, H = oklch_from_hex(h)
        print(f"  #{h}  L={L:.2f} C={C:.3f} H={H:.0f}  文字:#{readable_text(h)}")
    print(f"色盲安全: 最小分离度 {worst:.3f}(>=0.08)")


def cmd_critique(args):
    """五镜报告生成器:机械发现预填,guided 表单待补 taste 裁决,附 finding ledger。"""
    lines = ["# 五镜自审报告(机械部分预填)", ""]
    pal = palette_list(args.palette) if args.palette else []
    here = os.path.abspath(__file__)
    if pal:
        sc = subprocess.run([sys.executable, here, "score", "--palette", ",".join(pal)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines += ["## 镜3 色彩(机械)", "", "```", sc.stdout or "", "```", ""]
        sl = subprocess.run([sys.executable, here, "slop", "--palette", ",".join(pal)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        lines += ["slop: " + (sl.stdout or "").strip(), ""]
    if args.evidence and os.path.exists(args.evidence):
        ev = json.load(open(args.evidence, encoding="utf-8"))
        lines += ["## 镜4 渲染实测(机械)", "",
                  f"- 主题: {ev.get('theme')} / bodyBg {ev.get('bodyBg')}",
                  f"- 实测最小字号: {ev.get('minFont')}px(样本: {ev.get('fontSample','')})",
                  "- 最差对比对: " + ", ".join(f"#{p['fg']}/#{p['bg']}={p['ratio']}" for p in ev.get("worstPairs", [])[:4]),
                  "- 色彩面积占比: " + ", ".join(f"#{c['hex']} {c['areaRatio']*100:.0f}%" for c in ev.get("colors", [])[:6]), ""]
    lines += ["## 镜0 意图(待裁决)", "- 给谁看/场景/3秒带走: ____", "- 语域匹配: ____", "",
              "## 镜1 构成(待裁决)", "- 视线落点顺序: ____", "- 签名元素唯一: ____", "",
              "## 镜2 信息(待裁决)", "- 数据是否成对出现: ____", "- 删减候选: ____", "",
              "## 镜4 文字(待裁决)", "- 字体声音匹配: ____", "",
              "## finding ledger", "",
              "```",
              "ledger: <问题1> answered | <问题2> partially(剩X) | <问题3> unresolved(原因)",
              "预算: 已用 N 轮 | 剩余: 最多 1 轮修复",
              "```"]
    out = args.out or "critique_report.md"
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    print(f"报告: {out}(机械发现已预填;taste 裁决按镜填空)")


def cmd_doctor(args):
    """环境体检:部署健康一键诊断。"""
    ok, bad = [], []
    def check(name, cond, detail=""):
        (ok if cond else bad).append(name)
        print(("PASS  " if cond else "FAIL  ") + name + (f"  {detail}" if detail else ""))
    check("python>=3.8", sys.version_info >= (3, 8))
    try:
        import PIL
        check("Pillow(extract 可用)", True)
    except ImportError:
        check("Pillow(extract 可用)", False, "pip install pillow")
    try:
        lib = json.load(open(LIBRARY, encoding="utf-8"))
        check(f"调色板库({lib['_meta']['counts']['kept']} 板)", lib["_meta"]["counts"]["kept"] >= 50)
    except Exception as e:
        check("调色板库", False, str(e)[:60])
    th = load_themes()
    check(f"主题包({len(th)} 个)", len(th) >= 5)
    pr = load_profile()
    check("profile.json(偏好档案)", "registers" in pr)
    sdir = os.path.dirname(THEMES_FILE)
    for f in ("lint_page.py", "make_variants.py", "render_probe.js", "build_library.py"):
        check(f"工具 {f}", os.path.exists(os.path.join(sdir, "..", "scripts", f)))
    st = subprocess.run([sys.executable, os.path.abspath(__file__), "selftest"],
                        capture_output=True, text=True)
    check("引擎 selftest", st.returncode == 0)
    print("")
    print(f"{len(ok)} PASS / {len(bad)} FAIL")
    sys.exit(0 if not bad else 1)


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
      <span style="font:500 13px system-ui;color:#888">aesthete-agent card</span>
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
    if args.format == "w3c":
        print(_export_w3c(hexes))
    elif args.format == "context":
        print(_export_context(hexes))
    elif args.format == "css":
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
    s.add_argument("--method", default="wcag", choices=["wcag", "apca"], help="apca=WCAG3 草案感知算法")
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

    s = sub.add_parser("themes")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_themes)

    s = sub.add_parser("theme")
    s.add_argument("name", help="主题名(中文或英文)")
    s.add_argument("--format", default="css", choices=["css", "json"])
    s.set_defaults(fn=cmd_theme)

    s = sub.add_parser("matrix")
    s.add_argument("--palette", required=True)
    s.add_argument("--recommend", action="store_true")
    s.add_argument("--method", default="wcag", choices=["wcag", "apca"], help="apca=WCAG3 草案感知算法")
    s.set_defaults(fn=cmd_matrix)

    s = sub.add_parser("semantic")
    s.add_argument("--count", type=int, default=8)
    s.add_argument("--base", default=None, help="基准色(取其色相)")
    s.add_argument("--hue", type=float, default=210.0, help="无 --base 时的起始色相")
    s.set_defaults(fn=cmd_semantic)

    s = sub.add_parser("critique")
    s.add_argument("--palette", default=None)
    s.add_argument("--evidence", default=None, help="render_probe 采集的 evidence.json")
    s.add_argument("--out", default=None)
    s.set_defaults(fn=cmd_critique)

    s = sub.add_parser("doctor")
    s.set_defaults(fn=cmd_doctor)

    s = sub.add_parser("visualize")
    s.add_argument("--palette", required=True)
    s.add_argument("--name", default="Palette")
    s.add_argument("--theme", default=None, choices=["light", "dark"])
    s.add_argument("--svg", default=None, help="对其做重着色(纯黑白保留)")
    s.add_argument("--variants", type=int, default=1, help="同场景 N 次色板排列对比(旋转+反转)")
    s.add_argument("--out", default=None)
    s.set_defaults(fn=cmd_visualize)

    s = sub.add_parser("selftest")
    s.set_defaults(fn=cmd_selftest)

    s = sub.add_parser("house")
    s.add_argument("--name", required=True)
    s.add_argument("--hexes", required=True)
    s.add_argument("--from-proj", default=None, help="来源项目名")
    s.set_defaults(fn=cmd_house)

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
    s.add_argument("--format", default="css", choices=["css", "tailwind", "json", "svg", "w3c", "context"])
    s.set_defaults(fn=cmd_export)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
