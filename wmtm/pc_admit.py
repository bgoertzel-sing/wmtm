"""Track I/K: admit PeTTaChainer conclusions into WMTM.

Flag ``reasoner`` (flags file / env WMTM_REASONER; API default WMTMConfig.reasoner) = pettachainer (default) | off.
  * pettachainer: only PeTTaChainer conclusions are admitted.  Track L: the Python PLN engine is removed.
  * off (also any unknown/invalid value): the reasoner is off and nothing is admitted.
The cycle never waits on PeTTaChainer.  The detached shadow worker (wmtm/workers/pc_shadow.py: canary, negative
control, per-query timeout and run budget) writes ``<shadow_dir>/admit.json`` with ONLY the results that passed: run
status ok, canary proved and negative control not proved, query proved within its timeout and the run budget,
structural check passed, STV parsed, proof term present.  A later cycle admits from that file if it is fresh
(reasoner_max_age_s) and at least one supporting item is still in the active set.  If the file is missing, stale,
unreadable or from a failed run (worker dead / canary_fail / warm_fail), NOTHING is admitted that cycle
(info["skipped"] says why).  Each admitted item carries provenance: reasoner, goal, STV, proof term, run timestamp.

rc2: admission no longer depends on the full cycle running.  It happens on every user turn (in cycle(), or on its
own when cycle() is skipped for the cycle budget) and on automated turns (admit_on_snapshot, flag
``reasoner_admit_on_automated``).  Each admit.json run (run_id) is consumed at most once: the id is recorded in the
state (``pc_admit.consumed_run``) as soon as the run yielded gated candidates, and later turns skip it
("already_consumed").  Every attempt is logged (numbers only) to ``<shadow_dir>/admit_log.jsonl`` (size-capped).
"""
from __future__ import annotations
import json, os, re, time

ADMIT_FILE = "admit.json"
ADMIT_LOG = "admit_log.jsonl"
REASONERS = ("pettachainer", "off")
# F1 item 3 (t-2026-11-06-wmtm-f1-memory): no confidence cutoff.  A low-confidence engine answer is still an answer
# (Roman), so nothing is dropped for c alone; reasoner_max_admit (best first) bounds how many enter per run.
_RULE = re.compile(r"\b(?:inh_trans|imp_trans|mem_inh)\b")   # legacy wmtm rule names (pre F3 v2 shadow docs)
# F3 v3 (review 1 finding 4): revision-only heads (merge/revision, factored-revision, and the engine prior it carries)
# over fact labels are not derivations; a factored revision of two asserted facts must not be admitted.
_ASSERTED_TOKENS = re.compile(r"\(prior\s*\(STV\s+[\d.eE+-]+\s+[\d.eE+-]+\)\)|\b(?:sp|wm)\d+\b|factored-revision|merge/revision|[():\s]")


def is_derivation(proof) -> bool:
    """F3 v2: a proof is a derivation unless its proof term is only fact labels and their revision.
    Native engine steps ((by ..), conditioned, conditional-implication, specializes, ...) count; so do legacy rules."""
    p = str(proof or "").strip()
    if _RULE.search(p) or _PARSER_RULE.search(p):
        return True
    m = re.match(r"^\(:\s*(.*?)\s*\((?:Inheritance|Member|Implies|Similarity|Evaluation)\s+\S+\s+\S+\)\s*\(STV[^()]*\)\)\s*$", p, re.S)
    term = m.group(1) if m else p
    return bool(_ASSERTED_TOKENS.sub("", term))
_PARSER_RULE = re.compile(r"\(by i_\w+?__\w*implication\w*\b")   # P4 rev5: direct step through a parser Implication rule (<note>__<id>) is a derivation too
_LABEL = re.compile(r"\b(?:sp|wm)\d+\b")
_GOAL = re.compile(r"^\((Inheritance|Member|Implies|Similarity|Evaluation) (\S+) (\S+)\)$")
_TEXT = {"Inheritance": "{} is a {}", "Member": "{} is a {}", "Implies": "{} implies {}",
         "Similarity": "{} is similar to {}", "Evaluation": "{} has {}"}   # same rendering as the removed pln_bridge (Track L)


