"""Flag-off differential: same seeded admit/tick/forget sequence on a given wmtm tree; prints eviction trace."""
import json, random, sys, os
sys.path.insert(0, sys.argv[1])
for k in list(os.environ):
    if k.startswith("WMTM_"): del os.environ[k]
from wmtm.store import WMTMStore
from wmtm.orchestrator import WMTMOrchestrator
out = []
for seed in range(200):
    rnd = random.Random(seed)
    orch = WMTMOrchestrator(WMTMStore(capacity=rnd.randint(2, 8)), use_goalchainer=False)
    st = orch.store
    for step in range(rnd.randint(10, 60)):
        op = rnd.random()
        if op < 0.6:
            sid = "i%d" % rnd.randint(0, 40)
            stype = rnd.choice(["recalled", "derived", "asserted", "user"])
            it = st.admit(sid, "t" + sid, source_type=stype, initial_sti=round(rnd.uniform(0, 10), 3))
            it.utility = round(rnd.uniform(0, 6), 3)
            it.attention.lti = round(rnd.uniform(0, 2), 3)
            if rnd.random() < 0.2: it.age = rnd.randint(0, 80)
        else:
            orch.forget_phase()
        out.append([seed, step, sorted(st._items), [e.id for e in st.drain_pending_evicted()],
                    [r.item_id for r in orch.forget_log.get_records()]])
print(json.dumps(out))
