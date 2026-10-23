"""v0.7: GoalChainer v2 as the goal engine's core (need regulation, deontic admissibility, ranking).

WMTM keeps its own layers: needs.py turns memory items into open signals and need levels (explicit markers, resolved
detection, request-history replies, speaker_map addressees), actions.py instantiates per-item candidates (timing,
re-ask, addressee and self-task rules).  This module then
  1. generates, per run, a GoalChainer v2 domain (.metta): the two needs (unc, comp) with target bands, one gc-action
     per WMTM candidate (v2 declares actions statically, so the domain is generated per run), the WMTM legitimacy
     rules as defeasible deontic norms over declared action effects, and a gc-need-expectation per action and need;
  2. builds the inputs: attributed readings (one signal per open item, plus automated_turn) and need observations
     for a per-run motivation stream;
  3. runs v2 in its OWN interpreter and environment (a separate process; see client()), never in this process.
     GoalChainer v2 is GPL-3.0-only AND MIT AND Apache-2.0; WMTM neither imports nor vendors any of its code;
  4. maps v2's review records (propose / hold / escalate / blocked, deontic proof, ranking steps) back onto the
     proposal records WMTM already writes (proposals.jsonl, display.jsonl, latest.json), plus v2 fields.

Selection: v2 proposes ONE action per review.  WMTM asks for up to goal_max_proposals: after each proposal, that
action and its (person, topic) duplicates are withdrawn from the domain and v2 reviews the rest again (same
process, warm engine).  The first non-propose disposition ends the series.  hold / escalate / blocked are logged in
runs.jsonl and never shown.
"""
from __future__ import annotations

import hashlib
import re
import json
import math
import os
import shutil
import signal as _signal
import subprocess
import sys
import time

from . import actions, legitimacy, needs

ENGINE = "goalchainer-v2"
JOB_PROTOCOL = "wmtm-gc2-job-v1"
RESULT_PROTOCOL = "wmtm-gc2-result-v1"
RUNNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "v2_runner.py")
GOALS = {"unc": "settle_open_questions", "comp": "keep_commitments"}
GOAL_TEXT = {"unc": "Keep the open questions WMTM tracks few (uncertainty reduction).",
             "comp": "Keep pending items and own promises few (competence)."}
_CODE = {"ClarifyQuestion": "ask", "FlagUncertainty": "flag", "LookUp": "look", "SummarizeStatus": "status",
         "RemindPending": "remind", "SelfTask": "self"}
# The WMTM legitimacy rules (legitimacy.RULES: rule id, effect, reason, priority) as defeasible deontic norms.
# Live changes and pushes are defeasible (an explicit approval of that action defeats them); memories in git and
# writes are strict.  Every message / write / live-change / git / push effect is forbidden on an automated turn.
STRICT = ("no_git_memory", "read_only")
CAP_STEP = 0.01        # a single action never reaches the band on paper: change <= gap * (1 - CAP_STEP * (rank + 1))
TIE_STEP = 1e-6        # exact ties between candidates are broken in WMTM's candidate order
RULE_IDS = tuple(r[0] for r in legitimacy.RULES) + tuple("no_autonomous_" + e for e in legitimacy.AUTONOMOUS_EFFECTS)


def iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(float(ts)))


def _h(s, n=10):
    return hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:n]


def _str(s):
    """A MeTTa string literal (double quotes, backslashes escaped, one line)."""
    s = " ".join(str(s or "").split())
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _num(x):
    return repr(float(round(x, 9)))


def signal_id(sig):
    return "item_" + _h(sig.get("need", "") + "|" + "|".join(sig.get("items") or ()) + "|" + sig.get("text", ""))


def action_id(c, i):
    return "a%02d_%s_%s" % (i, _CODE.get(c["action"], "act"), _h(c["key"], 8))


def gmean(xs):
    xs = [max(1e-6, min(1.0, float(x))) for x in xs]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else 1.0


