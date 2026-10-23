"""Track R: scoring, structural check, goal canary and the log-only shadow hook."""
from __future__ import annotations

import json
import math
import os
import time

from . import actions, legitimacy, needs, v2

SUBDIR = "goalchainer"
NEEDS = ("unc", "comp")
FIELDS = ("id", "action", "need", "text", "why", "score", "urge", "cons", "legit", "status", "items")
V2_FIELDS = ("engine", "decision", "v2")      # v0.7: added to proposal / display records by the v2 engine
ENGINES = ("v2", "native")


def cfg_value(cfg, key):
    """cfg[key], else the runtime_config default (callers that pass a plain dict instead of rc.resolve())."""
    if cfg and key in cfg:
        return cfg[key]
    from .. import runtime_config as rc
    spec = rc.SPEC.get(key)
    return spec[2] if spec else None


def engine_name(cfg=None):
    """goal_engine flag: "v2" (GoalChainer v2 core, default from v0.7) or "native" (the v0.6 scoring core, kept as
    the rollback switch for one release).  Anything else -> "v2"."""
    e = str(cfg_value(cfg, "goal_engine") or "v2").strip().lower()
    return e if e in ENGINES else "v2"


def v2_cfg(cfg=None):
    return {k: cfg_value(cfg, k) for k in ("goal_v2_python", "goal_v2_runner", "goal_v2_timeout_s", "goal_v2_mem_mb",
                                          "goal_v2_inferences", "goal_v2_release")}


def _floats(v, n, dflt):
    try:
        xs = [float(x) for x in str(v).split(",")]
        return xs if len(xs) == n else dflt
    except ValueError:
        return dflt


def settings(cfg=None):
    cfg = cfg or {}
    w = _floats(cfg.get("goal_weights", "1,1"), 2, [1.0, 1.0])
    t = _floats(cfg.get("goal_targets", "0.8,0.8"), 2, [0.8, 0.8])
    return {"weights": dict(zip(NEEDS, w)), "targets": dict(zip(NEEDS, t)), "scale": float(cfg.get("goal_scale", 1.0)),
            "age_cap_d": float(cfg.get("goal_age_cap_d", 7.0)), "max_proposals": int(cfg.get("goal_max_proposals", 5)),
            "min_score": float(cfg.get("goal_min_score", 0.05)), "repeat_s": float(cfg.get("goal_repeat_s", 21600.0)),
            "people": needs.people_patterns(cfg.get("speaker_map")), "self_name": str(cfg.get("speaker_self") or ""),
            "requests": list(cfg.get("goal_requests") or ()),
            "remind_after_s": float(cfg.get("goal_remind_after_s", 86400.0)),
            "reask_s": float(cfg.get("goal_reask_s", 3 * 86400.0)),
            # v0.7.0rc2 (Track V)
            "topic_overlap": float(cfg.get("goal_topic_overlap", needs.TOPIC_OVERLAP)),
            "max_item_age_s": float(cfg.get("goal_max_item_age_days", 7.0)) * 86400.0,
            "aliases": needs.alias_map(cfg.get("speaker_map"), cfg.get("speaker_self")),
            "names": sorted({str(v).lower() for v in (cfg.get("speaker_map") or {}).values() if v}),
            "close_unattributed": bool(cfg.get("goal_close_unattributed", True)),
            "notes": list(cfg.get("goal_notes") or ()),
            "flags": live_flags(cfg)}


def live_flags(cfg):
    """rc2: the boolean flags of this run's config (flags file / env / defaults) -> {name: value}, for the
    'item contradicted by live state' check.  Only keys the config actually carries."""
    from .. import runtime_config as rc
    return {k: cfg[k] for k, spec in rc.SPEC.items() if spec[1] is bool and isinstance(cfg.get(k), bool)}


def same_cluster(a, b, thr=None):
    """(person, topic cluster) identity of two proposal-like records (who + topic)."""
    return (str(a.get("who") or "") == str(b.get("who") or "")
            and needs.cluster_match(set(a.get("topic") or ()), set(b.get("topic") or ()), thr))


def dedupe_cluster(props, thr=None):
    """rc2: keep the first proposal per (person, topic cluster) (input order = rank / score order)."""
    out = []
    for p in props:
        if not any(same_cluster(p, q, thr) for q in out if q.get("action") in actions.MESSAGE_ACTIONS
                   and p.get("action") in actions.MESSAGE_ACTIONS):
            out.append(p)
    return out


