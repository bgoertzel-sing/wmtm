#!/usr/bin/env python3
"""Label-leak and budget checks on the logs (labels joined only here).
1. keyword hits per query (arm A, every turn): the 15-slot budget must have room.
2. graph-only scored candidates in arm B: score by planted label, overall and per (score, n_direct_active_links)
   cell, so a score difference can only come from graph position, not from the label."""
import json, collections as C, statistics as S
L = json.load(open("data/labels.json"))["labels"]
A = [json.loads(l) for l in open("results/A/turns.jsonl")]
B = [json.loads(l) for l in open("results/B/turns.jsonl")]
kw = [sum(1 for s in r["scored"] if s["source"] == "keyword") for r in A]
kwB = [sum(1 for s in r["scored"] if s["source"] == "keyword") for r in B]
print(json.dumps({"keyword_hits_per_query_A": {"min": min(kw), "max": max(kw), "hist": dict(sorted(C.Counter(kw).items()))},
                  "keyword_hits_per_query_B": {"min": min(kwB), "max": max(kwB)}}))
by = C.defaultdict(list)
for r in B:
    for s in r["scored"]:
        if s["source"] == "graph-only":
            l = L.get(s["id"]); by["useful" if l and l["useful"] else "noise"].append(s["score"])
print(json.dumps({k: {"n": len(v), "mean": round(S.mean(v), 4), "median": round(S.median(v), 4)} for k, v in by.items()}))
# text does not carry the label: filler words per item, by label
wl = C.defaultdict(list)
import re
txt = {}
for line in open("data/journal.metta"):
    m = re.match(r'\(EventNote ev-(\S+) "(.*)"\)', line.strip())
    if m: txt[m.group(1)] = m.group(2)
for cid, l in L.items():
    if l["role"] == "linked": wl["useful" if l["useful"] else "noise"].append(len(txt[cid].split()))
print(json.dumps({"linked_text_words": {k: sorted(set(v)) for k, v in wl.items()}}))
