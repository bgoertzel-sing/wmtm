#!/usr/bin/env python3
"""t-2026-11-15-wmtm-master-shadow-wiring (review 1, finding 4): legacy byte diff through the worker.
Run from a repo root (old 4193844 worktree or new head).  Builds a legacy spec from a synthetic store (the tests'
fake semparse, no note content, shadow_load_order unset) and runs wmtm.workers.pc_shadow on it.
Usage: python3 legacy_bytediff.py OUTDIR PETTA VENDOR"""
import sys, os, json, subprocess
REPO = os.getcwd(); sys.path.insert(0, REPO); sys.path.insert(0, os.path.join(REPO, "tests"))
from wmtm import pc_shadow as PS, runtime_config as rc
from wmtm.store import WMTMStore
import _fake_semparse
class MP:
    def setattr(self, o, n, v): setattr(o, n, v)
_fake_semparse.install(MP())
out, petta, vendor = sys.argv[1:4]; os.makedirs(out, exist_ok=True)
SYN = ["cat is a mammal", "mammal is an animal", "dog is a mammal", "rain -> wet", "wet -> slippery", "sky is blue"]
st = WMTMStore()
for i, t in enumerate(SYN):
    st.admit("s%d" % i, t, source_type="recalled", initial_sti=1.0)
cfg = rc.resolve(); cfg.pop("shadow_load_order", None)
sp = PS.build_snapshot(st, k=len(SYN), cfg=cfg, cycle=1)
sp.pop("ts", None)
json.dump(sp, open(os.path.join(out, "spec.json"), "w"), sort_keys=True)
cfg.update(petta_dir=petta, pettachainer_dir=vendor)
r = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", os.path.join(out, "spec.json"),
                    "--out", os.path.join(out, "shadow.jsonl"), "--petta", petta, "--vendor", vendor, "--keep-spec"],
                   env=rc.worker_env(cfg), cwd=REPO, timeout=300)
print("rc", r.returncode)
