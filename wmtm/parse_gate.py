"""Track J: parse-quality gate for PeTTaChainer conclusions (applies in reasoner = pettachainer).

Track I replay: most admitted PeTTaChainer conclusions came from ONE parsed fact of the shape "(Inheritance A trivial)",
which the parser had tagged with the quantifier "mostly" (QuantifierPhrase) but which still reached the KB as a
universal Inheritance.  Every "X is a A" then became "X is a trivial".  Three defences, all thresholds in the
flags file (<state_dir>/_wmtm_flags.json) or env, see runtime_config.SPEC "gate_*":

1. Per-fact sanity rules (worker side, in pc_shadow.build_snapshot, BEFORE facts enter the KB, so PeTTaChainer and
   the worker's Python comparison see the same gated facts):
     placeholder_subject   subject is a parser placeholder (sk_* witness) or a pronoun-like word  -> reject
     low_confidence        parse confidence < gate_min_conf                                        -> reject
     negative_quantifier   QuantifierPhrase "no"/"none"/"nothing"... on the pair (the parse is NOT
                           a positive fact)                                                         -> reject
     broad_category        Inheritance/Member into a very broad or evaluative category
                           (gate_broad_terms: thing, entity, trivial, ...)                          -> gate_broad_action
     hedged_quantifier     QuantifierPhrase "mostly"/"some"/"often"...: not universal, so
                           transitivity over it is unsound                                          -> gate_hedged_action
     identifier_category   (Track M) Member/Inheritance where the CATEGORY is an identifier (commit
                           hash, hex id, pid, uuid), or where an identifier SUBJECT is typed as a
                           named-thing kind it cannot be (gate_identifier_bad_categories: branch,
                           dir, path, file, repo, ... and *_branch etc.).  "c_7c8d9e0 is merged"
                           and "c_5e6f7a8 is a commit" stay.  Track K: "0a1b2c3 is a topic_branch",
                           "id_4d5e6f7 is a release_branch" (commit hashes typed as branches)        -> gate_identifier_action
   action = reject (fact dropped) | discount (strength x gate_discount; the fact stays).
2. Cap per source fact per cycle (cycle side, pc_admit.load_candidates): at most gate_max_per_fact admitted
   conclusions whose proof uses any one KB fact (highest initial STI first).
3. Review log <shadow_dir>/parse_review.jsonl (worker side): gated facts, facts behind >= gate_review_min proved
   conclusions, and facts behind Python / PeTTaChainer disagreements, so the parser can be reviewed.
"""
from __future__ import annotations
import collections, os, re, time

REVIEW_FILE = "parse_review.jsonl"
ACTIONS = ("reject", "discount", "keep")
_LABEL = re.compile(r"\b(?:sp|wm)\d+\b")
_GOAL = re.compile(r"^\((\w+) (\S+) (\S+)\)$")
# Track M: whole-token identifiers.  Optional short prefix (c_, id_, sha_, commit_, rev_, proc_, pid_), then a hex
# run of 7-40 chars with at least one digit (git short/long hashes), a >= 5 digit number after a prefix (pids), or a uuid.
# Track P: also ANY short alphabetic prefix (1-8 letters + _ or -: ref_, tag_, build_, ...) before a hex run that has
# both a digit and a letter a-f (an all-digit run after an unknown prefix may be a date, e.g. release_20250307).
_ID_PREFIX = r"(?:c|id|sha|commit|rev|ref|hash|proc|pid|h)[_-]"
_ANY_PREFIX = r"[a-z]{1,8}[_-]"
_IDENT = re.compile(r"^(?:%s)?(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}$|^%s[0-9]{5,}$|"
                    r"^%s(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}$|"
                    r"^(?:%s)?[0-9a-f]{8}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{4}[-_][0-9a-f]{12}$"
                    % (_ID_PREFIX, _ID_PREFIX, _ANY_PREFIX, _ANY_PREFIX))


def _csv(v):
    return {x.strip().lower() for x in str(v or "").split(",") if x.strip()}


def settings(cfg=None) -> dict:
    """Gate thresholds from a resolved runtime config (falls back to the SPEC defaults)."""
    from .runtime_config import SPEC
    cfg = cfg or {}

    def g(k):
        v = cfg.get(k)
        return SPEC[k][2] if v is None else v
    act = lambda k: (str(g(k)).strip().lower() if str(g(k)).strip().lower() in ACTIONS else "reject")
    return {"on": bool(g("gate_on")), "min_conf": float(g("gate_min_conf")),
            "broad": _csv(g("gate_broad_terms")), "placeholders": _csv(g("gate_placeholder_terms")),
            "hedged": _csv(g("gate_hedged_quantifiers")), "negative": _csv(g("gate_negative_quantifiers")),
            "broad_action": act("gate_broad_action"), "hedged_action": act("gate_hedged_action"),
            "identifier_action": act("gate_identifier_action"), "id_bad": _csv(g("gate_identifier_bad_categories")),
            "discount": min(1.0, max(0.0, float(g("gate_discount")))),
            "max_per_fact": max(0, int(g("gate_max_per_fact"))), "review_min": max(1, int(g("gate_review_min")))}


