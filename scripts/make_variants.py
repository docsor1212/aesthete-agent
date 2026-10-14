#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_variants.py — 候选纪律的机制:≥2 个整页候选合成一张对比页。

用法:
  python make_variants.py a.html b.html [c.html ...] --labels "暗夜" "素雅" --out compare.html
  (对比页与候选文件放同目录即可;iframe 同源直接渲染)

纪律:交付用户裁决前必须 ≥2 个候选;只有 1 个方案 = 退出码 1。
"""
import argparse
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+", help="候选页面(≥2)")
    ap.add_argument("--labels", nargs="+", default=None, help="每个候选的名字")
    ap.add_argument("--out", default="compare.html")
    args = ap.parse_args()

    if len(args.pages) < 2:
        print("候选纪律:只有 1 个方案不得送审——至少给 2 个候选(replace/mutate/harmony 换种子再来)")
        sys.exit(1)
    labels = args.labels or [f"候选 {chr(0x41+i)}" for i in range(len(args.pages))]
    assert len(labels) == len(args.pages), "labels 数量与 pages 不一致"

    cells = []
    for p, lab in zip(args.pages, labels):
        cells.append(f"""
    <div class="cell">
      <div class="cap"><b>{lab}</b><span>{os.path.basename(p)}</span></div>
      <iframe src="{p}" loading="lazy"></iframe>
    </div>""")
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>候选对比 — pick one</title><style>
  body{{margin:0;background:#20242B;font-family:system-ui;color:#E8EEF6}}
  header{{padding:18px 26px;font-size:15px;letter-spacing:.08em;
         border-bottom:1px solid rgba(255,255,255,.12)}}
  header b{{color:#F2CC8F}}
  .grid{{display:grid;grid-template-columns:repeat({min(len(cells), 2)},1fr);gap:14px;padding:14px}}
  .cell{{border:1px solid rgba(255,255,255,.14);border-radius:8px;overflow:hidden}}
  .cap{{display:flex;justify-content:space-between;padding:9px 14px;font-size:13px;
       background:rgba(255,255,255,.06)}}
  .cap span{{opacity:.55;font-family:monospace;font-size:12px}}
  iframe{{width:100%;height:78vh;border:0;display:block;background:#fff}}
</style></head><body>
<header>候选对比 —— 看完点名,<b>说出字母</b>即为你所用</header>
<div class="grid">{''.join(cells)}
</div></body></html>"""
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"对比页: {args.out}({len(args.pages)} 候选)")
    print("送审语:把对比页发给用户,等点名,不要替用户决定。")


if __name__ == "__main__":
    main()