def mode(cfg=None, default="pettachainer") -> str:
    """Effective reasoner mode. Unknown/invalid values (incl. the removed "python") mean "off": nothing admitted."""
    m = str((cfg or {}).get("reasoner") or default or "pettachainer").strip().lower()
    return m if m in REASONERS else "off"


def min_strength(cfg) -> float:
    """Track O: admit as a positive statement only when strength >= this (default 0.5)."""
    try:
        v = float((cfg or {}).get("reasoner_min_strength", 0.5))
    except (TypeError, ValueError):
        return 0.5
    return v if 0.0 <= v <= 1.0 else 0.5


def negation_mode(cfg) -> str:
    """Track O: conclusions below reasoner_min_strength are "skip"ped (default) or admitted as "unlikely: ..."."""
    m = str((cfg or {}).get("reasoner_negation") or "skip").strip().lower()
    return m if m in ("skip", "unlikely") else "skip"


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
    if not ids and "implication-instance-fold" in (proof or ""):
        # t-2026-11-11 rev2: a fold proof carries no fact labels; its premises are the goal's own chain
        # (the shared Member facts listed by induction_goal_pool), so map those to their WMTM items.
        chain = set(((spec.get("goal_meta") or {}).get(goal) or {}).get("chain") or [])
        for (h, x, y, iid) in spec.get("fact_src") or []:
            if "(%s %s %s)" % (h, x, y) in chain and iid not in ids:
                ids.append(iid)
    if not ids:
        m = _GOAL.match(goal or "")
        if m:
            for (_h, x, y, iid) in spec.get("fact_src") or []:
                if (x == m.group(2) or y == m.group(3)) and iid not in ids:
                    ids.append(iid)
    return ids


def proof_facts(goal, proof, spec):
    """Facts a proof rests on: its fact labels, else (fold proofs) the goal's chain facts."""
    lf = spec.get("label_fact") or {}
    out = sorted({lf.get(x, x) for x in _LABEL.findall(proof or "")})
    if not out and "implication-instance-fold" in (proof or ""):
        out = sorted(((spec.get("goal_meta") or {}).get(goal) or {}).get("chain") or [])
    return out


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
                                "facts": proof_facts(q["goal"], q["proof"], spec),
                                "rules": proof_rules(q["proof"], spec.get("atoms"))})
    doc = {"ts": now or time.time(), "spec_ts": spec.get("ts"), "cycle": spec.get("cycle"), "status": rec.get("status"),
           "canary_ok": canary_ok, "timeout_s": rec.get("timeout_s"), "budget_s": rec.get("budget_s"),
           "skipped_budget": rec.get("skipped_budget"), "timeouts": rec.get("timeouts"),
           "asked": len(rec.get("queries", [])), "results": results,
           "gate": {k: (spec.get("gate") or {}).get(k) for k in ("on", "rejected", "discounted")}}
    rc.write_json_atomic(os.path.join(out_dir, ADMIT_FILE), doc)
    return doc


def run_id(doc):
    """Identity of one worker run (its spec time and write time)."""
    return "%s/%s" % (doc.get("spec_ts"), doc.get("ts"))


def initial_sti(text, context_rel, cfg):
    """F1 §4: a conclusion's starting STI comes from its relevance to the current request, not from s*c.
    base + span * rel, rel in [0, 1] = IDF overlap of the text with the request terms / smax (context.request_relevance
    scale).  base (reasoner_initial_sti, default 1.0) is well above ForgettingPolicy.derived_sti_threshold (0.10) after
    one tick, so a low-confidence conclusion is never evicted in the cycle that admits it."""
    base = float(cfg.get("reasoner_initial_sti") or 1.0)
    span = float(cfg.get("reasoner_initial_sti_rel") or 4.0)
    rel = 0.0
    terms = (context_rel or {}).get("terms") or {}
    smax = float((context_rel or {}).get("smax") or 0.0)
    if terms and smax > 0:
        try:
            from .context import lexical_relevance
            rel = min(1.0, lexical_relevance(text, terms) / smax)
        except Exception:
            rel = 0.0
    return round(base + span * rel, 4)


