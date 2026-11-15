#!/usr/bin/env python3
"""t-2026-11-15-wmtm-master-shadow-wiring: the driver that built run/spec.json (review 1, finding 5).
A store holding the note ids (source_type note), then wmtm.pc_shadow.build_snapshot with
shadow_load_order=master_ops.  shadow_max_goals=0 (no cap) so all goals are asked; the runtime default is 60.
Usage: python3 build_spec.py NOTE_IDS PARSED_JSONL SPH_TEMPLATES OUT_SPEC [MAX_GOALS]"""
import sys, os, json
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from wmtm import pc_shadow as PS, runtime_config as rc

class It:
    def __init__(s, i): s.id = i; s.source_type = "note"
class St:
    def __init__(s, ids): s.ids = ids
    def get_active_set(s): return [It(i) for i in s.ids]

if __name__ == "__main__":
    ids_path, parsed, tdir, out = sys.argv[1:5]
    mg = int(sys.argv[5]) if len(sys.argv) > 5 else 0
    notes = [l.strip() for l in open(ids_path) if l.strip()]
    cfg = rc.resolve()
    cfg.update(shadow_load_order="master_ops", shadow_sph_templates=tdir, shadow_master_parsed=parsed, shadow_max_goals=mg)
    sp = PS.build_snapshot(St(notes), k=len(notes), cfg=cfg)
    json.dump(sp, open(out, "w"))
    print(json.dumps({"goals": len(sp["goals"]), "goal_total": sp["goal_total"], "master_ops": len(sp["master_ops"]),
                      "semparse_items": sp["semparse_items"], "unparsed_items": sp["unparsed_items"], "max_goals": mg}))
