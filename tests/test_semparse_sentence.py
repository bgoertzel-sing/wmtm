"""t-2026-11-15-wmtm-sentence-feed: semparse_mode "sentence" (wmtm/semparse_sentence.py) on synthetic notes only.

The call loop runs with upstream tmpl.blocks when WMTM_PC_SHADOW_SPH_TEMPLATES points at the 24e37182 templates, and
otherwise with a small stand-in that has the same walk / context rule (a sentence's stored reply counts only if it
was made under the context of the earlier sentences).  No test makes a network call; the gate tests use a fake
upstream module whose provider counts what it would have sent."""
import hashlib, json, os, subprocess, sys, types
import pytest

from wmtm import runtime_config as rc, semparse_sentence as SS
from wmtm.parse_budget import ParseBudget, ShareFull, live_root
from wmtm.parse_cache import ParseCache

T = os.environ.get("WMTM_PC_SHADOW_SPH_TEMPLATES", "")
REAL = bool(T and os.path.isfile(os.path.join(T, "tmpl", "blocks.py")))
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------- blocks: upstream or a stand-in with the same rule
class FakeBlocks:
    @staticmethod
    def _sha(t):
        return hashlib.sha256(t.encode()).hexdigest()

    @staticmethod
    def context_section(prior):
        if not prior:
            return ""
        return "CONTEXT\n" + "\n".join("[s%d] %s %s" % (p["k"], p["text"], json.dumps(p["instances"])) for p in prior)

    @classmethod
    def walk(cls, block, replies):
        prior = []
        for k, row in enumerate(block, start=1):
            ctx = cls.context_section(prior)
            rec = replies.get(row["id"])
            ok = bool(rec) and not rec.get("error") and isinstance(rec.get("response"), dict)
            if not (ok and (rec.get("item") or {}).get("context_sha256") == (cls._sha(ctx) if ctx else None)):
                return prior, row
            prior.append({"k": k, "text": row["text"], "instances": rec["response"].get("instances") or [],
                          "unmapped": [], "row": row})
        return prior, None


def blocks():
    if REAL:
        from wmtm import master_loader as ML
        ML._tmpl(T)
        from tmpl import blocks as B
        return B
    return FakeBlocks


def record(text, item_id, context):
    """A good run record in upstream parse_sentence's shape (no instances: nothing note-derived)."""
    rec = {"provider": "chat-completions", "model": "stub", "effort": "low", "temperature": 0.0,
           "prompt_path": "templates/generated/PROMPT_CATALOG.txt", "prompt_sha256": "0" * 64,
           "item": {"id": item_id, "text": text}, "usage": {"input": 10, "output": 2, "total": 12, "cached": 8},
           "request_config": {}, "raw_usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
           "raw_text": "{}", "response": {"id": item_id, "instances": [], "unmapped": []}}
    if context:
        rec["item"]["context_sha256"] = hashlib.sha256(context.encode()).hexdigest()
    return rec


class Stub:
    """parse_fn that reserves one call in the share before 'sending' (like gateway_parse_fn) and counts sends."""
    def __init__(self, budget, fail=None, raise_for=None):
        self.budget, self.fail, self.raise_for = budget, dict(fail or {}), dict(raise_for or {})
        self.call_ids, self.sent = [], []

    def __call__(self, text, item_id, context=None):
        self.call_ids.append(self.budget.acquire({"tool": "test"}, wait=False))
        self.sent.append(item_id)
        if self.raise_for.get(item_id):
            self.raise_for[item_id] -= 1
            raise RuntimeError("HTTP 429 too many requests")
        if self.fail.get(item_id):
            self.fail[item_id] -= 1
            return {**record(text, item_id, context), "response": None, "error": "the reply is not valid JSON: x"}
        return record(text, item_id, context)


def cfg_for(tmp_path, share=20, cap=20, **kw):
    cfg = rc.resolve()
    live = str(tmp_path / "live")
    cfg.update(semparse_dir=live, parse_role="live", parse_live_dir=live, parse_share_live_per_hour=share,
               parse_cap_per_hour=cap, semparse_mode="sentence", semparse_feed=True, speaker_link=False)
    cfg.update(kw)
    return cfg


def sent_cache(cfg):
    return ParseCache(os.path.join(cfg["semparse_dir"], SS.SENT_VERSION), cfg=cfg)


