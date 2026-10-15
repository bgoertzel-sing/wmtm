"""Reference Iter tool wrapper: what tools/goalchainer_decide.py becomes (not installed)."""
from pathlib import Path
from wmtm.api import WMTM, WMTMConfig

DESCRIPTION = "Run the GoalChainer goal-aware decision pipeline. Arg: request (str) describing the decision scenario. Returns ranked actions with deontic status and motivation."


def run(request):
    return WMTM(WMTMConfig(state_dir=Path(__file__).resolve().parent.parent / 'memory')).decide(request)
