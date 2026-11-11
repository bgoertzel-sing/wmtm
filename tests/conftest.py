import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_parse_budget(tmp_path_factory, monkeypatch):
    """Each test gets its own host-wide parse budget dir (task ledger + task-log registry), so tests never read or
    write ~/.wmtm/parse_budget and never share counted calls with each other."""
    from wmtm import runtime_config as rc
    d = str(tmp_path_factory.mktemp("parse_budget"))
    e, t, _d, b = rc.SPEC["parse_budget_dir"]
    monkeypatch.setitem(rc.SPEC, "parse_budget_dir", (e, t, d, b))   # holds even where a test clears WMTM_* env
    monkeypatch.setenv("WMTM_PARSE_BUDGET_DIR", d)
    monkeypatch.delenv("WMTM_PARSE_LIVE_DIR", raising=False)
    monkeypatch.delenv("WMTM_PARSE_ROLE", raising=False)


@pytest.fixture(autouse=True)
def _fake_goalchainer_v2(monkeypatch):
    """v0.7: the goal engine defaults to GoalChainer v2, run as a subprocess in its own environment.  Unit tests use
    a protocol-compatible test double (tests/_fake_v2_runner.py, run by this interpreter) through the same
    subprocess client; tests/test_goals_v2.py::test_real_* use the real runtime when WMTM_TEST_GC2_PYTHON is set."""
    from wmtm import runtime_config as rc
    fake = str(Path(__file__).resolve().parent / "_fake_v2_runner.py")
    for key, val in (("goal_v2_python", sys.executable), ("goal_v2_runner", fake)):
        e, t, _d, b = rc.SPEC[key]
        monkeypatch.setitem(rc.SPEC, key, (e, t, val, b))
