"""rev3: judge each induced rule per parse. Mechanical W1 (premises from >1 note plus an sk_ fact), the order's exception
(an identical class-level fact in two notes is NOT W1: per-note skolem suffix stripped, facts identical), then the hand
verdict from hand_verdicts.json. Also the trivial/non-trivial split of all B goals (via reader_replay.tsv) and the count line."""
import json, os, re, sys, glob, csv
H = os.path.join(os.path.dirname(__file__), "..", "evidence")
hand = json.load(open(os.path.join(H, "hand_verdicts.json")))
rr = {r["run"]: r for r in csv.DictReader(open(os.path.join(H, "reader_replay.tsv")), delimiter="\t")}
A_C, A_W = 2, 2   # A baseline, F3 v3 (2C/2W), as in the parent reports
print("\t".join(["run", "induced_rule", "stv", "premise_notes", "premise_facts", "mech_W1", "class_level_identical",
                 "verdict", "B_goals", "trivial", "non_trivial", "B_C", "B_W", "count_rule"]))
for d in sorted(glob.glob(os.path.join(H, "runs_rev2", "*"))):
    n = os.path.basename(d); a = json.load(open(d + "/admit.json"))
    ind = [r for r in a["results"] if r["goal"].startswith("(Inheritance")]
    r_ = rr[n]; tot = int(r_["results"]); triv = int(r_["trivial_refused"]); nt = tot - triv
    C = W = 0; rows = []
    for r in ind:
        facts = r.get("facts") or []
        notes = sorted(set(r.get("sources") or []))
        sk = any("sk_" in f for f in facts)
        mech = len(notes) > 1 and sk
        cls = {re.sub(r"__i_ep_note_\w+", "", f) for f in facts}
        per_note = {}
        for f in facts:
            m = re.search(r"__i_ep_note_(\w+)", f)
            per_note.setdefault(m.group(1) if m else "?", set()).add(re.sub(r"__i_ep_note_\w+", "", f))
        ident = len(notes) > 1 and len({frozenset(v) for v in per_note.values()}) == 1
        v = "WRONG" if (mech and not ident) else hand.get(n + "|" + r["goal"], hand.get(r["goal"], "UNJUDGED"))
        C += v == "CORRECT"; W += v == "WRONG"
        rows.append([r["goal"], "%s/%s" % tuple(r["stv"]), ";".join(notes), str(len(facts)), str(mech), str(ident), v])
    cr = "HOLDS" if (C >= A_C and W <= A_W) else "FAILS"
    for row in rows or [["-", "-", "-", "-", "-", "-", "-"]]:
        print("\t".join([n] + row + [str(tot), str(triv), str(nt), str(C), str(W), cr]))