def load_candidates(cfg, store, now=None, consumed=None, live_ids=None, known=None, context_rel=None):
    """Cycle side.  -> (candidates, info).  candidates is None when nothing may be admitted (info["skipped"]).

    consumed: run id already admitted from (rc2) -> skipped "already_consumed".
    live_ids: ids of the active items (default: from store); the automated fast path passes the snapshot's ids.
    known: optional predicate(text) -> True if the conclusion is already in WMTM or forgotten (rc2).  Such results are
    dropped BEFORE the caps (drop["known"]), so a later run that re-proves admitted conclusions still admits its new
    ones instead of filling the cap with duplicates."""
    from .candidate import InferenceCandidate
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
    info = {"run": run_id(doc), "age_s": round(age, 1), "run_cycle": doc.get("cycle"), "status": doc.get("status")}
    if consumed and info["run"] == consumed:
        return None, dict(info, skipped="already_consumed")
    if age > float(cfg.get("reasoner_max_age_s") or 900):
        return None, dict(info, skipped="stale")
    if doc.get("status") != "ok" or not doc.get("canary_ok"):
        return None, dict(info, skipped="run_" + str(doc.get("status") or "unknown"))
    live = set(live_ids) if live_ids is not None else {it.id for it in store.get_active_set()}
    cands, cand_facts, drop = [], [], {"asserted": 0, "no_live_source": 0, "bad": 0, "known": 0,
                                       "negative": 0}
    n_triv = 0      # GAP-5: dropped["trivial"] appears only when > 0, so existing dropped records keep their shape
    triv_on, triv_log = trivial_filter_on(cfg), []
    min_s, neg_mode = min_strength(cfg), negation_mode(cfg)
    for r in doc["results"]:
        try:
            g = r["goal"]; s, c = float(r["stv"][0]), float(r["stv"][1]); text = render(g)
        except (KeyError, TypeError, ValueError, IndexError):
            drop["bad"] += 1; continue
        if not text or not r.get("proof"):
            drop["bad"] += 1; continue
        if not is_derivation(r.get("proof")):
            # proved straight from asserted facts (or their revision): already in WMTM, not a new conclusion
            drop["asserted"] += 1; continue
        if triv_on:   # GAP-5 TRIVIAL_RULE: proof-shape check, before the caps so a restatement takes no slot
            why = trivial_reason(r.get("proof"), r.get("rules"))
            if why:
                n_triv += 1; drop["trivial"] = n_triv
                triv_log.append({"rule": TRIVIAL_RULE, "reason": why, "goal": g,
                                 "steps": sorted(set(re.findall(r"\(by\s+(\S+)", str(r.get("proof")))))})
                continue
        s, c = min(1.0, max(0.0, s)), min(0.99, max(0.0, c))
        # Track O: strength is a probability.  s < reasoner_min_strength means "probably not", never a weak yes.
        neg = s < min_s
        if neg:
            if neg_mode != "unlikely" or (1.0 - s) < min_s:
                drop["negative"] += 1; continue
            text = "unlikely: " + text
        srcs = [x for x in r.get("sources") or [] if x in live]
        if not srcs:
            drop["no_live_source"] += 1; continue
        if known is not None and known(text, srcs):
            drop["known"] += 1; continue
        cand_facts.append(list(r.get("facts") or _LABEL.findall(str(r.get("proof")))))
        cands.append(InferenceCandidate(
            content=text, confidence=c, derived_from=srcs, inference_type="pc_deduction",
            initial_sti=initial_sti(text, context_rel, cfg),
            provenance={"reasoner": "pettachainer", "goal": g, "stv": [s, c], "polarity": "negative" if neg else "positive", "proof": str(r["proof"])[:2000], "rules": r.get("rules"),
                        "run_ts": doc.get("spec_ts"), "query_s": r.get("s")}))
    # Track J: cap admitted conclusions per KB fact per cycle (best first)
    from . import parse_gate as _pg
    gst = _pg.settings(cfg)
    # F1 §4: best first = most relevant, then the engine's answer weight s*c (was s*c alone)
    def _w(cd):
        s_, c_ = cd.provenance["stv"]
        return ((1.0 - s_) if cd.provenance.get("polarity") == "negative" else s_) * c_
    order = sorted(range(len(cands)), key=lambda j: (-cands[j].initial_sti, -_w(cands[j])))
    pairs = [(cands[j], cand_facts[j]) for j in order]
    cands, n_cap, over = _pg.cap_per_fact(pairs, gst)
    drop["per_fact_cap"] = n_cap
    cap = int(cfg.get("reasoner_max_admit") or 5)
    info.update(results=len(doc["results"]), candidates=min(len(cands), cap), dropped=drop, cap_hit=over,
                gate=doc.get("gate"), trivial_filter=triv_on, trivial_refused=triv_log,
                trivial_refused_n=n_triv)
    return cands[:cap], info


