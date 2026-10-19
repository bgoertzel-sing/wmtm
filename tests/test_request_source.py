"""Track Q wiring (rc4): request metadata on the source_type=user request item -> semparse feed -> speaker linking.
Synthetic ids, usernames and names only; no LLM (adapter mocked)."""
import json

import pytest

from wmtm import context as ctx
from wmtm import parse_cache as pcm
from wmtm import request_source as rs
from wmtm import runtime_config as rc
from wmtm import semparse_adapter as sp
from wmtm import semparse_speaker as ss
from wmtm.api import WMTM, WMTMConfig

M = {"111": "zed", "zedhandle": "zed", "222": "quinn"}
RID = "ab" * 32
Q = "I want the otter-lamp hinge report by Friday please"


class NoJournal:
    def read_lines(self):
        return []

    def append(self, note, supersedes=None, about=None):
        return {"ok": True}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("WMTM_SPEAKER_LINK", "WMTM_SPEAKER_MAP", "WMTM_SPEAKER_SELF", "WMTM_REQUEST_ITEM", "WMTM_REASONER",
              "ITER_REQUEST_IDS", "ITER_OUTER_CHANNEL_ROOT", "WMTM_SEMPARSE_FEED"):
        monkeypatch.delenv(k, raising=False)


def _channel(tmp_path, chat_id, prompt=Q, rid=RID):
    root = tmp_path / "chan"
    (root / "processing").mkdir(parents=True, exist_ok=True)
    (root / "processing" / (rid + ".json")).write_text(json.dumps(
        {"request_id": rid, "prompt": prompt, "source": {"chat_id": chat_id, "message_id": 5, "update_id": 6}}))
    return {"ITER_OUTER_CHANNEL_ROOT": str(root), "ITER_REQUEST_IDS": json.dumps({"chan": rid})}


def test_normalise():
    assert rs.normalise({"chat_id": 111, "message_id": 1}) == {"user_id": 111, "chat_type": "private"}
    assert rs.normalise({"chat_id": -999, "message_id": 1}) == {"chat_type": "group"}
    assert rs.normalise({"chat_id": -999, "user_id": 222, "sender_username": "@x"}) == \
        {"user_id": 222, "sender_username": "@x", "chat_type": "group"}
    assert rs.normalise(None) == {} and rs.normalise({"chat_id": True}) == {}


def test_from_iter_env_bound_unbound_mismatch(tmp_path):
    env = _channel(tmp_path, 111, prompt="<ctx>noise</ctx>\n\n[reply to your message 4] " + Q)
    st = {}
    assert rs.from_iter_env(Q, env, st) == {"user_id": 111, "chat_type": "private"} and st["how"] == "iter_env"
    unbound = {"ITER_OUTER_CHANNEL_ROOT": env["ITER_OUTER_CHANNEL_ROOT"]}
    assert rs.from_iter_env(Q, unbound) == {"user_id": 111, "chat_type": "private"}     # single open request
    assert rs.from_iter_env("a completely different request text", env, st) is None and st["how"] == "request_mismatch"
    assert rs.from_iter_env(Q, {}, st) is None and st["how"] == "no_request"
    assert rs.from_iter_env(Q, dict(env, ITER_REQUEST_IDS=json.dumps({"chan": "../x"}))) is None
    assert rs.from_iter_env(Q, dict(env, ITER_REQUEST_IDS="{bad")) is None
    _channel(tmp_path, 222, rid="cd" * 32)
    assert rs.from_iter_env(Q, unbound) is None                                          # two open, none bound


def _mem(tmp_path, flags):
    sd = tmp_path / "state"; sd.mkdir(exist_ok=True)
    (sd / rc.FLAGS_FILENAME).write_text(json.dumps(flags))
    return WMTM(WMTMConfig(state_dir=sd, journal=NoJournal(), reasoner="off")), sd


def _user_items(sd):
    st = json.loads((sd / "_wmtm_state.json").read_text())
    return [d for d in st["store"]["items"].values() if d["source_type"] == "user"]


def test_request_item_carries_source_from_env_when_speaker_link_on(tmp_path, monkeypatch):
    for k, v in _channel(tmp_path, 111).items():
        monkeypatch.setenv(k, v)
    m, sd = _mem(tmp_path, {"speaker_link": True, "speaker_map": M, "reasoner": "off"})
    m.observe({"user": Q}); m.context_for(Q)
    (u,) = _user_items(sd)
    assert u["source_meta"] == {"user_id": 111, "chat_type": "private", "first_person": "speaker"}


