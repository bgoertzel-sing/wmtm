#!/usr/bin/env python3
"""Recover petta-stage rejects through SemParseAdapter.recover_rejected (-> _admit, the live load step), real
PeTTaChainer loader.  No parse calls (llm stub raises).  Usage: recover.py <run name> <cache dir> <out dir>.
Writes <out>/recovered.jsonl (item_id, accepted, refused) and <out>/counts.json (ids/counts/hashes only)."""
import json, os, sys, hashlib, collections
R = "/home/openclaw/research-agent/projects/omegaclaw/wmtm-module"; sys.path.insert(0, R)
PETTA = "/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b"; PC = "/home/openclaw/scratch/ppv/pc"
sys.path.insert(0, os.path.join(PETTA, "python")); sys.path.insert(0, PC); os.environ["PETTA_PATH"] = PETTA
from pettachainer.pettachainer import PeTTaChainer
from wmtm.semparse_adapter import SemParseAdapter
name, cdir, out = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
rl = os.path.join(out, "rerejects.jsonl")
if os.path.exists(rl): os.remove(rl)          # fresh log per run (an earlier run appended to the same file)
def nollm(s, u): raise RuntimeError("parse call refused (narrow-preload eval)")
L = PeTTaChainer()
for s in ["(: cf (Member grace pilot) (STV 1.0 0.99))", "(: cg (Inheritance pilot person) (STV 1.0 0.99))"]:
    L.add_atom(s)
canary = "Member grace person" in str(L.query("(: $prf (Member grace person) $tv)", steps=30, timeout_sec=0)) and \
         "Member grace robot" not in str(L.query("(: $prf (Member grace robot) $tv)", steps=30, timeout_sec=0))
ad = SemParseAdapter(nollm, loader=L, system="X", mode="legacy", reject_log=os.path.join(out, "rerejects.jsonl"))
by = collections.OrderedDict(); n_in = 0; reasons = collections.Counter()
for l in open(os.path.join(cdir, "rejects.jsonl")):
    d = json.loads(l)
    if d.get("stage") != "petta": continue
    n_in += 1; reasons["member_class" if "member_class" in d["reason"] else ("inheritance_class" if "inheritance_class" in d["reason"] else "other")] += 1
    by.setdefault(d["item_id"], []).append(d["atom"])
rows = []; acc_stmt = acc_nwdef = 0
for iid, atoms in by.items():
    r = ad.recover_rejected(iid, atoms)
    st = [a for a in r.accepted if not a.startswith("(: nwdef_")]
    acc_stmt += len(st); acc_nwdef += len(r.accepted) - len(st)
    rows.append({"item_id": iid, "in": len(atoms), "accepted": r.accepted, "refused": [x["atom"] if isinstance(x, dict) else x for x in r.rejected]})
with open(os.path.join(out, "recovered.jsonl"), "w") as fh:
    for x in rows: fh.write(json.dumps(x) + "\n")
ref = collections.Counter()
if os.path.exists(os.path.join(out, "rerejects.jsonl")):
    for l in open(os.path.join(out, "rerejects.jsonl")):
        d = json.loads(l); ref[(d["stage"], d["reason"][:90])] += 1
c = {"run": name, "canary": canary, "petta_rejects_in": n_in, "in_by_reason": dict(reasons), "items": len(by),
     "statements_recovered": acc_stmt, "nwdef_loaded": acc_nwdef, "still_refused": sum(ref.values()),
     "refused_reasons": {"%s|%s" % k: v for k, v in ref.items()},
     "rejects_sha256": hashlib.sha256(open(os.path.join(cdir, "rejects.jsonl"), "rb").read()).hexdigest(),
     "cache_sha256": hashlib.sha256(open(os.path.join(cdir, "cache.jsonl"), "rb").read()).hexdigest()}
json.dump(c, open(os.path.join(out, "counts.json"), "w"), indent=1, sort_keys=True); print(json.dumps(c))
