# -*- coding: utf-8 -*-
"""page_audit.py — audit 命令实现体:外部页面机械审计,每个问题给可执行的修复值。

对象是"已经存在的页面"(不是本引擎生成的):色板漂移(带最近板色替换+色距)/
禁渐变(P0)/紫域大底风险/文字对比对(给调墨后的达标替换值)/字号下限/
AI 默认签名(玻璃拟态·emoji·默认字体开局·圆角膨胀)。
只读文档内联样式与全文档色值(SVG 属性计入库存);外链 CSS 不在静态审计范围,如实声明。
P0 存在或 P1≥2 → FAIL。纯 stdlib,被 palette_forge.py 的 cmd_audit 调用。
"""
import colorsys
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palette_forge import oklch_from_hex, hex_from_oklch, gamut_fit, contrast_ratio  # noqa: E402

HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*[, ]\s*(\d+)\s*[, ]\s*(\d+)\s*\)?")
HSL_RE = re.compile(r"hsla?\(\s*([\d.]+)(?:deg)?\s*[, ]\s*([\d.]+)%\s*[, ]\s*([\d.]+)%\s*\)?")
OKLCH_RE = re.compile(r"oklch\(\s*([\d.]+)%?\s*[, ]\s*([\d.]+)\s*[, ]\s*([\d.]+)(?:deg)?\s*\)?")
GRAD_RE = re.compile(r"linear-gradient|radial-gradient|conic-gradient")
GLASS_RE = re.compile(r"backdrop-filter\s*:\s*blur|filter\s*:\s*blur\((?!0)")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2700-\u27BF\u2600-\u26FF]")
FONT_RE = re.compile(r"font-size:\s*(\d+(?:\.\d+)?)px")
COLOR_DECL_RE = re.compile(r"(?:^|[;{}])\s*color\s*:\s*([^;}]+)", re.I)
BG_DECL_RE = re.compile(r"(?:^|[;{}])\s*background(?:-color)?\s*:\s*([^;}]+)", re.I)
RULE_RE = re.compile(r"\{([^{}]*)\}")
DEFAULT_FONT_RE = re.compile(r"font-family\s*:\s*[\"']?(inter|roboto|arial|helvetica)\b", re.I)


def _is_neutral(rgb):
    return (max(rgb) - min(rgb)) < 30


