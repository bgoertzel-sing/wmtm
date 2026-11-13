#!/usr/bin/env python3
"""t-2026-11-11-wmtm-graph-only-probe: synthetic journal + turn script + planted labels (fixed seed).

Writes, under --out:
  journal.metta   the synthetic petta-memory journal (MemoryCluster blocks, same format as the floor replay)
  turns.json      the turn script (identical for arm A and arm B)
  labels.json     planted labels per cluster (role, topic, useful/noise, depth); read ONLY by analyse.py,
                  never by the code under test (probe_turns.py does not open it)

Design (order step 1):
  * 10 topics, each with 3 query keywords (pseudo-words).  Per topic 0-3 keyword hubs (text carries 1-2 topic
    keywords, planted useful for that topic) and 0-2 keyword distractors (one topic keyword, planted noise), so a
    query has at most 5 keyword hits and the 15-slot recall budget has room.
  * Each hub has depth-1 neighbours (EvidenceFor or PromotesFrom, random direction), some planted useful and some
    planted noise; each depth-1 neighbour may have depth-2 children over EvidenceFor (useful or noise).  Two topics
    (4, 8) get a heavy fan-out hub (3 useful + 10 noise depth-1 neighbours) so the 15-slot cut can bind.
  * Linked items carry no query keyword: their text is drawn from one shared filler vocabulary, by the same
    procedure for useful and noise items, so they reach recall only through the graph and their text says
    nothing about their label.  Cluster ids are random hex (no label, topic or depth in the id).
  * 200 unlinked background clusters (filler text) give realistic IDF.
  * Every cluster has the same ClusterOpenedAt (FIXED_NOW - 2 h), so the recency factor is the same for all.
Turn script: per topic 3 turns: Q1 two topic keywords, Q2 the third keyword, Q3 no topic keyword (a pure
follow-up, so only the graph can bring anything new); then a revisit block (topics 0, 2, 4, 6, 8: R2 = that
topic's Q2 again, R3 = keyword-free follow-up).  40 turns.
"""
import argparse, json, os, random, hashlib, time

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--seed", type=int, default=20261111)
a = ap.parse_args()
R = random.Random(a.seed)
FIXED_NOW = 1794350000.0              # same fixed clock value as the floor replay
OPENED = FIXED_NOW - 2 * 3600

SYL = ["ka", "zo", "ri", "vel", "mun", "tar", "quo", "shi", "bex", "lor", "nim", "dra", "fen", "gul", "hesh", "jav",
       "kiv", "mox", "pra", "sul", "tov", "wen", "yar", "zim", "cro", "dex", "fip", "gor"]
used = set()
def word():
    while True:
        w = "".join(R.choice(SYL) for _ in range(R.choice((2, 3))))
        if w not in used and len(w) >= 4:
            used.add(w); return w

GENERIC_Q = ["status", "next", "follows", "consequence", "update", "then", "regarding"]
topics = [[word() for _ in range(3)] for _ in range(10)]
qwords = {w for t in topics for w in t}
FILLER = []
while len(FILLER) < 400:              # filler words: never contain (or equal) a topic keyword (substring layer)
    w = word()
    if not any(q in w or w in q for q in qwords):
        FILLER.append(w)

def filler(n):
    return " ".join(R.sample(FILLER, n))

clusters, labels = {}, {}
def new_id():
    while True:
        cid = "syn-%010x" % R.getrandbits(40)
        if cid not in clusters: return cid

def add(text, label):
    cid = new_id()
    clusters[cid] = {"text": text, "links": []}
    labels[cid] = label
    return cid

def link(a_id, b_id, rel):
    if R.random() < 0.5: clusters[a_id]["links"].append((rel, b_id))
    else: clusters[b_id]["links"].append((rel, a_id))

