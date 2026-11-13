#!/usr/bin/env python3
"""t-2026-11-13-wmtm-spread-seed-default: tools/check_rerun.py (sweep/probe copy, unchanged) with one widening: the
orchestrator's journal write-back note id is ep-note-<real wall-clock UTC second>, and journal.append adds a -2, -3 ...
suffix when two notes fall in the same second.  check_rerun.py normalises ep-note-<stamp> but not the suffix, so two
otherwise identical runs can differ when one of them happened to write two notes in one second.  This normalises
ep-note-<stamp>[-n] to ep-note-X.  Usage: check_rerun_wb.py <a.jsonl> <b.jsonl>"""
import json, re, sys
def load(p):
    L = [json.loads(re.sub(r"ep-note-\d{8}T\d{6}Z(-\d+)?", "ep-note-X", l)) for l in open(p)]
    for r in L: r.pop("meta", None)
    return L
a, b = load(sys.argv[1]), load(sys.argv[2])
same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
pos = sum(1 for r in a + b for s in r["scored"] if not s["id"].startswith("syn-") and s["score"] > 0)
print(json.dumps({"identical_modulo_writeback_ids": same, "writeback_positive_scores_both": pos}))
sys.exit(0 if same else 1)