def admit_on_snapshot(snapshot, cfg, now=None):
    """Automated fast path (rc2): admit from admit.json straight into a persisted state snapshot (dict, in place).

    The common case (no file / stale / already consumed / no live source) reads admit.json only.  The engine
    modules (orchestrator: store, utility, forgetting log; no PLN) are imported only when a new run has gated
    candidates, i.e. at most once per worker run.  Same guards and caps as the cycle.  -> info (info["admitted"])."""
    st = snapshot.get("pc_admit") or {}
    items = (snapshot.get("store") or {}).get("items") or {}
    present = {str(v.get("content", "")).lower().strip() for v in items.values()}
    recs = (snapshot.get("forgetting_log") or {}).get("records") or []
    forgotten = set()
    if recs:   # F1 §4: derivation keys (conclusion + sorted sources), old records computed from content_hash
        from .forgetting_log import deriv_hash
        forgotten = {deriv_hash("", r.get("derived_from") or [], r.get("content_hash")) for r in recs}

    def known(text, srcs=()):
        t = text.lower().strip()
        if t in present:
            return True
        if forgotten:
            from .forgetting_log import deriv_hash
            return deriv_hash(t, list(srcs)) in forgotten     # = ForgettingLog.is_forgotten(text, srcs)
        return False
    cands, info = load_candidates(cfg, None, now, consumed=st.get("consumed_run"), live_ids=items.keys(), known=known,
                                  context_rel=snapshot.get("context_rel"))
    if not cands:
        if cands is not None:
            info["skipped"] = "no_candidates"
        info["admitted"] = 0
        return info
    from .orchestrator import WMTMOrchestrator
    from .store import WMTMStore
    orch = WMTMOrchestrator(WMTMStore(), use_goalchainer=False)
    orch.restore_state(snapshot)
    orch.trivial_filter = trivial_filter_on(cfg)   # GAP-5: same flag as load_candidates (flag off = guard off too)
    admitted, info = orch.admit_pc_candidates(cands, info)
    new = orch.snapshot_state()
    for k in ("store", "utility", "forgetting_log", "pc_admit"):
        if k in new:
            snapshot[k] = new[k]
    return info


def log_admission(cfg, path, info, timing=None, now=None):
    """Append one record (numbers / ids only, no content) to <shadow_dir>/admit_log.jsonl.  Never raises."""
    try:
        d = cfg.get("shadow_dir")
        if not d:
            return None
        info = info or {}
        rec = {"ts": round(now or time.time(), 3), "path": path, "run": info.get("run"),
               "age_s": info.get("age_s"), "status": info.get("status"), "results": info.get("results"),
               "candidates": info.get("candidates"), "admitted": info.get("admitted"),
               "skipped": info.get("skipped"), "dropped": info.get("dropped")}
        if info.get("trivial_refused"):   # GAP-5: one entry per refusal (rule, reason, goal symbols, step labels)
            rec["trivial_refused"] = info["trivial_refused"]
        for k in ("admit_error", "error"):
            if info.get(k):
                rec[k] = info[k]
        if timing:
            rec["timing"] = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in timing.items()}
        os.makedirs(d, exist_ok=True)
        from . import runtime_config as rc
        rc.append_jsonl(os.path.join(d, ADMIT_LOG), rec, max_bytes=int(cfg.get("admit_log_max_bytes") or 0))
        return rec
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------------------------
# GAP-5 (S part), t-2026-11-10-wmtm-trivial-filter: named admission rule TRIVIAL_RULE, flag admit_trivial_filter
# (default on).  It looks at the PROOF TERM and the rule atoms the proof cites, never at symbol names or text.
# A derived conclusion is trivial (refused) when every inference step on a weighted path of its proof is one of
#   nwdef_head_noun : a defining rule  (: L (Implication (Member $x S) (Member $x B)) (CTV ..))  -- "an X_Y is a Y"
#   narrow_echo     : a rule  (Implication (Member $x S) (Member $x C))  whose premise class S is the named form of
#                     (Narrow B (Member C)) or (Narrow B (Mod C)), B taken from S's defining rule; i.e. the rule only
#                     restates the restriction already inside its own premise ("a staged commit is staged")
# and every such step is applied DIRECTLY to asserted fact labels (sp<n>/wm<n>), possibly revised together.
# Weighted path: a factored-revision branch whose prior has confidence 0 (e.g. "(inverted L with cpu (prior (STV
# 0.5 0.0)))") contributes nothing to the conclusion and is skipped.  A weighted "(inverted L ...)" branch is
# counted as one more step through rule L, classified like a (by L ..) step (so an inverted nwdef over an asserted
# fact is still head-noun only).  Anything else (another rule, a step over a derived premise = two-step chain, a
# weighted branch of any other head such as "reported", an unknown head, missing rule atoms) means NOT trivial: the
# filter fails open and admits.  "Defining rule" means the EXACT narrow_defining_rules shape (_is_nwdef_shape), not
# any CTV Member implication: a parser class rule such as (pilot -> person) is never treated as nwdef.
TRIVIAL_RULE = "trivial_restatement"
_STEP_HEADS = ("by",)


