"""Track O: CONTEXT coreference helpers + adapter context path (LLM mocked)."""
from wmtm import semparse_adapter as sp
from wmtm import semparse_context as sc

CTX = ["(: i_n1__maya_name (Name maya \"Maya\") (STV 1.0 0.99))",
       "(: i_n1__e_k (Member sk_kitten_1__i_n1 kitten) (STV 1.0 0.99))"]


def test_user_message_plain_and_context():
    assert sc.user_message("hi") == "TEXT: hi"
    m = sc.user_message("The kitten slept.", CTX)
    assert m.startswith("CONTEXT:\n") and "\n\nTEXT:\nThe kitten slept." in m and CTX[1] in m


def test_atom_terms_and_body():
    assert sc.atom_body(CTX[1]) == "(Member sk_kitten_1__i_n1 kitten) (STV 1.0 0.99)"
    t = sc.atom_terms(CTX)
    assert {"maya", "kitten"} <= t and not any(x.startswith("i_") for x in t)


def test_select_context_shared_terms_then_recency_and_caps():
    early = [{"item_id": "n1", "atoms": CTX, "ts": 1},
             {"item_id": "n2", "atoms": ["(: i_n2__a (Inheritance dog animal) (STV 1.0 0.99))"], "ts": 5},
             {"item_id": "n3", "atoms": [], "ts": 9}]
    atoms, ids, shared = sc.select_context("The kitten scratched Maya.", early)
    assert ids == ["n1"] and "kitten" in shared and atoms == CTX
    atoms, ids, _ = sc.select_context("Nothing related here whatsoever.", early)
    assert ids == ["n2"]                                     # recency fallback, empty notes ignored
    atoms, ids, _ = sc.select_context("kitten maya", early, max_atoms=1)
    assert atoms == CTX[:1]


def test_split_passages():
    assert sc.split_passages("short.") == ["short."]
    t = " ".join("Sentence number %d is here." % i for i in range(60))
    ps = sc.split_passages(t, 200)
    assert len(ps) > 1 and all(len(p) <= 200 for p in ps) and " ".join(ps).split() == t.split()
    long1 = "x" * 450
    assert all(len(p) <= 200 for p in sc.split_passages(long1, 200))


def _ad(replies):
    calls = []

    def llm(system, user):
        calls.append(user)
        return replies.pop(0) if replies else ""
    return sp.SemParseAdapter(llm, system="SYS"), calls


def test_context_symbol_reused_new_witness_scoped_and_reemits_dropped():
    reply = ("(: e_s (Member sk_scratch_1 scratch) (STV 1.0 0.99))\n"
             "(: e_a (Agent sk_scratch_1 sk_kitten_1__i_n1) (STV 1.0 0.99))\n"
             "(: e_k (Member sk_kitten_1__i_n1 kitten) (STV 1.0 0.99))")   # last = context re-emit
    ad, calls = _ad([reply])
    r = ad.parse_item("n2", "The kitten scratched her.", context_atoms=CTX)
    assert calls[0].startswith("CONTEXT:")
    assert any("(Agent sk_scratch_1__i_n2 sk_kitten_1__i_n1)" in a for a in r.accepted)
    assert len(r.accepted) == 2 and any(why == "context atom re-emitted" for _, why in r.rejected)


def test_parse_item_ctx_passages_share_note_scope():
    replies = ["(: e1 (Member sk_report_1 report) (STV 1.0 0.99))",
               "(: e2 (Inheritance report document) (STV 1.0 0.99))"]
    ad, calls = _ad(replies)
    text = ("A report arrived today. " * 20).strip() + " " + ("Reports are documents. " * 5).strip()
    r = ad.parse_item_ctx("n5", text, context_atoms=(), passage_chars=300)
    assert len(calls) >= 2 and calls[0].startswith("TEXT: ") and calls[1].startswith("CONTEXT:")
    assert "sk_report_1__i_n5" in calls[1]                    # passage 2 sees passage 1's atoms
    assert any("sk_report_1__i_n5 " in a for a in r.accepted) and r.error is None
    assert any(a.startswith("(: i_n5_p1__e2") for a in r.accepted)


def test_no_context_path_unchanged():
    ad, calls = _ad(["(: e (Inheritance cat animal) (STV 1.0 0.99))"])
    r = ad.parse_item("x", "Cats are animals.")
    assert calls == ["TEXT: Cats are animals."] and r.accepted == ["(: i_x__e (Inheritance cat animal) (STV 1.0 0.99))"]


