"""F1 section 9 (t-2026-11-06-wmtm-f1-memory), acceptance condition 9: the automated fast path and the user-turn
cycle evict and forget by one rule.  The same starting state and run leave the same memory (items, STI, utility,
forgetting log, cycle).  Negative control: forget_one_rule off (the rc2 JSON-only fast path) -> the paths diverge."""
import copy, json, os, time
import pytest
from wmtm import context as ctx, runtime_config as rc
from wmtm.store import WMTMStore
from wmtm.orchestrator import WMTMOrchestrator


def _item(iid, text, st, sti, util, age_h, now, srcs=()):
    return {"id": iid, "content": text, "source_type": st, "origin_cluster": iid if st == "recalled" else None,
            "derived_from": list(srcs), "attention": {"sti": sti, "ati": 0.0, "lti": 0.0, "sti_decay": 0.9,
            "ati_decay": 0.97, "lti_decay": 0.995, "sti_to_ati_rate": 0.05, "ati_to_lti_rate": 0.02},
            "age": 3, "utility": util, "last_used": 0, "created_at": now - age_h * 3600, "origin_timestamp": 0.0}


def _snapshot(now):
    items = {}
    for k, v in {
        "r-keep": ("synthetic rex is a dog", "recalled", 8.0, 4.0, 2.0, ()),
        "r-stale": ("synthetic old vet visit note", "recalled", 6.0, 0.0, 60.0, ()),        # 48 h zero-utility tier
        "d-low": ("synthetic rex is a mammal by deduction", "derived", 0.105, 4.0, 0.2, ("r-keep",)),  # STI floor
        "d-ok": ("synthetic dogs are animals by deduction", "derived", 5.0, 4.0, 0.2, ("r-keep",)),
        "r-floor": ("synthetic faint memory of a walk", "recalled", 0.011, 4.0, 2.0, ()),      # store tick floor
    }.items():
        items[k] = _item(k, *v[:5], now, v[5])
    return {"cycle": 17, "store": {"capacity": 200, "tick": 17, "items": items},
            "utility": {"records": {}}, "forgetting_log": {"max_records": 500, "records": []}}


def _flags(d, **kw):
    kw = dict({"reasoner": "off", "pc_shadow": False, "semparse_feed": False}, **kw)
    (d / rc.FLAGS_FILENAME).write_text(json.dumps(kw))


def _fast(tmp_path, snap):
    sf = tmp_path / "_wmtm_state.json"
    sf.write_text(json.dumps(snap))
    ctx.fast_path_automated(str(sf), run_hooks=False, admit=False)
    return json.loads(sf.read_text())


def _cycle(tmp_path, snap):
    cfg = rc.resolve(str(tmp_path))
    o = WMTMOrchestrator(WMTMStore(), use_pln=False, use_goalchainer=False)
    o.restore_state(copy.deepcopy(snap))
    o.stale_cleanup(protect=ctx.protect_settings(cfg))     # the user turn's cleanup, then the cycle
    o.cycle()
    return o.snapshot_state()


def _memory(s):
    items = s["store"]["items"]
    return {"items": {k: (round(v["attention"]["sti"], 9), round(v.get("utility", 0.0), 9)) for k, v in items.items()},
            "forgot": sorted((r["item_id"], r["content_hash"], r["evicted_at_tick"], tuple(r.get("derived_from") or []))
                             for r in s["forgetting_log"]["records"]),
            "cycle": s["cycle"]}


def test_fast_path_and_cycle_leave_same_memory(tmp_path, monkeypatch):
    monkeypatch.delenv("WMTM_FORGET_ONE_RULE", raising=False)
    _flags(tmp_path)
    snap = _snapshot(time.time())
    a, b = _memory(_fast(tmp_path, copy.deepcopy(snap))), _memory(_cycle(tmp_path, snap))
    assert a == b
    # sanity: the run exercised every rule (stale tier, derived STI threshold, store floor) and kept the rest
    assert set(a["items"]) == {"r-keep", "d-ok"}
    assert {f[0] for f in a["forgot"]} == {"r-stale", "d-low", "r-floor"} and a["cycle"] == 18


def test_control_rc2_fast_path_diverges(tmp_path, monkeypatch):
    monkeypatch.delenv("WMTM_FORGET_ONE_RULE", raising=False)
    _flags(tmp_path, forget_one_rule=False)
    snap = _snapshot(time.time())
    a, b = _memory(_fast(tmp_path, copy.deepcopy(snap))), _memory(_cycle(tmp_path, snap))
    assert a != b
    assert a["forgot"] == [] and "d-low" in a["items"]      # rc2: no forgetting log, no derived STI threshold