N_HUBS = [2, 1, 3, 0, 2, 1, 3, 2, 1, 2]      # topic 3: no hub (its keyword hits are distractors only)
N_DIST = [1, 2, 0, 2, 1, 0, 2, 1, 2, 0]
HEAVY = {4, 8}
for t, kws in enumerate(topics):
    for h in range(N_HUBS[t]):
        k = R.sample(kws, R.choice((1, 2)))
        hub = add(" ".join(k) + " " + filler(5), {"role": "hub", "topic": t, "useful": True, "depth": 0})
        heavy = (t in HEAVY and h == 0)
        n_u = 3 if heavy else R.randint(1, 3)
        n_n = 10 if heavy else R.randint(0, 3)
        d1 = [True] * n_u + [False] * n_n
        R.shuffle(d1)
        for useful in d1:
            rel = R.choice(("EvidenceFor", "PromotesFrom"))
            n1 = add(filler(6), {"role": "linked", "topic": t, "useful": useful, "depth": 1, "rel": rel})
            link(n1, hub, rel)
            for _ in range(R.randint(0, 2)):
                u2 = R.random() < (0.6 if useful else 0.2)
                n2 = add(filler(6), {"role": "linked", "topic": t, "useful": u2, "depth": 2, "rel": "EvidenceFor"})
                link(n2, n1, "EvidenceFor")
    for d in range(N_DIST[t]):
        add(R.choice(kws) + " " + filler(5), {"role": "distractor", "topic": t, "useful": False, "depth": 0})
for _ in range(200):
    add(filler(6), {"role": "background", "topic": None, "useful": False, "depth": None})

for cid, c in clusters.items():           # no keyword leak into linked/background text, no generic-word hits
    for g in GENERIC_Q:
        assert g not in c["text"], (g, cid)
    if labels[cid]["role"] in ("linked", "background"):
        assert not any(w in c["text"] for w in qwords), cid

ids = list(clusters); R.shuffle(ids)
os.makedirs(a.out, exist_ok=True)
ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(OPENED))
with open(os.path.join(a.out, "journal.metta"), "w") as fh:
    for cid in ids:
        c = clusters[cid]; ev = "ev-" + cid
        fh.write(";;; BEGIN MemoryCluster %s\n(MemoryCluster %s)\n(SchemaVersion %s medium-memory-v1)\n(ClusterType %s Episode)\n"
                 "(ClusterSource %s synthetic)\n(ClusterOpenedAt %s %s)\n(Contains %s %s)\n(ObservedEvent %s)\n"
                 "(About %s journal)\n(EventNote %s \"%s\")\n" % (cid, cid, cid, cid, cid, cid, ts, cid, ev, ev, cid, ev, c["text"]))
        for rel, tgt in c["links"]:
            fh.write("(%s %s %s)\n" % (rel, cid, tgt))
        fh.write(";;; END MemoryCluster %s\n" % cid)

turns = []
for t, kws in enumerate(topics):
    k = list(kws); R.shuffle(k)
    turns.append({"topic": t, "kind": "Q1", "q": "status of %s %s and what follows" % (k[0], k[1])})
    turns.append({"topic": t, "kind": "Q2", "q": "next update regarding %s then" % k[2]})
    turns.append({"topic": t, "kind": "Q3", "q": "consequence then, what follows next"})
    t_q2 = turns[-2]["q"]
    topics_q2 = topics_q2 if "topics_q2" in dir() else {}
    topics_q2[t] = t_q2
# Revisit block: back to topics 0, 2, 4, 6, 8 (re-ask Q2, then a keyword-free follow-up), so the run also shows
# whether items admitted for a topic are still resident and shown when the topic comes back.
for t in (0, 2, 4, 6, 8):
    turns.append({"topic": t, "kind": "R2", "q": topics_q2[t]})
    turns.append({"topic": t, "kind": "R3", "q": "consequence then, what follows next"})
json.dump({"seed": a.seed, "fixed_now": FIXED_NOW, "turns": turns}, open(os.path.join(a.out, "turns.json"), "w"), indent=1)
json.dump({"seed": a.seed, "topics": topics, "labels": labels}, open(os.path.join(a.out, "labels.json"), "w"), indent=0)
roles = {}
for l in labels.values():
    key = "%s/d%s/%s" % (l["role"], l.get("depth"), "useful" if l["useful"] else "noise")
    roles[key] = roles.get(key, 0) + 1
print(json.dumps({"seed": a.seed, "clusters": len(clusters), "turns": len(turns), "by_role": dict(sorted(roles.items())),
                  "journal_sha256": hashlib.sha256(open(os.path.join(a.out, "journal.metta"), "rb").read()).hexdigest()}))
