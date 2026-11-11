#!/usr/bin/env python3
"""t-2026-11-11-wmtm-graph-only-probe: run the turn script on one arm (one process per arm).

Usage: probe_turns.py --code <wmtm src dir of the arm> --state <fresh sandbox dir> --data <dir with journal.metta,
       turns.json> --out <dir>
Same script, same journal, same turns for A and B; only --code differs.  labels.json is NOT read here (the analysis
joins labels afterwards), so the labels cannot reach the scores.

Path under test: the live API turn, WMTM.observe() + WMTM.context_for(q) (api.py recall loop: rb.recall(top_k=15
[, floor]) -> store.admit(initial_sti=max(score*10, 1)) -> relevance stimulus -> request item -> stale cleanup ->
orchestrator cycle -> context block).  Config: WMTMConfig(reasoner="off", use_pln=False): no PeTTaChainer/PLN
inference, so the probe isolates recall + attention; pc_shadow.maybe_launch*/parse_cache.maybe_feed are replaced by
recorders that refuse (no worker, no parse calls; any call is logged as a violation).
Clock: time.time is fixed at FIXED_NOW + 60 s * turn for the whole process, the same in both arms (deterministic
recency, budget checks never trip, journal ages 2 h so the wall-clock stale tiers never fire).
Logs per turn (results/<arm>/turns.jsonl): every cluster scored inside recall() (score, keyword-only score, spread,
source keyword/graph-only/zero, rank, in top_k, cut reason), every admit (initial STI, STI after), every eviction
(id, STI, which admit caused it), store before/after, and the ids rendered in the context block."""
import argparse, json, os, re, sys, time, hashlib

ap = argparse.ArgumentParser()
for k in ("--code", "--state", "--data", "--out"): ap.add_argument(k, required=True)
a = ap.parse_args()
assert not os.path.exists(os.path.join(a.state, "_wmtm_state.json")), "state dir must be fresh"
os.makedirs(a.state, exist_ok=True); os.makedirs(a.out, exist_ok=True)
T = json.load(open(os.path.join(a.data, "turns.json")))
CLOCK = [float(T["fixed_now"])]
time.time = lambda: CLOCK[0]                     # fixed clock (both arms identical)

sys.path.insert(0, a.code)
os.environ["JOURNAL_DIR"] = os.path.join(a.state, "_journal")
from wmtm.api import WMTM, WMTMConfig
from wmtm.journal import PettaJournal
from wmtm.store import WMTMStore
import wmtm.recall_bridge as rbm
import wmtm.pc_shadow as pcs, wmtm.parse_cache as pcc

VIOL = []
def _refuse(name):
    def f(*x, **k):
        VIOL.append(name); return None
    return f
for mod, names in ((pcs, ("maybe_launch", "maybe_launch_raw")), (pcc, ("maybe_feed",))):
    for n in names:
        if hasattr(mod, n): setattr(mod, n, _refuse("%s.%s" % (mod.__name__, n)))

# --- recorders -------------------------------------------------------------------------------------------------
ST = {"in_recall": False, "scored": [], "recall_calls": [], "admits": [], "evicts": [], "admitting": None}
_orig_score = rbm.RecallBridge._score_cluster
def _score(self, cluster, qt, act, store, *args, **kw):
    s = _orig_score(self, cluster, qt, act, store, *args, **kw)
    if ST["in_recall"]:
        graph = kw.get("graph", args[0] if args else False)
        kws = _orig_score(self, cluster, qt, act, store) if graph else s     # keyword path only (graph=False / arm A)
        try: spr = self._spreading_activation_for(cluster, act, store)
        except Exception: spr = None
        src = "zero" if s <= 0 else ("keyword" if kws > 0 else "graph-only")
        ST["scored"].append({"id": cluster.id, "score": round(s, 5), "kw_score": round(kws, 5),
                             "spread": None if spr is None else round(spr, 5), "source": src})
    return s
rbm.RecallBridge._score_cluster = _score

_orig_recall = rbm.RecallBridge.recall
def _recall(self, q, store, *args, **kw):
    ST["in_recall"] = True; n0 = len(ST["scored"])
    try: out = _orig_recall(self, q, store, *args, **kw)
    finally: ST["in_recall"] = False
    top_k = kw.get("top_k", args[0] if args else 20); floor = kw.get("floor", 0.0)
    rank = {c.cluster_id: i for i, c in enumerate(out)}
    rows = ST["scored"][n0:]
    ordered = sorted([r for r in rows if r["score"] > 0], key=lambda r: -r["score"])
    for i, r in enumerate(ordered):
        r["cand_rank"] = i
    for r in rows:
        if r["id"] in rank: r["cut"] = None; r["out_rank"] = rank[r["id"]]
        elif r["score"] <= 0: r["cut"] = "zero"
        elif r["score"] <= floor: r["cut"] = "floor"
        else: r["cut"] = "top_k"
    ST["recall_calls"].append({"top_k": top_k, "floor": floor, "n_active": len(store.get_active_set()),
                               "returned": [c.cluster_id for c in out]})
    return out