def mark_recent(cands, ctx, thr=None):
    """rc2: a candidate in the same (person, topic cluster) as a proposal logged inside goal_repeat_s counts as that
    proposal (repeat discount, not re-logged, owns the topic), whatever its id: paraphrases get new ids."""
    ents = list(ctx.get("recent_entries") or ())
    if not ents:
        return
    rec = set(ctx.get("recent") or ())
    for c in cands:
        if c["key"] not in rec and any(same_cluster(c, e, thr) for e in ents):
            rec.add(c["key"])
    ctx["recent"] = rec


def gmean(xs):
    xs = [max(1e-6, min(1.0, float(x))) for x in xs]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else 1.0


def _why(c, est, now):
    s = c["signals"][0]; n = est[c["need"]]
    age_d = max(0.0, (now - s["ts"]) / 86400.0)
    w = "%s urge %.2f (level %.2f < target %.2f, %d open); %s open %.1f d, salience %.2f, from %s" % (
        {"unc": "uncertainty", "comp": "competence"}[c["need"]], n["urge"], n["level"], n["target"], len(n["signals"]),
        s["kind"] if s.get("origin") != "parser" else "parser query", age_d, s["sal"], ",".join(c["items"][:3]))
    if c.get("proof"):
        w += "; KB proof: " + c["proof"][:160]
    return w


def check_proposal(p):
    """Structural check; returns None if well-formed, else the reason.  A failing proposal is never logged."""
    for f in FIELDS:
        if f not in p:
            return "missing " + f
    if p["need"] not in NEEDS or p["action"] not in actions.TEMPLATES:
        return "bad need/action"
    if not isinstance(p["score"], float) or not math.isfinite(p["score"]) or p["score"] <= 0:
        return "bad score"
    if p["status"] != "proposed" or p["legit"].get("d", 0) <= 0:
        return "vetoed or not proposed"
    if not str(p["text"]).strip() or not p["items"]:
        return "empty text/items"
    if "(" in p["text"] and "$" in p["text"] and p["need"] != "unc":
        return "unevaluated query in non-question"
    if p["action"] in actions.MESSAGE_ACTIONS and p.get("who") in (None, "", "user", needs.SELF):
        return "message without a resolved addressee"
    if p["action"] == "SelfTask" and "message" in (p.get("effects") or ()):
        return "self-task must not message"
    return None


def propose(raw_items, cfg=None, ctx=None, now=None, kb=None, extra_candidates=(), trace=None):
    now = time.time() if now is None else now
    st = settings(cfg); ctx = dict(ctx or {})
    if "requester" not in ctx:
        ctx["requester"] = needs.requester_at([r for r in st["requests"] if float(r.get("ts", 0)) <= now], now)
    est = needs.estimate(raw_items, now, st, trace=trace)
    cl, supp = actions.candidates(est, kb, now, st["age_cap_d"], st, ctx)
    if trace is not None:
        trace.extend((None, t, r) for t, r in supp)
    cands = cl + [dict(c) for c in extra_candidates]
    mark_recent(cands, ctx, st["topic_overlap"])
    impl = None
    for c in cands:
        lg = legitimacy.evaluate(c, ctx, cfg); impl = lg["impl"]
        u = est[c["need"]]["urge"]
        c["urge"] = u; c["legit"] = lg
        c["score"] = round(float(u * gmean(c.get("cons", {}).values()) * lg["d"]), 4)
        c["status"] = "vetoed" if lg["d"] <= 0 else ("proposed" if c["score"] >= st["min_score"] else "weak")
        c["id"] = c["key"]; c["why"] = _why(c, est, now) if c.get("signals") else c.get("why", "")
    cands.sort(key=lambda c: -c["score"])
    props, refused = [], []
    rec = set(ctx.get("recent") or ())                   # a recently logged proposal still owns its (person, topic)
    kept = [c for c in cands if c["id"] in rec and c["action"] in actions.DEDUPE_ACTIONS]
    for c in cands:
        if c["status"] != "proposed":
            continue
        r = check_proposal(c)
        if r:
            refused.append((c["id"], r)); continue
        if c["action"] in actions.DEDUPE_ACTIONS:          # R2.1: one proposal per (person, topic) across action types
            ks = set(c.get("topic") or ())
            dup = next((k for k in kept if k is not c and k["who"] == c.get("who")
                        and needs.cluster_match(ks, set(k.get("topic") or ()), st["topic_overlap"])), None)
            if dup:
                c["status"] = "dup"; supp.append((c["text"], "r21_same_topic_as_" + dup["action"]))
                if trace is not None:
                    trace.append((None, c["text"], "r21_same_topic_as_" + dup["action"]))
                continue
            if c not in kept:
                kept.append(c)
        props.append(c)
    return {"needs": {n: {k: est[n][k] for k in ("level", "target", "weight", "urge")} | {"signals": len(est[n]["signals"])}
                      for n in NEEDS},
            "candidates": cands, "proposals": props[:st["max_proposals"]], "all_proposed": props,
            "vetoed": [c for c in cands if c["status"] == "vetoed"], "refused": refused, "deontic_impl": impl,
            "suppressed": supp}