def _sx(text):
    from .semparse_adapter import split_toplevel
    for _src, node, err in split_toplevel(str(text or "")):
        return None if err else node
    return None


def _member_imp(atom):
    """-> (label, S, C, is_defining) for (: L (Implication (Member v S) (Member v C)) tv), same subject v, symbol S, C."""
    n = _sx(atom)
    if not (isinstance(n, list) and len(n) == 4 and n[0] == ":" and isinstance(n[1], str)):
        return None
    imp, tv = n[2], n[3]
    if not (isinstance(imp, list) and len(imp) == 3 and imp[0] == "Implication"):
        return None
    a, b = imp[1], imp[2]
    if not all(isinstance(t, list) and len(t) == 3 and t[0] == "Member" and all(isinstance(z, str) for z in t[1:])
               for t in (a, b)):
        return None
    if a[1] != b[1]:          # same subject on both sides: a variable ($x, nwdef) or one ground witness (parser rule)
        return None
    return n[1], a[2], b[2], _is_nwdef_shape(a[1], a[2], b[2], tv)


# Exact shape of a pc_shadow.narrow_defining_rules atom (t-2026-11-10-wmtm-trivial-filter-followup-v2, finding 2):
#   (: L (Implication (Member $x <B>__nw_<10 hex>) (Member $x <B>)) (CTV (STV 1.0 0.99) (STV 0.0 0.0)))
# i.e. variable subject, premise class = the deterministic Narrow symbol whose base is exactly the conclusion class,
# and the fixed definitional truth value.  A parser class rule (e.g. r1 pilot -> person, CTV (STV 0.95 0.9) ...)
# is NOT a defining rule, whatever its truth-value form.  The label is not used (labels may be anything).
_NWDEF_TV = ["CTV", ["STV", "1.0", "0.99"], ["STV", "0.0", "0.0"]]
_NW_SYM = re.compile(r"^(.+)__nw_[0-9a-f]{10}$")


def _is_nwdef_shape(subj, S, B, tv) -> bool:
    if not (isinstance(subj, str) and subj.startswith("$")):
        return False
    m = _NW_SYM.match(S)
    if not (m and m.group(1) == B):
        return False
    try:
        return (isinstance(tv, list) and len(tv) == 3 and tv[0] == "CTV"
                and all(isinstance(x, list) and len(x) == 3 and x[0] == "STV" for x in tv[1:])
                and [float(v) for v in tv[1][1:] + tv[2][1:]] == [1.0, 0.99, 0.0, 0.0])
    except (TypeError, ValueError):
        return False


def proof_rules(proof, atoms):
    """Worker side: the rule atoms a proof cites (by its step labels) plus the defining rule of each cited rule's
    premise class.  -> {label: atom}.  Lets the cycle side classify steps without the KB."""
    labs = set(re.findall(r"\((?:by|inverted)\s+(\S+)", str(proof or "")))
    by_lab, defining = {}, {}
    for a in atoms or []:
        a = str(a)
        if not a.startswith("(: ") or not ("(Implication" in a or "(Inheritance" in a):
            continue
        lab = a[3:].split(None, 1)[0]
        by_lab[lab] = a
        if "(Implication" not in a:
            continue
        m = _member_imp(a)
        if m and m[3]:
            defining.setdefault(m[1], (lab, a))
    out = {}
    for lab in sorted(labs):
        if lab in by_lab:
            out[lab] = by_lab[lab]
            m = _member_imp(by_lab[lab])
            if m and m[1] in defining:
                out[defining[m[1]][0]] = defining[m[1]][1]
    return out


