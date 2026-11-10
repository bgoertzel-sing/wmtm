"""Unit tests for wmtm/semparse_adapter.py (LLM mocked, PeTTa loader mocked)."""
import json
import pytest

from wmtm import semparse_adapter as sp


@pytest.fixture(autouse=True)
def _legacy_semparse_mode(monkeypatch):
    """These tests exercise legacy mode (the model writes MeTTa); catalog is the default since p2 review-1."""
    monkeypatch.setenv("WMTM_SEMPARSE_MODE", "legacy")


class FakeLoader:
    def __init__(self, fail_on=None):
        self.atoms, self.fail_on = [], fail_on

    def add_atom(self, a):
        if self.fail_on and self.fail_on in a:
            raise RuntimeError("PeTTa refused")
        self.atoms.append(a)
        return "ok"


def mk(reply, loader=None, tmp_path=None, raise_exc=None):
    calls = []

    def llm(system, user):
        calls.append((system, user))
        if raise_exc:
            raise raise_exc
        return reply
    log = str(tmp_path / "rej.jsonl") if tmp_path else None
    ad = sp.SemParseAdapter(llm, loader=loader, system="SYS", reject_log=log)
    return ad, calls, log


def read_log(log):
    try:
        return [json.loads(l) for l in open(log)]
    except FileNotFoundError:
        return []


def test_tokenize_strings_and_comments():
    assert sp.tokenize('(Name x "a b") ; hi\n(y)') == ['(', 'Name', 'x', '"a b"', ')', '(', 'y', ')']


def test_unterminated_string():
    with pytest.raises(sp.SexprError):
        sp.tokenize('(Name x "abc)')


def test_good_atoms_accepted_and_prefixed(tmp_path):
    L = FakeLoader()
    ad, calls, log = mk("(: grace_is_pilot (Member grace pilot) (STV 1.0 0.99))\n"
                        '(: grace_name (Name grace "Grace") (STV 1.0 0.99))', L, tmp_path)
    r = ad.parse_item("m1", {"content": "Grace is a pilot."})
    assert calls == [("SYS", "TEXT: Grace is a pilot.")]
    assert r.accepted == ["(: i_m1__grace_is_pilot (Member grace pilot) (STV 1.0 0.99))",
                          '(: i_m1__grace_name (Name grace "Grace") (STV 1.0 0.99))']
    assert L.atoms == r.accepted and r.rejected == [] and read_log(log) == []


def test_code_fences_stripped(tmp_path):
    ad, _, _ = mk("```metta\n(: a (Member x y) (STV 1.0 0.99))\n```", None, tmp_path)
    assert len(ad.parse_item("x", "t").accepted) == 1


def test_multiline_atom(tmp_path):
    ad, _, _ = mk("(: a\n  (Member x y)\n  (STV 1.0 0.99))", None, tmp_path)
    assert ad.parse_item("x", "t").accepted == ["(: i_x__a (Member x y) (STV 1.0 0.99))"]


@pytest.mark.parametrize("bad,why", [
    ("(: a (Member x y) (STV 1.0 1.5))", "confidence"),
    ("(: a (Member x y) (STV 1.2 0.9))", "strength"),
    ("(: a (Member x y) (STV 1.0 1.0))", "confidence"),
    ("(: a (Member x y) (STV hi 0.9))", "numbers"),
    ("(: a (Member x y))", "form"),
    ("(Member x y)", "form"),
    ("(: a b (STV 1.0 0.9))", "content"),
    ("(: a (Member x y) (TV 1.0 0.9))", "truth value"),
])
def test_structure_rejects_logged(tmp_path, bad, why):
    L = FakeLoader()
    ad, _, log = mk(bad + "\n(: ok (Member x y) (STV 1.0 0.99))", L, tmp_path)
    r = ad.parse_item("x", "t")
    assert len(r.accepted) == 1 and len(r.rejected) == 1
    assert why in r.rejected[0][1]
    recs = read_log(log)
    assert len(recs) == 1 and recs[0]["stage"] == "structure" and recs[0]["item_id"] == "x"
    assert len(L.atoms) == 1


def test_unbalanced_logged_and_rest_kept(tmp_path):
    ad, _, log = mk("(: a (Member x y) (STV 1.0 0.99)\n\n(: b (Member x z) (STV 1.0 0.99))", None, tmp_path)
    r = ad.parse_item("x", "t")
    assert any("syntax" in why for _, why in r.rejected)
    assert read_log(log)[0]["stage"] == "syntax"