def raw_change(c, est, st, now, recent=()):
    """Expected rise of the need's level if this action is taken: the level gain from closing the action's open
    items (needs.level over the remaining load), times the WMTM considerations (geometric mean: salience,
    specificity, fit, age, KB support), times the repeat discount for a proposal logged inside goal_repeat_s."""
    n = c["need"]; cap = st.get("age_cap_d", 7.0); scale = st.get("scale", 1.0)
    load = sum(needs.weight(s, now, cap) for s in est[n]["signals"])
    rm = min(load, sum(needs.weight(s, now, cap) for s in c.get("signals") or ()))
    lv = 1.0 / (1.0 + load / max(scale, 1e-9))
    after = 1.0 / (1.0 + max(0.0, load - rm) / max(scale, 1e-9))
    disc = legitimacy.REPEAT_DISCOUNT if c["key"] in set(recent or ()) else 1.0
    return max(0.0, after - lv) * gmean((c.get("cons") or {}).values()) * disc


def expectations(cands, est, st, now, recent=()):
    """-> [declared change per candidate].  Raw changes in candidate order; exact ties broken by that order; a
    change that would bring the need into its band is capped just below the band edge (asking or reminding does
    not by itself close an item), keeping the raw order, so v2 never sees two candidates tie at 'satisfied'."""
    raw = [raw_change(c, est, st, now, recent) for c in cands]
    order = sorted(range(len(cands)), key=lambda i: (-raw[i], i))
    rank = {i: r for r, i in enumerate(order)}
    out = []
    for i, c in enumerate(cands):
        x = raw[i] * (1.0 - TIE_STEP * rank[i])
        gap = est[c["need"]]["target"] - est[c["need"]]["level"]
        if gap > 0:
            x = min(x, gap * (1.0 - CAP_STEP * (rank[i] + 1)))
        out.append(max(0.0, x))
    return out


def norms_text(approved=False):
    lines = ["(normally permit (candidate ?a) (may (do ?a)))"]
    for rid, eff, _reason, _prio in legitimacy.RULES:
        kind = "always" if rid in STRICT else "normally"
        lines.append("(%s %s (wmtm-effect ?a %s) (forbidden (do ?a)))" % (kind, rid, eff))
        if kind == "normally":
            lines.append("(prefer %s permit)" % rid)
            if approved:
                lines.append("(prefer approved_change %s)" % rid)
    if approved:
        lines.append("(normally approved_change (approved ?a) (may (do ?a)))")
    for eff in legitimacy.AUTONOMOUS_EFFECTS:
        lines.append("(always no_autonomous_%s (and (signal automated_turn) (wmtm-effect ?a %s)) (forbidden (do ?a)))"
                     % (eff, eff))
    return "\n".join(lines)


