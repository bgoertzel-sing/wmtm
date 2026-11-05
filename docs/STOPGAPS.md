# wmtm-side stopgaps for upstream problems

Each entry is marked in code with `STOPGAP(upstream: <item>)`. Remove it when the upstream item is fixed on the pinned HEAD.

| Item | Upstream | Code | What it does | Remove when |
|---|---|---|---|---|
| F7 | PeTTaChainer: "a Member class must be a symbol" (refuses `(Member x (Narrow c R))`) | `wmtm/pc_shadow.py` `narrow_symbol`, `_name_narrow`, `narrow_defining_rules` | Names each narrowed class with a deterministic symbol `<base>__nw_<sha1(form)[:10]>` and adds the defining rule `(Implication (Member $x sym) (Member $x base))` | PeTTaChainer accepts a compound Member class; then pass the Narrow form through unchanged |
