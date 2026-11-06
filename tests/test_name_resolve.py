"""P3 Deviation 6 (cos answer 4): (Name sk_x "label") -> deterministic symbol before the gate."""
import os, pytest
from wmtm import name_resolve as nr, parse_gate as pg, pc_shadow
from wmtm.pc_shadow import semparse_facts


def _note(n, rows):
    return ['(: i_%s__a%d (%s) (STV 1.0 0.99))' % (n, k, r) for k, r in enumerate(rows)]


def test_slug_matches_semparse_hitl():
    assert nr.slug("GitHub") == "github" and nr.slug("/tmp/pcmig-wt") == "tmp_pcmig_wt" and nr.slug("") == "x"


def test_same_name_across_notes_same_symbol():
    a, _ = nr.resolve(_note("n1", ['Name sk_github_1__i_n1 "GitHub"', 'Member sk_github_1__i_n1 remote']))
    b, _ = nr.resolve(_note("n2", ['Name sk_github_7__i_n2 "GitHub"', 'Member sk_github_7__i_n2 host']))
    fa, fb = semparse_facts(a), semparse_facts(b)
    assert fa[0][1] == fb[0][1] == "github"


def test_two_bearers_in_one_note_stay_distinct_and_reported():
    a, rep = nr.resolve(_note("n1", ['Name sk_pc3_1__i_n1 "PC3"', 'Name sk_pc3_2__i_n1 "PC3"',
                                     'Member sk_pc3_1__i_n1 issue', 'Member sk_pc3_2__i_n1 test']))
    subj = sorted(f[1] for f in semparse_facts(a))
    assert subj == ["pc3_1__i_n1", "pc3_2__i_n1"]
    assert rep["multi_bearer"] == [{"base": "pc3", "labels": ["PC3"], "witnesses": ["sk_pc3_1__i_n1", "sk_pc3_2__i_n1"]}]


def test_unnamed_witnesses_unchanged():
    rows = ['Name sk_wmtm_1__i_n1 "wmtm"', 'Member sk_post_1__i_n1 post', 'Agent sk_post_1__i_n1 sk_wmtm_1__i_n1',
            'Member sk_wmtm_10__i_n1 thing']
    a, _ = nr.resolve(_note("n1", rows))
    assert "(Member sk_post_1__i_n1 post)" in a[1] and "(Agent sk_post_1__i_n1 wmtm)" in a[2]
    assert "sk_wmtm_10__i_n1" in a[3]                     # prefix of a longer symbol is not rewritten


def test_resolved_fact_passes_gate():
    a, _ = nr.resolve(_note("n1", ['Name sk_github_1__i_n1 "GitHub"', 'Inheritance sk_github_1__i_n1 forge']))
    st = pg.settings()
    raw = semparse_facts(_note("n1", ['Name sk_github_1__i_n1 "GitHub"', 'Inheritance sk_github_1__i_n1 forge']))
    st0 = dict(st, scoped_witness=False)
    assert pg.gate_facts(raw, {}, st0, "n1")[0] == []     # before (scoped witnesses off): placeholder_subject
    assert [f[:3] for f in pg.gate_facts(raw, {}, st, "n1")[0]] == [("Inheritance", "sk_github_1__i_n1", "forge")]
    kept, _ = pg.gate_facts(semparse_facts(a), {}, st, "n1")
    assert [f[:3] for f in kept] == [("Inheritance", "github", "forge")]


_CFG = __import__("wmtm.runtime_config", fromlist=["x"]).resolve()
HAVE_PC = os.path.isdir(os.path.join(_CFG["petta_dir"], "python")) and os.path.isdir(os.path.join(_CFG["pettachainer_dir"], "pettachainer"))


@pytest.mark.skipif(not HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_real_engine_resolved_cross_note_fact_derives(tmp_path, monkeypatch):
    """Real PeTTaChainer: a name in note n1 and the same name in note n2 link only after resolution, and derive."""
    import json, subprocess, sys
    from wmtm import runtime_config as rc
    from wmtm.store import WMTMStore
    notes = {"n1": ['Name sk_github_1__i_n1 "GitHub"', 'Inheritance sk_github_1__i_n1 forge'],
             "n2": ['Name sk_github_4__i_n2 "GitHub"', 'Inheritance sk_github_4__i_n2 host',
                    'Inheritance forge service']}
    st = WMTMStore()
    for k, n in enumerate(notes):
        st.admit(n, "note " + n, source_type="recalled", initial_sti=1.0 - k * 0.01)
    monkeypatch.setattr(pc_shadow, "_cache_lookup", lambda items, *a, **kw: {it.id: _note(it.id, notes[it.id]) for it in items})
    cfg = dict(_CFG, name_resolve=False)
    before = pc_shadow.build_snapshot(st, cycle=1, cfg=cfg)["goals"]
    # before: no cross-note link (P4 rev3 keeps in-note goals about scoped witnesses sk_<x>__i_<note>)
    assert "(Inheritance github service)" not in before and all("__i_" in g for g in before)
    cfg["name_resolve"] = True
    spec = pc_shadow.build_snapshot(st, cycle=1, cfg=cfg)
    assert "(Inheritance github service)" in spec["goals"]
    sp = tmp_path / "spec.json"; sp.write_text(json.dumps(spec)); out = tmp_path / "shadow.jsonl"
    code = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", str(sp), "--out", str(out)],
                          env=rc.worker_env(_CFG), cwd=rc.DIST_ROOT, timeout=120).returncode
    rec = json.loads(out.read_text().strip().splitlines()[-1])
    assert code == 0 and rec["status"] == "ok" and rec["canary"]["ok"]
    assert "(Inheritance github service)" in {q["goal"] for q in rec["queries"] if q["ok"]}