def build_series(label, cands, est, st, now, ctx=None, passes=("human",), groups=None):
    """-> (series job dict, {action_id: candidate}).  passes: "human" (automated_turn refuted) and/or "automated"
    (detected).  groups: {candidate key: [candidate keys withdrawn with it]} (WMTM's one-per-(person, topic))."""
    ctx = ctx or {}
    recent = set(ctx.get("recent") or ())
    approved = set(ctx.get("approved") or ())
    ch = expectations(cands, est, st, now, recent)
    ids = [action_id(c, i) for i, c in enumerate(cands)]
    by_key = {c["key"]: a for c, a in zip(cands, ids)}
    sigs = {}
    for c in cands:
        for s in c.get("signals") or ():
            sigs.setdefault(signal_id(s), s)
    t_unc, t_comp = est["unc"]["target"], est["comp"]["target"]
    head = [
        "; WMTM goal domain, generated per run by wmtm/goals/v2.py (log only: nothing here is ever executed)",
        '(gc-domain "WMTM goals")',
        "(gc-policy-version wmtm-goals-v1)",
        '(gc-authority advisory 0 "A logged suggestion; WMTM sends nothing and changes nothing.")',
        *("(gc-estimator-ceiling %s advisory)" % e for e in
          ("deterministic", "measured", "human-asserted", "model-proposed", "receipt-calibrated")),
        "(gc-goal %s wmtm individual %s %s (priority-source policy:wmtm-goal-weights))"
        % (GOALS["unc"], _num(est["unc"]["weight"]), _str(GOAL_TEXT["unc"])),
        "(gc-goal %s wmtm individual %s %s (priority-source policy:wmtm-goal-weights))"
        % (GOALS["comp"], _num(est["comp"]["weight"]), _str(GOAL_TEXT["comp"])),
        "(gc-need unc %s (scale 0 1) (band %s 1) (drive 1) (need-source policy:wmtm-goal-targets))"
        % (GOALS["unc"], _num(min(1.0, max(0.0, t_unc)))),
        "(gc-need comp %s (scale 0 1) (band %s 1) (drive 1) (need-source policy:wmtm-goal-targets))"
        % (GOALS["comp"], _num(min(1.0, max(0.0, t_comp)))),
        '(gc-signal automated_turn "this run follows an automated (non-user) turn")',
        '(gc-signal goal_review "WMTM is reviewing its goals")',
        *("(gc-signal %s %s)" % (k, _str("open %s item from %s" % (s.get("kind", ""), ",".join(s.get("items") or ())[:80])))
          for k, s in sigs.items()),
        norms_text(bool(approved & set(by_key))),
    ]
    blocks = {}
    for c, a, x in zip(cands, ids, ch):
        body = [signal_id(s) for s in c.get("signals") or ()]
        cond = ("(signal %s)" % body[0]) if len(body) == 1 else "(and %s)" % " ".join("(signal %s)" % b for b in body)
        b = ["(gc-action %s %s %s (authority advisory))" % (a, _str(c["action"]), _str(str(c["text"])[:600]))]
        b += ["(given (wmtm-effect %s %s))" % (a, e) for e in c.get("effects") or ()]
        if c["key"] in approved:
            b.append("(given (approved %s))" % a)
        b.append("(normally cand_%s %s (candidate %s))" % (a, cond, a) if body else
                 "(normally cand_%s (signal goal_review) (candidate %s))" % (a, a))
        for n in ("unc", "comp"):
            b.append("(gc-need-expectation %s %s %s model-proposed (expectation-source policy:wmtm-goals))"
                     % (a, n, _num(x if n == c["need"] else 0.0)))
        blocks[a] = "\n".join(b)
    readings = [{"signal": k, "state": "detected", "estimator": "deterministic",
                 "source": "wmtm:items:" + ",".join(s.get("items") or ())[:200],
                 "observed_at": iso(min(float(s.get("ts_last") or now), now)),
                 "note": "%s item, addressee %s" % (s.get("kind", ""), s.get("who") or "-")} for k, s in sigs.items()]
    obs = [{"need": n, "level": float(est[n]["level"]), "scale": [0, 1], "estimator": "deterministic",
            "source": "wmtm:needs.estimate", "observed_at": iso(now)} for n in ("unc", "comp")]
    rem = {}
    for k, ks in (groups or {}).items():
        if k in by_key:
            rem[by_key[k]] = sorted(by_key[x] for x in ks if x in by_key and x != k)
    ps = []
    for p in passes:
        auto = {"signal": "automated_turn", "state": "detected" if p == "automated" else "refuted",
                "estimator": "deterministic", "source": "wmtm:run", "observed_at": iso(now)}
        rev = {"signal": "goal_review", "state": "detected", "estimator": "deterministic", "source": "wmtm:run",
               "observed_at": iso(now)}
        ps.append({"label": p, "readings": readings + [auto, rev]})
    job = {"label": label, "header": "\n".join(head), "blocks": blocks, "order": ids, "observations": obs,
           "as_of": iso(now), "passes": ps, "remove": rem, "max_reviews": int(st.get("max_proposals", 5))}
    return job, dict(zip(ids, cands))


def dedupe_groups(cands, thr=None):
    """WMTM's R2.1 rule as withdrawal groups: one proposal per (person, topic cluster; rc2) across
    Ask/Flag/Remind/LookUp."""
    out = {}
    for c in cands:
        if c["action"] not in actions.DEDUPE_ACTIONS:
            continue
        ks = set(c.get("topic") or ())
        out[c["key"]] = [d["key"] for d in cands if d is not c and d["action"] in actions.DEDUPE_ACTIONS
                         and d.get("who") == c.get("who") and needs.cluster_match(ks, set(d.get("topic") or ()), thr)]
    return out


