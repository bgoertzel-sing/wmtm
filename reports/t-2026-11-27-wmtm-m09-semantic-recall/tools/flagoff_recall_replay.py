"""M-09 flag-off recall replay: run RecallBridge.recall on the synthetic journal, print ids+scores+sha256."""
import hashlib, json, random, sys, time
time.time = lambda: 1795744000.0  # frozen clock: recency term uses time.time()
from wmtm.recall_bridge import RecallBridge, parse_journal
from wmtm.store import WMTMStore
from wmtm import api, runtime_config
lines = open("tests/fixtures/synthetic/journal.metta").read().splitlines()
cl = parse_journal(lines)
rb = RecallBridge(cl)
vocab = sorted({t for c in cl for t in RecallBridge._tokenize(c.event_note or c.text)} | {t for c in cl for t in c.about_tags})
rng = random.Random(909)
out = []
kw = api._recall_semantic_kw({}) if hasattr(api, "_recall_semantic_kw") else {}
for i in range(300):
    q = " ".join(rng.sample(vocab, k=rng.randint(1, 4))) if i % 10 else "forgetting"
    store = WMTMStore(capacity=20)
    for c in rng.sample(cl, k=rng.randint(0, min(5, len(cl)))):
        store.admit(item_id=c.id, content="x")
    for args in ({}, {"floor": 0.1, "spread_seeds": "turn", "add_pct": 10.0, "request_id": None}):
        r = rb.recall(q, store, top_k=15, **args, **kw)
        out.append([i, sorted(args), [(c.cluster_id, round(c.score, 12)) for c in r]])
blob = json.dumps(out, sort_keys=True).encode()
import os
if os.environ.get("DUMP"): open(os.environ["DUMP"], "w").write(json.dumps(out, sort_keys=True, indent=0))
print(len(cl), "clusters", len(out), "recalls", sum(len(o[2]) for o in out), "candidates sha256", hashlib.sha256(blob).hexdigest())
