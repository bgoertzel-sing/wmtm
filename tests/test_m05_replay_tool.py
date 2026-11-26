"""M-05: tools/m05_replay.py (frozen-run eviction replay) - ids/hashes only, deterministic, flag honoured."""
import importlib.util
import json
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "synthetic", "wmtm_state.json")


def _tool():
    spec = importlib.util.spec_from_file_location("m05_replay", os.path.join(ROOT, "tools", "m05_replay.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(tmp_path, flag, name):
    out = tmp_path / name
    assert _tool().main([FIXTURE, str(flag), "--capacity", "12", "--out", str(out)]) == 0
    lines = out.read_text().splitlines()
    assert len(lines) == 1
    return json.loads(lines[0]), out.read_text()


def test_replay_writes_ids_and_hashes_only(tmp_path):
    rec, raw = _run(tmp_path, 0, "f0.jsonl")
    snap = json.load(open(FIXTURE))
    n = len(snap["store"]["items"])
    assert len(rec["evicted"]) + len(rec["surviving"]) == n
    assert len(rec["surviving"]) <= 12
    for row in rec["evicted"] + rec["surviving"]:
        assert "content" not in row and len(row["content_sha256"]) == 64
        assert set(row) >= {"id", "sti", "utility", "lti", "source_type"}
    for item in snap["store"]["items"].values():          # no note text leaks into the output
        assert str(item["content"]) not in raw


def test_replay_is_deterministic_and_flag_matters(tmp_path):
    a, _ = _run(tmp_path, 0, "a.jsonl")
    b, _ = _run(tmp_path, 0, "b.jsonl")
    c, _ = _run(tmp_path, 1, "c.jsonl")
    assert a == b
    assert a["flag"] == 0 and c["flag"] == 1
    assert [e["id"] for e in a["evicted"]] != [e["id"] for e in c["evicted"]]


def test_replay_directory_and_no_snapshot(tmp_path):
    d = tmp_path / "run"; d.mkdir()
    (d / "a.json").write_text(open(FIXTURE).read())
    (d / "other.json").write_text("{\"x\": 1}")
    out = tmp_path / "o.jsonl"
    assert _tool().main([str(d), "1", "--out", str(out)]) == 0
    assert len(out.read_text().splitlines()) == 1
    empty = tmp_path / "empty"; empty.mkdir()
    assert _tool().main([str(empty), "0", "--out", str(tmp_path / "e.jsonl")]) == 2
