#!/usr/bin/env python3
"""t-2026-11-17-wmtm-impl-premise-proving-v2: build the master_ops spec for the 20 notes (no parser calls).
FLAGS: 'off' = label_replace and reference_time off; 'on' = both on; 'lr' / 'rt' = one on.
Note dates come from the note id (ep-note-YYYYMMDDTHHMMSSZ) as created_at, since the stub store has no items.
Usage: python3 build_spec_s35.py NOTE_IDS PARSED SPH_TEMPLATES OUT_SPEC FLAGS REPO"""
import sys, json, datetime as dt
sys.path.insert(0, sys.argv[6])
from wmtm import pc_shadow as PS, runtime_config as rc, semparse_adapter as SA
calls = {}
for name in ("narrow_preload", "parse", "parse_sentence", "parse_text"):
    f = getattr(SA, name, None)
    if callable(f):
        calls[name] = 0
        def spy(*a, _f=f, _n=name, **k):
            calls[_n] += 1; return _f(*a, **k)
        setattr(SA, name, spy)
class It:
    def __init__(s, i):
        s.id = i; s.source_type = "note"
        s.created_at = dt.datetime.strptime(i.split("-")[-1], "%Y%m%dT%H%M%SZ").replace(tzinfo=dt.timezone.utc).timestamp()
class St:
    def __init__(s, ids): s.ids = ids
    def get_active_set(s): return [It(i) for i in s.ids]
ids_path, parsed, tdir, out, flags = sys.argv[1:6]
notes = [l.strip() for l in open(ids_path) if l.strip()]
cfg = rc.resolve()
cfg.update(shadow_load_order="master_ops", shadow_sph_templates=tdir, shadow_master_parsed=parsed, shadow_max_goals=0)
cfg["shadow_note_impl_premise"] = flags == "ip"
cfg["shadow_note_impl_goals"] = flags != "base"
sp = PS.build_snapshot(St(notes), k=len(notes), cfg=cfg)
sp.pop("ts", None)
json.dump(sp, open(out, "w"), sort_keys=True)
print(json.dumps({"flags": flags, "goals": len(sp["goals"]), "master_ops": len(sp["master_ops"]),
                  "master_meta": sp["master_meta"], "semparse_items": sp["semparse_items"], "unparsed_items": sp["unparsed_items"],
                  "spy": calls}, sort_keys=True, default=str))
