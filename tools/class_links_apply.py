"""t-2026-11-24-wmtm-p01-class-links: apply the class_links shadow pass to an arm's retained atoms (load_arm ATOMS_OUT).
Usage: class_links_apply.py ATOMS_IN.jsonl ATOMS_OUT.jsonl [PROV_OUT.jsonl]
Flag WMTM_CLASS_LINKS (runtime_config "class_links", default off): off -> ATOMS_OUT is a byte copy of ATOMS_IN.
On -> every note's derived statements are appended after that note's atoms; PROV_OUT gets one row per derived atom
{doc, rule, name, sources, units} (statement names and parse unit ids only). Counts to stdout."""
import json, os, sys, collections, shutil
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from wmtm import runtime_config as rc
from wmtm.class_links import derive

src, dst = sys.argv[1], sys.argv[2]; prov = sys.argv[3] if len(sys.argv) > 3 else None
on = bool(rc.resolve().get("class_links"))
if not on:
    shutil.copyfile(src, dst); print(json.dumps({"class_links": False})); sys.exit(0)
lines = open(src).read().splitlines(keepends=True)
bydoc = collections.OrderedDict()
for l in lines:
    bydoc.setdefault(json.loads(l)["doc"], []).append(l)
c = collections.Counter(); P = open(prov, "w") if prov else None
with open(dst, "w") as o:
    for d, ls in bydoc.items():
        for l in ls: o.write(l)
        for r in derive([json.loads(l)["atom"] for l in ls]):
            o.write(json.dumps({"doc": d, "atom": r["atom"]}) + "\n"); c[r["rule"]] += 1
            if P: P.write(json.dumps({"doc": d, "rule": r["rule"], "name": r["name"], "sources": r["sources"], "units": r["units"]}) + "\n")
print(json.dumps({"class_links": True, **dict(c)}))