CANARY_NOW = 1_800_000_000.0
CANARY_ITEMS = [{"id": "canary-q", "content": "Open question for Quill: should the canary widget7 gadget be renamed to sprocket9?",
                 "sti": 1.0, "source_type": "recalled", "origin_ts": CANARY_NOW - 3 * 86400}]
CANARY_NEG = [{"id": "canary-n", "content": "The canary widget7 is a gadget and sprocket9 is a part of it.",
               "sti": 1.0, "source_type": "recalled", "origin_ts": CANARY_NOW - 3 * 86400}]
CANARY_FORBIDDEN = {"action": "ClarifyQuestion", "need": "unc", "effects": ["message", "live_change"], "who": "quill",
                    "text": "Turn widget7 on in the live flags file", "signals": [], "key": "canary-forbidden",
                    "items": ["canary-q"], "cons": {"fit": 1.0}, "why": "canary: forbidden live change"}


def goal_canary(cfg=None):
    """Known answer through the exact scoring path: the open question -> ClarifyQuestion (ask quill) is the top
    proposal; a live-change action is vetoed; a note with no open question yields no uncertainty proposal."""
    try:
        cfg = dict(cfg or {}, speaker_map={"quill": "quill"}, goal_requests=[])   # made-up person; no live history
        r = propose(CANARY_ITEMS, cfg, {"autonomous": False}, now=CANARY_NOW, extra_candidates=[CANARY_FORBIDDEN])
        top = r["proposals"][0] if r["proposals"] else {}
        forb = [c for c in r["candidates"] if c["key"] == "canary-forbidden"]
        n = propose(CANARY_NEG, cfg, {"autonomous": False}, now=CANARY_NOW)
        res = {"top": top.get("action"), "who": top.get("who"),
               "forbidden": forb[0]["status"] if forb else None,
               "neg_unc": sum(1 for c in n["proposals"] if c["need"] == "unc")}
        res["ok"] = (res["top"] == "ClarifyQuestion" and res["who"] == "quill" and "widget7" in top.get("text", "")
                     and res["forbidden"] == "vetoed" and res["neg_unc"] == 0)
        return res
    except Exception as e:   # noqa: BLE001
        return {"ok": False, "error": type(e).__name__ + ": " + str(e)[:160]}


# ------------------------------------------------------------------ v0.7: GoalChainer v2 core
def _dedupe_recent(cands, ctx, supp, trace=None, thr=None):
    """R2.1 against the log: a recently logged proposal still owns its (person, topic); other candidates on it are
    dropped before v2 sees them (within one run, v2's withdrawal groups apply the same rule)."""
    rec = set(ctx.get("recent") or ())
    kept = [c for c in cands if c["key"] in rec and c["action"] in actions.DEDUPE_ACTIONS]
    keep, dups = [], []
    for c in cands:
        if c["action"] in actions.DEDUPE_ACTIONS and c["key"] not in rec:
            ks = set(c.get("topic") or ())
            dup = next((k for k in kept if k["who"] == c.get("who")
                        and needs.cluster_match(ks, set(k.get("topic") or ()), thr)), None)
            if dup:
                c["status"] = "dup"; c["id"] = c["key"]; c.setdefault("score", 0.0)
                supp.append((c["text"], "r21_same_topic_as_" + dup["action"]))
                if trace is not None:
                    trace.append((None, c["text"], "r21_same_topic_as_" + dup["action"]))
                dups.append(c)
                continue
        keep.append(c)
    return keep, dups


def prepare_v2(raw_items, cfg=None, ctx=None, now=None, kb=None, extra_candidates=(), trace=None, label="main",
               passes=("human",)):
    """WMTM layers (needs.estimate, actions.candidates, R2.1 dedupe) -> one v2 series job + what finish_v2 needs."""
    now = time.time() if now is None else now
    st = settings(cfg); ctx = dict(ctx or {})
    if "requester" not in ctx:
        ctx["requester"] = needs.requester_at([r for r in st["requests"] if float(r.get("ts", 0)) <= now], now)
    est = needs.estimate(raw_items, now, st, trace=trace)
    cl, supp = actions.candidates(est, kb, now, st["age_cap_d"], st, ctx)
    if trace is not None:
        trace.extend((None, t, r) for t, r in supp)
    cands, seen = [], set()
    for c in cl + [dict(c) for c in extra_candidates]:
        if c["key"] in seen:            # the same self-task can come from two rules (remind + summary own promises)
            continue
        seen.add(c["key"]); cands.append(c)
        c["why"] = _why(c, est, now) if c.get("signals") else c.get("why", "")
    mark_recent(cands, ctx, st["topic_overlap"])
    keep, dups = _dedupe_recent(cands, ctx, supp, trace, st["topic_overlap"])
    job, amap = v2.build_series(label, keep, est, st, now, ctx, passes, v2.dedupe_groups(keep, st["topic_overlap"]))
    return {"st": st, "est": est, "ctx": ctx, "now": now, "supp": supp, "dups": dups, "job": job, "amap": amap,
            "label": label}