def quantifiers(atom_strs) -> dict:
    """(subject, object) -> quantifier word, from the parser's (QuantifierPhrase a b "q") atoms."""
    from .semparse_adapter import split_toplevel
    out = {}
    for _src, node, err in split_toplevel("\n".join(atom_strs or [])):
        if err or not isinstance(node, list):
            continue
        if node and node[0] == "Interpretation" and len(node) == 3:
            node = node[2]
        if len(node) == 4 and node[0] == ":" and isinstance(node[2], list) and len(node[2]) == 4 \
                and node[2][0] == "QuantifierPhrase" and all(isinstance(x, str) for x in node[2][1:]):
            out[(node[2][1], node[2][2])] = node[2][3].strip('"').strip().lower()
    return out


def is_placeholder(term, st) -> bool:
    t = str(term).lower()
    return t.startswith("sk_") or t in st["placeholders"]


def is_identifier(term) -> bool:
    """Commit hash / hex id / pid / uuid token (whole token; 'pettachainer_36b3fe6_dedup' is a name, not an id)."""
    return bool(_IDENT.match(str(term).lower()))


def identifier_category(h, a, b, st) -> bool:
    if h not in ("Inheritance", "Member"):
        return False
    if is_identifier(b):
        return True                                   # an identifier used as a category
    if not is_identifier(a):
        return False
    cat = str(b).lower()
    return any(cat == t or cat.endswith("_" + t) for t in st.get("id_bad", ()))


def check_fact(fact, quant, st):
    """-> (fact_or_None, reason_or_None, action).  fact = (head, a, b, s, c)."""
    h, a, b, s, c = fact
    if not st["on"]:
        return fact, None, "keep"
    if is_placeholder(a, st):
        return None, "placeholder_subject", "reject"
    if c < st["min_conf"]:
        return None, "low_confidence", "reject"
    if quant and quant in st["negative"]:
        return None, "negative_quantifier", "reject"
    reasons, out = [], fact
    for reason, hit, action in (("broad_category", h in ("Inheritance", "Member") and str(b).lower() in st["broad"],
                                 st["broad_action"]),
                                ("hedged_quantifier", bool(quant) and quant in st["hedged"], st["hedged_action"]),
                                ("identifier_category", identifier_category(h, a, b, st),
                                 st.get("identifier_action", "reject"))):
        if not hit or action == "keep":
            continue
        if action == "reject":
            return None, reason, "reject"
        out = (h, a, b, round(out[3] * st["discount"], 4), c); reasons.append(reason)
    return out, ("+".join(reasons) or None), ("discount" if reasons else "keep")


def gate_facts(facts, quants, st, item_id=None):
    """-> (kept facts, decisions).  decisions: one record per rejected / discounted fact."""
    kept, dec = [], []
    for f in facts:
        q = (quants or {}).get((f[1], f[2]))
        nf, reason, action = check_fact(f, q, st)
        if reason:
            dec.append({"fact": "(%s %s %s)" % f[:3], "stv": [f[3], f[4]], "quant": q, "reason": reason,
                        "action": action, "item": item_id})
        if nf is not None:
            kept.append(nf)
    return kept, dec


def summary(decisions) -> dict:
    c = collections.Counter((d["action"], d["reason"]) for d in decisions)
    return {"rejected": {r: n for (a, r), n in c.items() if a == "reject"},
            "discounted": {r: n for (a, r), n in c.items() if a == "discount"}}


def labels(proof) -> list:
    out = []
    for lab in _LABEL.findall(proof or ""):
        if lab not in out:
            out.append(lab)
    return out


def cap_per_fact(cands, st):
    """cands: [(candidate, [fact keys])] sorted best first.  -> (kept candidates, n dropped, {fact: n dropped})."""
    cap = st["max_per_fact"]
    if not st["on"] or cap <= 0:
        return [c for c, _ in cands], 0, {}
    used, kept, over = collections.Counter(), [], collections.Counter()
    for cand, keys in cands:
        hot = [k for k in keys if used[k] >= cap]
        if hot:
            over.update(hot); continue
        used.update(keys); kept.append(cand)
    return kept, len(cands) - len(kept), dict(over)


def review(out_dir, rec, spec, cfg=None, now=None):
    """Worker side: append one review record (only if something is worth reviewing).  Never raises."""
    try:
        from . import runtime_config as rc
        st = settings(cfg)
        lf = spec.get("label_fact") or {}
        per = collections.defaultdict(list)
        for q in rec.get("queries", []):
            if q.get("ok") and q.get("proof"):
                for lab in labels(q["proof"]):
                    per[lf.get(lab, lab)].append(q["goal"])
        heavy = {f: {"n": len(g), "goals": g[:10]} for f, g in per.items() if len(g) >= st["review_min"]}
        gate = spec.get("gate") or {}
        if not (heavy or gate.get("decisions")):
            return None
        doc = {"ts": now or time.time(), "cycle": spec.get("cycle"), "status": rec.get("status"),
               "gated": gate.get("decisions", [])[:100], "gate_summary": {k: gate.get(k) for k in ("rejected", "discounted")},
               "many_conclusions": heavy}
        rc.append_jsonl(os.path.join(out_dir, REVIEW_FILE), doc, (cfg or {}).get("jsonl_max_bytes"))
        return doc
    except Exception:
        return None
