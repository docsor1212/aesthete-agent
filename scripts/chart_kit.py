# -*- coding: utf-8 -*-
"""chart_kit.py — chartpal 命令实现体:图表用色派生(分类/顺序/发散)+色盲区分度验证。

分类板:候选色在三种色盲模拟(protan/deutan/tritan)下的两两 ΔE 择优,明度强制拉开;
顺序板:单色相 OKLCH 明度爬坡(gamut 内收敛),相邻步差与单调性验证;
发散板:双端色相向中性中点对称爬坡,中点必须近中性。
产出 JSON + 带标注色样 HTML(每对相邻色给三模拟最小 ΔE)。零依赖 stdlib,
被 palette_forge.py 的 cmd_chartpal 调用。
"""
import hashlib
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palette_forge import (oklch_from_hex, hex_from_oklch, gamut_fit,  # noqa: E402
                           simulate_cb, parse_hex)

CVK = ("protanopia", "deuteranopia", "tritanopia")
NEUTRAL = lambda r, g, b: (max(r, g, b) - min(r, g, b)) < 30


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _is_neutral(h):
    return NEUTRAL(*_rgb(h))


def _cvd_de(h):
    """色在三种模拟下的 OKLCH 坐标(含原色)。"""
    pts = [oklch_from_hex(h)]
    for k in CVK:
        pts.append(oklch_from_hex(simulate_cb(h, k)))
    return pts


def _dE(p1, p2):
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2 + (p1[2] - p2[2]) ** 2)


def pair_dE(h1, h2):
    """两色在(原色+三模拟)空间的最小 ΔE——区分度下界。"""
    a, b = _cvd_de(h1), _cvd_de(h2)
    return min(_dE(x, y) for x in a for y in b)


def categorical(hexes, n):
    """从候选色选 n 个系列色:贪心最大化最小 CVD 区分度;不够则色相旋转补足。
    → (series list, checks dict)。"""
    cand = [h.upper().lstrip("#") for h in hexes]
    cand = [h for h in cand if len(h) == 6]
    # 补足:n 超过候选数时按色相 30° 步进旋转基色(gamut 内)
    base = cand[0]
    while len(cand) < n:
        k = len(cand)
        L, C, H = oklch_from_hex(base)
        h2 = hex_from_oklch(L, gamut_fit(L, C, (H + 30 * k) % 360), (H + 30 * k) % 360).upper()
        if h2 not in cand:
            cand.append(h2)
        else:
            break
    # 贪心:首取饱和度最高者,其后每次加入使"最小两两区分度"最大的候选
    cand.sort(key=lambda h: -oklch_from_hex(h)[1])
    series = [cand[0]]
    while len(series) < n and len(series) < len(cand):
        best, bestscore = None, -1.0
        for h in cand:
            if h in series:
                continue
            score = min(pair_dE(h, s) for s in series)
            if score > bestscore:
                best, bestscore = h, score
        if best is None:
            break
        series.append(best)
    Ls = [oklch_from_hex(h)[0] for h in series]
    checks = {
        "min_pair_dE_cvd": round(min(pair_dE(a, b) for i, a in enumerate(series)
                                     for b in series[i + 1:]), 3) if len(series) > 1 else 1.0,
        "l_range": round(max(Ls) - min(Ls), 3),
        "count": len(series),
    }
    checks["verdict"] = "PASS" if (checks["min_pair_dE_cvd"] >= 0.10 and checks["l_range"] >= 0.20) else "WARN"
    return series, checks


def sequential(base, n, reverse=False):
    """单色相明度爬坡:L 从 0.92 降到 0.28, chroma 中段隆起(gamut 收敛)。
    → (series, checks)。"""
    L0, C0, H0 = oklch_from_hex(base)
    H0 = H0 if not _is_neutral(base) else 250.0  # 近中性基色给默认蓝相,不生成灰坡
    out = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        L = 0.92 - (0.92 - 0.28) * t
        C = C0 * (0.45 + 0.55 * math.sin(math.pi * min(max(t, 0.08), 0.92)))
        C = gamut_fit(L, max(C, 0.02), H0)
        out.append(hex_from_oklch(L, C, H0).upper())
    if reverse:
        out = out[::-1]
    Ls = [oklch_from_hex(h)[0] for h in out]
    steps = [abs(Ls[i + 1] - Ls[i]) for i in range(len(Ls) - 1)]
    mono = all(Ls[i] >= Ls[i + 1] for i in range(len(Ls) - 1)) or \
           all(Ls[i] <= Ls[i + 1] for i in range(len(Ls) - 1))
    checks = {"min_step": round(min(steps), 3) if steps else 0.0,
              "monotonic": bool(mono), "l_range": round(max(Ls) - min(Ls), 3), "count": len(out)}
    checks["verdict"] = "PASS" if (mono and checks["min_step"] >= 0.03 and checks["l_range"] >= 0.45) else "WARN"
    return out, checks