rbm.RecallBridge.recall = _recall

_orig_admit = WMTMStore.admit
def _admit(self, item_id, content, *args, **kw):
    new = item_id not in self._items
    prev = ST["admitting"]; ST["admitting"] = item_id
    try: it = _orig_admit(self, item_id, content, *args, **kw)
    finally: ST["admitting"] = prev
    ST["admits"].append({"id": item_id, "new": new, "source_type": kw.get("source_type", args[0] if args else "recalled"),
                         "initial_sti": round(float(kw.get("initial_sti", 1.0)), 4),
                         "sti_after": round(float(it.attention.sti), 4)})
    return it
WMTMStore.admit = _admit
_orig_evl = WMTMStore._evict_lowest_sti
def _evl(self):
    it = _orig_evl(self)
    if it is not None:
        ST["evicts"].append({"id": it.id, "sti": round(float(it.attention.sti), 4), "source_type": it.source_type,
                             "by": ST["admitting"]})
    return it
WMTMStore._evict_lowest_sti = _evl

# --- sandbox journal --------------------------------------------------------------------------------------------
jr = PettaJournal(os.environ["JOURNAL_DIR"])
os.makedirs(os.path.dirname(str(jr.path)), exist_ok=True)
jtxt = open(os.path.join(a.data, "journal.metta")).read()
open(jr.path, "w").write(jtxt)
clusters = rbm.parse_journal(jtxt.splitlines(True))
text2id = {}
for c in clusters: text2id[(c.event_note or c.text)[:200]] = c.id

mem = WMTM(WMTMConfig(state_dir=a.state, journal=jr, reasoner="off", use_pln=False))
log = open(os.path.join(a.out, "turns.jsonl"), "w")
meta = {"code": os.path.abspath(a.code), "journal_sha256": hashlib.sha256(jtxt.encode()).hexdigest(),
        "turns_sha256": hashlib.sha256(open(os.path.join(a.data, "turns.json"), "rb").read()).hexdigest(),
        "n_clusters": len(clusters), "python": sys.version.split()[0]}
for i, t in enumerate(T["turns"]):
    CLOCK[0] = float(T["fixed_now"]) + 60.0 * i
    for k in ("scored", "recall_calls", "admits", "evicts"): ST[k] = []
    mem._ensure_store_ready()
    before = {it.id: round(float(it.attention.sti), 4) for it in mem.orchestrator.store.get_active_set()}
    err = None
    try:
        mem.observe({"user": t["q"], "assistant": None}); ctx = mem.context_for(t["q"]); mem.save()
    except Exception as e:
        ctx, err = None, "%s: %s" % (type(e).__name__, str(e)[:300])
    store = mem.orchestrator.store
    after = {it.id: round(float(it.attention.sti), 4) for it in store.get_active_set()}
    shown, focus, sec = [], [], "main"          # main block (the 15-line budget) vs the [recent focus] section
    for line in (ctx or "").splitlines()[1:]:
        if "[recent focus]" in line: sec = "focus"; continue
        m = re.search(r"from=(\S+)", line)
        if not m: continue
        cid = m.group(1).split(",")[0]
        body = line.split("] ", 1)[1] if "] " in line else ""
        assert text2id.get(body[:200], cid) == cid, ("shown id/text mismatch", cid)
        (shown if sec == "main" else focus).append(cid)
    rec = {"i": i, "topic": t["topic"], "kind": t["kind"], "q": t["q"], "err": err, "recall_calls": ST["recall_calls"],
           "scored": ST["scored"], "admits": ST["admits"], "evicts": ST["evicts"], "store_before": before,
           "store_after": after, "shown": shown, "focus": focus, "ctx": ctx, "ctx_header": (ctx or "").splitlines()[0] if ctx else None,
           "violations": list(VIOL)}
    if i == 0: rec["meta"] = meta
    log.write(json.dumps(rec) + "\n"); log.flush()
    print(json.dumps({"i": i, "err": err, "n_scored_pos": sum(r["score"] > 0 for r in ST["scored"]),
                      "returned": len(ST["recall_calls"][0]["returned"]) if ST["recall_calls"] else None,
                      "admits": len(ST["admits"]), "evicts": len(ST["evicts"]), "store": len(after), "shown": len(shown)}), flush=True)
print("PROBE_DONE violations=%d" % len(VIOL), flush=True)
