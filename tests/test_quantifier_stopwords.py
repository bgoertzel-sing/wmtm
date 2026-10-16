"""Quantifier/negation pronouns must not become triple subjects or objects."""
from wmtm.inference import extract_triples


def _t(text):
    return [(t.subject, t.relation, t.object) for t in extract_triples(text)]


def test_quantifier_subjects_dropped():
    for text in ["nothing has room", "none has budget", "someone has access",
                 "everything is a test", "nobody has keys"]:
        assert _t(text) == [], text


def test_real_subjects_kept():
    assert _t("flipper has antenna") == [("flipper", "has", "antenna")]
    assert _t("grace is a pilot") == [("grace", "is-a", "pilot")]