def finish_v2(prep, sres, pass_label="human"):
    """v2's reviews for one pass -> the same result dict as propose() (+ "decisions": compact review log).
    Raises v2.V2Error when the series or a review reported an error."""
    st, est = prep["st"], prep["est"]
    dec, props, cands = [], [], []
    if prep["amap"]:
        if not isinstance(sres, dict):
            raise v2.V2Error("v2_error", "series %s missing from the runner result" % prep["label"])
        if sres.get("error") or sres.get("observe_error"):
            raise v2.V2Error("v2_error", str(sres.get("error") or sres.get("observe_error"))[:300])
        pr = next((p for p in sres.get("passes") or () if p.get("label") == pass_label), None)
        if pr is None:
            raise v2.V2Error("v2_error", "pass %s missing" % pass_label)
        bad = [r.get("error") for r in pr.get("reviews") or () if r.get("error")]
        if bad:
            raise v2.V2Error("v2_review_error", str(bad[0])[:300])
        props, cands, dec = v2.map_pass(pr, prep["amap"], est, prep["now"], prep["ctx"], prep["job"].get("remove"))
        for c in cands:
            c["why"] = (c.get("why") or "") + ("; v2 %s" % c["decision"] + (
                " (%s, %s urgency reduction %.3f)" % (c["v2"]["decided_at"], c["need"],
                                                      float((c["v2"]["reduction"] or {}).get("low") or 0.0))
                if c.get("v2") else ""))
    else:
        dec = [{"disposition": "no-candidates", "review_id": None}]
    ok, refused = [], []
    for p in props:
        r = check_proposal(p)
        if r:
            refused.append((p["id"], r)); p["status"] = "refused"
        else:
            ok.append(p)
    return {"needs": {n: {k: est[n][k] for k in ("level", "target", "weight", "urge")} | {"signals": len(est[n]["signals"])}
                      for n in NEEDS},
            "candidates": cands + prep["dups"], "proposals": ok[:st["max_proposals"]], "all_proposed": ok,
            "vetoed": [c for c in cands if c["status"] == "vetoed"], "refused": refused, "deontic_impl": v2.ENGINE,
            "suppressed": prep["supp"], "decisions": dec}


def propose_v2(raw_items, cfg=None, ctx=None, now=None, kb=None, extra_candidates=(), trace=None, workdir=None,
               passes=("human",)):
    """One-shot v2 proposal (replay, tests): prepare -> runner subprocess -> finish.  -> {pass label: result}."""
    import tempfile
    prep = prepare_v2(raw_items, cfg, ctx, now, kb, extra_candidates, trace, "main", passes)
    wd = workdir or tempfile.mkdtemp(prefix="wmtm-gc2-")
    try:
        res = v2.client({"series": [prep["job"]]}, v2_cfg(cfg), wd) if prep["amap"] else {"series": []}
    finally:
        v2.cleanup(wd)
    s = next((x for x in res["series"] if x.get("label") == "main"), None)
    out = {p: finish_v2(prep, s, p) for p in passes}
    out["_runner"] = {k: res.get(k) for k in ("s", "maxrss_mb", "versions")}
    return out


def canary_v2_prepare(cfg=None):
    c = dict(cfg or {}, speaker_map={"quill": "quill"}, goal_requests=[])   # made-up person; no live history
    pos = prepare_v2(CANARY_ITEMS, c, {"autonomous": False}, now=CANARY_NOW, extra_candidates=[CANARY_FORBIDDEN],
                     label="canary", passes=("human", "automated"))
    neg = prepare_v2(CANARY_NEG, c, {"autonomous": False}, now=CANARY_NOW, label="canary_neg")
    return pos, neg


