#!/usr/bin/env python3
"""Make a sandbox state dir for one arm: copy of the live flags with every path moved into the sandbox.
Usage: mkarm.py <arm name> <semparse cache dir>.  Same PeTTa + PeTTaChainer b6aacc68 for every arm."""
import json, os, sys, shutil
arm, cache = sys.argv[1], sys.argv[2]
LIVE = "/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory/_wmtm_flags.json"
st = "/tmp/lpr/loop/%s/state" % arm
if os.path.exists(os.path.dirname(st)): shutil.rmtree(os.path.dirname(st))
os.makedirs(st); os.makedirs(st + "/../goal_requests", exist_ok=True)
f = json.load(open(LIVE))
f.update({"runtime_dir": st + "/runtime", "shadow_dir": st + "/runtime/pc_shadow", "semparse_dir": cache,
          "semparse_feed": False,                      # caches prefilled; no parse spend inside the loop
          "goal_requests_dir": os.path.abspath(st + "/../goal_requests"),
          "petta_dir": "/home/openclaw/research-agent/projects/omegaclaw/p1-engine/petta-3681b9b",
          "pettachainer_dir": "/tmp/lpr/pc", "shadow_min_interval_s": 0, "_sandbox": arm})
json.dump(f, open(st + "/_wmtm_flags.json", "w"), indent=1)
print(st)
