#!/usr/bin/env python3
"""t-2026-11-14-wmtm-render-master-goals: counts-only recompute through the real admission path.

For each B arm (full_s2, sens_s2): rebuild sources/facts of the stored admit.json results with this repo's
write-side code (master_loader.spec_maps over the stored spec's master_ops + pc_admit.sources_for/proof_facts),
write the admit file to a private tempfile.mkdtemp dir (mode 700, removed at exit), run pc_admit.load_candidates with
the trivial filter at its default (on), live ids = the 20 note ids.  Then C/W/U of the admitted goals (verdicts by goal
id, as judged in t-2026-11-14-wmtm-trivial-filter-coref) and the count rule against A_v3 and the old loader M17 runs
as judged in v2.  Also a known-answer canary (one synthetic renderable, sourced, non-trivial result must be admitted).
Usage: python3 reports/<task>/tools/recompute.py EV  -> EV/tables/counts.json (ids/counts only)."""
import sys, os, json, re, time, tempfile, shutil, atexit, stat
from collections import Counter
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from wmtm import pc_admit as P, master_loader as ML
sys.path.insert(0, os.path.join(REPO, "reports", "t-2026-11-14-wmtm-trivial-filter-coref", "tools"))
import rescore as RS   # m17 / A_v3 baselines as judged (same input layout)

ARMS = ("full_s2", "sens_s2")
_TMP = []


def tmpdir():
    if not _TMP:
        d = tempfile.mkdtemp(prefix="rmg_lc_"); _TMP.append(d); atexit.register(cleanup)
    return _TMP[0]


def cleanup():
    if not _TMP:
        return None
    d = _TMP.pop(); shutil.rmtree(d, ignore_errors=True); return d


def run_lc(name, adm, live):
    sd = os.path.join(tmpdir(), name); os.makedirs(sd, mode=0o700)
    json.dump(adm, open(os.path.join(sd, P.ADMIT_FILE), "w"))
    c, info = P.load_candidates({"shadow_dir": sd, "reasoner_max_admit": 1000, "gate_max_per_fact": 0}, None,
                                now=float(adm.get("spec_ts") or adm["ts"]) + 1, live_ids=live)
    return c or [], info


