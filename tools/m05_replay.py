"""tools/m05_replay.py - M-05 eviction replay on a frozen run (t-2026-11-26-wmtm-m05-eviction).

Usage: python3 tools/m05_replay.py <frozen-run path> <flag 0|1> [--capacity N] [--cycles K] [--out FILE]

<frozen-run path>: one orchestrator snapshot JSON (snapshot_state() output, e.g. wmtm_state.json), or a
directory; every *.json in it that holds a "store" is replayed, in sorted path order.
For each snapshot: restore it, optionally lower the store capacity to N (forces capacity eviction), then run
forget_phase K times (default 1) with composite_eviction = <flag>.  Writes one JSON line per snapshot with
the eviction order and the STI/utility/LTI of each evicted and surviving item.  Ids and sha256 content
hashes only: no note text is ever written.  All WMTM_* env vars are cleared so only <flag> varies.
"""
import argparse, hashlib, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for _k in list(os.environ):
    if _k.startswith("WMTM_"):
        del os.environ[_k]

from wmtm.orchestrator import WMTMOrchestrator   # noqa: E402
from wmtm.store import WMTMStore                  # noqa: E402


def _row(it):
    return {"id": it.id, "content_sha256": hashlib.sha256(str(it.content).encode("utf-8")).hexdigest(),
            "source_type": it.source_type, "sti": it.attention.sti, "utility": it.utility,
            "lti": it.attention.lti, "age": it.age}


def snapshots(path):
    if os.path.isdir(path):
        for root, _d, files in sorted(os.walk(path)):
            for f in sorted(files):
                if f.endswith(".json"):
                    yield os.path.join(root, f)
    else:
        yield path


def replay_one(snap, flag, capacity=None, cycles=1):
    orch = WMTMOrchestrator(WMTMStore(capacity=snap["store"]["capacity"]), use_goalchainer=False)
    orch.restore_state(snap)
    if capacity is not None:
        orch.store.capacity = capacity
    cfg = {"composite_eviction": bool(flag)}
    order = []
    for c in range(cycles):
        for ev in orch.forget_phase(cfg):
            order.append(dict(_row(ev), cycle=c))
    survivors = sorted((_row(it) for it in orch.store._items.values()), key=lambda r: r["id"])
    return {"flag": int(bool(flag)), "capacity": orch.store.capacity, "cycles": cycles,
            "evicted": order, "surviving": survivors}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path"); ap.add_argument("flag", type=int, choices=(0, 1))
    ap.add_argument("--capacity", type=int); ap.add_argument("--cycles", type=int, default=1)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    out = open(a.out, "w") if a.out else sys.stdout
    n = 0
    for p in snapshots(a.path):
        try:
            snap = json.load(open(p))
        except (OSError, ValueError):
            continue
        if not isinstance(snap, dict) or "store" not in snap:
            continue
        rec = replay_one(snap, a.flag, a.capacity, a.cycles)
        rec["snapshot_sha256"] = hashlib.sha256(open(p, "rb").read()).hexdigest()
        out.write(json.dumps(rec, sort_keys=True) + "\n"); n += 1
    if a.out:
        out.close()
    print("m05_replay: %d snapshot(s), flag=%d" % (n, a.flag), file=sys.stderr)
    return 0 if n else 2


if __name__ == "__main__":
    sys.exit(main())