def canary_v2_check(pos, neg, by_label):
    """Known answer through the real v2 runtime: the open question -> ClarifyQuestion to quill is v2's first proposal
    (human pass); the live-change action is vetoed by v2's deontic norms; on an automated turn v2 proposes no
    message action; a note with no open question yields no uncertainty candidate/proposal."""
    try:
        h = finish_v2(pos, by_label.get("canary"), "human")
        a = finish_v2(pos, by_label.get("canary"), "automated")
        n = finish_v2(neg, by_label.get("canary_neg"), "human")
        top = h["proposals"][0] if h["proposals"] else {}
        forb = [c for c in h["candidates"] if c["key"] == "canary-forbidden"]
        res = {"top": top.get("action"), "who": top.get("who"), "decision": (h["decisions"] or [{}])[0].get("disposition"),
               "forbidden": forb[0]["status"] if forb else None,
               "auto_msgs": sum(1 for p in a["proposals"] if p["action"] in actions.MESSAGE_ACTIONS),
               "neg_unc": sum(1 for c in n["proposals"] if c["need"] == "unc"), "engine": v2.ENGINE}
        res["ok"] = (res["top"] == "ClarifyQuestion" and res["who"] == "quill" and "widget7" in top.get("text", "")
                     and res["decision"] == "propose" and res["forbidden"] == "vetoed" and res["auto_msgs"] == 0
                     and res["neg_unc"] == 0)
        return res
    except Exception as e:   # noqa: BLE001
        return {"ok": False, "engine": v2.ENGINE, "error": type(e).__name__ + ": " + str(e)[:160]}


def goal_canary_v2(cfg=None):
    """Standalone v2 goal canary (one runner process).  -> canary record."""
    import tempfile
    pos, neg = canary_v2_prepare(cfg)
    wd = tempfile.mkdtemp(prefix="wmtm-gc2-canary-")
    try:
        res = v2.client({"series": [j["job"] for j in (pos, neg) if j["amap"]]}, v2_cfg(cfg), wd)
    except v2.V2Error as e:
        return {"ok": False, "engine": v2.ENGINE, "error": e.status + ": " + str(e)[:160]}
    finally:
        v2.cleanup(wd)
    return canary_v2_check(pos, neg, {s.get("label"): s for s in res["series"]})


def cached_queries(cfg, ids):
    """item id -> parser queries stored in the semparse caches (base, ctx1, spk1); empty for pre-Track-R entries."""
    out = {}
    try:
        from ..parse_cache import ParseCache
        d = cfg.get("semparse_dir")
        for sub in ("", "ctx1", "spk1"):
            p = os.path.join(d, sub) if sub else d
            if not p or not os.path.isdir(p):
                continue
            for e in ParseCache(p, cfg=cfg).entries().values():
                if e.get("item_id") in ids and e.get("queries"):
                    out[e["item_id"]] = list(e["queries"])
    except Exception:
        pass
    return out


def _tail(path):
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2); n = fh.tell(); fh.seek(max(0, n - 262144))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict):
            yield e


def _recent(path, now, window, hist_window=0.0, asked_path=None, entries=None):
    """Proposal ids logged within window (repeat discount; from proposals.jsonl) and the proposals that were really
    ASKED within hist_window as {ts, who, topic, action} (R2 re-ask rule).  Track T: "asked" = rendered into a goal
    prompt block (asked.jsonl, written by wmtm/goal_prompt.py) -- logging alone no longer counts, so with
    goal_prompt off nothing is ever asked.  Reads file tails only.  rc2: entries (optional list) receives the logged
    proposals within window as {id, who, topic, action} for the (person, topic cluster) repeat rule."""
    keys, hist = set(), []
    for e in _tail(path):
        try:
            if now - float(e.get("ts") or 0) <= window:
                keys.add(e.get("id"))
                if e.get("who") and e.get("topic"):
                    (entries if entries is not None else []).append({"id": e.get("id"), "who": e.get("who"), "topic": list(e.get("topic") or ()),
                                           "action": e.get("action")})
        except (TypeError, ValueError):
            continue
    for e in _tail(asked_path) if asked_path else ():
        try:
            ts = float(e.get("ts"))
        except (TypeError, ValueError):
            continue
        if 0 <= now - ts < hist_window and e.get("who"):
            hist.append({"ts": ts, "who": e["who"], "topic": list(e.get("topic") or ()), "action": e.get("action")})
    return keys, hist


class _Budget(Exception):
    pass


def _alarm(_sig, _frm):
    raise _Budget()


