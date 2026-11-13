#!/usr/bin/env python3
"""Compare two turns.jsonl of the same arm (committed run vs a rerun).  The only allowed difference is the id of the
orchestrator's journal write-back notes (ep-note-<real wall-clock UTC>, written by journal.append, which does not use
time.time): they are normalised to ep-note-X.  Usage: check_rerun.py <a.jsonl> <b.jsonl>"""
import json, re, sys
def load(p):
    L = [json.loads(re.sub(r"ep-note-\d{8}T\d{6}Z", "ep-note-X", l)) for l in open(p)]
    for r in L: r.pop("meta", None)
    return L
a, b = load(sys.argv[1]), load(sys.argv[2])
same = json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
wb = sorted({s["id"] for r in a for s in r["scored"] if not s["id"].startswith("syn-")})
pos = sum(1 for r in a for s in r["scored"] if not s["id"].startswith("syn-") and s["score"] > 0)
print(json.dumps({"identical_modulo_writeback_ids": same, "writeback_note_ids": len(wb), "writeback_positive_scores": pos}))
sys.exit(0 if same else 1)
