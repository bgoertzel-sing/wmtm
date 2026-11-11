"""rev2: scan a shadow spec for class rules (Implication (Member $x A) (Member $x B)) sharing structure:
>=2 antecedents A_i with A_i->B and A_i->C give a rule-induction goal (Implication (Member $x B) (Member $x C))."""
import json, re, sys, collections
pat = re.compile(r"^\(: (\S+) \(Implication \(Member \$\w+ (\S+?)\) \(Member \$\w+ (\S+?)\)\) ")
for d in sys.argv[1:]:
    s = json.load(open(d + "/spec.json"))
    cons = collections.defaultdict(dict); n = nw = 0
    for a in s["atoms"]:
        t = a if isinstance(a, str) else json.dumps(a)
        m = pat.match(t)
        if not m: continue
        n += 1; lab, A, B = m.groups()
        if lab.startswith("nwdef_"): nw += 1
        cons[A][B] = lab
    pairs = collections.defaultdict(list)
    for A, bs in cons.items():
        for B in bs:
            for C in bs:
                if B < C: pairs[(B, C)].append(A)
    shared = {k: v for k, v in pairs.items() if len(v) >= 2}
    print(json.dumps({"run": d, "class_rules": n, "nwdef": nw, "antecedent_classes": len(cons),
                      "max_consequents_per_antecedent": max((len(v) for v in cons.values()), default=0),
                      "pairs_shared_ge2": {"%s|%s" % k: v for k, v in shared.items()},
                      "pairs_shared_1": len(pairs) - len(shared)}))
