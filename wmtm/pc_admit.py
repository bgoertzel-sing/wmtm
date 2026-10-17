"""Track I/K: admit PeTTaChainer conclusions into WMTM.

Flag ``reasoner`` (flags file / env WMTM_REASONER; API default WMTMConfig.reasoner) = python | pettachainer.
  * python (default, legacy; to be removed): Python PLN derivations are admitted.
  * pettachainer: only PeTTaChainer conclusions are admitted.  Track K: there is no Python reference or fallback.
The cycle never waits on PeTTaChainer.  The detached shadow worker (wmtm/workers/pc_shadow.py: canary, negative
control, per-query timeout and run budget) writes ``<shadow_dir>/admit.json`` with ONLY the results that passed: run
status ok, canary proved and negative control not proved, query proved within its timeout and the run budget,
structural check passed, STV parsed, proof term present.  A later cycle admits from that file if it is fresh
(reasoner_max_age_s) and at least one supporting item is still in the active set.  If the file is missing, stale,
unreadable or from a failed run (worker dead / canary_fail / warm_fail), NOTHING is admitted that cycle
(info["skipped"] says why).  Each admitted item carries provenance: reasoner, goal, STV, proof term, run timestamp.
"""
from __future__ import annotations
import json, os, re, time

ADMIT_FILE = "admit.json"
REASONERS = ("python", "pettachainer")
MIN_STRENGTH, MIN_CONFIDENCE = 0.1, 0.05      # same admission threshold as the Python PLN engine
_RULE = re.compile(r"\b(?:inh_trans|imp_trans|mem_inh)\b")   # proof used a derivation rule
_LABEL = re.compile(r"\b(?:sp|wm)\d+\b")
_GOAL = re.compile(r"^\((Inheritance|Member|Implies|Similarity|Evaluation) (\S+) (\S+)\)$")
_TEXT = {"Inheritance": "{} is a {}", "Member": "{} is a {}", "Implies": "{} implies {}",
         "Similarity": "{} is similar to {}", "Evaluation": "{} has {}"}   # same rendering as pln_bridge


def mode(cfg=None, default="python") -> str:
    m = str((cfg or {}).get("reasoner") or default or "python").strip().lower()
    return m if m in REASONERS else "python"


def render(goal):
    m = _GOAL.match(goal or "")
    return _TEXT[m.group(1)].format(m.group(2), m.group(3)) if m else None


def admissible(q) -> bool:
    """One query record from the shadow worker is admissible only if it proved cleanly within its budget."""
    tv = q.get("stv")
    return bool(q.get("ok") and not q.get("timeout") and not q.get("structural_fail") and not q.get("error")
                and isinstance(tv, list) and len(tv) == 2 and q.get("proof"))


def sources_for(goal, proof, spec):
    """Supporting WMTM item ids: from the fact labels in the proof term, else items whose facts touch the goal."""
    src = spec.get("atom_src") or {}
    ids = []
    for lab in _LABEL.findall(proof or ""):
        iid = src.get(lab)
        if iid and iid not in ids:
            ids.append(iid)
    if not ids:
        m = _GOAL.match(goal or "")
        if m:
            for (_h, x, y, iid) in spec.get("fact_src") or []:
                if (x == m.group(2) or y == m.group(3)) and iid not in ids:
                    ids.append(iid)
    return ids


