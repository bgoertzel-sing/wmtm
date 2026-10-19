"""Track Q: speaker linking (synthetic names and ids only; LLM mocked)."""
import json, os

from wmtm import semparse_speaker as ss
from wmtm import semparse_adapter as sp
from wmtm import parse_cache as pcm
from wmtm import runtime_config as rc

M = {"111": "zed", "222": "quinn", "zedhandle": "zed"}


def test_resolve_from_source_id_and_username():
    assert ss.resolve("The user asked.", {"user_id": 111}, M) == ("zed", "source:user_id")
    assert ss.resolve("x", {"sender_username": "@ZedHandle"}, M) == ("zed", "source:sender_username")
    assert ss.resolve("Quinn asked.", {"user_id": 999}, M) == (None, "source_unmapped")   # never guess


def test_resolve_from_text_meta_request_phrase_and_unresolved():
    assert ss.resolve('msg user_id=222 sender_is_bot=false', None, M) == ("quinn", "text:meta")
    assert ss.resolve("user_id=111 and user_id=222", None, M)[0] is None
    assert ss.resolve("Answered zedhandle's 10:00 request.", None, M) == ("zed", "text:request")
    assert ss.resolve("The user asked something.", None, M) == (None, "unresolved")
    assert ss.resolve("anything", None, {}) == (None, "no_map")


def test_link_names_speaker_bot_and_handles():
    t, info = ss.link("Answered the user's 10:00 request. I fixed my bug; the requester was happy.",
                      {"user_id": "111"}, M, "botty")
    assert t.startswith("Speaker: Zed. ")
    assert "Zed's 10:00 request" in t and "Zed was happy" in t
    assert "Botty fixed Botty's bug" in t and " I " not in t
    assert info["speaker"] == "zed" and info["subs"] >= 4
    t, _ = ss.link("zedhandle asked about BOTTY.", None, M, "botty")
    assert "Zed asked about Botty." in t                      # handle -> canonical, bot name canonical


def test_link_first_person_of_speaker_and_track_labels():
    t, _ = ss.link("I want a report.", {"user_id": 222, "first_person": "speaker"}, M, "botty")
    assert t == "Speaker: Quinn. Quinn want a report."
    t, _ = ss.link("Track I done; I1 pinned; Track-I ok. I checked.", None, M, "botty")
    assert "Track I done" in t and "I1" in t and "Botty checked" in t


def test_unresolved_text_unchanged_except_bot():
    t, info = ss.link("The user asked; I answered.", None, M, "botty")
    assert t == "The user asked; Botty answered." and info["speaker"] is None


def test_flags_file_keys(tmp_path, monkeypatch):
    for k in ("WMTM_SPEAKER_LINK", "WMTM_SPEAKER_MAP", "WMTM_SPEAKER_SELF"):
        monkeypatch.delenv(k, raising=False)
    cfg = rc.resolve(str(tmp_path))
    assert cfg["speaker_link"] is False and cfg["speaker_map"] == {} and cfg["speaker_self"] == ""
    (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"speaker_link": True, "speaker_map": M,
                                                          "speaker_self": "botty"}))
    cfg = rc.resolve(str(tmp_path))
    assert cfg["speaker_link"] and cfg["speaker_map"] == M and "unknown_keys" not in cfg["_source"]
    (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"speaker_map": ["bad"]}))
    assert rc.resolve(str(tmp_path))["speaker_map"] == {}


def _ad(replies):
    calls = []

    def llm(system, user):
        calls.append(user)
        return replies.pop(0) if replies else ""
    return sp.SemParseAdapter(llm, system="SYS"), calls


def _cfg(tmp_path, **kw):
    cfg = dict(rc.resolve()); cfg.update(semparse_dir=str(tmp_path / "base"), parse_cap_per_hour=10,
                                         speaker_link=True, speaker_map=M, speaker_self="botty", **kw)
    return cfg


def test_spk_cache_version_new_dir_old_cache_untouched_and_source_kept(tmp_path):
    cfg = _cfg(tmp_path)
    base = pcm.ParseCache(cfg=cfg)
    base.enqueue([("n0", "Old note about the user.", 1.0)])
    h0 = next(iter(base._queue())); base.record(h0, base._queue()[h0], "ok", ["(: a (Member sk_user_1 user) (STV 1.0 0.99))"], {"ts": 1})
    before = open(base.entries_path).read()
    spk = pcm.speaker_cache(cfg, base)
    assert spk.d == str(tmp_path / "base" / "spk1")
    spk.enqueue([("n1", "The user asked for a map.", 1.0, {"user_id": 111}),
                 ("n2", "The user asked again.", 1.0, {"user_id": 222})])
    ad, calls = _ad(["(: e (Agent sk_ask_1 zed) (STV 1.0 0.99))", "(: e (Agent sk_ask_1 quinn) (STV 1.0 0.99))"])
    out = pcm.process_queue_spk(spk, ad.llm, ad, cfg=cfg, base=base)
    assert [o["speaker"] for o in out] == ["zed", "quinn"] and all(o["cache_version"] == "spk1" for o in out)
    assert calls[0] == "TEXT: Speaker: Zed. Zed asked for a map."
    e = spk.entries()
    assert {v["speaker"] for v in e.values()} == {"zed", "quinn"}
    assert all(v["cache_version"] == "spk1" and v["speaker_source"] == "source:user_id" for v in e.values())
    # keyed by the ORIGINAL content, so lookups by item content work
    assert spk.atoms_for("The user asked for a map.") == ["(: i_n1__e (Agent sk_ask_1__i_n1 zed) (STV 1.0 0.99))"]
    assert open(base.entries_path).read() == before          # no rewrite, no backfill
    assert not os.path.exists(os.path.join(base.d, "ctx1"))


def test_feed_routes_to_spk1_only_when_flag_on(tmp_path, monkeypatch):
    monkeypatch.setattr(pcm, "launch_worker", lambda cache, cfg, pending=None: cache.d)
    cfg = _cfg(tmp_path, semparse_feed=True)
    assert pcm.feed_rows([("n1", "hello there", 1.0)], cfg) == str(tmp_path / "base" / "spk1")
    cfg["speaker_link"] = False
    assert pcm.feed_rows([("n1", "hello there", 1.0)], cfg) == str(tmp_path / "base")


def test_shadow_lookup_prefers_spk1(tmp_path):
    from wmtm import pc_shadow
    from wmtm.store import WMTMStore
    cfg = _cfg(tmp_path)
    base = pcm.ParseCache(cfg=cfg); spk = pcm.speaker_cache(cfg, base)
    for c, atoms in ((base, ["(: a (Member sk_user_1 user) (STV 1.0 0.99))"]),
                     (spk, ["(: a (Member zed person) (STV 1.0 0.99))"])):
        c.enqueue([("n1", "The user is a person.", 1.0)])
        h = next(iter(c._queue())); c.record(h, c._queue()[h], "ok", atoms, {"ts": 1})
    st = WMTMStore(); st.admit("n1", "The user is a person.", source_type="recalled", initial_sti=1.0)
    items = st.get_active_set()
    assert "sk_user_1" in pc_shadow._cache_lookup(items, base.d)["n1"][0]
    assert "zed" in pc_shadow._cache_lookup(items, base.d, speaker=True)["n1"][0]
