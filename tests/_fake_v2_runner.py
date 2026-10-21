"""Test double for wmtm/goals/v2_runner.py (synthetic tests only; the real runtime is exercised by
tests/test_goals_v2.py::test_real_* when WMTM_TEST_GC2_PYTHON points at a GoalChainer v2 interpreter).

Speaks the same job/result protocol and emulates the parts of a v2 review that WMTM maps: deontic admissibility
from the generated norms (live_change/push unless approved, git_memory, write; every autonomous effect on an
automated turn), need values = urgency(level) - urgency(level + change) with drive 1 on the band [target, 1],
hold when nothing is worth more than 0, blocked when nothing is admissible, escalate on an exact tie, otherwise
propose the best; withdrawal groups between reviews like the real runner.  It parses only the lines
wmtm/goals/v2.py generates."""
import json
import re
import sys

AUTO = ("message", "write", "live_change", "git_memory", "push")


def review(s, p, keep, i):
    head = s["header"]
    band = {m.group(1): float(m.group(2)) for m in re.finditer(r"\(gc-need (\w+) \w+ \(scale 0 1\) \(band ([0-9.eE+-]+) 1\)", head)}
    prio = {}
    for m in re.finditer(r"\(gc-goal (\w+) wmtm individual ([0-9.eE+-]+)", head):
        prio[m.group(1)] = float(m.group(2))
    gneed = {m.group(2): m.group(1) for m in re.finditer(r"\(gc-need (\w+) (\w+)", head)}
    lvl = {o["need"]: o["level"] for o in s.get("observations") or ()}
    auto = any(r["signal"] == "automated_turn" and r["state"] == "detected" for r in p["readings"])
    cands, vals, forb, support = [], {}, [], []
    for a in keep:
        b = s["blocks"][a]
        eff = set(re.findall(r"\(given \(wmtm-effect %s (\w+)\)\)" % a, b))
        appr = "(given (approved %s))" % a in b
        rules = [r for r, e in (("no_git_memory", "git_memory"), ("read_only", "write")) if e in eff]
        rules += [r for r, e in (("no_live_change", "live_change"), ("no_push", "push")) if e in eff and not appr]
        if auto:
            rules += ["no_autonomous_" + e for e in AUTO if e in eff]
        if rules:
            forb.append(a)
            support.append({"kind": "rule", "literal": "(lit pos F none do (%s))" % a, "label": rules[0],
                            "premises": [{"kind": "fact", "literal": "(lit pos none none wmtm-effect (%s x))" % a, "label": "f"}]})
        else:
            support.append({"kind": "rule", "literal": "(lit pos P none do (%s))" % a, "label": "permit",
                            "premises": [{"kind": "rule", "literal": "(lit pos none none candidate (%s))" % a, "label": "cand_" + a,
                                          "premises": []}]})
        cands.append({"action": a, "deontic": "forbidden" if rules else "permitted"})
        ch = {m.group(1): float(m.group(2)) for m in re.finditer(r"\(gc-need-expectation %s (\w+) ([0-9.eE+-]+)" % a, b)}
        v = 0.0
        for n, c in ch.items():
            t = band.get(n, 0.8); l0 = lvl.get(n, 1.0)
            urg = lambda x: max(0.0, t - x) / t if t > 0 else 0.0
            v += prio.get([g for g, nn in gneed.items() if nn == n][0], 1.0) * (urg(l0) - urg(min(1.0, l0 + c)))
        vals[a] = (v, ch)
    ok = [a for a in keep if a not in forb]
    rid = "%s-%s-%d" % (s["label"], p["label"], i)
    rv = {"review_id": rid, "fingerprint": "sha256:fake-" + rid, "engine": {"inferences": 1}, "candidates": cands,
          "deontic_support": support, "steps": [{"name": "deontic admissibility", "survivors": ok,
                                                 "eliminated": [{"action": a, "reason": "forbidden by the theory"} for a in forb]}],
          "display_order": [], "proposal": None, "hold": None, "escalation": None, "blockers": []}
    if not ok:
        rv.update(disposition="blocked", blockers=[{"action": a, "reason": "forbidden by the theory"} for a in forb])
        return rv
    pos = sorted((a for a in ok if vals[a][0] > 0), key=lambda a: -vals[a][0])
    if not pos:
        rv.update(disposition="hold", hold={"satisfied": [n for n in lvl if lvl[n] >= band.get(n, 0.8)],
                                            "unserved": [n for n in lvl if lvl[n] < band.get(n, 0.8)]})
        return rv
    if len(pos) > 1 and vals[pos[0]][0] == vals[pos[1]][0]:
        rv.update(disposition="escalate", escalation={"reasons": ["tie"], "contested": pos[:2]})
        return rv
    a = pos[0]; v, ch = vals[a]
    n = max(ch, key=lambda k: ch[k])
    rv["display_order"] = [{"action": x, "projection": vals[x][0]} for x in pos]
    rv.update(disposition="propose", proposal={
        "action": a, "deontic": "permitted", "decided_at": "Pareto elimination", "licensed_authority_ceiling": "advisory",
        "authorization": "unresolved", "carrying_path": {"value": {"low": v, "high": v}},
        "predicted_need_changes": [{"need": n, "observed_level": lvl.get(n), "expected_change": ch[n],
                                    "predicted_level": {"low": lvl.get(n, 1) + ch[n], "high": lvl.get(n, 1) + ch[n]}}]})
    return rv


def main():
    job = json.loads(sys.stdin.read())
    out = {"protocol": "wmtm-gc2-result-v1", "series": [], "versions": {"fake": True}, "s": 0.0}
    for s in job["series"]:
        so = {"label": s["label"], "passes": [], "s": 0.0}
        for p in s["passes"]:
            removed, revs = set(), []
            for i in range(s["max_reviews"]):
                keep = [a for a in s["order"] if a not in removed]
                if not keep:
                    break
                r = review(s, p, keep, i)
                revs.append(r)
                if r["disposition"] != "propose":
                    break
                a = r["proposal"]["action"]
                removed |= {a} | set(s["remove"].get(a, ()))
            so["passes"].append({"label": p["label"], "reviews": revs})
        out["series"].append(so)
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