def write_admit_file(out_dir, rec, spec, now=None):
    """Worker side: write <out_dir>/admit.json (atomic).  Failed runs are written too, so readers admit nothing."""
    from . import runtime_config as rc
    can, neg = rec.get("canary") or {}, rec.get("neg") or {}
    canary_ok = bool(can.get("ok") and not neg.get("ok") and not neg.get("timeout"))
    results = []
    if rec.get("status") == "ok" and canary_ok:
        for q in rec.get("queries", []):
            if admissible(q):
                lf = spec.get("label_fact") or {}
                results.append({"goal": q["goal"], "stv": q["stv"], "proof": q["proof"], "s": q.get("s"),
                                "sources": sources_for(q["goal"], q["proof"], spec),
                                "facts": sorted({lf.get(x, x) for x in _LABEL.findall(q["proof"] or "")})})
    doc = {"ts": now or time.time(), "spec_ts": spec.get("ts"), "cycle": spec.get("cycle"), "status": rec.get("status"),
           "canary_ok": canary_ok, "timeout_s": rec.get("timeout_s"), "budget_s": rec.get("budget_s"),
           "skipped_budget": rec.get("skipped_budget"), "timeouts": rec.get("timeouts"),
           "asked": len(rec.get("queries", [])), "results": results,
           "gate": {k: (spec.get("gate") or {}).get(k) for k in ("on", "rejected", "discounted")}}
    rc.write_json_atomic(os.path.join(out_dir, ADMIT_FILE), doc)
    return doc


def load_candidates(cfg, store, now=None):
    """Cycle side.  -> (candidates, info).  candidates is None when the cycle must fall back to Python."""
    from .inference import InferenceCandidate
    path = os.path.join(cfg.get("shadow_dir") or "", ADMIT_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except FileNotFoundError:
        return None, {"skipped": "no_admit_file"}
    except (OSError, ValueError):
        return None, {"skipped": "bad_admit_file"}
    if not isinstance(doc, dict) or not isinstance(doc.get("results"), list):
        return None, {"skipped": "bad_admit_file"}
    try:
        age = (now or time.time()) - float(doc.get("spec_ts") or doc.get("ts") or 0)
    except (TypeError, ValueError):
        return None, {"skipped": "bad_admit_file"}
    info = {"age_s": round(age, 1), "run_cycle": doc.get("cycle"), "status": doc.get("status")}
    if age > float(cfg.get("reasoner_max_age_s") or 900):
        return None, dict(info, skipped="stale")
    if doc.get("status") != "ok" or not doc.get("canary_ok"):
        return None, dict(info, skipped="run_" + str(doc.get("status") or "unknown"))
    live = {it.id for it in store.get_active_set()}
    cands, cand_facts, drop = [], [], {"asserted": 0, "no_live_source": 0, "below_threshold": 0, "bad": 0}
    for r in doc["results"]:
        try:
            g = r["goal"]; s, c = float(r["stv"][0]), float(r["stv"][1]); text = render(g)
        except (KeyError, TypeError, ValueError, IndexError):
            drop["bad"] += 1; continue
        if not text or not r.get("proof"):
            drop["bad"] += 1; continue
        if not _RULE.search(str(r.get("proof"))):
            # proved straight from asserted facts (or their revision): already in WMTM, not a new conclusion
            drop["asserted"] += 1; continue
        s, c = min(1.0, max(0.0, s)), min(0.99, max(0.0, c))
        if s < MIN_STRENGTH or c < MIN_CONFIDENCE:
            drop["below_threshold"] += 1; continue
        srcs = [x for x in r.get("sources") or [] if x in live]
        if not srcs:
            drop["no_live_source"] += 1; continue
        cand_facts.append(list(r.get("facts") or _LABEL.findall(str(r.get("proof")))))
        cands.append(InferenceCandidate(
            content=text, confidence=c, derived_from=srcs, inference_type="pc_deduction", initial_sti=s * c,
            provenance={"reasoner": "pettachainer", "goal": g, "stv": [s, c], "proof": str(r["proof"])[:2000],
                        "run_ts": doc.get("spec_ts"), "query_s": r.get("s")}))
    # Track J: cap admitted conclusions per KB fact per cycle (best first)
    from . import parse_gate as _pg
    gst = _pg.settings(cfg)
    order = sorted(range(len(cands)), key=lambda j: -cands[j].initial_sti)
    pairs = [(cands[j], cand_facts[j]) for j in order]
    cands, n_cap, over = _pg.cap_per_fact(pairs, gst)
    drop["per_fact_cap"] = n_cap
    cap = int(cfg.get("reasoner_max_admit") or 5)
    info.update(results=len(doc["results"]), candidates=min(len(cands), cap), dropped=drop, cap_hit=over,
                gate=doc.get("gate"))
    return cands[:cap], info
