"""Reference Iter tool wrapper: what tools/wmtm_derive.py becomes (not installed)."""
from pathlib import Path
from wmtm.api import WMTM, WMTMConfig

DESCRIPTION = "Register a new derived belief in Working Memory. Arg: note (string) describing the conclusion. Optional: source_ids (list of str, the memory IDs this was derived from)."


def run(note, source_ids=None):
    return WMTM(WMTMConfig(state_dir=Path(__file__).resolve().parent.parent / 'memory')).derive(note, source_ids)
