"""M-09 (t-2026-11-27-wmtm-m09-semantic-recall): semantic recall behind the recall_semantic flag (default off).

Synthetic clusters only (no note text).  The stub ranker stands in for embed_index.EmbedIndex.rank, so no model
is needed; the real-model twin is skipped unless sentence-transformers and the pinned model are available locally.
"""
import importlib.util
import logging
import subprocess
import sys
import types
from pathlib import Path

import pytest

from wmtm import recall_bridge as rbmod
from wmtm.recall_bridge import LTMCluster, RecallBridge
from wmtm.store import WMTMStore

REPO = Path(__file__).resolve().parent.parent

FORGOT = "ep-syn-forgot"
UNREL = "ep-syn-unrel"
KW = "ep-syn-kw"


def _clusters():
    return [
        LTMCluster(id=FORGOT, cluster_type="EventNote", event_note="forgotten items"),
        LTMCluster(id=UNREL, cluster_type="EventNote", event_note="garden hose repair"),
        LTMCluster(id=KW, cluster_type="EventNote", event_note="forgetting curve notes"),
    ]


def _stub_ranker(calls=None):
    sims = {FORGOT: 0.91, KW: 0.70, UNREL: 0.12}

    def rank(query, clusters):
        if calls is not None:
            calls.append((query, [c.id for c in clusters]))
        return sorted(((c.id, sims.get(c.id, 0.0)) for c in clusters), key=lambda x: -x[1])
    return rank


def _ids(cands):
    return [c.cluster_id for c in cands]


def test_stub_flag_on_recalls_meaning_match_without_shared_token():
    b = RecallBridge(_clusters(), semantic_ranker=_stub_ranker())
    ids = _ids(b.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1, semantic=True))
    assert FORGOT in ids
    assert UNREL not in ids or ids.index(UNREL) > ids.index(FORGOT)


def test_stub_flag_off_twin_is_todays_behaviour():
    calls = []
    b = RecallBridge(_clusters(), semantic_ranker=_stub_ranker(calls))
    plain = RecallBridge(_clusters())
    off = b.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1)
    ref = plain.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1)
    assert FORGOT not in _ids(off)
    assert [(c.cluster_id, c.score) for c in off] == [(c.cluster_id, c.score) for c in ref]
    assert calls == []          # flag off never calls the ranker


def test_semantic_only_needs_min_sim():
    b = RecallBridge(_clusters(), semantic_ranker=_stub_ranker())
    ids = _ids(b.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1,
                        semantic=True, semantic_min_sim=0.95))
    assert FORGOT not in ids


def test_semantic_excludes_active_items():
    b = RecallBridge(_clusters(), semantic_ranker=_stub_ranker())
    store = WMTMStore(capacity=10)
    store.admit(item_id=FORGOT, content="x")
    assert FORGOT not in _ids(b.recall("forgetting", store, top_k=10, floor=0.1, semantic=True))


def test_ranker_failure_falls_back_to_keyword(caplog):
    def boom(q, cl):
        raise RuntimeError("no model")
    monkey = RecallBridge(_clusters(), semantic_ranker=boom)
    ref = RecallBridge(_clusters()).recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1)
    got = monkey.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1, semantic=True)
    assert _ids(got) == _ids(ref)


def test_unavailable_model_keyword_only_logged_once(monkeypatch, caplog):
    from wmtm import embed_index
    monkeypatch.setattr(embed_index, "available", lambda: False)
    monkeypatch.setattr(rbmod, "_semantic_fallback_logged", False)
    b = RecallBridge(_clusters())
    ref = b.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1)
    with caplog.at_level(logging.WARNING, logger="wmtm.recall_bridge"):
        for _ in range(3):
            got = b.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1, semantic=True)
            assert _ids(got) == _ids(ref)
    assert sum("recall_semantic" in r.getMessage() for r in caplog.records) == 1


def test_model_load_is_offline_and_pinned(monkeypatch):
    """The run-time load passes local_files_only=True and the pinned revision: never a download."""
    from wmtm import embed_index
    seen = {}

    class FakeST:
        def __init__(self, name, **kw):
            seen.update(kw, name=name)
            raise OSError("not cached")
    fake = types.ModuleType("sentence_transformers")
    fake.SentenceTransformer = FakeST
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)
    monkeypatch.setattr(embed_index, "_model", None)
    monkeypatch.setattr(embed_index, "_model_failed", False)
    assert embed_index.available() is False
    assert seen["local_files_only"] is True
    assert seen["revision"] == embed_index.PINNED_REVISION
    assert len(embed_index.PINNED_REVISION) == 40


def test_api_kwargs_empty_when_flag_off():
    from wmtm.api import _recall_semantic_kw
    assert _recall_semantic_kw({}) == {}
    assert _recall_semantic_kw({"recall_semantic": False}) == {}
    assert _recall_semantic_kw({"recall_semantic": True}) == {"semantic": True, "semantic_min_sim": 0.6}


def test_pins_in_repo():
    txt = (REPO / "pyproject.toml").read_text()
    assert 'sentence-transformers==' in txt


def test_flag_off_imports_no_torch_or_sentence_transformers():
    code = (
        "import sys\n"
        "from wmtm import api, runtime_config\n"
        "from wmtm.recall_bridge import LTMCluster, RecallBridge\n"
        "from wmtm.store import WMTMStore\n"
        "b = RecallBridge([LTMCluster(id='ep-a', event_note='forgotten items')])\n"
        "b.recall('forgetting', WMTMStore(capacity=5), top_k=5, **api._recall_semantic_kw({}))\n"
        "bad = [m for m in ('sentence_transformers', 'torch', 'wmtm.embed_index', 'transformers') if m in sys.modules]\n"
        "print('LOADED', bad)\n"
        "sys.exit(1 if bad else 0)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=str(REPO), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "LOADED []" in r.stdout


def _real_model_available():
    if importlib.util.find_spec("sentence_transformers") is None:
        return False
    from wmtm import embed_index
    return embed_index.available()


@pytest.mark.skipif(not _real_model_available(), reason="sentence-transformers or the pinned cached model missing")
def test_real_model_flag_on_recalls_meaning_match(tmp_path):
    from wmtm import embed_index
    idx = embed_index.EmbedIndex(cache_path=tmp_path / "emb.npz")
    b = RecallBridge(_clusters(), semantic_ranker=lambda q, cl: idx.rank(q, cl))
    ids = _ids(b.recall("forgetting", WMTMStore(capacity=10), top_k=10, floor=0.1,
                        semantic=True, semantic_min_sim=0.5))
    assert FORGOT in ids
    assert UNREL not in ids or ids.index(UNREL) > ids.index(FORGOT)
