;; t-2026-11-17-wmtm-extra-rules: extra rules loaded after the seeded master rules (sph 24e37182), behind the
;; flag shadow_extra_rules (WMTM_PC_SHADOW_EXTRA_RULES, default off).  Premises use only predicates the parser
;; emits under pettachainer-master (Time/Hour/Minute/Before/Member/Agent/Patient/Bearer/Theme/Past/Directive).
;; Conclusions Current/Valid/Applies are new 1- and 2-ary predicates (master Holds is 2-ary: Holds state prop).
;; hour_order: same-day assumption - the parser emits Hour/Minute mostly without Year/Month/Day (reads: time)
(: xr_hour_order (Implication (And (Time $e1 $a) (Hour $a $h1) (Time $e2 $b) (Hour $b $h2) (Compute < ($h1 $h2) -> true)) (Before $e1 $e2)) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
;; minute_order: within one hour, an earlier minute precedes (reads: time)
(: xr_minute_order (Implication (And (Time $e1 $a) (Hour $a $h) (Minute $a $m1) (Time $e2 $b) (Hour $b $h) (Minute $b $m2) (Compute < ($m1 $m2) -> true)) (Before $e1 $e2)) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
;; supersedes_not_current: what is superseded is no longer current (Agent/Patient and Bearer/Theme frames)
(: xr_supersedes_not_current_ap (Implication (And (Member $s supersede) (Patient $s $y)) (Not (Current $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
(: xr_supersedes_not_current_bt (Implication (And (Member $s supersede) (Theme $s $y)) (Not (Current $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
;; contradicts_not: what is contradicted no longer holds (1-ary Valid; see header)
(: xr_contradicts_not_ap (Implication (And (Member $c contradict) (Patient $c $y)) (Not (Valid $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
(: xr_contradicts_not_bt (Implication (And (Member $c contradict) (Theme $c $y)) (Not (Valid $y))) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
;; directive_inherit: a stated directive applies to every task
(: xr_directive_inherit (Implication (And (Directive $f) (Member $t task)) (Applies $f $t)) (CTV (STV 1.0 0.8) (STV 0.0 0.001)))
;; passed_closes (as close_closes): a past close of a task -> the task is closed.  The pass-gated form
;; (Member p pass)(Agent p r)(Member r review)(Past p) shares no variable with the close in the parses, so it joined a
;; pass from one note with a close from another (shadow probe, steps 300); the review gate is left to the parser.
(: xr_close_closes (Implication (And (Member $c close) (Patient $c $t) (Past $c)) (Member $t closed)) (CTV (STV 1.0 0.9) (STV 0.0 0.001)))