NOTE_A = "Lamine sold a quilt. The quilt was red. Yusra bought it."
NOTE_B = "A report was written. It was short."


def run(cache, cfg, stub, n=None):
    return SS.process_queue_sentence(cache, stub, cfg=cfg, n=n, B=blocks(), prompt_body_sha="b" * 64, manifest_id="m1")


def rows(path):
    return [json.loads(l) for l in open(path)] if os.path.exists(path) else []


# ---------------------------------------------------------------- cleanup + split
def test_strip_categories_and_keeps():
    raw = ("NEXT: run (1) the check with \x60git status\x60 and \x60my_flag\x60 at 3f9a2b1c. Version 1.0 stays; "
           "t-2026-11-15-x stays. <!-- meta: ignore -->")
    clean, cnt = SS.strip(raw)
    assert cnt == {"C1_markup_comment": 1, "C3_shell_command": 1, "C2_hash_id": 1, "C4_list_number": 1}
    assert "git status" not in clean and "3f9a2b1c" not in clean and "<!--" not in clean and "(1)" not in clean
    assert "\x60my_flag\x60" in clean and "1.0" in clean and "t-2026-11-15-x" in clean and clean.startswith("NEXT:")
    assert "  " not in clean and " ." not in clean


def test_sentences_split_and_abbreviations():
    assert SS.sentences("One thing, e.g. a cat. Two! Three? ...") == ["One thing, e.g. a cat.", "Two!", "Three?"]
    assert SS.sentences("") == []


def test_prepare_rows_have_the_offline_driver_shape():
    r, info = SS.prepare("ep-note-x", NOTE_A)
    assert [list(x) for x in r] == [["id", "dataset", "doc", "sent", "text"]] * 3
    assert [x["id"] for x in r] == ["ep-note-x.s01", "ep-note-x.s02", "ep-note-x.s03"]
    assert {x["dataset"] for x in r} == {SS.DATASET} and {x["doc"] for x in r} == {"ep-note-x"}
    assert info["sentences"] == info["sentences_total"] == 3 and info["capped"] is False


def test_cap_keeps_the_first_sentences():
    r, info = SS.prepare("n", NOTE_A, cfg={"semparse_sentence_cap": 2})
    assert [x["sent"] for x in r] == [1, 2] and info == dict(info, capped=True, sentences_total=3, sentences=2)
    assert len(SS.prepare("n", NOTE_A, cfg={"semparse_sentence_cap": 0})[0]) == 3      # 0 = no cap (default)
    assert len(SS.prepare("n", NOTE_A, cfg={"semparse_sentence_cap": 9})[0]) == 3


def test_speaker_linking_before_the_split_same_substitution_as_spk1():
    from wmtm.semparse_speaker import link
    cfg = {"speaker_link": True, "speaker_map": {"4242": "quill", "quillq": "quill"}, "speaker_self": "cosmo"}
    note = "The user asked for a summary. I wrote it for @quillq."
    r, info = SS.prepare("n", note, source={"user_id": 4242}, cfg=cfg)
    want, li = link(note, {"user_id": 4242}, cfg["speaker_map"], "cosmo", prefix=False)
    assert " ".join(x["text"] for x in r) == want                    # exactly spk1's substitution, then the split
    assert [x["text"] for x in r] == ["Quill asked for a summary.", "Cosmo wrote it for @Quill."]
    assert info["speaker"] == "quill" and info["speaker_source"] == "source:user_id" and info["subs"] == li["subs"]
    assert not any(x["text"].startswith("Speaker:") for x in r)      # no extra prefix sentence (one call less)
    off, info2 = SS.prepare("n", note, source={"user_id": 4242}, cfg=dict(cfg, speaker_link=False))
    assert [x["text"] for x in off] == ["The user asked for a summary.", "I wrote it for @quillq."]
    assert info2["speaker"] is None


def test_two_notes_share_the_linked_name():
    cfg = {"speaker_link": True, "speaker_map": {"4242": "quill"}, "speaker_self": "cosmo"}
    a, _ = SS.prepare("a", "The user wants tea.", source={"user_id": "4242"}, cfg=cfg)
    b, _ = SS.prepare("b", "The user asked again.", source={"user_id": "4242"}, cfg=cfg)
    assert a[0]["text"].startswith("Quill ") and b[0]["text"].startswith("Quill ")


