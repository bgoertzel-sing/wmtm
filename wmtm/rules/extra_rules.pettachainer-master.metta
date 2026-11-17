;; t-2026-11-17-wmtm-extra-rules-v2: extra rules loaded after the seeded master rules (sph 24e37182), behind the
;; flag shadow_extra_rules (WMTM_PC_SHADOW_EXTRA_RULES, default off).  Premises use only predicates the parser
;; emits under pettachainer-master (Member/Patient/Theme).  Conclusions Current/Valid are new 1-ary predicates.
;; Goals from these rules are kept only when all bindings come from one note (master_loader.rule_goals scoped=).
;; supersedes_not_current: what is superseded is no longer current (Patient and Theme frames)
(: xr_supersedes_not_current_ap (Implication (And (Member $s supersede) (Patient $s $y)) (Not (Current $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
(: xr_supersedes_not_current_bt (Implication (And (Member $s supersede) (Theme $s $y)) (Not (Current $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
;; contradicts_not: what is contradicted no longer holds (1-ary Valid)
(: xr_contradicts_not_ap (Implication (And (Member $c contradict) (Patient $c $y)) (Not (Valid $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
(: xr_contradicts_not_bt (Implication (And (Member $c contradict) (Theme $c $y)) (Not (Valid $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