def test_prose_reply_logged(tmp_path):
    ad, _, log = mk("Sorry, I cannot do that.", None, tmp_path)
    r = ad.parse_item("x", "t")
    assert r.accepted == [] and r.rejected and read_log(log)


def test_empty_reply_logged(tmp_path):
    ad, _, log = mk("   ", None, tmp_path)
    r = ad.parse_item("x", "t")
    assert r.error == "empty reply" and read_log(log)[0]["stage"] == "llm"


def test_llm_exception_logged(tmp_path):
    ad, _, log = mk(None, None, tmp_path, raise_exc=TimeoutError("boom"))
    r = ad.parse_item("x", "t")
    assert "boom" in r.error and read_log(log)[0]["stage"] == "llm"


def test_petta_load_failure_logged(tmp_path):
    L = FakeLoader(fail_on="Weird")
    ad, _, log = mk("(: a (Weird x) (STV 1.0 0.99))\n(: b (Member x y) (STV 1.0 0.99))", L, tmp_path)
    r = ad.parse_item("x", "t")
    assert len(r.accepted) == 1 and read_log(log)[0]["stage"] == "petta"


def test_loader_error_return_value_rejected(tmp_path):
    class ErrLoader:
        def add_atom(self, a):
            return "(Error (foo) bad)"
    ad, _, log = mk("(: a (Member x y) (STV 1.0 0.99))", ErrLoader(), tmp_path)
    r = ad.parse_item("x", "t")
    assert r.accepted == [] and read_log(log)[0]["stage"] == "petta"


def test_query_separated(tmp_path):
    ad, _, _ = mk("(: $prf (Member grace pilot) $tv)", None, tmp_path)
    r = ad.parse_item("x", "Is Grace a pilot?")
    assert r.queries == ["(: $prf (Member grace pilot) $tv)"] and r.accepted == []


def test_normalise_and_to_premises():
    n = sp.tokenize  # noqa
    node = sp.parse_one(sp.tokenize("(: r (Implication (And (P $a) (Q $a)) (R $a)) (STV 1.0 0.9))"), 0)[0]
    out = [sp.to_str(x) for x in sp.normalise(node)]
    assert out == ["(: r (Implication (And (P $a) (Q $a)) (R $a)) (STV 1.0 0.9))"]


def test_normalise_split_conclusions():
    node = sp.parse_one(sp.tokenize(
        "(: r (Implication (Premises (P $a)) (Conclusions (R $a) (S $a))) (STV 1.0 0.9))"), 0)[0]
    out = [sp.to_str(x) for x in sp.normalise(node)]
    assert out == ["(: r_c1 (Implication (P $a) (R $a)) (STV 1.0 0.9))",
                   "(: r_c2 (Implication (P $a) (S $a)) (STV 1.0 0.9))"]


def test_normalise_single_premise_unchanged():
    node = sp.parse_one(sp.tokenize("(: r (Implication (P $a) (R $a)) (STV 1.0 0.9))"), 0)[0]
    assert sp.to_str(sp.normalise(node)[0]) == "(: r (Implication (P $a) (R $a)) (STV 1.0 0.9))"


def test_normalise_premises_form_rewritten_to_and():
    node = sp.parse_one(sp.tokenize(
        "(: r (Implication (Premises (P $a) (Q $a)) (Conclusions (R $a))) (STV 1.0 0.9))"), 0)[0]
    assert sp.to_str(sp.normalise(node)[0]) == "(: r (Implication (And (P $a) (Q $a)) (R $a)) (STV 1.0 0.9))"


def test_interpretation_wrapper(tmp_path):
    ad, _, _ = mk("(Interpretation r1 (: e (Beside a b) (STV 1.0 0.99)))", None, tmp_path)
    assert ad.parse_item("x", "t").accepted == ["(Interpretation r1 (: i_x__e (Beside a b) (STV 1.0 0.99)))"]


def test_item_text_fields():
    assert sp.item_text({"content": "a"}) == "a"
    assert sp.item_text({"note": "b"}) == "b"
    assert sp.item_text("c") == "c"
    with pytest.raises(ValueError):
        sp.item_text({"x": 1})


def test_safe_id():
    assert sp.safe_id("wm-12:ab") == "i_wm_12_ab"