# ---------------------------------------------------------------- the call loop
def test_full_drain_one_call_per_sentence_under_the_live_share(tmp_path):
    cfg = cfg_for(tmp_path)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0), ("nb", NOTE_B, 0.5)], now=1.0)
    st = Stub(c.share)
    out = run(c, cfg, st)
    assert len(out["calls"]) == 5 and out["notes"]["ok"] == 2 and out["stop"] is None
    assert st.sent == ["na.s01", "na.s02", "na.s03", "nb.s01", "nb.s02"]
    p = rows(SS.parsed_path(c.d))
    assert [r["id"] for r in p] == st.sent
    assert all(list(r) == ["id", "dataset", "doc", "sent", "text", "reply"] for r in p)
    assert all(r["reply"]["block"] == {"doc": r["doc"], "k": r["sent"], "available_from": r["sent"]} for r in p)
    assert {r["reply"]["prompt_body_sha256"] for r in p} == {"b" * 64} and {r["reply"]["manifest_id"] for r in p} == {"m1"}
    assert p[1]["reply"]["item"]["context_sha256"] and "context_sha256" not in p[0]["reply"]["item"]
    led = rows(os.path.join(cfg["parse_live_dir"], "share_ledger.jsonl"))
    assert len(led) == 5 and {r["role"] for r in led} == {"live"}
    logs = rows(c.log_path)
    assert sorted(i for r in logs for i in r["call_ids"]) == sorted(r["call_id"] for r in led)
    assert c.share.used() == 5                                    # ledger + log joined: no double count
    assert ParseBudget("live", cfg=cfg).used() == 5               # what every other live cache sees
    assert c.pending() == 0 and {e["status"] for e in c.entries().values()} == {"ok"}
    assert not os.listdir(os.path.join(c.d, "work"))
    assert all("text" not in json.dumps(e) or True for e in c.entries().values())
    assert not any(k in e for e in c.entries().values() for k in ("content", "text"))


def test_partial_note_stays_queued_and_is_not_fed(tmp_path):
    cfg = cfg_for(tmp_path)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0)], now=1.0)
    out = run(c, cfg, Stub(c.share), n=2)
    assert len(out["calls"]) == 2 and out["notes"] == {"ok": 0, "failed": 0, "empty": 0, "partial": 1}
    assert rows(SS.parsed_path(c.d)) == []                        # nothing of the note reaches the master path
    assert c.pending() == 1 and c.entries() == {}
    st2 = Stub(c.share)
    out2 = run(c, cfg, st2)
    assert st2.sent == ["na.s03"] and out2["notes"]["ok"] == 1    # resumes at the next sentence, no re-parse
    assert [r["id"] for r in rows(SS.parsed_path(c.d))] == ["na.s01", "na.s02", "na.s03"]


def test_share_full_stops_with_nothing_sent_and_note_kept(tmp_path):
    cfg = cfg_for(tmp_path, share=2)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0)], now=1.0)
    st = Stub(c.share)
    out = run(c, cfg, st)
    assert len(st.sent) == 2 and out["stop"] == "share_full" and c.last_stop["status"] == "share_full"
    assert len(rows(os.path.join(cfg["parse_live_dir"], "share_ledger.jsonl"))) == 2
    assert rows(SS.parsed_path(c.d)) == [] and c.pending() == 1


def test_gate_refusal_mid_note_records_nothing(tmp_path):
    cfg = cfg_for(tmp_path, share=20, cap=20)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0)], now=1.0)

    class Refuse(Stub):
        def __call__(self, text, item_id, context=None):
            if item_id.endswith("s02"):
                raise ShareFull("parse share full: live share 20/h used")
            return Stub.__call__(self, text, item_id, context)
    st = Refuse(c.share)
    out = run(c, cfg, st)
    assert out["stop"] == "share_full" and len(out["calls"]) == 1 and len(rows(c.log_path)) == 1
    assert rows(SS.parsed_path(c.d)) == [] and c.pending() == 1


def test_at_most_two_attempts_then_gave_up_never_fed(tmp_path):
    cfg = cfg_for(tmp_path, parse_max_attempts=5)                 # the sentence mode caps it at 2
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0), ("nb", NOTE_B, 0.5)], now=1.0)
    st = Stub(c.share, fail={"na.s02": 99})
    out = run(c, cfg, st)
    assert st.sent[:3] == ["na.s01", "na.s02", "na.s02"] and out["notes"]["failed"] == 1 and out["notes"]["ok"] == 1
    assert [r["doc"] for r in rows(SS.parsed_path(c.d))] == ["nb", "nb"]
    e = {v["item_id"]: v for v in c.entries().values()}
    assert e["na"]["status"] == "failed" and e["na"]["failed_sentence"] == 2 and e["na"]["attempts"] == 2
    assert len(os.listdir(os.path.join(c.d, "gave_up"))) == 1
    st2 = Stub(c.share)
    run(c, cfg, st2)
    assert st2.sent == []                                         # not retried