def run_shadow(raw, rec, cfg, source=None, now=None):
    """Worker hook (after the PeTTaChainer shadow run).  Log only: writes <runtime_dir>/goalchainer/proposals.jsonl
    and runs.jsonl, nothing else (no prompt, block, journal or message).  Runs under goal_budget_s (SIGALRM when
    called from the main thread); any exception is caught and recorded in runs.jsonl.  Returns the run record, or
    None when off."""
    if not cfg.get("goalchainer"):
        return None
    import signal
    import threading
    from .. import runtime_config as rc
    t0 = time.time(); now = t0 if now is None else now
    d = os.path.join(cfg.get("runtime_dir") or ".", SUBDIR); os.makedirs(d, exist_ok=True)
    ppath = os.path.join(d, "proposals.jsonl"); mx = cfg.get("jsonl_max_bytes")
    run = {"ts": now, "run_id": "%d-%d" % (int(now), os.getpid()), "cycle": rec.get("cycle"), "source": source,
           "shadow_status": rec.get("status")}
    budget = float(cfg_value(cfg, "goal_budget_s") or 0)
    run["engine"] = engine_name(cfg)
    timer = budget > 0 and threading.current_thread() is threading.main_thread() and hasattr(signal, "setitimer")
    old = None
    try:
        if timer:
            old = signal.signal(signal.SIGALRM, _alarm); signal.setitimer(signal.ITIMER_REAL, budget)
        _run(raw, rec, cfg, source, now, run, d, ppath, mx, rc)
    except _Budget:
        run["status"] = "budget_exceeded"
    except Exception as e:   # noqa: BLE001  log only: never let the goal engine disturb the worker
        run["status"] = "error"; run["error"] = type(e).__name__ + ": " + str(e)[:160]
    finally:
        if timer:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old if old is not None else signal.SIG_DFL)
    run["budget_s"] = budget
    run["s"] = round(time.time() - t0, 3)
    latest = run.pop("_latest", None)
    try:
        rc.append_jsonl(os.path.join(d, "runs.jsonl"), run, mx)
    except Exception:   # noqa: BLE001
        pass
    write_latest(d, run, latest if run.get("status") == "ok" else [], cfg_value(cfg, "goal_topic_overlap"))
    return run


LATEST = "latest.json"
ASKED = "asked.jsonl"     # Track T: written by wmtm/goal_prompt.py when it renders a line (shown_at per proposal)
LATEST_FIELDS = ("id", "action", "need", "text", "who", "score", "status", "topic", "display_only", "engine", "decision")


DISPLAY = "display.jsonl"  # rc3: review log of display-only suggestions; never read by re-ask or anything actionable


def _display_key(p):
    return (str(p.get("who") or ""), tuple(str(t) for t in (p.get("topic") or ())), str(p.get("text") or ""))


def log_display(d, run, source, now, shown, dedupe_s, mx, rc, thr=None):
    """rc3: append the display-only suggestions of an automated run to <d>/display.jsonl (same record structure as
    proposals.jsonl + display_only: true, run_id, ts) so they can be reviewed / rated before phase 2.  A suggestion
    identical to one logged within dedupe_s (same who + topic + text), or (rc2) in the same (person, topic cluster),
    is not logged again: the log changes only when the line set does.  Size-rotated like the
    other JSONL logs.  Nothing reads this file back except this dedupe.  -> number of lines written."""
    if not shown:
        return 0
    path = os.path.join(d, DISPLAY)
    seen = []
    for e in _tail(path):
        try:
            if 0 <= now - float(e.get("ts") or 0) < dedupe_s:
                seen.append(e)
        except (TypeError, ValueError):
            continue
    n = 0
    for p in shown:
        if any(_display_key(p) == _display_key(e) or same_cluster(p, e, thr) for e in seen):
            continue
        seen.append(p)
        rc.append_jsonl(path, {"ts": now, "run_id": run["run_id"], "source": source, **{f: p.get(f) for f in FIELDS},
                               "who": p.get("who"), "effects": p.get("effects"), "topic": p.get("topic") or [],
                               **{f: p[f] for f in V2_FIELDS if f in p}, "display_only": True}, mx)
        n += 1
    return n


