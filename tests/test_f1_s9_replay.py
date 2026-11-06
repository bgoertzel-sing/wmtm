"""F1 §9 through the replay harness (review 1 fix): the real Iter transform path, one process per step, frozen
clock.  One seeded state + one admission file ('dog is a animal' at (0.6, 0.15) from two live notes) plus a
30-hour-old zero-utility derived note go through (a) an automated tick and (b) a user turn on the new tree.
Required: same stored memory (items, STI, utility) and same forgetting log.  Negative control: forget_one_rule
off -> the paths differ."""
import json, os
from pathlib import Path
import pytest

from replay import driver, scenarios

T0 = scenarios.BASE + 7200
R_DOG = {"goal": "(Inheritance dog animal)", "stv": [0.6, 0.15], "proof": "(inh_trans sp0 sp1)", "s": 0.3,
         "sources": ["s0", "s1"]}


def _item(iid, text, sti, util, age_s):
    return {"id": iid, "content": text, "source_type": "derived", "origin_cluster": iid, "derived_from": [],
            "attention": {"sti": sti, "ati": 0.0, "lti": 0.0, "sti_decay": 0.9}, "age": 0, "utility": util,
            "last_used": 0, "created_at": T0 - age_s, "origin_timestamp": 0.0}


def _state():
    items = {"s0": _item("s0", "The tabby housecat is a kind of mammal", 10.0, 5.0, 60),
             "s1": _item("s1", "Mammals are vertebrate animals with fur", 9.0, 5.0, 60),
             "d-old": _item("d-old", "synthetic stale derived note about a parked bicycle", 3.0, 0.0, 30 * 3600)}
    return json.dumps({"cycle": 7, "store": {"capacity": 60, "tick": 0, "items": items}})


def _run(tmp_path, name, text, one_rule):
    root = tmp_path / name
    driver.build_new_tree(root)
    base = driver.seed_memory(root, _state(), "")
    mem = root / "memory"
    (mem / "_wmtm_flags.json").write_text(json.dumps({
        "reasoner": "pettachainer", "pc_shadow": False, "semparse_feed": False, "forget_one_rule": one_rule,
        "shadow_min_interval_s": 3600}))
    sh = mem / "_wmtm_shadow" / "pc_shadow"
    sh.mkdir(parents=True)
    (sh / "admit.json").write_text(json.dumps({"ts": T0 - 9, "spec_ts": T0 - 10, "cycle": 0, "status": "ok",
                                               "canary_ok": True, "results": [R_DOG]}))
    stamp = sh / "last_launch"            # rate-limit the worker launch at the frozen clock: no real worker spawns
    stamp.write_text("")
    os.utime(stamp, (T0 - 1, T0 - 1))
    steps = [{"kind": "turn", "t": T0, "messages": [scenarios.SYS, scenarios.U(T0, text)]}]
    r = driver.run(root, steps, "fresh", str(driver.REPO), base)
    assert not (sh / "worker.pid").exists(), "a real worker was launched"
    st = json.loads(r[0]["files"]["memory/_wmtm_state.json"])
    items = {v["content"]: (round(v["attention"]["sti"], 6), round(v.get("utility", 0.0), 6))
             for v in st["store"]["items"].values()}
    forgot = sorted((x["item_id"], x["content_hash"], x["evicted_at_tick"])
                    for x in (st.get("forgetting_log") or {}).get("records", []))
    return items, forgot, r


AUTO = scenarios.AUTO_CONTINUE
USER = "[demo] tell me about dogs please"
USER_STORED = "tell me about dogs please"


def test_s9_replay_auto_tick_and_user_turn_same_memory(tmp_path):
    a_items, a_forgot, ra = _run(tmp_path, "auto", AUTO, True)
    u_items, u_forgot, ru = _run(tmp_path, "user", USER, True)
    # sanity: the scenario exercises both rules (admission and stale forgetting)
    assert "dog is a animal" in a_items, (a_items, ra[0]["stderr"][-2000:])
    assert [f[0] for f in a_forgot] == ["d-old"], a_forgot
    # the user turn also stores the user's own message (the input differs by design); compare everything else
    u_items = {k: v for k, v in u_items.items() if k != USER_STORED}
    assert set(a_items) == set(u_items)
    assert a_items == u_items              # same STI and utility per item
    assert a_forgot == u_forgot


def test_s9_replay_control_one_rule_off_diverges(tmp_path):
    a_items, a_forgot, _ = _run(tmp_path, "auto", AUTO, False)
    u_items, u_forgot, _ = _run(tmp_path, "user", USER, False)
    u_items = {k: v for k, v in u_items.items() if k != USER_STORED}
    assert (a_items, a_forgot) != (u_items, u_forgot)