def test_retry_success_keeps_the_error_row_like_the_offline_driver(tmp_path):
    cfg = cfg_for(tmp_path)
    c = sent_cache(cfg)
    c.enqueue([("nb", NOTE_B, 1.0)], now=1.0)
    st = Stub(c.share, fail={"nb.s01": 1})
    out = run(c, cfg, st)
    p = rows(SS.parsed_path(c.d))
    assert [r["id"] for r in p] == ["nb.s01", "nb.s01", "nb.s02"] and out["notes"]["ok"] == 1
    assert set(p[0]["reply"]) >= {"error", "item", "response", "block", "manifest_id", "prompt_body_sha256"}


def test_limit_error_stops_the_run(tmp_path):
    cfg = cfg_for(tmp_path)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0)], now=1.0)
    st = Stub(c.share, raise_for={"na.s01": 1})
    out = run(c, cfg, st)
    assert out["stop"] == "limit" and len(st.sent) == 1 and rows(SS.parsed_path(c.d)) == []
    w = rows(os.path.join(c.d, "work", os.listdir(os.path.join(c.d, "work"))[0]))
    assert w[0]["reply"]["error"].startswith("request failed: HTTP 429")
    assert set(w[0]["reply"]) == {"item", "response", "error", "prompt_body_sha256", "manifest_id", "block"}


def test_cap_flag_in_the_loop(tmp_path):
    cfg = cfg_for(tmp_path, semparse_sentence_cap=2)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0)], now=1.0)
    st = Stub(c.share)
    run(c, cfg, st)
    assert st.sent == ["na.s01", "na.s02"]
    e = list(c.entries().values())[0]
    assert e["status"] == "ok" and e["capped"] is True and e["sentences_total"] == 3 and e["sentences"] == 2


def test_own_hourly_cap_counts_sentence_calls(tmp_path):
    cfg = cfg_for(tmp_path, share=20, cap=3)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_A, 1.0), ("nb", NOTE_B, 0.5)], now=1.0)
    st = Stub(c.share)
    out = run(c, cfg, st, n=99)
    assert len(st.sent) == 3 and out["stop"] == "cap_full" and c.budget() == 0


def test_new_content_for_the_same_item_replaces_its_rows(tmp_path):
    cfg = cfg_for(tmp_path)
    c = sent_cache(cfg)
    c.enqueue([("na", NOTE_B, 1.0)], now=1.0)
    run(c, cfg, Stub(c.share))
    c.enqueue([("na", "One new sentence.", 1.0)], now=2.0)
    run(c, cfg, Stub(c.share))
    p = rows(SS.parsed_path(c.d))
    assert [r["text"] for r in p] == ["One new sentence."]


def test_empty_note_recorded_without_calls(tmp_path):
    cfg = cfg_for(tmp_path)
    c = sent_cache(cfg)
    c.enqueue([("na", "... !!", 1.0)], now=1.0)
    st = Stub(c.share)
    out = run(c, cfg, st)
    assert st.sent == [] and out["notes"]["empty"] == 1 and c.pending() == 0


@pytest.mark.skipif(not REAL, reason="sph templates not set")
def test_master_path_reads_only_finished_notes(tmp_path):
    from wmtm import master_loader as ML
    cfg = cfg_for(tmp_path)
    c = sent_cache(cfg)
    c.enqueue([("nb", NOTE_B, 1.0), ("na", NOTE_A, 0.5)], now=1.0)
    run(c, cfg, Stub(c.share), n=3)                               # nb done (2), na partial (1 of 3)
    notes, info = ML.notes_from_parsed(T, SS.parsed_path(c.d), ["na", "nb"])
    assert [n for n, _ in notes] == ["nb"] and info["complete"] == 1 and info["absent"] == ["na"]
    run(c, cfg, Stub(c.share))
    notes, info = ML.notes_from_parsed(T, SS.parsed_path(c.d), ["na", "nb"])
    assert info["complete"] == 2 and not info["incomplete"] and not info["absent"]