def test_process_queue_ctx_writes_new_cache_version_only(tmp_path):
    from wmtm import parse_cache as pcm
    from wmtm import runtime_config as rc
    cfg = dict(rc.resolve()); cfg.update(semparse_dir=str(tmp_path / "base"), parse_cap_per_hour=10)
    base = pcm.ParseCache(cfg=cfg)
    base.enqueue([("n1", "Maya adopted a kitten.", 1.0)])
    h1 = next(iter(base._queue()))
    base.record(h1, base._queue()[h1], "ok", CTX, {"ts": 1.0})
    before = open(base.entries_path).read()
    ctx = pcm.context_cache(cfg, base)
    assert ctx.d == str(tmp_path / "base" / "ctx1")
    ctx.enqueue([("n2", "The kitten scratched Maya.", 1.0)])
    ad, calls = _ad(["(: e_a (Agent sk_scratch_1 sk_kitten_1__i_n1) (STV 1.0 0.99))"])
    out = pcm.process_queue_ctx(ctx, base, ad.llm, ad, cfg=cfg)
    assert out[0]["status"] == "ok" and out[0]["context_ids"] == ["n1"] and calls[0].startswith("CONTEXT:")
    e = list(ctx.entries().values())[0]
    assert e["cache_version"] == "ctx1" and e["context_ids"] == ["n1"]
    assert "(Agent sk_scratch_1__i_n2 sk_kitten_1__i_n1)" in e["atoms"][0]
    assert open(base.entries_path).read() == before            # existing cache untouched


def test_process_queue_ctx_order_excludes_later_notes(tmp_path):
    from wmtm import parse_cache as pcm
    from wmtm import runtime_config as rc
    cfg = dict(rc.resolve()); cfg.update(semparse_dir=str(tmp_path / "base"), parse_cap_per_hour=10)
    base = pcm.ParseCache(cfg=cfg)
    base.enqueue([("n9", "Maya adopted a kitten.", 1.0)])
    h = next(iter(base._queue())); base.record(h, base._queue()[h], "ok", CTX, {"ts": 1.0})
    ctx = pcm.context_cache(cfg, base)
    ctx.enqueue([("n2", "The kitten scratched Maya.", 1.0)])
    ad, calls = _ad(["(: e (Member sk_scratch_1 scratch) (STV 1.0 0.99))"])
    out = pcm.process_queue_ctx(ctx, base, ad.llm, ad, cfg=cfg, order=str)
    assert out[0]["context_ids"] == [] and calls[0].startswith("TEXT: ")      # n9 is later than n2


def test_split_passages_drops_markup_tags():
    t = ("Word " * 130).strip() + ". <!-- project: path:/x/y -->"
    ps = sc.split_passages(t, 600)
    assert all("<!--" not in p for p in ps) and " ".join(ps).split()[-1] == "Word."
    assert sc.split_passages("<!-- only a tag -->") == []


def test_flags_key_semparse_context_default_off_and_routes_feed(tmp_path, monkeypatch):
    import json, os
    from wmtm import parse_cache as pcm
    from wmtm import runtime_config as rc
    from wmtm import pc_shadow
    monkeypatch.delenv("WMTM_SEMPARSE_CONTEXT", raising=False)
    monkeypatch.setattr(pcm, "launch_worker", lambda cache, cfg=None, pending=None, **k: cache.d)
    assert rc.resolve(str(tmp_path))["semparse_context"] is False
    base_dir = str(tmp_path / "sp")
    cfg = dict(rc.resolve(str(tmp_path)), semparse_feed=True, semparse_dir=base_dir)
    assert pcm.feed_rows([("n1", "Cats are animals.", 1.0)], cfg) == base_dir      # default: base cache
    assert not os.path.exists(os.path.join(base_dir, "ctx1"))
    (tmp_path / "_wmtm_flags.json").write_text(json.dumps({"semparse_context": True}))
    cfg2 = dict(rc.resolve(str(tmp_path)), semparse_feed=True, semparse_dir=base_dir)
    assert cfg2["semparse_context"] is True
    assert pcm.feed_rows([("n2", "Dogs are animals.", 1.0)], cfg2) == os.path.join(base_dir, "ctx1")
    ctx = pcm.ParseCache(os.path.join(base_dir, "ctx1"), cfg=cfg2)
    h = next(iter(ctx._queue())); ctx.record(h, ctx._queue()[h], "ok", ["(: x (Inheritance dog animal) (STV 1.0 0.99))"], {"ts": 1.0})
    from types import SimpleNamespace as NS
    it = NS(id="n2", content="Dogs are animals.")
    assert pc_shadow._cache_lookup([it], base_dir) == {}                      # context off: ctx1 ignored
    assert pc_shadow._cache_lookup([it], base_dir, context=True)["n2"]
