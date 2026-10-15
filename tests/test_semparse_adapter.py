"""Unit tests for wmtm/semparse_adapter.py (LLM mocked, PeTTa loader mocked)."""
import json
import pytest

from wmtm import semparse_adapter as sp


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
    assert out == ["(: r (Implication (Premises (P $a) (Q $a)) (Conclusions (R $a))) (STV 1.0 0.9))"]


def test_normalise_split_conclusions():
    node = sp.parse_one(sp.tokenize(
        "(: r (Implication (Premises (P $a)) (Conclusions (R $a) (S $a))) (STV 1.0 0.9))"), 0)[0]
    out = [sp.to_str(x) for x in sp.normalise(node)]
    assert out == ["(: r_c1 (Implication (Premises (P $a)) (Conclusions (R $a))) (STV 1.0 0.9))",
                   "(: r_c2 (Implication (Premises (P $a)) (Conclusions (S $a))) (STV 1.0 0.9))"]


def test_normalise_single_premise_wrapped():
    node = sp.parse_one(sp.tokenize("(: r (Implication (P $a) (R $a)) (STV 1.0 0.9))"), 0)[0]
    assert sp.to_str(sp.normalise(node)[0]) == \
        "(: r (Implication (Premises (P $a)) (Conclusions (R $a))) (STV 1.0 0.9))"


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
