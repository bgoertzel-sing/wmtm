"""Replay runner: executes Iter transform/derive steps in ONE process.

Mirrors how Iter calls a transformation (iter.py invoke_dynamic): the
module is loaded from <root>/transformations/wmtm_context.py with
sys.path[0] = <root> and cwd = <root>. The wall clock (time.time and
datetime.now) is frozen per step so two implementations see identical
time; within a step the clock does not advance (the 20 s budget never
trips).

usage: runner.py ROOT STEPS_JSON OUT_JSON [EXTRA_SYS_PATH]
"""
import contextlib, datetime as _dtmod, importlib.util, io, json, os, sys, time

ROOT, STEPS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
EXTRA = sys.argv[4] if len(sys.argv) > 4 else ""

if "iter-port" in os.path.realpath(ROOT):
    raise SystemExit("refusing to run against a live iter-port tree")

_NOW = [0.0]
time.time = lambda: _NOW[0]


class _FrozenDT(_dtmod.datetime):
    @classmethod
    def now(cls, tz=None):
        return _dtmod.datetime.fromtimestamp(_NOW[0], tz)


_dtmod.datetime = _FrozenDT

os.environ.pop("JOURNAL_DIR", None)
os.chdir(ROOT)
sys.path.insert(0, ROOT)
if EXTRA:
    sys.path.insert(1, EXTRA)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, rel))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


steps = json.load(open(STEPS))
ctx_mod = None
results = []
for step in steps:
    _NOW[0] = step["t"]
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        if step["kind"] == "turn":
            if ctx_mod is None:
                ctx_mod = _load("wmtm_context", "transformations/wmtm_context.py")
            msgs, tools = ctx_mod.transform(json.loads(json.dumps(step["messages"])), [])
            out = msgs
        elif step["kind"] == "derive":
            tool = _load("wmtm_derive", "tools/wmtm_derive.py")
            out = tool.run(step["note"], step.get("source_ids"))
        else:
            raise SystemExit(f"bad step kind {step['kind']}")
    files = {}
    for rel in ("memory/_wmtm_state.json", "memory/_wmtm_pending_derives.jsonl", "memory/_journal/journal.metta"):
        fp = os.path.join(ROOT, rel)
        files[rel] = open(fp, encoding="utf-8").read() if os.path.exists(fp) else None
    j = files.pop("memory/_journal/journal.metta")
    files["journal_len"] = None if j is None else len(j)
    files["journal_tail"] = None if j is None else j[int(os.environ.get("WMTM_REPLAY_JOURNAL_BASE", "0")):]
    results.append({"out": out, "stderr": err.getvalue(), "files": files})

json.dump(results, open(OUT, "w"))
