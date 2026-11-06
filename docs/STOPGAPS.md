# wmtm-side stopgaps for upstream problems

Each entry is marked in code with `STOPGAP(upstream: <item>)`. Remove it when the upstream item is fixed on the pinned HEAD.

| Item | Upstream | Code | What it does | Remove when |
|---|---|---|---|---|
| PC-EQ1 Equivalence add rejected | PeTTaChainer bdae8d7e: adding an `(Equivalence ...)` atom from the semparse cache fails with fact_without_free_variables (not on LIST-roman R1-R8; raised as a new engine item for Roman in P4 rev4) | wmtm/pc_shadow.py shadow_rules (`STOPGAP(upstream: PC-EQ1 ...)`) | Equivalence forms are not passed to the shadow worker; only flat Member->Member Implications and Narrow defining rules are | PeTTaChainer on the pinned HEAD accepts the Equivalence add, then pass it through and drop this row |

F7 (narrowed-class naming) is not a stopgap and is not on this list. Roman's answer (Track P README, "Roman's answers"): rejecting compound classes such as `(Narrow c R)` is intended, and naming each narrowed class with a deterministic symbol plus a defining rule `(Implication (Member $x <sym>) (Member $x c))` is the design. The code is `wmtm/pc_shadow.py` (`narrow_symbol`, `narrow_defining_rules`); it carries no `STOPGAP` marker.