def normalize(tok):
    """颜色字面量 → 6 位 HEX;不认识返回 None。"""
    tok = tok.strip().strip("'\"")
    m = re.fullmatch(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", tok)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(x * 2 for x in h)
        return h.upper()
    m = RGB_RE.fullmatch(tok.split("/")[0].strip())
    if m:
        r, g, b = (int(x) for x in m.groups())
        return "%02X%02X%02X" % (r, g, b)
    m = HSL_RE.fullmatch(tok.split("/")[0].strip())
    if m:
        hh, ll, ss = (float(x) for x in m.groups())
        r, g, b = colorsys.hls_to_rgb(hh / 360, ll / 100, ss / 100)
        return "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))
    m = OKLCH_RE.fullmatch(tok.split("/")[0].strip())
    if m:
        L, C, H = (float(x) for x in m.groups())
        if L > 1:
            L = L / 100
        C = gamut_fit(min(max(L, 0), 1), C, H % 360)
        return hex_from_oklch(min(max(L, 0), 1), C, H % 360).upper()
    return None


def _decl_value(decl):
    """声明值 → 首个可归一颜色(var() 等不可静态解析返回 None)。"""
    tok = decl.split()[0] if " " in decl.strip() and "(" not in decl else decl.strip()
    if tok.startswith("var("):
        return None
    return normalize(tok)


def collect(html):
    """全文档颜色库存:hex→出现次数(近中性灰阶照收,判定时再分层)。"""
    inv = {}
    for m in HEX_RE.finditer(html):
        h = m.group(1)
        if len(h) == 3:
            h = "".join(x * 2 for x in h)
        inv[h.upper()] = inv.get(h.upper(), 0) + 1
    for regex in (RGB_RE,):
        for m in regex.finditer(html):
            r, g, b = (int(x) for x in m.groups())
            inv["%02X%02X%02X" % (r, g, b)] = inv.get("%02X%02X%02X" % (r, g, b), 0) + 1
    for m in HSL_RE.finditer(html):
        hh, ll, ss = (float(x) for x in m.groups())
        r, g, b = colorsys.hls_to_rgb(hh / 360, ll / 100, ss / 100)
        k = "%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))
        inv[k] = inv.get(k, 0) + 1
    for m in OKLCH_RE.finditer(html):
        L, C, H = (float(x) for x in m.groups())
        if L > 1:
            L /= 100
        c2 = gamut_fit(min(max(L, 0), 1), C, H % 360)
        k = hex_from_oklch(min(max(L, 0), 1), c2, H % 360).upper()
        inv[k] = inv.get(k, 0) + 1
    return inv


def nearest(hex_c, palette):
    """OKLCH 色距最近的板色 → (hex, deltaE)。"""
    L1, a1, b1 = oklch_from_hex(hex_c)
    best, bestd = None, 1e9
    for h in palette:
        L2, a2, b2 = oklch_from_hex(h)
        d = ((L1 - L2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2) ** 0.5
        if d < bestd:
            best, bestd = h, d
    return best, bestd


def fix_contrast(hex_fg, hex_bg, need=4.5):
    """把前景调到达标(向黑压或向白提),返回(达标色, 实测比);不可达返回原色。"""
    def lum(h):
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        lin = lambda c: (c / 255) / 12.92 if c / 255 <= 0.04045 else (((c / 255) + 0.055) / 1.055) ** 2.4
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    r = contrast_ratio(hex_fg, hex_bg)
    if r >= need:
        return hex_fg, r
    l_fg, l_bg = lum(hex_fg), lum(hex_bg)
    toward = "000000" if l_fg <= l_bg else "FFFFFF"
    fr, fg_, fb = (int(hex_fg[i:i + 2], 16) for i in (0, 2, 4))
    tr, tg, tb = (int(toward[i:i + 2], 16) for i in (0, 2, 4))
    for k in range(1, 21):
        mix = k / 20.0
        cand = "%02X%02X%02X" % (round(fr + (tr - fr) * mix),
                                 round(fg_ + (tg - fg_) * mix), round(fb + (tb - fb) * mix))
        r = contrast_ratio(cand, hex_bg)
        if r >= need:
            return cand, r
    return hex_fg, r


def audit_page(html, declared_palette=None, floor=12.0):
    """→ findings [{sev, check, msg, fix}], inventory。"""
    findings = []
    inv = collect(html)

    # 1 禁渐变(P0)
    grads = GRAD_RE.findall(html)
    if grads:
        stops = [normalize(m.group(1)) for m in re.finditer(
            r"gradient\([^)]{0,80}?(#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\b", html)][:4]
        stops = [s for s in stops if s]
        findings.append({
            "sev": "P0", "check": "gradient",
            "msg": "禁渐变:渐变出现 %d 处%s" % (len(grads),
                  ("(取样 %s)" % ", ".join("#" + s for s in stops)) if stops else ""),
            "fix": "一律纯色分层替代:大底一块纯色,层次用明度差与留白做,不做过渡带"})

    # 2 色板漂移 + 紫域大底
    chromatic = {h: n for h, n in inv.items() if not _is_neutral((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))}
    if declared_palette:
        pal = [h.upper().lstrip("#") for h in declared_palette]
        pal6 = ["".join(x * 2 for x in h) if len(h) == 3 else h for h in pal]
        drift = [h for h in chromatic if h not in pal6]
        drift.sort(key=lambda h: -chromatic[h])
        for h in drift[:5]:
            rep, dE = nearest(h, pal6)
            findings.append({
                "sev": "P1", "check": "drift",
                "msg": "色板漂移:#%s ×%d(声明板外)" % (h, chromatic[h]),
                "fix": "最近板色 #%s(ΔE %.2f)——若该色确有语义,先把它补进声明再罢" % (rep, dE)})
    bg_declared = [_decl_value(m.group(1)) for m in BG_DECL_RE.finditer(html)]
    bg_declared = [h for h in bg_declared if h and not _is_neutral(
        (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))]
    for h in sorted(set(bg_declared)):
        hh, ll, ss = colorsys.rgb_to_hls(*[int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])
        hue = hh * 360
        if 255 <= hue <= 330 and ss > 0.30 and 0.10 < ll < 0.85:
            rep, dE = (nearest(h, [x.upper().lstrip("#") for x in declared_palette])
                       if declared_palette else (None, 0))
            findings.append({
                "sev": "P1", "check": "purple_background",
                "msg": "紫域大底:#%s 作 background(hue %.0f,饱和 %.2f)——大面积紫是 AI 默认审美的头号签名" % (h, hue, ss),
                "fix": ("换板或改用 #%s;低饱灰紫可保留但需降饱和到 0.30 以下" % rep) if rep else
                       "换板,或把饱和降到 0.30 以下并复核大面积观感"})

    # 3 文字对比对(color 与 background 同规则块且均可静态解析)
    for m in RULE_RE.finditer(html):
        body = m.group(1)
        cm, bm = COLOR_DECL_RE.search(body), BG_DECL_RE.search(body)
        if not (cm and bm):
            continue
        fg, bg = _decl_value(cm.group(1)), _decl_value(bm.group(1))
        if not (fg and bg):
            continue
        r = contrast_ratio(fg, bg)
        if r < 4.5:
            fixed, rr = fix_contrast(fg, bg, 4.5)
            findings.append({
                "sev": "P1", "check": "contrast_pair",
                "msg": "对比不足:#%s on #%s = %.2f:1" % (fg, bg, r),
                "fix": "字色换 #%s(实测 %.2f:1)" % (fixed, rr) if fixed != fg
                       else "该对无法单向调墨达标,换底色或加大字号走大字 3:1 档"})

    # 4 字号下限
    sizes = [float(x) for x in FONT_RE.findall(html)]
    small = sorted(s for s in sizes if s < floor)
    if small:
        sev = "P1" if min(small) < floor * 0.7 else "P2"
        findings.append({
            "sev": sev, "check": "font_floor",
            "msg": "字号低于下限 %.0fpx: %s" % (floor, sorted(set(small))),
            "fix": "正文下限 12px(数据/说明);投影与海报场景建议 24-34px"})

    # 4b 排印:中文负字距 / display 行高松弛
    lang_zh = re.search(r"<html[^>]*lang=[\"']zh", html, re.I) is not None
    if lang_zh:
        negs = ["%s%s" % (v, u) for v, u in
                re.findall(r"letter-spacing:\s*(-\d*\.?\d+)(em|px|rem)", html) if float(v) < 0]
        if negs:
            findings.append({"sev": "P2", "check": "cjk_negative_tracking",
                             "msg": "中文页出现负字距 %s——方块字负字距致笔画碰撞" % sorted(set(negs)),
                             "fix": "中文任何字号 0~+0.02em;Latin display 才可用 -0.02em(隔离到 Latin 专用类)"})
    for m in re.finditer(r"<h[1-3][^>]*>[^<]*</h[1-3]>|h[1-3][^{]*\{[^{}]*\}", html):
        block = m.group(0)
        fs = re.search(r"font-size:\s*(\d+(?:\.\d+)?)px", block)
        lh = re.search(r"line-height:\s*(\d+(?:\.\d+)?)", block)
        if fs and lh and float(fs.group(1)) >= 28 and float(lh.group(1)) >= 1.4:
            findings.append({"sev": "P2", "check": "display_line_height",
                             "msg": "display 级标题 %.0fpx 配行高 %s——无 display 感" % (float(fs.group(1)), lh.group(1)),
                             "fix": "巨标行高 1.05-1.15;行高对比律(巨标/导语/正文强制拉开)"})
            break

    # 4c 布局:三等分滥用 / 间距档位 / 跑马灯计数
    span4 = len(re.findall(r"grid-column:\s*span\s*4\b", html))
    if span4 >= 3:
        findings.append({"sev": "P2", "check": "equal_thirds",
                         "msg": "span 4 出现 %d 次——三等分卡片惯性;连续两节禁同跨度组合,4+4+4 每页最多一次" % span4,
                         "fix": "换跨度词汇:7+5/5+4+3/2+8+2/6+3+3,或不对称比 7:5/8:4/5:8"})
    tier_ok = {40, 48, 64, 80, 96, 120}
    bad_pad = []
    for m in re.finditer(r"(?:^|\n)\s*section[^{]*\{[^}]*?padding(?:-top)?:\s*(\d+)px", html):
        v = int(m.group(1))
        if v not in tier_ok and min(abs(v - x) for x in tier_ok) > 4:
            bad_pad.append(v)
    if bad_pad:
        findings.append({"sev": "P2", "check": "section_spacing_tier",
                         "msg": "节距越档: %s——只用 96/64/40 三档(海报风 120/80/48)" % sorted(set(bad_pad)),
                         "fix": "节距三级制:96(幕间)/64(分节)/40(紧凑);保持 8 的倍数"})
    kf_names = set(re.findall(r"@keyframes\s+([\w-]+)\s*\{(?:(?!@keyframes)[\s\S])*?translateX", html))
    marquees = sum(len(re.findall(r"animation(?:-name)?\s*:[^;}]*\b" + re.escape(n) + r"\b", html))
                   for n in kf_names)
    if marquees > 1:
        findings.append({"sev": "P2", "check": "marquee_count",
                         "msg": "跑马灯/无限横移动画 %d 处(每页≤1)" % marquees,
                         "fix": "一页一条跑马灯;其余改静态带"})
    # 4d 大面积背景脏色检查:结构级标签的背景须为浅 tint/低饱和/深暗幕
    for m in re.finditer(r"(?:^|\n)\s*(?:body|section|header|footer|main|nav|aside)[^{]*"
                         r"\{[^}]*?background(?:-color)?:\s*([^;}]+)", html, re.I):
        col = _decl_value(m.group(1))
        if not col:
            continue
        rr, gg, bb = (int(col[i:i + 2], 16) / 255 for i in (0, 2, 4))
        hh, ll, ss = colorsys.rgb_to_hls(rr, gg, bb)
        if ss >= 0.25 and 0.30 < ll < 0.85:
            findings.append({
                "sev": "P2", "check": "muddy_large_bg",
                "msg": "大面积背景用了中饱和中明度色 #%s(显脏风险)" % col,
                "fix": "大面积背景三选一:向白 tint 到 L≥0.85 / 低饱和深暗幕(L≤0.25) / 干脆白底+细边"})
    # 5 AI 默认签名
    if GLASS_RE.search(html):
        findings.append({"sev": "P1", "check": "glassmorphism",
                         "msg": "玻璃拟态(backdrop-filter/filter blur)——高 AI 默认签名,且可读性不可控",
                         "fix": "实色卡片面 + 发丝线描边替代磨砂层"})
    if EMOJI_RE.search(html):
        n = len(EMOJI_RE.findall(html))
        findings.append({"sev": "P2", "check": "emoji",
                         "msg": "emoji 出现 %d 处(图标位尤甚)" % n,
                         "fix": "线性 SVG 图标或纯文字 pills 替代"})
    if DEFAULT_FONT_RE.search(html):
        findings.append({"sev": "P2", "check": "default_font",
                         "msg": "字体栈以默认系统字开局(Inter/Roboto/Arial/Helvetica 打头)",
                         "fix": "中英混排给完整栈(苹方/雅黑/思源),标题考虑衬线对微字"})
    radii = [float(x) for x in re.findall(r"border-radius:\s*(\d+(?:\.\d+)?)px", html)]
    if len([r for r in radii if r >= 28]) > 3:
        findings.append({"sev": "P2", "check": "radius_inflation",
                         "msg": "圆角膨胀:≥28px 圆角 %d 处" % len([r for r in radii if r >= 28]),
                         "fix": "圆角克制(8/12/16/24 四档封顶),大圆角堆叠=廉价感签名"})

    return findings, inv


def run(page, declared_palette=None, floor=12.0, out_base=None):
    with open(page, encoding="utf-8") as f:
        html = f.read()
    findings, inv = audit_page(html, declared_palette, floor)
    n = {s: sum(1 for f in findings if f["sev"] == s) for s in ("P0", "P1", "P2")}
    verdict = "FAIL" if n["P0"] or n["P1"] >= 2 else ("PASS" if not findings else "WARN")
    order = {"P0": 0, "P1": 1, "P2": 2}
    findings.sort(key=lambda f: order[f["sev"]])
    with open(page, "rb") as f:
        page_fp = hashlib.sha256(f.read()).hexdigest()
    payload = {
        "page": os.path.abspath(page), "page_sha256": page_fp,
        "palette": [h.upper().lstrip("#") for h in declared_palette] if declared_palette else [],
        "inventory_top": dict(sorted(inv.items(), key=lambda kv: -kv[1])[:16]),
        "findings": findings, "counts": n, "verdict": verdict,
        "scope": "静态审计:内联样式+全文档色值;外链 CSS 与浏览器实测不在本闸范围(用 render probe/evidence 补)",
    }
    payload["fingerprint"] = hashlib.sha256(
        ("aesthete-audit/v1|" + page_fp + "|" + verdict).encode("utf-8")).hexdigest()
    if out_base:
        with open(out_base + ".json", "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
    return payload
