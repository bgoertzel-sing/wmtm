"""t-2026-11-13-wmtm-spread-seed-default: graph recall's default is the spread-seed sweep's arm P10.

P10 = recall_spread_seeds=turn + recall_spread_add_pct=10: spreading starts from this turn's keyword-matched clusters
(+ the request item) plus the top 10% most active residents (by STI), on every turn.  Before this task the default was
all (every resident seeds).  These tests check:
  - the default in SPEC, in resolve(), in the context.py readers and in the README flags table;
  - that a WMTM with no flags runs exactly as explicit P10 (same admissions and context blocks), and differs from
    all and from plain turn (E) on the same scripts (negative controls);
  - that the old modes stay selectable (all, focus, plain turn = E, turn + fallback), via the flags file and env, and
    that the API makes the old calls for them (spy).
Synthetic journals only.
"""
import random
import re
from pathlib import Path

import pytest

from wmtm import context as ctx
from wmtm import runtime_config as rc
from wmtm.api import WMTM, WMTMConfig
from wmtm.recall_bridge import RecallBridge

from test_recall_spread_sweep import ENV, ListJournal, _journal, _run_api, _world, _ids, MATCH, NOMATCH

P10 = {"recall_spread_seeds": "turn", "recall_spread_add_pct": 10, "recall_spread_fallback_pct": 0}
E = {"recall_spread_seeds": "turn", "recall_spread_add_pct": 0}
ALL = {"recall_spread_seeds": "all"}
README = Path(__file__).resolve().parent.parent / "README.md"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)


# ------------------------------------------------------------------------------------------------ the default

def test_spec_default_is_p10():
    assert rc.SPEC["recall_spread_seeds"][:3] == ("WMTM_RECALL_SPREAD_SEEDS", str, "turn")
    assert rc.SPEC["recall_spread_add_pct"][:3] == ("WMTM_RECALL_SPREAD_ADD_PCT", float, 10.0)
    assert rc.SPEC["recall_spread_fallback_pct"][:3] == ("WMTM_RECALL_SPREAD_FALLBACK_PCT", float, 0.0)


@pytest.mark.parametrize("cfg", [{}, None, "resolved"])
def test_readers_give_p10(cfg, tmp_path):
    if cfg == "resolved":
        cfg = rc.resolve(tmp_path, environ={})          # empty state dir: no flags file
    assert ctx.recall_spread_seeds(cfg) == "turn"
    assert ctx.recall_spread_pct(cfg, "recall_spread_add_pct") == 10.0
    assert ctx.recall_spread_pct(cfg, "recall_spread_fallback_pct") == 0.0


def test_readme_rows_show_the_default():
    rows = {}
    for ln in README.read_text().splitlines():
        m = re.match(r"\|\s*`(recall_spread_\w+)`\s*\|[^|]*\|[^|]*\|\s*`([^`]*)`\s*\|", ln)
        if m:
            rows[m.group(1)] = m.group(2)
    assert rows == {"recall_spread_seeds": "turn", "recall_spread_fallback_pct": "0", "recall_spread_add_pct": "10"}


@pytest.mark.parametrize("seed", range(4))
def test_api_unset_equals_explicit_p10(tmp_path, seed):
    """No flags file entry, no env: the run equals explicit P10 (admissions and context blocks)."""
    assert _run_api(tmp_path / "unset", seed, {}, nomatch_every=3) == _run_api(tmp_path / "p10", seed, P10,
                                                                               nomatch_every=3)


def test_api_default_is_not_all_and_not_e(tmp_path):
    """Negative controls for the test above: on the same scripts the default admits something other than all and
    other than plain turn (E) on some seed, so "unset = P10" is not vacuous."""
    d_all = d_e = False
    for seed in range(4):
        d = _run_api(tmp_path / ("u%d" % seed), seed, {}, nomatch_every=3)[0]
        d_all |= d != _run_api(tmp_path / ("a%d" % seed), seed, ALL, nomatch_every=3)[0]
        d_e |= d != _run_api(tmp_path / ("e%d" % seed), seed, E, nomatch_every=3)[0]
    assert d_all and d_e


