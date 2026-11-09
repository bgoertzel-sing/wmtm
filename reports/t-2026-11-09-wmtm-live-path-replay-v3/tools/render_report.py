#!/usr/bin/env python3
"""Render REPORT.md for t-2026-11-09-wmtm-live-path-replay-v3 from LOOP_RESULTS.json + fixed offline numbers."""
import json, os
R = "/home/openclaw/research-agent/projects/omegaclaw/wmtm-module/reports/t-2026-11-09-wmtm-live-path-replay-v3"
L = json.load(open(R + "/runs_loop/LOOP_RESULTS.json"))
arms = [("full_A", "A (live rc2, parse 3ec15bd1)"), ("full_B533", "B, parser 533c2274"),
        ("full_Bp3", "B, parse 1f1a7a6f (Nov 5, stand-in)"), ("fullf44_Bf44", "B, fresh parse f44d7b74")]
g = lambda a, k: L.get(a, {}).get(k, "n/a")
rows = ["turns", "errors", "gc_runs", "gc_ok", "gc_canary_ok", "gc_decisions", "escalations", "choices",
        "evictions_total", "focus_headers", "focus_lines", "derived_lines", "derived_with_tv", "derived_with_src",
        "shadow_goals_max", "shadow_proved_max"]
tbl = "| metric | " + " | ".join(n for _, n in arms) + " |\n|---|" + "---|" * len(arms) + "\n"
for r in rows:
    tbl += "| %s | %s |\n" % (r, " | ".join(str(g(a, r)) for a, _ in arms))
txt = open(R + "/REPORT_TEMPLATE.md").read().replace("{{LOOP_TABLE}}", tbl)
for a, _ in arms:
    for r in rows:
        txt = txt.replace("{{%s.%s}}" % (a, r), str(g(a, r)))
open(R + "/REPORT.md", "w").write(txt)
print("rendered", len(txt))
