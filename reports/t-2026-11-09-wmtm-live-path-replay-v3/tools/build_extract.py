#!/usr/bin/env python3
"""Build extract.json rows (premise id -> source note + fact, gate rejects, nw symbol -> notes) from kept pc_shadow specs.
Usage: build_extract.py <out.json> <key>=<run dir> ...   (run dir holds spec.json + shadow.jsonl). No note text is written."""
import json, sys, re, hashlib, os
out = {}
for kv in sys.argv[2:]:
    k, d = kv.split("=", 1)
    s = json.load(open(os.path.join(d, "spec.json")))
    src = s["atom_src"] if isinstance(s["atom_src"], dict) else dict(s["atom_src"])
    prem = {}
    for a in s["atoms"]:
        m = re.match(r"\(: (\w+) (\(.*\)) \(STV", a)
        if m and m.group(1) in src:
            prem[m.group(1)] = {"src": src[m.group(1)], "fact": m.group(2)}
    rej = sorted({x["fact"] for x in (s.get("gate") or {}).get("decisions", []) if x.get("action") == "reject"})
    nw = {}
    for a in s["atoms"]:
        for sym in set(re.findall(r"\b(\w+?__nw_[0-9a-f]+)\b", a)):
            m = re.match(r"\(: (\w+) ", a)
            if m and m.group(1) in src: nw.setdefault(sym, set()).add(src[m.group(1)])
    sh = os.path.join(d, "shadow.jsonl")
    out[k] = {"shadow": sh, "premises": prem, "gate_rejected": rej, "nw_symbol_notes": {x: sorted(v) for x, v in sorted(nw.items())},
              "record_sha256": hashlib.sha256(open(sh, "rb").read()).hexdigest(),
              "spec_atoms_sha256": hashlib.sha256("\n".join(s["atoms"]).encode()).hexdigest()}
json.dump(out, open(sys.argv[1], "w"), indent=1, sort_keys=True)
for k, v in out.items(): print(k, len(v["premises"]), "premises", len(v["gate_rejected"]), "rejected", len(v["nw_symbol_notes"]), "nw")
