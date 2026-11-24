"""Synthetic tests for wmtm/class_links.py (t-2026-11-24-wmtm-p01-class-links): each rule fires, and must not fire."""
from wmtm.class_links import derive, unit_of

D = "(STV 1.0 0.99)"

def rules(out, r): return [o for o in out if o["rule"] == r]

def test_unit_of():
    assert unit_of("s2_x1_member_3") == "s2_x1"
    assert unit_of("kind__foo") is None

def test_r1_fires_universal_isa():
    out = derive(["(: s1_g1_implication (Implication (Member $x badger) (Member $x mustelid)) (STV 1.0 0.9))"])
    r = rules(out, "generic_isa")
    assert len(r) == 1 and "(Inheritance badger mustelid) (STV 1 0.9)" in r[0]["atom"]
    assert r[0]["units"] == ["s1_g1"]

def test_r1_bare_generic_09():
    assert rules(derive(["(: s1_g1_i (Implication (Member $x a) (Member $x b)) (STV 0.9 0.7))"]), "generic_isa")

def test_r1_not_most_few_no():
    for s in ("0.7", "0.1", "0.0"):
        assert not rules(derive([f"(: s1_g1_i (Implication (Member $x a) (Member $x b)) (STV {s} 0.9))"]), "generic_isa")

def test_r1_not_ground_or_other_var_or_event():
    assert not derive(["(: s1_g1_i (Implication (Member sk_a_1 a) (Member sk_a_1 b)) (STV 0.9 0.7))"])
    assert not derive(["(: s1_g1_i (Implication (Member $x a) (Member $y b)) (STV 1.0 0.9))"])
    assert not derive(["(: s1_g1_i (Implication (Member $x a) (And (Member (sk_s $x) sleep) (Agent (sk_s $x) $x))) (STV 1.0 0.9))"])
    assert not derive(["(: s1_g1_i (Implication (And (Member $x a) (On $x sk_t)) (Member $x b)) (STV 1.0 0.9))"])

def test_r2_narrow_subset():
    st = [f"(: kind__a2 (Inheritance a2 report) {D})", f"(: kind__a1 (Inheritance a1 report) {D})",
          f"(: by_1__a2 (NarrowBy a2 (Is old)) {D})", f"(: by_2__a2 (NarrowBy a2 (Mod x)) {D})",
          f"(: by_1__a1 (NarrowBy a1 (Is old)) {D})", f"(: s3_x2_member (Member sk_r_1 a2) {D})"]
    r = rules(derive(st), "narrow_subset")
    assert len(r) == 1 and "(Inheritance a2 a1)" in r[0]["atom"] and r[0]["units"] == ["s3_x2"]


def test_r2_not_when_untraceable_to_a_parse_unit():
    st = [f"(: kind__a2 (Inheritance a2 report) {D})", f"(: kind__a1 (Inheritance a1 report) {D})",
          f"(: by_1__a2 (NarrowBy a2 (Is old)) {D})", f"(: by_2__a2 (NarrowBy a2 (Mod x)) {D})",
          f"(: by_1__a1 (NarrowBy a1 (Is old)) {D})"]
    assert not rules(derive(st), "narrow_subset")

def test_r2_not_across_bases_or_equal_or_disjoint():
    st = [f"(: kind__a (Inheritance a report) {D})", f"(: kind__b (Inheritance b memo) {D})",
          f"(: by_1__a (NarrowBy a (Is old)) {D})", f"(: by_2__a (NarrowBy a (Mod x)) {D})", f"(: by_1__b (NarrowBy b (Is old)) {D})"]
    assert not rules(derive(st), "narrow_subset")
    st = [f"(: kind__a (Inheritance a report) {D})", f"(: kind__b (Inheritance b report) {D})",
          f"(: by_1__a (NarrowBy a (Is old)) {D})", f"(: by_1__b (NarrowBy b (Is old)) {D})"]
    assert not rules(derive(st), "narrow_subset")
    st = [f"(: kind__a (Inheritance a report) {D})", f"(: kind__b (Inheritance b report) {D})",
          f"(: by_1__a (NarrowBy a (Is old)) {D})", f"(: by_1__b (NarrowBy b (Is new)) {D})"]
    assert not rules(derive(st), "narrow_subset")

def test_r3_member_link_via_r1():
    st = [f"(: s1_x1_member (Member sk_b_1 badger) {D})",
          "(: s2_g1_i (Implication (Member $x badger) (Member $x mustelid)) (STV 1.0 0.9))"]
    r = rules(derive(st), "member_link")
    assert len(r) == 1 and "(Member sk_b_1 mustelid)" in r[0]["atom"] and r[0]["units"] == ["s1_x1", "s2_g1"]

def test_r3_not_when_already_stated():
    st = [f"(: s1_x1_member (Member sk_r_1 a1) {D})", f"(: s1_x1_member_2 (Member sk_r_1 report) {D})",
          f"(: kind__a1 (Inheritance a1 report) {D})"]
    assert not rules(derive(st), "member_link")

def test_r3_not_downward():
    st = [f"(: s1_x1_member (Member sk_r_1 report) {D})", f"(: kind__a1 (Inheritance a1 report) {D})"]
    assert not derive(st)

def test_empty_and_deterministic():
    assert derive([]) == []
    st = [f"(: s1_x1_member (Member sk_b_1 badger) {D})",
          "(: s2_g1_i (Implication (Member $x badger) (Member $x mustelid)) (STV 1.0 0.9))"]
    assert derive(st) == derive(list(st))
