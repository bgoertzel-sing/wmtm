"""Track N: Design A goal ranking (synthetic data only)."""
from types import SimpleNamespace as NS
from wmtm import pc_shadow as ps


def test_pool_chains_up_to_three_hops():
    rel = {("Inheritance", "a", "b"), ("Inheritance", "b", "c"), ("Inheritance", "c", "d"), ("Inheritance", "d", "e"),
           ("Member", "x", "a")}
    p = ps.goal_pool(rel, max_hops=3)
    assert p[("Inheritance", "a", "c")][0] == 1 and p[("Inheritance", "a", "d")][0] == 2
    assert p[("Inheritance", "a", "e")][0] == 3 and ("Inheritance", "a", "f") not in p
    assert p[("Member", "x", "d")][0] == 3 and ("Member", "x", "e") not in p      # Member + 3 Inheritance steps
    assert ("Inheritance", "a", "b") not in p                                     # asserted
    assert ps.goal_pool(rel, max_hops=1).keys() == {("Inheritance", "a", "c"), ("Inheritance", "b", "d"),
                                                     ("Inheritance", "c", "e"), ("Member", "x", "b")}


def test_pool_cycles_and_skolem():
    rel = {("Implies", "p", "q"), ("Implies", "q", "p"), ("Member", "sk_a__i1", "q"), ("Inheritance", "q", "r")}
    p = ps.goal_pool(rel)
    assert all(t[1] != t[2] for t in p) and not any("sk_" in t[1] for t in p)


def test_rank_echo_and_broad_category_lose():
    rel = {("Member", "path_x", "path_like"), ("Inheritance", "path_like", "path"),
           ("Member", "rex", "dog"), ("Inheritance", "dog", "mammal")}
    for i in range(6):
        rel |= {("Member", "e%d" % i, "entry_k"), ("Inheritance", "entry_k", "entry")}
    r = dict(ps.rank_goals(ps.goal_pool(rel), rel))
    assert r["(Member path_x path)"]["echo"] and r["(Member path_x path)"]["info"] == 0.0
    assert r["(Member rex mammal)"]["score"] > r["(Member e0 entry)"]["score"] > 0
    assert r["(Member rex mammal)"]["score"] > r["(Member path_x path)"]["score"]


def test_rank_request_overlap_hops_and_min_hops():
    rel = {("Member", "rex", "dog"), ("Inheritance", "dog", "mammal"), ("Inheritance", "mammal", "animal"),
           ("Member", "tom", "cat"), ("Inheritance", "cat", "feline")}
    pool = ps.goal_pool(rel)
    plain = dict(ps.rank_goals(pool, rel))
    assert plain["(Member rex animal)"]["hops"] == 2 and plain["(Member rex animal)"]["score"] > plain["(Member rex mammal)"]["score"]
    anchored = ps.rank_goals(pool, rel, req=({"tom"}, set()))
    assert anchored[0][0] == "(Member tom feline)" and anchored[0][1]["overlap"] == 1.0
    assert [g for g, m in ps.rank_goals(pool, rel, min_hops=2)] == ["(Member rex animal)"]
    assert len(ps.rank_goals(pool, rel, max_goals=2)) == 2


def test_request_terms_from_user_item_and_neighbours():
    users = [NS(id="u", content="Is tom a feline?")]
    ents, toks = ps.request_terms({"u": [("Member", "tom", "cat")]}, users, {("Member", "tom", "cat"), ("Inheritance", "cat", "feline")})
    assert {"tom", "cat", "feline"} <= ents and "feline" in toks and "is" not in toks


def test_weights_parse():
    assert ps._weights("1,2,3,4") == (1.0, 2.0, 3.0, 4.0) and ps._weights("x") == ps.GOAL_WEIGHTS and ps._weights("1,2") == ps.GOAL_WEIGHTS


def test_snapshot_ranked_and_source_type_roundtrip(monkeypatch):
    from wmtm.store import WMTMStore
    import _fake_semparse; _fake_semparse.install(monkeypatch)
    st = WMTMStore()
    for i, t in enumerate(["cat is a mammal", "mammal is a animal", "rain -> wet", "wet -> slippery"]):
        st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0 - i * 0.01)
    st.admit("u0", "rain -> wet", source_type="user", initial_sti=0.5)
    spec = ps.build_snapshot(st, cycle=1, k=200)
    assert spec["goal_rank"]["user_items"] == 1 and spec["goals"][0] == "(Implies rain slippery)"
    assert spec["goal_meta"]["(Implies rain slippery)"]["overlap"] == 1.0
    raw = [ps.raw_item(it) for it in st.get_active_set()]
    assert any(r["source_type"] == "user" for r in raw)
    full = ps.snapshot_from_raw({"raw_items": raw, "cycle": 1, "k": 200, "ts": 0})
    assert full["goals"] == spec["goals"]
    monkeypatch.setenv("WMTM_PC_SHADOW_GOAL_RANK", "0")
    off = ps.build_snapshot(st, cycle=1, k=200)
    assert off["goal_rank"] is None and "(Implies rain slippery)" in off["goals"]