def write_latest(d, run, proposals, thr=None):
    """Track S: <d>/latest.json = this run's time, status, canary result and ALL its proposals (repeats included;
    proposals.jsonl holds new ones only).  A failed run writes an empty list, so an older run's suggestions never
    survive it.  Atomic (tmp + os.replace).  Never raises."""
    try:
        can = run.get("canary") or {}
        if run.get("status") != "ok":
            proposals = []
        proposals = dedupe_cluster(list(proposals or []), thr)     # rc2: one line per (person, topic cluster)
        rec = {"ts": run.get("ts"), "run_id": run.get("run_id"), "status": run.get("status"),
               "canary_ok": bool(can.get("ok")) and run.get("status") == "ok",
               "proposals": [{k: p.get(k) for k in LATEST_FIELDS} for p in (proposals or [])]}
        tmp = os.path.join(d, LATEST + ".%d.tmp" % os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(rec, fh)
        os.replace(tmp, os.path.join(d, LATEST))
    except Exception:   # noqa: BLE001
        pass


def _run(raw, rec, cfg, source, now, run, d, ppath, mx, rc):
    if engine_name(cfg) == "v2":
        return _run_v2(raw, rec, cfg, source, now, run, d, ppath, mx, rc)
    can = goal_canary(cfg); run["canary"] = can
    if rec.get("status") != "ok":
        run["status"] = "shadow_canary_fail"      # the shared sanity gate failed: trust nothing this run
        return
    if not can.get("ok"):
        run["status"] = "canary_fail"
        return
    raw, q, kb, rq, cfg = _inputs(raw, rec, cfg, now)
    st = settings(cfg)
    ents = []
    recent, hist = _recent(ppath, now, st["repeat_s"], st["reask_s"], os.path.join(d, ASKED), ents)
    ctx = {"autonomous": source == "automated", "recent": recent, "history": hist, "recent_entries": ents}
    res = propose(raw, cfg, ctx, now=now, kb=kb)
    logged = 0
    run["_latest"] = [p for p in res["proposals"] if p.get("status") == "proposed" and p["legit"].get("d", 0) > 0]
    if ctx["autonomous"]:
        # Track T fix 1: an automated run vetoes message actions (never acted on, never logged).  For the optional
        # prompt block only, compute them again on the SAME items without the autonomous norm (every other norm
        # still applies) and put them in latest.json marked display_only.  Not logged, not actionable; their
        # freshness is this run's ts, i.e. the data they come from.
        disp = propose(raw, cfg, dict(ctx, autonomous=False), now=now, kb=kb)
        shown = [dict(p, display_only=True) for p in disp["proposals"] if p["action"] in actions.MESSAGE_ACTIONS
                 and p.get("status") == "proposed" and p["legit"].get("d", 0) > 0 and not check_proposal(p)]
        run["_latest"] += shown
        run["display_only"] = len(shown)
        run["display_logged"] = log_display(d, run, source, now, shown, max(st["repeat_s"], st["reask_s"]), mx, rc,
                                             st["topic_overlap"])
    for p in res["proposals"]:
        if p["legit"]["discounts"].get("repeat"):
            continue                       # already logged inside the repeat window
        rc.append_jsonl(ppath, {"ts": now, "run_id": run["run_id"], "source": source, **{k: p[k] for k in FIELDS},
                                "who": p.get("who"), "effects": p.get("effects"), "topic": p.get("topic") or []}, mx)
        logged += 1
    run.update(status="ok", needs=res["needs"], candidates=len(res["candidates"]), vetoed=len(res["vetoed"]),
               refused=res["refused"], logged=logged, kb_proofs=len(kb), autonomous=ctx["autonomous"],
               deontic_impl=res["deontic_impl"], parser_queries=sum(len(v) for v in q.values()),
               requests=rq or {"dir": "inline" if cfg.get("goal_requests") else "unset"},
               history=len(hist), suppressed=len(res.get("suppressed") or ()))


def _inputs(raw, rec, cfg, now):
    raw = [dict(r) for r in raw or []]
    q = cached_queries(cfg, {r.get("id") for r in raw})
    for r in raw:
        if r.get("id") in q:
            r["queries"] = q[r["id"]]
    kb = [x.get("proof") for x in rec.get("queries") or [] if x.get("ok") and x.get("proof")]
    rq = {}
    oldest = min([needs.item_ts(r, now) for r in raw if r.get("content")] or [now])
    if not cfg.get("goal_requests") and cfg.get("goal_requests_dir"):
        from . import requests as _rq
        # rc2: the reply lookup reaches back to the oldest active item (bounded by goal_history_max_days)
        cfg = dict(cfg, goal_requests=_rq.load(cfg, now, rq, days=_rq.window_days(cfg, oldest, now)))
    if not cfg.get("goal_notes") and cfg.get("goal_journal_closure", True):
        from . import notes as _nt
        ns = {}
        cfg = dict(cfg, goal_notes=_nt.load(cfg, now, ns))
        rq = dict(rq, journal=ns) if rq else {"journal": ns}
    return raw, q, kb, rq, cfg


def _log_proposals(res, ppath, run, source, now, mx, rc):
    logged = 0
    for p in res["proposals"]:
        if p["legit"]["discounts"].get("repeat"):
            continue                       # already logged inside the repeat window
        rc.append_jsonl(ppath, {"ts": now, "run_id": run["run_id"], "source": source, **{k: p[k] for k in FIELDS},
                                "who": p.get("who"), "effects": p.get("effects"), "topic": p.get("topic") or [],
                                **{f: p[f] for f in V2_FIELDS if f in p}}, mx)
        logged += 1
    return logged


def _run_v2(raw, rec, cfg, source, now, run, d, ppath, mx, rc):
    """v0.7 run: the WMTM layers prepare the canary series and the main series; ONE runner process (the v2
    interpreter) answers all of them; the canary must pass before anything is trusted; hold / escalate / blocked
    reviews go to runs.jsonl only.  An automated run asks v2 for two passes over the same domain: "automated"
    (automated_turn detected: v2's norms forbid every message action) for the log, and "human" for the
    display-only message suggestions (Track T)."""
    if rec.get("status") != "ok":
        run["status"] = "shadow_canary_fail"      # the shared sanity gate failed: trust nothing, do not start v2
        run["canary"] = {"ok": False, "skipped": "shadow_canary_fail", "engine": v2.ENGINE}
        return
    raw, q, kb, rq, cfg = _inputs(raw, rec, cfg, now)
    st = settings(cfg)
    ents = []
    recent, hist = _recent(ppath, now, st["repeat_s"], st["reask_s"], os.path.join(d, ASKED), ents)
    auto = source == "automated"
    ctx = {"autonomous": auto, "recent": recent, "history": hist, "recent_entries": ents}
    main_pass = "automated" if auto else "human"
    main = prepare_v2(raw, cfg, ctx, now=now, kb=kb, label="main", passes=("automated", "human") if auto else ("human",))
    pos, neg = canary_v2_prepare(cfg)
    vc = v2_cfg(cfg)
    wd = os.path.join(d, ".v2work-" + run["run_id"])     # per-run scratch (domain, motivation stream); removed after
    t0 = time.time()
    jobs = [j["job"] for j in (pos, neg, main) if j["amap"]]
    run["v2"] = {"release": vc.get("goal_v2_release"), "series": len(jobs), "actions": len(main["amap"])}
    try:
        res = v2.client({"series": jobs}, vc, wd)
    except v2.V2Error as e:
        run["v2"].update(status=e.status, s=round(time.time() - t0, 3))
        run["status"] = e.status; run["error"] = str(e)[:300]
        run["canary"] = {"ok": False, "engine": v2.ENGINE, "error": e.status}
        return
    finally:
        v2.cleanup(wd)
    by = {s.get("label"): s for s in res["series"]}
    run["v2"].update(status="ok", s=round(time.time() - t0, 3), runner_s=res.get("s"), maxrss_mb=res.get("maxrss_mb"),
                     versions=res.get("versions"))
    can = canary_v2_check(pos, neg, by); run["canary"] = can
    if not can.get("ok"):
        run["status"] = "canary_fail"
        return
    try:
        r = finish_v2(main, by.get("main"), main_pass)
    except v2.V2Error as e:
        run["v2"]["status"] = e.status
        run["status"] = e.status; run["error"] = str(e)[:300]
        return
    dmix = {}
    for x in r["decisions"]:
        dmix[x.get("disposition")] = dmix.get(x.get("disposition"), 0) + 1
    run["v2"].update(decisions=dmix, reviews=r["decisions"][-6:])
    run["_latest"] = [p for p in r["proposals"] if p.get("status") == "proposed" and p["legit"].get("d", 0) > 0]
    if auto:
        dh = finish_v2(main, by.get("main"), "human")
        shown = [dict(p, display_only=True) for p in dh["proposals"] if p["action"] in actions.MESSAGE_ACTIONS
                 and p.get("status") == "proposed" and p["legit"].get("d", 0) > 0 and not check_proposal(p)]
        run["_latest"] += shown
        run["display_only"] = len(shown)
        run["display_logged"] = log_display(d, run, source, now, shown, max(st["repeat_s"], st["reask_s"]), mx, rc,
                                             st["topic_overlap"])
        run["v2"]["display_decisions"] = [x.get("disposition") for x in dh["decisions"]]
    logged = _log_proposals(r, ppath, run, source, now, mx, rc)
    run.update(status="ok", needs=r["needs"], candidates=len(r["candidates"]), vetoed=len(r["vetoed"]),
               refused=r["refused"], logged=logged, kb_proofs=len(kb), autonomous=auto,
               deontic_impl=r["deontic_impl"], parser_queries=sum(len(v) for v in q.values()),
               requests=rq or {"dir": "inline" if cfg.get("goal_requests") else "unset"},
               history=len(hist), suppressed=len(r.get("suppressed") or ()))