def compute(EV):
    I = os.path.join(EV, "inputs")
    notes = [l.strip() for l in open(os.path.join(I, "note_ids.txt")) if l.strip()]
    base, _rows = RS.compute(EV)          # baselines (A_v3, M17 as judged); its own temp dir is cleaned by rescore
    vd = {r["goal"]: r["verdict"] for f in ("verdicts_restate.tsv", "verdicts23.tsv", "verdicts_sens_impl.tsv")
          for r in RS.tsv(os.path.join(I, "verdicts", f))}
    aC, aW = [int(x[:-1]) for x in base["inputs"]["A_v3"].split("/")]
    out = {"inputs": {"A_v3": base["inputs"]["A_v3"], "notes": len(notes), "filter_on_default": P.trivial_filter_on({})},
           "m17_as_judged": {r: v["as_judged"] for r, v in base["m17"].items()}, "arms": {}}
    for arm in ARMS:
        A = os.path.join(I, "armB", arm)
        spec = json.load(open(os.path.join(A, "spec.json")))
        adm = json.load(open(os.path.join(A, "admit.json")))
        qs = [q for q in json.loads(open(os.path.join(A, "shadow.jsonl")).readlines()[-1])["queries"]]
        gid = {RS.norm(q["goal"]): "b%02d" % (i + 1) for i, q in enumerate(qs)}
        sp = dict(spec, **ML.spec_maps(spec.get("master_ops"), notes))
        stored_src = run_lc(arm + "_stored", adm, notes)[1]["dropped"]   # stored (empty) sources, new render
        res = [dict(r, sources=P.sources_for(r["goal"], r["proof"], sp), facts=P.proof_facts(r["goal"], r["proof"], sp))
               for r in adm["results"]]
        shapes = Counter("(%s %s %s)" % ((r["goal"].strip("()").split()[0],) + tuple(
            "SK" if a.startswith("sk_") else "S" for a in r["goal"].strip("()").split()[1:])) for r in res)
        unrend = Counter(r["goal"].strip("()").split()[0] for r in res if P.render(r["goal"]) is None)
        nosrc = Counter(r["goal"].strip("()").split()[0] for r in res if not r["sources"])
        c, info = run_lc(arm, dict(adm, results=res), notes)
        ag = [gid.get(RS.norm(x.provenance["goal"]), "?") for x in c]
        refused = [gid.get(RS.norm(e["goal"]), "?") for e in info.get("trivial_refused") or []]
        cv = Counter(vd.get(g, "unjudged") for g in ag)
        C, W, U = cv["correct"], cv["wrong"], cv["unclear"]
        out["arms"][arm] = {
            "results": len(res), "goal_shapes": dict(sorted(shapes.items())), "unrenderable_by_head": dict(unrend),
            "no_source_by_head": dict(nosrc), "dropped_old_code": json.load(open(os.path.join(I, "tfc_counts.json")))["goals"][arm]["load_candidates_raw"]["dropped"],
            # dropped_old_code: as recorded by t-2026-11-14-wmtm-trivial-filter-coref on 2fe5389 (rescore now runs this repo's render)
            "dropped_render_only": stored_src, "dropped": info["dropped"],
            "refused_by_reason": dict(Counter(e["reason"] for e in info.get("trivial_refused") or [])),
            "refused_CWU": dict(Counter(vd.get(g, "unjudged") for g in refused)),
            "admitted": len(c), "admitted_by_head": dict(Counter(x.provenance["goal"].strip("()").split()[0] for x in c)),
            "C": C, "W": W, "U": U, "unjudged": cv["unjudged"],
            "admitted_wrong_ids": sorted(g for g in ag if vd.get(g) == "wrong"),
            "admitted_unclear_ids": sorted(g for g in ag if vd.get(g) == "unclear"),
            "vs_A_v3": RS.rule_verdict(C, W, aC, aW),
            "vs_M17_as_judged": {r: RS.rule_verdict(C, W, v["C"], v["W"]) for r, v in out["m17_as_judged"].items()}}
    # known-answer canary through the same path: one sourced coref-role result (admit), one coref_sym (refuse)
    N = "__ep_note_20990101T000000Z"; nid = "ep-note-20990101T000000Z"
    ops = [("atom", "(: s1_c1_coref%s (Coref sk_m%s sk_a%s) (STV 1.0 0.99))" % (N, N, N)),
           ("atom", "(: s1_v1_agent%s (Agent sk_e%s sk_m%s) (STV 1.0 0.99))" % (N, N, N))]
    csp = ML.spec_maps(ops, [nid])
    pr = ["(: (by coref_agent (conjunction s1_c1_coref%s s1_v1_agent%s)) (Agent sk_e%s sk_a%s) (STV 0.8 0.9))" % (N, N, N, N),
          "(: (by (bi-forward coref_sym) s1_c1_coref%s) (Coref sk_a%s sk_m%s) (STV 1.0 0.98))" % (N, N, N)]
    gl = ["(Agent sk_e%s sk_a%s)" % (N, N), "(Coref sk_a%s sk_m%s)" % (N, N)]
    t = time.time()
    cdoc = {"ts": t, "spec_ts": t, "status": "ok", "canary_ok": True, "results": [
        {"goal": g, "stv": [0.8, 0.9], "proof": p, "sources": P.sources_for(g, p, csp), "facts": P.proof_facts(g, p, csp)}
        for g, p in zip(gl, pr)]}
    cc, ci = run_lc("canary", cdoc, [nid])
    out["canary"] = {"admitted": len(cc), "refused": ci.get("trivial_refused_n"), "dropped": ci["dropped"],
                     "ok": len(cc) == 1 and ci.get("trivial_refused_n") == 1 and cc[0].derived_from == [nid]}
    d = _TMP[0]
    out["tmp"] = {"mode": oct(stat.S_IMODE(os.stat(d).st_mode)), "removed": not os.path.exists(cleanup() or d)}
    return out


if __name__ == "__main__":
    EV = sys.argv[1]
    out = compute(EV)
    os.makedirs(os.path.join(EV, "tables"), exist_ok=True)
    json.dump(out, open(os.path.join(EV, "tables", "counts.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in out.items() if k != "arms"}, sort_keys=True))
    for a, v in out["arms"].items():
        print(a, json.dumps({k: v[k] for k in ("dropped_old_code", "dropped_render_only", "dropped", "refused_by_reason", "admitted", "C", "W", "U",
                                               "unjudged", "vs_A_v3", "vs_M17_as_judged", "unrenderable_by_head", "no_source_by_head")}, sort_keys=True))
