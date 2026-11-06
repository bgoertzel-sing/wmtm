# wmtm-side stopgaps for upstream problems

Each entry is marked in code with `STOPGAP(upstream: <item>)`. Remove it when the upstream item is fixed on the pinned HEAD.

| Item | Upstream | Code | What it does | Remove when |
|---|---|---|---|---|
| PC-EQ1 Equivalence add rejected | PeTTaChainer bdae8d7e: adding an `(Equivalence ...)` atom from the semparse cache fails with fact_without_free_variables (not on LIST-roman R1-R8; raised as a new engine item for Roman in P4 rev4) | wmtm/pc_shadow.py shadow_rules (`STOPGAP(upstream: PC-EQ1 ...)`) | Equivalence forms are not passed to the shadow worker; only flat Member->Member Implications and Narrow defining rules are | PeTTaChainer on the pinned HEAD accepts the Equivalence add, then pass it through and drop this row |

(F7 naming was removed from this list in P4 rev3: per Track P README 8cf5006 it is the design.)
