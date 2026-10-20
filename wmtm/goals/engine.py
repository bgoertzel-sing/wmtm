"""Track R: scoring, structural check, goal canary and the log-only shadow hook."""
from __future__ import annotations

import json
import math
import os
import time

from . import actions, legitimacy, needs

SUBDIR = "goalchainer"
NEEDS = ("unc", "comp")
FIELDS = ("id", "action", "need", "text", "why", "score", "urge", "cons", "legit", "status", "items")


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
            "reask_s": float(cfg.get("goal_reask_s", 3 * 86400.0))}


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
            dup = next((k for k in kept if k is not c and k["who"] == c.get("who") and needs.topic_match(ks, set(k.get("topic") or ()))),
                       None)
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


def _recent(path, now, window, hist_window=0.0):
    """Proposal ids logged within window (repeat discount) and the logged proposals within hist_window as
    {ts, who, topic, action} (R2 re-ask rule).  Reads the tail of proposals.jsonl only."""
    keys, hist = set(), []
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2); n = fh.tell(); fh.seek(max(0, n - 262144))
            for line in fh.read().decode("utf-8", "replace").splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(e, dict):
                    continue
                age = now - float(e.get("ts") or 0)
                if age <= window:
                    keys.add(e.get("id"))
                if age < hist_window and e.get("who"):
                    hist.append({"ts": float(e["ts"]), "who": e["who"], "topic": list(e.get("topic") or ()),
                                 "action": e.get("action")})
    except OSError:
        pass
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
    budget = float(cfg.get("goal_budget_s", 10.0) or 0)
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
    write_latest(d, run, latest if run.get("status") == "ok" else [])
    return run


LATEST = "latest.json"
LATEST_FIELDS = ("id", "action", "need", "text", "who", "score", "status")


def write_latest(d, run, proposals):
    """Track S: <d>/latest.json = this run's time, status, canary result and ALL its proposals (repeats included;
    proposals.jsonl holds new ones only).  A failed run writes an empty list, so an older run's suggestions never
    survive it.  Atomic (tmp + os.replace).  Never raises."""
    try:
        can = run.get("canary") or {}
        if run.get("status") != "ok":
            proposals = []
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
    can = goal_canary(cfg); run["canary"] = can
    if rec.get("status") != "ok":
        run["status"] = "shadow_canary_fail"      # the shared sanity gate failed: trust nothing this run
        return
    if not can.get("ok"):
        run["status"] = "canary_fail"
        return
    raw = [dict(r) for r in raw or []]
    q = cached_queries(cfg, {r.get("id") for r in raw})
    for r in raw:
        if r.get("id") in q:
            r["queries"] = q[r["id"]]
    kb = [x.get("proof") for x in rec.get("queries") or [] if x.get("ok") and x.get("proof")]
    st = settings(cfg)
    rq = {}
    if not cfg.get("goal_requests") and cfg.get("goal_requests_dir"):
        from . import requests as _rq
        cfg = dict(cfg, goal_requests=_rq.load(cfg, now, rq))
    recent, hist = _recent(ppath, now, st["repeat_s"], st["reask_s"])
    ctx = {"autonomous": source == "automated", "recent": recent, "history": hist}
    res = propose(raw, cfg, ctx, now=now, kb=kb)
    logged = 0
    run["_latest"] = [p for p in res["proposals"] if p.get("status") == "proposed" and p["legit"].get("d", 0) > 0]
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
