#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aesthete-agent MCP server — the engine as MCP tools.

Run (FastMCP environment):
    uvx --from "git+https://github.com/docsor1212/aesthete-agent#subdirectory=mcp" aesthete-agent-mcp
    # or: python mcp/server.py            # stdio mode

Design (inherited from the family pattern):
- Core logic `_call_engine` shells out to scripts/palette_forge.py — single source of
  truth, no duplicated color math, works without fastmcp (safe to import for tests).
- Zero keys, zero telemetry; fully offline engine.
- Tools cover the highest-value surface: library match, generation, validation
  (scorecard / WCAG / APCA / color-blind), themes, and token exports (w3c/context).
"""
import argparse
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(_HERE, "..", "scripts", "palette_forge.py")

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - engine calls remain available without fastmcp
    FastMCP = None


def _call_engine(args, timeout=60):
    """Run palette_forge.py with args; return (ok, text)."""
    cmd = [sys.executable, ENGINE] + [str(a) for a in args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "engine timeout"
    text = (r.stdout or r.stderr or "").strip()
    return r.returncode == 0, text


def _tool(fn):
    """Register a tool when FastMCP is available; expose impl regardless."""
    if FastMCP is not None:
        return mcp.tool(fn)
    return fn


def palette_match_impl(brief: str, limit: int = 6, no_flags: bool = False) -> str:
    """Rank the 89-palette evidence library for a natural-language brief.
    Auto-detects register, applies learned preference penalties, sorts by endorsement tiers."""
    args = ["match", "--brief", brief, "--limit", str(limit)]
    if no_flags:
        args.append("--no-flags")
    ok, text = _call_engine(args)
    return text


def palette_harmony_impl(base: str, mode: str = "analogous", theme: str = "light") -> str:
    """Generate an OKLCH harmony palette from a seed color (7 rules x light/dark)."""
    ok, text = _call_engine(["harmony", "--base", base, "--mode", mode, "--theme", theme])
    return text


def palette_score_impl(palette: str) -> str:
    """5-dimension scorecard (/20) with P0-P3 findings: architecture, readability,
    CB-safety, saturation discipline, uniqueness. Exit non-zero = untrustworthy."""
    ok, text = _call_engine(["score", "--palette", palette])
    return text


def palette_contrast_impl(fg: str, bg: str, method: str = "wcag") -> str:
    """Contrast for one fg/bg pair. method='apca' uses the APCA 0.1.9 perceptual
    algorithm (WCAG 3 draft direction; Lc>=75 body, >=60 large, >=45 bold)."""
    ok, text = _call_engine(["contrast", "--fg", fg, "--bg", bg, "--method", method])
    return text


def palette_matrix_impl(palette: str, method: str = "wcag", recommend: bool = True) -> str:
    """Full pairwise contrast matrix (WCAG ratios or APCA Lc) + best-pair recommendation."""
    args = ["matrix", "--palette", palette, "--method", method]
    if recommend:
        args.append("--recommend")
    ok, text = _call_engine(args)
    return text


def palette_blind_impl(palette: str) -> str:
    """Simulate protanopia/deuteranopia/tritanopia; flags collision risk."""
    ok, text = _call_engine(["blind", "--palette", palette])
    return text


def palette_semantic_impl(count: int = 8, base: str = "") -> str:
    """Color-blind-safe categorical colors for charts: interleaved luminance ramp +
    evenly spread hues, verified >=0.08 min separation under deuteranopia."""
    args = ["semantic", "--count", str(count)]
    if base:
        args += ["--base", base]
    ok, text = _call_engine(args)
    return text


def palette_themes_impl() -> str:
    """List named theme packs (colors + fonts + voice + use-when), all dogfood-proven."""
    ok, text = _call_engine(["themes"])
    return text


def palette_theme_impl(name: str, fmt: str = "css") -> str:
    """Emit a named theme as CSS custom properties (or full JSON)."""
    ok, text = _call_engine(["theme", name, "--format", fmt])
    return text


def palette_export_impl(palette: str, fmt: str = "css") -> str:
    """Export tokens: css | tailwind | json | svg | w3c (W3C Design Tokens) |
    context (paste-ready color-system context for any LLM)."""
    ok, text = _call_engine(["export", "--palette", palette, "--format", fmt])
    return text


def palette_slop_impl(palette: str) -> str:
    """Detect AI-slop signatures: training-median hexes, purple gradients,
    flat lightness, all-loud palettes."""
    ok, text = _call_engine(["slop", "--palette", palette])
    return text


def palette_visualize_impl(palette: str, out: str = "visualizer.html", theme: str = "") -> str:
    """Render the palette into 6 realistic UI scenes (mobile, landing, dashboard,
    branding, typography, pattern) with derived roles and legibility gates;
    optionally recolor an SVG keeping pure black/white."""
    args = ["visualize", "--palette", palette, "--out", out]
    if theme:
        args += ["--theme", theme]
    ok, text = _call_engine(args)
    return text


if FastMCP is not None:
    mcp = FastMCP("aesthete-agent")

    _tool(palette_match_impl)
    _tool(palette_harmony_impl)
    _tool(palette_score_impl)
    _tool(palette_contrast_impl)
    _tool(palette_matrix_impl)
    _tool(palette_blind_impl)
    _tool(palette_semantic_impl)
    _tool(palette_themes_impl)
    _tool(palette_theme_impl)
    _tool(palette_export_impl)
    _tool(palette_slop_impl)
    _tool(palette_visualize_impl)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="import/impl self-check, no server")
    a = ap.parse_args(argv)
    if a.check:
        ok, text = _call_engine(["selftest"])
        print("engine selftest:", "OK" if ok else "FAIL")
        print("tools exposed:", 12 if FastMCP is not None else 0, "(fastmcp",
              "available)" if FastMCP is not None else "NOT installed — impl-only mode)")
        return 0 if ok else 1
    if FastMCP is None:
        print('缺少 FastMCP 运行环境:uvx --from "git+https://github.com/docsor1212/aesthete-agent#subdirectory=mcp" aesthete-agent-mcp')
        return 2
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