def test_max_chars_truncates(tmp_path):
    seen = []
    ad = sp.SemParseAdapter(lambda s, u: seen.append(u) or "(: a (P x) (STV 1.0 0.9))", system="S", max_chars=5)
    ad.parse_item("x", "abcdefghij")
    assert seen == ["TEXT: abcde"]


def test_prompt_sha_recorded(tmp_path):
    ad, _, log = mk("(: a (P x) (STV 1.0 1.0))", None, tmp_path)
    ad.parse_item("x", "t")
    import hashlib
    assert read_log(log)[0]["prompt_sha256"] == hashlib.sha256(b"SYS").hexdigest()


def test_or_inside_and_rejected(tmp_path):
    L = FakeLoader()
    ad, _, log = mk("(: x (And (Member o offer) (Or (Member o a) (Member o b)) (Past o)) (STV 1.0 0.99))\n"
                    "(: y (Or (And (Theme o v1) (Member v1 a)) (And (Theme o v2) (Member v2 b))) (STV 1.0 0.99))",
                    L, tmp_path)
    r = ad.parse_item("x", "t")
    assert len(r.accepted) == 1 and "i_x__y" in r.accepted[0]
    assert "Or inside And" in r.rejected[0][1] and read_log(log)[0]["stage"] == "structure"
    assert L.atoms == r.accepted


def test_skolems_scoped_per_item(tmp_path):
    ad, _, _ = mk("(: a (Member sk_request_1 request) (STV 1.0 0.99))", None, tmp_path)
    r1 = ad.parse_item("n1", "t"); r2 = ad.parse_item("n2", "t")
    assert r1.accepted == ["(: i_n1__a (Member sk_request_1__i_n1 request) (STV 1.0 0.99))"]
    assert r1.accepted[0].split()[3] != r2.accepted[0].split()[3]


def test_preamble_prepended_file_untouched(tmp_path, monkeypatch):
    """Track M: pre-instruction block goes before the pinned prompt; the file itself is not modified."""
    from wmtm import semparse_preamble as pre
    import hashlib
    p = tmp_path / "prompt.txt"; p.write_text("SYS")
    seen = []
    monkeypatch.delenv("WMTM_SEMPARSE_PREAMBLE", raising=False)
    ad = sp.SemParseAdapter(lambda s, u: seen.append(s) or "(: a (Member x y) (STV 1.0 0.9))", prompt_path=str(p))
    ad.parse_item("i1", "x is a y")
    assert seen[0] == pre.PREAMBLE + "SYS" and seen[0].endswith("SYS") and p.read_text() == "SYS"
    assert ad.preamble and ad.file_sha256 == hashlib.sha256(b"SYS").hexdigest() != ad.prompt_sha256
    monkeypatch.setenv("WMTM_SEMPARSE_PREAMBLE", "0")
    assert sp.SemParseAdapter(lambda s, u: "", prompt_path=str(p)).system == "SYS"
    assert sp.SemParseAdapter(lambda s, u: "", system="RAW").system == "RAW"     # explicit system: no preamble


# ------------------------------------------------------------ integration: normalise() output on the real engine
import os as _os, subprocess as _sp, sys as _sys, json as _json
from wmtm import runtime_config as _rc
_CFG = _rc.resolve()
_HAVE_PC = _os.path.isdir(_os.path.join(_CFG["petta_dir"], "python")) and \
    _os.path.isdir(_os.path.join(_CFG["pettachainer_dir"], "pettachainer"))

_ENGINE_SCRIPT = r"""
import sys, os, json
petta, vendor = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(petta, "python")); sys.path.insert(0, vendor)
os.environ["PETTA_PATH"] = petta
from pettachainer.pettachainer import PeTTaChainer
spec = json.loads(sys.stdin.read())
h = PeTTaChainer(); fails = []
for s in spec["atoms"]:
    try: h.add_atom(s)
    except Exception as e: fails.append([s, type(e).__name__])
out = {}
for g in spec["goals"]:
    r = h.query("(: $prf %s $tv)" % g, steps=200, timeout_sec=0)
    out[g] = [str(x) for x in ([r] if isinstance(r, str) else list(r or []))]
print("JSON " + json.dumps({"fails": fails, "res": out}))
"""