# ---------------------------------------------------------------- the production gate (fake upstream module)
def fake_upstream():
    m = types.ModuleType("fake_semantic_parse")
    m.sends = []

    class CC:
        name = "chat-completions"

        def __init__(self, args):
            self.args = args

        def complete(self, system, user, model):
            m.sends.append(user)
            return types.SimpleNamespace(text="{}", usage={}, raw_usage={})
    m.PROVIDERS = {"chat-completions": CC}

    def add_provider_args(ap):
        for f in ("--provider", "--base-url", "--api-key-env", "--model", "--prompt"):
            ap.add_argument(f, default=None)
        ap.add_argument("--timeout", type=float, default=600.0)
        ap.add_argument("--temperature", type=float, default=None)
    m.add_provider_args = add_provider_args

    def parse_sentence(text, args, item_id="item", context=None):
        prov = m.PROVIDERS[args.provider](args)
        prov.complete("SYSTEM", (context + "\n\n" if context else "") + "Item id: %s\nTEXT: %s" % (item_id, text), args.model)
        return record(text, item_id, context)
    m.parse_sentence = parse_sentence
    return m


def test_gateway_parse_fn_reserves_before_sending_and_refuses_when_full(tmp_path, monkeypatch):
    monkeypatch.setenv("BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LLM_MODEL", "stub-model")
    cfg = cfg_for(tmp_path, share=1)
    c = sent_cache(cfg)
    m = fake_upstream()
    fn = SS.gateway_parse_fn("unused", "/nonexistent/prompt", c.share, module=m, meta={"tool": "semparse_feed"})
    assert m.PROVIDERS["chat-completions"].name == "chat-completions"     # same provider name -> same record
    assert fn.args.temperature == 0.0 and fn.args.timeout == 300.0 and fn.args.model == "stub-model"
    fn("A cat sat.", "x.s01", None)
    led = rows(os.path.join(cfg["parse_live_dir"], "share_ledger.jsonl"))
    assert len(m.sends) == 1 and len(led) == 1 and fn.call_ids == [led[0]["call_id"]] and led[0]["role"] == "live"
    with pytest.raises(ShareFull):
        fn("A dog sat.", "x.s02", None)
    assert len(m.sends) == 1                                      # the refused call was never sent


def test_gateway_parse_fn_needs_a_base_url(monkeypatch):
    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.delenv("WMTM_LLM_ENV_FILE", raising=False)
    with pytest.raises(RuntimeError):
        SS.gateway_parse_fn("unused", "p", None, module=fake_upstream())


# ---------------------------------------------------------------- feed routing, share root, config, worker gate
def test_feed_rows_routes_sentence_mode_to_sent1_and_records_launch(tmp_path, monkeypatch):
    from wmtm import parse_cache as PC
    cfg = cfg_for(tmp_path, speaker_link=True)
    spawned = []
    monkeypatch.setattr(rc, "spawn_worker", lambda c, mod, args, pidfile: spawned.append(args) or 4242)
    pid = PC.feed_rows([("na", NOTE_A, 1.0)], cfg)
    d = os.path.join(cfg["semparse_dir"], "sent1")
    assert pid == 4242 and spawned[0][:2] == ["--dir", d]
    assert json.load(open(os.path.join(d, "queue.json")))
    assert not os.path.exists(os.path.join(cfg["semparse_dir"], "spk1"))
    assert not os.path.exists(os.path.join(cfg["semparse_dir"], "queue.json"))
    dec = rows(os.path.join(d, "launch_decisions.jsonl"))
    assert dec[-1]["decision"] == "launched" and dec[-1]["role"] == "live"


def test_feed_rows_other_modes_unchanged(tmp_path, monkeypatch):
    from wmtm import parse_cache as PC
    monkeypatch.setattr(rc, "spawn_worker", lambda c, mod, args, pidfile: 1)
    for mode, link, sub in (("legacy", True, "spk1"), ("catalog", False, ""), ("legacy", False, "")):
        cfg = cfg_for(tmp_path / (mode + str(link)), semparse_mode=mode, speaker_link=link)
        PC.feed_rows([("na", NOTE_A, 1.0)], cfg)
        assert os.path.exists(os.path.join(cfg["semparse_dir"], sub, "queue.json"))
        assert not os.path.exists(os.path.join(cfg["semparse_dir"], "sent1"))