def test_request_item_without_flag_reads_no_env_but_explicit_source_wins(tmp_path, monkeypatch):
    for k, v in _channel(tmp_path, 111).items():
        monkeypatch.setenv(k, v)
    m, sd = _mem(tmp_path, {"reasoner": "off"})
    m.observe({"user": Q}); m.context_for(Q)
    assert _user_items(sd)[0]["source_meta"] == {"first_person": "speaker"}             # rc3 + first_person only
    m.observe({"user": Q + " and Monday"}); m.context_for(Q + " and Monday", source={"chat_id": -5, "user_id": 222})
    assert _user_items(sd)[0]["source_meta"] == {"user_id": 222, "chat_type": "group", "first_person": "speaker"}


def test_rows_carry_source_meta_both_paths():
    from wmtm.store import WMTMStore
    st = WMTMStore()
    it = ctx.admit_request_item(st, Q, 1, {}, source={"user_id": 111})
    st.admit("n1", "a plain note", source_type="recalled", initial_sti=1.0)
    rows = {r[0]: r for r in pcm.top_k_rows(st, 10)}
    assert rows[it.id][3] == {"user_id": 111, "first_person": "speaker"} and len(rows["n1"]) == 3
    d = it.to_dict()
    from wmtm.item import WMTMItem
    assert WMTMItem.from_dict(d).source_meta == d["source_meta"]


def _ad(replies):
    calls = []

    def llm(system, user):
        calls.append(user)
        return replies.pop(0) if replies else ""
    return sp.SemParseAdapter(llm, system="SYS"), calls


def test_request_item_feed_parses_speaker_linked(tmp_path, monkeypatch):
    monkeypatch.setattr(pcm, "launch_worker", lambda cache, cfg, pending=None: cache.d)
    cfg = dict(rc.resolve()); cfg.update(semparse_dir=str(tmp_path / "base"), parse_cap_per_hour=10, semparse_feed=True,
                                         speaker_link=True, speaker_map=M, speaker_self="botty")
    from wmtm.store import WMTMStore
    st = WMTMStore()
    ctx.admit_request_item(st, Q, 1, {}, source=rs.normalise({"chat_id": 111}))
    st.admit("n1", "I answered the user's question.", source_type="recalled", initial_sti=1.0)
    assert pcm.maybe_feed(st, 1, cfg=cfg) == str(tmp_path / "base" / "spk1")
    spk = pcm.speaker_cache(cfg)
    ad, calls = _ad(["(: e (Agent sk_w_1 zed) (STV 1.0 0.99))", "(: e (Agent sk_a_1 botty) (STV 1.0 0.99))"])
    out = pcm.process_queue_spk(spk, ad.llm, ad, cfg=cfg)
    by = {o["item_id"].split("-")[0]: o for o in out}
    assert by["user"]["speaker"] == "zed" and by["user"]["speaker_source"] == "source:user_id"
    assert "TEXT: Speaker: Zed. Zed want the otter-lamp" in calls[[c.count("otter") for c in calls].index(1)]
    assert by["n1"]["speaker"] is None and by["n1"]["speaker_source"] == "unresolved"
    assert any("Botty answered" in c for c in calls)


def test_group_request_falls_back_to_text_routes():
    src = rs.normalise({"chat_id": -77})
    src["first_person"] = "speaker"
    assert ss.resolve("please check this", src, M) == (None, "unresolved")
    t, info = ss.link("I need it, zedhandle asked", src, M, "botty")
    assert info["speaker_source"] == "text:request" and t.startswith("Speaker: Zed. Zed need it")


def test_automated_hook_rows_carry_source_meta(tmp_path, monkeypatch):
    got = {}
    monkeypatch.setattr(pcm, "feed_rows", lambda rows, cfg, skip_unchanged=False: got.setdefault("rows", rows))
    cfg = dict(rc.resolve()); cfg.update(semparse_feed=True, pc_shadow=False, hooks_on_automated=True)
    items = {"u": {"id": "u", "content": Q, "attention": {"sti": 5.0}, "source_meta": {"user_id": 111}},
             "n": {"id": "n", "content": "x note", "attention": {"sti": 1.0}}}
    ctx.automated_hooks(str(tmp_path), items, 3, cfg=cfg)
    rows = {r[0]: r for r in got["rows"]}
    assert rows["u"][3] == {"user_id": 111} and len(rows["n"]) == 3


def test_capacity_overflow_keeps_the_request_item():
    from wmtm.store import WMTMStore
    st = WMTMStore(capacity=3)
    it = ctx.admit_request_item(st, Q, 1, {}, source={"user_id": 111})
    it.attention.sti = 0.01                                    # lowest STI in the store
    for k in range(5):
        st.admit("n%d" % k, "note %d" % k, initial_sti=1.0 + k)
    assert it.id in st and len(st) == 3 and st.get(it.id).source_meta["user_id"] == 111