def _engine(atoms, goals):
    p = _sp.run([_sys.executable, "-c", _ENGINE_SCRIPT, _CFG["petta_dir"], _CFG["pettachainer_dir"]],
                input=_json.dumps({"atoms": atoms, "goals": goals}), capture_output=True, text=True,
                env=_rc.worker_env(_CFG), timeout=180)
    line = [l for l in p.stdout.splitlines() if l.startswith("JSON ")]
    assert line, p.stderr[-2000:]
    return _json.loads(line[-1][5:])


@pytest.mark.skipif(not _HAVE_PC, reason="vendored PeTTa / PeTTaChainer not present")
def test_integration_normalise_output_loads_and_derives_on_engine():
    """answer 6: normalise() output must compile on 202b9379 and chain (Premises form was rejected)."""
    rules = ["(: r (Implication (Premises (P $a) (Q $a)) (Conclusions (R $a))) (STV 1.0 0.9))",
             "(: m (Implication (Premises (P $a)) (Conclusions (S $a) (T $a))) (STV 1.0 0.9))"]
    atoms = []
    for r in rules:
        atoms += [sp.to_str(n) for n in sp.normalise(sp.parse_one(sp.tokenize(r), 0)[0])]
    assert not any("Premises" in a or "Conclusions" in a for a in atoms)
    atoms += ["(: f1 (P x) (STV 1.0 0.9))", "(: f2 (Q x) (STV 1.0 0.9))"]
    out = _engine(atoms, ["(R x)", "(S x)", "(T x)", "(R y)"])
    assert out["fails"] == [], out["fails"]
    for g in ("(R x)", "(S x)", "(T x)"):
        assert any("STV" in x for x in out["res"][g]), (g, out["res"][g])
    assert not any("STV" in x for x in out["res"]["(R y)"])          # negative control


# --- narrow_preload STOPGAP (t-2026-11-10-wmtm-narrow-preload): M2 rewrite before the PeTTa load ---------------

class NarrowRefusingLoader(FakeLoader):
    """Mimics PeTTaChainer: a narrowed class under Member is refused."""
    def add_atom(self, a):
        if "(Member" in a and "(Narrow" in a:
            raise RuntimeError("member_class: narrowed class under Member")
        return super().add_atom(a)


NARROW_REPLY = "(: f (Member sk_a (Narrow pilot (Mod harbour))) (STV 1.0 0.9))"


def test_narrow_preload_member_narrow_loads(tmp_path):
    L = NarrowRefusingLoader()
    ad, _, log = mk(NARROW_REPLY, L, tmp_path)
    r = ad.parse_item("m1", {"content": "x"})
    assert len(r.accepted) == 2 and not r.rejected
    fact, rule = r.accepted
    assert "(Narrow" not in fact and "pilot__nw_" in fact and fact.startswith("(: i_m1__f (Member ")
    assert rule.startswith("(: nwdef_pilot__nw_") and "(Member $x pilot))" in rule
    assert L.atoms == r.accepted and read_log(log) == []


def test_narrow_preload_negative_control_unrewritten_is_refused(tmp_path, monkeypatch):
    """Without the rewrite the same statement is refused at stage petta (the pre-fix behaviour)."""
    monkeypatch.setattr(sp, "narrow_preload", lambda n: (n, []))
    L = NarrowRefusingLoader()
    ad, _, log = mk(NARROW_REPLY, L, tmp_path)
    r = ad.parse_item("m1", {"content": "x"})
    assert r.accepted == [] and [d["stage"] for d in read_log(log)] == ["petta"]


def test_narrow_preload_plain_member_untouched():
    n = [":", "m", ["Member", "a", "pilot"], ["STV", "1.0", "0.9"]]
    assert sp.narrow_preload(n) == (n, [])


def test_narrow_preload_nwdef_once_per_symbol(tmp_path):
    L = NarrowRefusingLoader()
    ad, _, _ = mk(NARROW_REPLY + "\n(: g (Member sk_b (Narrow pilot (Mod harbour))) (STV 1.0 0.9))", L, tmp_path)
    r = ad.parse_item("m1", {"content": "x"})
    assert sum(a.startswith("(: nwdef_") for a in r.accepted) == 1 and len(r.accepted) == 3
    r2 = ad.parse_item("m2", {"content": "x"})          # same symbol, later note: rule not loaded again
    assert sum(a.startswith("(: nwdef_") for a in L.atoms) == 1
    assert sum(a.startswith("(: nwdef_") for a in r2.accepted) == 1   # still reported as part of the parse