# ------------------------------------------------------------------ subprocess client
class V2Error(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


def client(job, cfg, workdir):
    """Run the job in the v2 interpreter (goal_v2_python) as a separate process group with a hard wall-clock
    timeout (SIGKILL of the group) and an address-space cap set by the runner itself.  -> parsed result.
    Raises V2Error(status) with status v2_unconfigured / v2_timeout / v2_crash / v2_bad_output."""
    py = str(cfg.get("goal_v2_python") or "")
    runner = str(cfg.get("goal_v2_runner") or "") or RUNNER
    if not py or not os.path.exists(py):
        raise V2Error("v2_unconfigured", "goal_v2_python not set or missing")
    tmo = float(cfg.get("goal_v2_timeout_s") or 60.0)
    os.makedirs(workdir, mode=0o700, exist_ok=True)
    os.chmod(workdir, 0o700)    # rc2: per-run scratch is private whatever the umask (v2 refuses world-writable dirs)
    env = {"PATH": "/usr/bin:/bin", "HOME": workdir, "TMPDIR": workdir, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    job = dict(job, protocol=JOB_PROTOCOL, workdir=workdir,
               budget={"inferences": int(cfg.get("goal_v2_inferences") or 50_000_000),
                       "timeout_seconds": max(1.0, tmo - 5.0)})
    cmd = [py, "-I", runner, "--mem-mb", str(int(cfg.get("goal_v2_mem_mb") or 1536))]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=workdir,
                         env=env, start_new_session=True, close_fds=True)
    try:
        out, err = p.communicate(json.dumps(job).encode("utf-8"), timeout=tmo)
    except subprocess.TimeoutExpired:
        raise V2Error("v2_timeout", "no answer within %gs" % tmo)
    finally:
        try:
            os.killpg(p.pid, _signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            p.wait(timeout=5)
        except Exception:   # noqa: BLE001
            pass
    if p.returncode != 0:
        raise V2Error("v2_crash", "exit %s: %s" % (p.returncode, (err or b"").decode("utf-8", "replace")[-300:]))
    try:
        res = json.loads(out.decode("utf-8"))
    except ValueError:
        raise V2Error("v2_bad_output", "unparseable runner output")
    if not isinstance(res, dict) or res.get("protocol") != RESULT_PROTOCOL or not isinstance(res.get("series"), list):
        raise V2Error("v2_bad_output", "unexpected runner protocol")
    if res.get("error"):
        raise V2Error("v2_error", str(res["error"])[:300])
    return res


def cleanup(workdir):
    shutil.rmtree(workdir, ignore_errors=True)


# ------------------------------------------------------------------ review -> proposal mapping
def _deontic_of(review, aid):
    for c in review.get("candidates") or ():
        if c.get("action") == aid:
            return c.get("deontic")
    return None


def proof(review, aid, mode):
    """Compact deontic proof of (mode do aid) from the review's deontic_support: 'P(do a) <- permit <- cand_a <-
    signal item_x'.  mode: P (permitted) / F (forbidden)."""
    want = "(lit pos %s none do (%s))" % (mode, aid)

    def walk(n, depth=0):
        if depth > 4 or not isinstance(n, dict):
            return ""
        lab = n.get("label") or n.get("kind") or ""
        lit = str(n.get("literal") or "")
        head = lab if n.get("kind") == "rule" else lit.replace("(lit pos none none ", "(")
        ps = [walk(x, depth + 1) for x in n.get("premises") or ()]
        ps = [p for p in ps if p]
        return head + (" <- " + " & ".join(ps) if ps else "")
    for n in review.get("deontic_support") or ():
        if n.get("literal") == want and n.get("kind") == "rule":
            return ("%s(do %s) <- " % (mode, aid) + walk(n))[:400]
    return ""


def _steps(review, aid):
    out = []
    for s in review.get("steps") or ():
        el = [e for e in s.get("eliminated") or () if e.get("action") == aid]
        out.append({"step": s.get("name"), "kept": aid in (s.get("survivors") or ()),
                    **({"why": str(el[0].get("reason"))[:160]} if el else {})})
    return out


def summarize(review):
    d = review.get("disposition")
    out = {"review_id": review.get("review_id"), "disposition": d, "fingerprint": review.get("fingerprint"),
           "inferences": (review.get("engine") or {}).get("inferences")}
    if d == "hold":
        out["hold"] = review.get("hold")
    elif d == "escalate":
        e = review.get("escalation") or {}
        out["escalation"] = {"reasons": [str(r)[:240] for r in e.get("reasons") or ()][:3],
                             "contested": list(e.get("contested") or ())[:10]}
    elif d == "blocked":
        out["blockers"] = [str(b)[:200] for b in review.get("blockers") or ()][:5]
    elif d == "propose":
        out["action"] = (review.get("proposal") or {}).get("action")
    return out


def map_pass(pres, amap, est, now, ctx=None, remove=None):
    """One pass's reviews -> (proposals in v2 order, candidates with status/legit/v2 fields, decision log).
    Candidate status: proposed (v2 proposed it), vetoed (v2 deontic: forbidden), held / escalated / blocked /
    not_selected (the series ended on that disposition), plus check_proposal refusals in engine."""
    ctx = ctx or {}
    recent = set(ctx.get("recent") or ())
    reviews = [r for r in pres.get("reviews") or () if isinstance(r, dict)]
    first = reviews[0] if reviews else {}
    last = reviews[-1] if reviews else {}
    end = last.get("disposition") if last.get("disposition") != "propose" else "not_selected"
    end_status = {"hold": "held", "escalate": "escalated", "blocked": "blocked", "no-candidates": "no_candidates"}.get(
        end, "not_selected")
    props, cands = [], []
    chosen = {}
    for r in reviews:
        if r.get("disposition") == "propose":
            chosen[(r.get("proposal") or {}).get("action")] = (len(chosen), r)     # (rank - 1, review)
    withdrawn = {x for a in chosen for x in (remove or {}).get(a, ())} - set(chosen)
    for aid, c in amap.items():
        c = dict(c)
        deon = _deontic_of(first, aid)
        u = est[c["need"]]["urge"]
        c.update(id=c["key"], urge=u, engine=ENGINE, action_id=aid)
        disc = {"repeat": legitimacy.REPEAT_DISCOUNT} if c["key"] in recent else {}
        if deon == "forbidden":
            pr = proof(first, aid, "F")
            toks = set(re.split(r"[\s()&<-]+", pr))
            rules = [r for r in RULE_IDS if r in toks]
            c.update(score=0.0, status="vetoed", decision="vetoed",
                     legit={"d": 0.0, "status": "forbidden", "rules": rules, "reasons": [pr], "discounts": disc,
                            "impl": ENGINE})
        elif aid in chosen:
            i, r = chosen[aid]
            p = r.get("proposal") or {}
            val = ((p.get("carrying_path") or {}).get("value") or {})
            proj = next((x.get("projection") for x in r.get("display_order") or () if x.get("action") == aid), None)
            score = float(proj if proj is not None else val.get("low") or 0.0)
            ch = next((x for x in p.get("predicted_need_changes") or () if x.get("need") == c["need"]), {})
            pf = proof(r, aid, "P")
            c.update(score=round(max(score, 1e-4), 4), status="proposed", decision="propose",
                     legit={"d": 1.0, "status": p.get("deontic") or "permitted", "rules": [], "reasons": [pf] if pf else [],
                            "discounts": disc, "impl": ENGINE},
                     v2={"review_id": r.get("review_id"), "fingerprint": r.get("fingerprint"), "rank": i + 1,
                         "decided_at": p.get("decided_at"), "reduction": val,
                         "level": ch.get("observed_level"), "predicted_level": ch.get("predicted_level"),
                         "expected_change": ch.get("expected_change"), "proof": pf,
                         "authority": p.get("licensed_authority_ceiling"), "authorization": p.get("authorization"),
                         "steps": _steps(r, aid),
                         # v2's planner is not used: no procedures are declared, every WMTM action is one step.
                         "plan": [{"step": 1, "action": c["action"], "who": c.get("who"),
                                   "check": "deontic %s; %s urgency reduction %s" % (
                                       p.get("deontic") or "permitted", c["need"], _num(val.get("low") or 0.0))}]})
            props.append(c)
        elif aid in withdrawn:            # same (person, topic) as a proposed action: R2.1, one proposal per topic
            c.update(score=0.0, status="dup", decision="withdrawn",
                     legit={"d": 1.0, "status": deon or "unknown", "rules": [], "reasons": [], "discounts": disc,
                            "impl": ENGINE})
        else:
            c.update(score=0.0, status=end_status if deon else "not_candidate", decision=end_status,
                     legit={"d": 1.0 if deon in ("permitted", "obligated") else 0.0, "status": deon or "unknown",
                            "rules": [], "reasons": [], "discounts": disc, "impl": ENGINE})
        cands.append(c)
    props.sort(key=lambda c: c["v2"]["rank"])
    return props, cands, [summarize(r) for r in reviews]