def test_bridge_default_matches_flag_default():
    """What the API passes by default (turn + add 10) recalls what turn + add 10 recalls at the bridge, and that is
    not what E recalls (the added resident seeds reach their links)."""
    rb, st = _world()
    for q in (MATCH, NOMATCH):
        p10 = _ids(rb, st, q, spread_seeds="turn", add_pct=10.0)
        assert p10 == _ids(rb, st, q, spread_seeds=ctx.recall_spread_seeds({}),
                           add_pct=ctx.recall_spread_pct({}, "recall_spread_add_pct"))
    assert _ids(rb, st, NOMATCH, spread_seeds="turn", add_pct=10.0) != _ids(rb, st, NOMATCH, spread_seeds="turn")


# ------------------------------------------------------------------------------------ old modes stay selectable

def _spy_calls(tmp_path, monkeypatch, steps):
    """steps: [(env dict, query)].  -> the recall kwargs the API used on each step."""
    seen = []
    orig = RecallBridge.recall

    def spy(self, q, store, *a, **kw):
        seen.append(dict(kw))
        return orig(self, q, store, *a, **kw)
    monkeypatch.setattr(RecallBridge, "recall", spy)
    (tmp_path / "_wmtm_flags.json").write_text("{}")
    m = WMTM(WMTMConfig(state_dir=tmp_path, journal=ListJournal(_journal(random.Random(5))), reasoner="off",
                        use_pln=False))
    out = []
    for env, q in steps:
        for k in ENV:
            monkeypatch.delenv(k, raising=False)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        seen.clear()
        m.observe({"user": q})
        m.context_for(q)
        assert seen, "context_for made no recall call"
        out.append({k: v for k, v in seen[-1].items() if k in ("spread_seeds", "fallback_pct", "add_pct")})
    return out


def test_api_calls_per_mode(tmp_path, monkeypatch):
    S, F, A = "WMTM_RECALL_SPREAD_SEEDS", "WMTM_RECALL_SPREAD_FALLBACK_PCT", "WMTM_RECALL_SPREAD_ADD_PCT"
    got = _spy_calls(tmp_path, monkeypatch, [
        ({}, "amber"),                                  # default: P10
        ({S: "all"}, "ember"),                          # all: the call before the flag (no seed kwargs)
        ({S: "focus"}, "cobalt"),                       # focus: no pcts
        ({S: "turn", A: "0"}, "basalt"),                # plain turn = arm E: the probe's call
        ({A: "0"}, "dynamo"),                           # default mode + add 0 = E as well
        ({S: "turn", A: "0", F: "50"}, "fjord"),        # the fallback rule (arm F50)
        ({S: "turn", A: "25"}, "garnet"),               # arm P25
        ({S: "junk"}, "harbor"),                        # invalid mode = the default
    ])
    assert got == [
        {"spread_seeds": "turn", "add_pct": 10.0},
        {},
        {"spread_seeds": "focus"},
        {"spread_seeds": "turn"},
        {"spread_seeds": "turn"},
        {"spread_seeds": "turn", "fallback_pct": 50.0},
        {"spread_seeds": "turn", "add_pct": 25.0},
        {"spread_seeds": "turn", "add_pct": 10.0},
    ]


@pytest.mark.parametrize("seed", range(3))
def test_old_modes_via_flags_file_equal_env(tmp_path, monkeypatch, seed):
    """all and E set in the flags file run exactly as the same setting from env, and differ from each other."""
    runs = {}
    for name, flags, env in (("all", ALL, {"WMTM_RECALL_SPREAD_SEEDS": "all"}),
                             ("e", E, {"WMTM_RECALL_SPREAD_SEEDS": "turn", "WMTM_RECALL_SPREAD_ADD_PCT": "0"})):
        a = _run_api(tmp_path / (name + "-file"), seed, flags, nomatch_every=3)
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        b = _run_api(tmp_path / (name + "-env"), seed, {}, nomatch_every=3)
        for k in env:
            monkeypatch.delenv(k)
        assert a == b
        runs[name] = a
    assert runs["all"] != runs["e"]