def test_narrow_preload_nested_defines_chain():
    n = [":", "n", ["Member", "a", ["Narrow", ["Narrow", "pilot", ["Mod", "harbour"]], ["Mod", "night"]]],
         ["STV", "1.0", "0.9"]]
    out, rules = sp.narrow_preload(n)
    assert "Narrow" not in sp.to_str(out) and len(rules) == 2
    assert any("(Member $x pilot))" in r for r in rules)


def test_narrow_preload_f1_groupof_left_as_written(tmp_path):
    """F1 guard: no GroupOf->PartOf bridge and no rename of a GroupOf narrow; it stays refused as before."""
    g = [":", "g", ["GroupOf", "sk_g", ["Narrow", "pilot", ["Mod", "harbour"]]], ["STV", "1.0", "0.9"]]
    assert sp.narrow_preload(g) == (g, [])
    L = FakeLoader(fail_on="(GroupOf")
    ad, _, log = mk(sp.to_str(g), L, tmp_path)
    r = ad.parse_item("m1", {"content": "x"})
    assert r.accepted == [] and not any("PartOf" in a for a in L.atoms)
    # control: the mapped Member form in the same reply IS rewritten, so the guard is shape-specific
    ad2, _, _ = mk(sp.to_str(g) + "\n" + NARROW_REPLY, FakeLoader(fail_on="(GroupOf"), tmp_path)
    assert len(ad2.parse_item("m2", {"content": "x"}).accepted) == 2


def test_narrow_preload_f2_modifier_never_a_property(tmp_path):
    """F2 guard: the modifier (harbour) appears in no loaded atom as a predicate or argument."""
    L = NarrowRefusingLoader()
    ad, _, _ = mk(NARROW_REPLY, L, tmp_path)
    r = ad.parse_item("m1", {"content": "x"})
    toks = [t for a in r.accepted for t in sp.tokenize(a)]
    assert "harbour" not in toks and "Mod" not in toks
    # control: a statement that really names harbour keeps it (the check can see the token)
    ad2, _, _ = mk("(: h (Member sk_a harbour) (STV 1.0 0.9))", FakeLoader(), tmp_path)
    assert "harbour" in sp.tokenize(ad2.parse_item("m2", {"content": "x"}).accepted[0])


def test_recover_rejected_uses_live_admit(tmp_path, monkeypatch):
    """A logged petta reject (already named) loads via recover_rejected; it calls the same _admit as parse_item."""
    L = NarrowRefusingLoader()
    ad, _, log = mk("", L, tmp_path)
    logged = "(: i_m1__f (Member sk_a__i_m1 (Narrow pilot (Mod harbour))) (STV 1.0 0.9))"
    seen = []
    real = sp.SemParseAdapter._admit
    monkeypatch.setattr(sp.SemParseAdapter, "_admit", lambda self, *a, **k: seen.append(1) or real(self, *a, **k))
    r = ad.recover_rejected("m1", [logged])
    assert seen == [1] and len(r.accepted) == 2 and r.accepted[0].startswith("(: i_m1__f (Member sk_a__i_m1 pilot__nw_")


def test_recover_rejected_inheritance_narrow_is_m2_mapped(tmp_path):
    """Inheritance over a Narrow is an M2-mapped shape (as in parse_normalise): recovered as symbol + one nwdef;
    the modifier never becomes a property (F2)."""
    L = NarrowRefusingLoader()
    ad, _, log = mk("", L, tmp_path)
    r = ad.recover_rejected("m1", ["(: i_m1__k (Inheritance (Narrow request (Mod user)) open) (STV 0.0 0.9))"])
    assert len(r.accepted) == 2 and r.accepted[0].startswith("(: i_m1__k (Inheritance request__nw_")
    assert "user" not in [x for a in r.accepted for x in sp.tokenize(a)]


def test_recover_rejected_negative_control_groupof_narrow_stays_refused(tmp_path):
    """GroupOf over a Narrow is not mapped (F1: no bridge): recovery leaves it as written, refused at petta."""
    L = FakeLoader(fail_on="(GroupOf")
    ad, _, log = mk("", L, tmp_path)
    r = ad.recover_rejected("m1", ["(: i_m1__g (GroupOf sk_g__i_m1 (Narrow pilot (Mod harbour))) (STV 1.0 0.9))"])
    assert r.accepted == [] and [d["stage"] for d in read_log(log)] == ["petta"]
    assert not any("PartOf" in a for a in L.atoms)