def test_sent1_shares_the_live_root_without_parse_live_dir(tmp_path):
    base = str(tmp_path / "live")
    assert live_root(os.path.join(base, "sent1")) == base
    cfg = cfg_for(tmp_path, parse_live_dir="")
    a = ParseBudget("live", cfg=cfg, cache_dir=os.path.join(base, "sent1"))
    b = ParseBudget("live", cfg=cfg, cache_dir=os.path.join(base, "spk1"))
    assert a.ledger == b.ledger == os.path.join(os.path.realpath(base), "share_ledger.jsonl")


def test_runtime_config_cap_key(tmp_path, monkeypatch):
    monkeypatch.delenv("WMTM_SEMPARSE_SENTENCE_CAP", raising=False)
    assert rc.resolve()["semparse_sentence_cap"] == 0
    (tmp_path / rc.FLAGS_FILENAME).write_text(json.dumps({"semparse_sentence_cap": 6, "semparse_mode": "sentence"}))
    c = rc.resolve(str(tmp_path))
    assert c["semparse_sentence_cap"] == 6 and c["semparse_mode"] == "sentence"


def test_require_pin_refuses_other_commits(tmp_path, monkeypatch):
    from wmtm import semparse_catalog as SC
    d = tmp_path / "hitl"
    (d / "templates" / "tmpl").mkdir(parents=True)
    monkeypatch.setattr(SC, "verify_checkout", lambda root: root)
    (d / "VERSION").write_text("commit=%s\n" % SC.PIN)
    with pytest.raises(SC.HitlPinError):
        SS.require_pin(str(d))
    (d / "VERSION").write_text("commit=%s\n" % SS.SENTENCE_PIN)
    assert SS.require_pin(str(d)) == os.path.abspath(str(d))


def test_worker_refuses_sentence_mode_without_the_pinned_checkout(tmp_path):
    cfg = cfg_for(tmp_path, semparse_hitl=str(tmp_path / "missing-hitl"))
    d = os.path.join(cfg["semparse_dir"], "sent1")
    os.makedirs(d)
    cp = os.path.join(d, "worker_config.json")
    rc.write_json_atomic(cp, cfg)
    env = dict(os.environ, PYTHONPATH=REPO)
    env.pop("WMTM_SEMPARSE_HITL", None)
    r = subprocess.run([sys.executable, "-m", "wmtm.workers.semparse_feed", "--dir", d, "--config", cp, "--no-loader"],
                       cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
    st = rows(os.path.join(d, "worker_runs.jsonl"))[-1]
    assert r.returncode == 5 and st["status"] == "hitl_pin" and st["mode"] == "sentence"
    assert not os.path.exists(os.path.join(cfg["parse_live_dir"], "share_ledger.jsonl"))


# ---------------------------------------------------------------- fetch_semparse_hitl.sh
SCRIPT = os.path.join(REPO, "scripts", "fetch_semparse_hitl.sh")
SRC = os.environ.get("WMTM_TEST_SEMPARSE_SRC") or os.path.expanduser("~/scratch/pma/sph-24e37182")


def test_fetch_script_refuses_an_unknown_pin(tmp_path):
    r = subprocess.run(["bash", SCRIPT, str(tmp_path / "d"), "deadbeef"], capture_output=True, text=True, timeout=30)
    assert r.returncode == 2 and "unknown pin" in r.stderr and not (tmp_path / "d").exists()


@pytest.mark.skipif(not os.path.exists(os.path.join(SRC, ".git")), reason="no local semantic-parsing-hitl clone")
def test_fetch_script_24e37182_from_a_local_clone(tmp_path):
    if subprocess.run(["git", "-C", SRC, "cat-file", "-e", SS.SENTENCE_PIN + "^{commit}"]).returncode:
        pytest.skip("clone lacks 24e37182")
    d = tmp_path / "sph"
    r = subprocess.run(["bash", SCRIPT, str(d), "24e37182"], env=dict(os.environ, SEMPARSE_SRC=SRC),
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    v = (d / "VERSION").read_text()
    assert "commit=%s\n" % SS.SENTENCE_PIN in v and "seeded_rules.pettachainer-master.metta=9c58f2e0" in v
    from wmtm import semparse_catalog as SC
    assert SC.verify_checkout(str(d)) == str(d) and SS.require_pin(str(d)) == str(d)
