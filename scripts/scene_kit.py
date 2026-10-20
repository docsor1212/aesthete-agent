# -*- coding: utf-8 -*-
"""scene_kit.py — showcase 级单场景构建器(scene 命令的实现体)。

把推广 showcase 的场景手艺(设备框/证据徽章/真实内容密度)开放为引擎能力:
scene --kind wallet --theme "Deep Pine" → 独立 HTML,可作实际页面的起点或嵌入块。
含 AI 默认紫守门:大底角色落在紫 hue 域即拒绝(用户令 2026-10-20)。
"""
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
SCENE_CSS = io_open = None


def _load_css():
    global SCENE_CSS
    if SCENE_CSS is None:
        with open(os.path.join(_HERE, "scene_css.css"), encoding="utf-8") as f:
            SCENE_CSS = f.read()
    return SCENE_CSS


def _hue(h):
    """OKLCH hue(度)。"""
    import colorsys
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return hh * 360


def purple_guard(hexes, roles_map, force=False):
    """AI 默认紫守门:大底/大面积角色(最浅或最深)落在紫 hue 域(265-330)即拒绝。
    返回 (ok, message)。--force 可越过但会留下记录。"""
    import colorsys
    for h in hexes:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
        hue = hh * 360
        # 紫域窗口 255-330(紫罗兰→品红);高饱和才触发(低饱灰紫不算大面积紫)
        if 255 <= hue <= 330 and ss > 0.30 and 0.10 < ll < 0.85:
            if force:
                return True, f"FORCE: 紫 hue 色 #{h}(hue {hue:.0f})——已记录,质量责任自负"
            return False, (f"AI 默认紫守门:#{h}(hue {hue:.0f})在紫域且高饱和,极可能形成大面积紫。"
                           f"紫渐变/紫大底是 AI 默认审美的头号签名——换板,或 --force 强行越过。")
    return True, ""


def _lum(h):
    def lin(c):
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


KINDS = {
    "wallet": "sc_mobile",
    "landing": "sc_landing",
    "dashboard": "sc_dashboard",
    "branding": "sc_branding",
    "typography": "sc_typography",
    "chart": "sc_chart",
    "ecom": "sc_ecom",
    "email": "sc_email",
    "editorial": "sc_editorial",
    "pattern": "sc_pattern",
}


def build_scene(kind, hexes, name, dark=False, force=False):
    """kind + 色板 → (html, declared_palette)。紫守门不过则抛 ValueError。"""
    import _showcase_scenes as ss
    kind = kind.lower().strip()
    if kind not in KINDS:
        raise ValueError(f"未知场景类型: {kind}——可选: {', '.join(KINDS)}")
    hexes = [h.upper().lstrip("#") for h in hexes]
    ok, msg = purple_guard(hexes, None, force=force)
    if not ok:
        raise ValueError(msg)
    p = {"hexes": hexes, "theme": "dark" if dark else "light", "name": name}
    R = ss.roles(p)
    inner = getattr(ss, KINDS[kind])(R)
    badges = ss.badge(R)
    css = _load_css()
    html = (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
        f"<title>scene · {kind} · {name}</title>\n<style>\n"
        "body{margin:0;padding:34px 20px;display:flex;justify-content:center;"
        "font-family:system-ui,sans-serif}\n"
        + css +
        "\n</style>\n</head>\n<body>\n"
        "<div class='stage' style=\"border-radius:24px;padding:56px 40px;display:flex;"
        "justify-content:center;align-items:center;min-height:420px\">\n"
        + inner + "\n" + badges + "\n</div>\n</body>\n</html>\n"
    )
    declared = ",".join(sorted(hexes))
    return html, declared
