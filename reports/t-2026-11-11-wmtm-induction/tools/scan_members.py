"""rev2: per spec, class pairs by shared Member instances (the instance-fold induction shape).
Prints max shared, and every pair with >=2 shared (alias X vs X__nw_* flagged)."""
import json, re, sys, collections
pat = re.compile(r"^\(Member (\S+) (\S+)\)$")
for d in sys.argv[1:]:
    s = json.load(open(d + "/spec.json"))
    mem = collections.defaultdict(set)
    for f in s.get("fact_src") or []:
        if f[0] == "Member": mem[f[2]].add(f[1])
    cls = sorted(mem); pairs = []
    for i, a in enumerate(cls):
        for b in cls[i + 1:]:
            n = len(mem[a] & mem[b])
            if n >= 2:
                alias = a.split("__nw_")[0] == b.split("__nw_")[0]
                pairs.append({"a": a, "b": b, "shared": n, "alias": alias})
    mx = max((len(mem[a] & mem[b]) for i, a in enumerate(cls) for b in cls[i + 1:]), default=0)
    print(json.dumps({"run": d, "member_classes": len(cls), "max_shared": mx, "pairs_ge2": pairs}))
