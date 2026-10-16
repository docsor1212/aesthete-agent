#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""aesthete-agent MCP server — the engine as MCP tools.

Run (FastMCP environment):
    uvx aesthete-agent-mcp            # PyPI (self-contained wheel)
    # or: uvx --from "git+https://github.com/docsor1212/aesthete-agent#subdirectory=mcp" aesthete-agent-mcp
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
# 引擎解析: skill 安装树优先(单一事实源), PyPI 独立安装用捆绑副本
_ENGINE_CANDIDATES = [
    os.path.join(_HERE, "..", "scripts", "palette_forge.py"),
    os.path.join(_HERE, "server_data", "scripts", "palette_forge.py"),
]
ENGINE = next((p for p in _ENGINE_CANDIDATES if os.path.exists(p)), _ENGINE_CANDIDATES[0])

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



# ---- pure-stdlib stdio transport (fallback when fastmcp is absent) ----
_STDIO_TOOLS = [
    ("palette_match", "Rank the evidence palette library for a design brief",
     {"brief": {"type": "string"}, "limit": {"type": "number"}}, ["brief"]),
    ("palette_harmony", "Generate an OKLCH harmony from a base hex",
     {"base": {"type": "string"}, "mode": {"type": "string"}, "theme": {"type": "string"}}, ["base"]),
    ("palette_score", "5-dimension scorecard /20 for a palette",
     {"palette": {"type": "string"}}, ["palette"]),
    ("palette_contrast", "WCAG/APCA contrast for fg+bg with fix suggestions",
     {"fg": {"type": "string"}, "bg": {"type": "string"}, "method": {"type": "string"}}, ["fg", "bg"]),
    ("palette_matrix", "Full pairwise contrast matrix",
     {"palette": {"type": "string"}, "method": {"type": "string"}, "recommend": {"type": "boolean"}}, ["palette"]),
    ("palette_blind", "Three color-blindness simulations with collision checks",
     {"palette": {"type": "string"}}, ["palette"]),
    ("palette_semantic", "CB-safe categorical data colors",
     {"count": {"type": "number"}, "base": {"type": "string"}}, []),
    ("palette_themes", "List named theme packs", {}, []),
    ("palette_theme", "Emit a named theme pack as css/json tokens",
     {"name": {"type": "string"}, "fmt": {"type": "string"}}, ["name"]),
    ("palette_export", "Export palette as css/tailwind/json/w3c/context",
     {"palette": {"type": "string"}, "fmt": {"type": "string"}}, ["palette"]),
    ("palette_slop", "AI-slop signature detection (exit-code enforced)",
     {"palette": {"type": "string"}}, ["palette"]),
    ("palette_visualize", "Render palette into 10 realistic UI scenes (+svg recolor)",
     {"palette": {"type": "string"}, "out": {"type": "string"}, "theme": {"type": "string"}}, ["palette"]),
]


def _stdio_serve():
    """MCP stdio JSON-RPC loop in pure stdlib — zero-dependency fallback."""
    dispatch = {
        "palette_match": lambda a: palette_match_impl(a.get("brief", ""), int(a.get("limit", 6))),
        "palette_harmony": lambda a: palette_harmony_impl(a.get("base", ""), a.get("mode", "analogous"), a.get("theme", "light")),
        "palette_score": lambda a: palette_score_impl(a.get("palette", "")),
        "palette_contrast": lambda a: palette_contrast_impl(a.get("fg", ""), a.get("bg", ""), a.get("method", "wcag")),
        "palette_matrix": lambda a: palette_matrix_impl(a.get("palette", ""), a.get("method", "wcag"), bool(a.get("recommend", True))),
        "palette_blind": lambda a: palette_blind_impl(a.get("palette", "")),
        "palette_semantic": lambda a: palette_semantic_impl(int(a.get("count", 8)), a.get("base", "")),
        "palette_themes": lambda a: palette_themes_impl(),
        "palette_theme": lambda a: palette_theme_impl(a.get("name", ""), a.get("fmt", "css")),
        "palette_export": lambda a: palette_export_impl(a.get("palette", ""), a.get("fmt", "css")),
        "palette_slop": lambda a: palette_slop_impl(a.get("palette", "")),
        "palette_visualize": lambda a: palette_visualize_impl(a.get("palette", ""), a.get("out", "visualizer.html"), a.get("theme", "")),
    }
    tools = [{"name": n, "description": (d.strip() if d else n),
              "inputSchema": {"type": "object", "properties": props, "required": req}}
             for n, d, props, req in _STDIO_TOOLS]

    def respond(mid, result=None, error=None):
        msg = {"jsonrpc": "2.0", "id": mid}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result if result is not None else {}
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            respond(mid, {"protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "aesthete-agent-mcp", "version": "0.4.0"}})
        elif method == "notifications/initialized" or mid is None:
            continue
        elif method == "ping":
            respond(mid, {})
        elif method == "tools/list":
            respond(mid, {"tools": tools})
        elif method == "tools/call":
            params = msg.get("params", {}) or {}
            name = params.get("name")
            try:
                text = dispatch[name](params.get("arguments", {}) or {})
                respond(mid, {"content": [{"type": "text", "text": str(text)}]})
            except KeyError:
                respond(mid, error={"code": -32602, "message": f"unknown tool: {name}"})
            except Exception as e:
                respond(mid, {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True})
        else:
            respond(mid, error={"code": -32601, "message": f"method not found: {method}"})
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="import/impl self-check, no server")
    ap.add_argument("--stdio", action="store_true", help="force pure-stdlib stdio MCP transport")
    a = ap.parse_args(argv)
    if a.check:
        ok, text = _call_engine(["selftest"])
        print("engine selftest:", "OK" if ok else "FAIL")
        print("tools exposed:", 12 if FastMCP is not None else 0, "(fastmcp",
              "available)" if FastMCP is not None else "NOT installed — impl-only mode)")
        return 0 if ok else 1
    if FastMCP is None or a.stdio:
        return _stdio_serve()  # zero-dependency stdio MCP (MCPB bundles / bare venvs)
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