def step_coverage(proof, rules):
    """followup-v2 finding 1: for evidence, -> {"steps": n, "known": k, "missing": [labels]}.  A step is known when
    the atom it cites (Implication rule, or Inheritance fact used as a rule) is in rules, so a control that admits
    with missing == [] admitted because each step was classified, not because the filter failed open."""
    labs = re.findall(r"\((?:by|inverted)\s+(\S+)", str(proof or ""))
    miss = sorted({l for l in labs if l not in (rules or {})})
    return {"steps": len(labs), "known": sum(1 for l in labs if l in (rules or {})), "missing": miss}


def _step_kind(label, rules):
    """'nwdef_head_noun' | 'narrow_echo' | None (any other rule, or atoms missing)."""
    from .pc_shadow import narrow_symbol
    m = _member_imp((rules or {}).get(label))
    if not m:
        return None
    _l, S, C, is_def = m
    if is_def:
        return "nwdef_head_noun"
    for a in (rules or {}).values():          # S's defining rule gives the base B
        d = _member_imp(a)
        if d and d[3] and d[1] == S:
            B = d[2]
            if any(narrow_symbol(["Narrow", B, [h, C]]) == S for h in ("Member", "Mod")):
                return "narrow_echo"
    return None


def _zero_weight(head):
    """A revision branch head carrying (prior (STV s 0.0)): confidence 0, contributes nothing."""
    if not isinstance(head, list):
        return False
    for x in head:
        if isinstance(x, list) and len(x) == 2 and x[0] == "prior" and isinstance(x[1], list) and len(x[1]) == 3 \
                and x[1][0] == "STV":
            try:
                return float(x[1][2]) == 0.0
            except ValueError:
                return False
    return False


def trivial_reason(proof, rules):
    """-> 'nwdef_head_noun' | 'narrow_echo' if the proof is trivial (see TRIVIAL_RULE above), else None."""
    n = _sx(proof)
    if not (isinstance(n, list) and len(n) == 4 and n[0] == ":"):
        return None
    steps, bad = [], []

    def walk(t):          # -> True if t's weighted support is asserted fact labels only
        if isinstance(t, str):
            if _LABEL.fullmatch(t):
                return True
            bad.append(t); return False
        if not isinstance(t, list) or not t:
            bad.append(t); return False
        h = t[0]
        if h == "by" and len(t) == 3 and isinstance(t[1], str):
            steps.append((t[1], walk(t[2])))
            return False
        if h == "merge/revision" and len(t) == 3:
            a, b = walk(t[1]), walk(t[2])
            return a and b
        if h == "factored-revision" and len(t) == 4 and isinstance(t[3], list):
            base = walk(t[1])
            for br in t[3]:
                if not (isinstance(br, list) and len(br) == 2):
                    bad.append(br); return False
                if _zero_weight(br[0]):
                    continue
                hd = br[0]
                if (isinstance(hd, list) and len(hd) >= 2 and hd[0] == "inverted" and isinstance(hd[1], str)):
                    # weighted inverted branch: the same rule read backwards over its argument; it is a step
                    # like any other (classified by _step_kind; an inverted nwdef over a fact stays trivial)
                    steps.append((hd[1], walk(br[1])))
                    continue
                bad.append(hd); walk(br[1]); return False
            return base
        bad.append(h); return False

    walk(n[1])
    if bad or not steps or not all(on_fact for _l, on_fact in steps):
        return None
    kinds = [_step_kind(l, rules) for l, _f in steps]
    if any(k is None for k in kinds):
        return None
    return "narrow_echo" if "narrow_echo" in kinds else "nwdef_head_noun"


def trivial_filter_on(cfg) -> bool:
    v = (cfg or {}).get("admit_trivial_filter", True)
    return v if isinstance(v, bool) else str(v).strip().lower() not in ("0", "false", "off", "no", "")