def diverging(hex_a, hex_b, n):
    """双端色相 → 近中性中点 → 两侧对称明度拱。n 取奇数(中点占一位)。"""
    if n % 2 == 0:
        n += 1
    half = n // 2
    left, _ = sequential(hex_a, half + 1, reverse=True)   # 深→浅(向中点)
    right, _ = sequential(hex_b, half + 1, reverse=False)  # 浅→深(离中点)
    midL = 0.93
    mid = hex_from_oklch(midL, gamut_fit(midL, 0.015, 250), 250).upper()
    out = left[:-1] + [mid] + right[1:]
    Ls = [oklch_from_hex(h)[0] for h in out]
    m = len(out) // 2
    lmono = all(Ls[i] <= Ls[i + 1] for i in range(m)) and all(Ls[i] >= Ls[i + 1] for i in range(m, len(Ls) - 1))
    checks = {"midpoint": mid, "midpoint_neutral": _is_neutral(mid),
              "arch": bool(lmono), "l_range": round(max(Ls) - min(Ls), 3), "count": len(out)}
    checks["verdict"] = "PASS" if (lmono and checks["midpoint_neutral"]) else "WARN"
    return out, checks


def emit(kind, series, checks, name="", out_base="chartpal"):
    """JSON + 色样 HTML。"""
    verdict = checks.get("verdict", "WARN")
    payload = {"kind": kind, "name": name, "series": series, "checks": checks, "verdict": verdict}
    payload["fingerprint"] = hashlib.sha256(
        ("aesthete-chartpal/v1|" + kind + "|" + ",".join(series) + "|" + verdict).encode("utf-8")).hexdigest()
    with open(out_base + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    cells = []
    n = len(series)
    for i, h in enumerate(series):
        ink = "FFFFFF" if oklch_from_hex(h)[0] < 0.55 else "1A1A1A"
        note = "中点" if (kind == "diverging" and i == n // 2) else ("高" if i == 0 else ("低" if i == n - 1 else ""))
        cells.append(
            f'<div style="flex:1;min-width:86px"><div style="background:#{h};height:72px;border-radius:10px;'
            f'display:flex;align-items:flex-end;justify-content:flex-start;padding:8px">'
            f'<code style="color:#{ink};font-size:12px;font-weight:700">#{h}</code></div>'
            f'<p style="margin:6px 2px 0;font:600 12px system-ui;color:#444">{note or ("系列 %d" % (i + 1))}</p></div>')
    pairs = []
    for i in range(n - 1):
        pairs.append(f"<li>#{series[i]} ↔ #{series[i + 1]}:min ΔE(CVD×3) "
                     f"{pair_dE(series[i], series[i + 1]):.2f}</li>")
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><title>chartpal · {name or kind}</title></head>
<body style="font:15px/1.7 system-ui;margin:0;padding:28px;background:#FBFBF9;color:#222">
<h2 style="margin:0 0 4px">chartpal · {name or kind} <span style="font-size:13px;color:#777">裁决 {verdict}</span></h2>
<p style="color:#666;margin:0 0 18px">一个主角系列给重点,其余为衬托;直接标注数据,少用图例;数字列用 tabular-nums。</p>
<div style="display:flex;gap:12px;flex-wrap:wrap">{''.join(cells)}</div>
<h3 style="font-size:15px;margin:22px 0 8px">相邻区分度(三色盲模拟下界)</h3>
<ul style="font-size:13.5px;color:#555">{''.join(pairs)}</ul>
<p style="font-size:12.5px;color:#888">指纹 {payload["fingerprint"][:16]}… · aesthete-agent chartpal(0.10.0)</p>
</body></html>"""
    with open(out_base + ".html", "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return payload
