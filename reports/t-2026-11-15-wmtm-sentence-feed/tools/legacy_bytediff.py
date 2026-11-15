#!/usr/bin/env python3
"""t-2026-11-15-wmtm-sentence-feed: legacy / spk1 / catalog feed byte diff, old code vs new code.
Run from a repo root (the merge base 66c33ae checkout, or the task head): python3 <this> OUTDIR.
Synthetic notes only; the clock, uuid4, pid and the worker spawn are fixed, the LLM is a stub (no calls).  For each
of legacy, legacy + speaker_link (spk1) and catalog it runs feed_rows (enqueue + launch decision) and, for the
legacy modes, one worker body (process_queue / process_queue_spk with the stub adapter), then lists every file the
feed wrote with its sha256 in OUTDIR/manifest.json (worker_config.json normalised: the new key semparse_sentence_cap
= 0 removed, checkout and output paths replaced).  Compare the two manifests: they must be identical."""
import hashlib, itertools, json, os, sys, time, uuid
REPO = os.getcwd(); sys.path.insert(0, REPO)
out = os.path.abspath(sys.argv[1]); os.makedirs(out, exist_ok=True)
T0 = 1800000000.0
time.time = lambda: T0
_n = itertools.count(1)
uuid.uuid4 = lambda: uuid.UUID(int=next(_n))
os.getpid = lambda: 4242
from wmtm import runtime_config as rc, parse_cache as PC           # noqa: E402
from wmtm.semparse_adapter import SemParseAdapter                    # noqa: E402
rc.spawn_worker = lambda cfg, module, args, pidfile: 4242
os.environ.pop("WMTM_SEMPARSE_MODE", None)


class LLM:
    def __init__(self):
        self.last_usage, self.call_ids = {}, []

    def __call__(self, system, user):
        self.last_usage = {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}
        return "(: f1 (Inheritance thing stuff) (STV 1.0 0.9))"


NOTES = [("n1", "The user asked for a summary. I wrote it.", 1.0, {"user_id": "4242"}),
         ("n2", "Grace is a pilot. Pilots are people.", 0.9), ("n3", "Rain makes the road wet.", 0.8)]
for mode, link in (("legacy", False), ("legacy", True), ("catalog", False)):
    name = mode + ("_spk" if link else "")
    live = os.path.join(out, name, "live")
    cfg = rc.resolve()
    cfg.update(semparse_dir=live, parse_role="live", parse_live_dir=live, parse_share_live_per_hour=20,
               parse_cap_per_hour=20, parse_budget_dir=os.path.join(out, name, "pb"), semparse_feed=True,
               semparse_mode=mode, speaker_link=link, speaker_map={"4242": "quill"}, speaker_self="cosmo")
    os.makedirs(live, exist_ok=True)
    pid = PC.feed_rows(list(NOTES), cfg)
    if mode == "legacy":
        llm = LLM()
        ad = SemParseAdapter(llm, loader=None, system="SYS")
        base = PC.ParseCache(live, cfg=cfg)
        if link:
            PC.process_queue_spk(PC.speaker_cache(cfg, base), llm, ad, cfg=cfg, base=base)
        else:
            PC.process_queue(base, llm, adapter=ad)
man = {}
for root, _, files in os.walk(out):
    for f in sorted(files):
        p = os.path.join(root, f)
        if p.endswith("manifest.json"):
            continue
        data = open(p, "rb").read()
        if f == "worker_config.json":
            # the launcher dumps the whole resolved config: normalise the two expected differences, the new SPEC
            # key semparse_sentence_cap (default 0) and the checkout / output paths; everything else must match
            w = json.loads(data)
            if w.pop("semparse_sentence_cap", 0) != 0:
                raise SystemExit("semparse_sentence_cap is not 0")
            data = json.dumps(w, sort_keys=True).replace(REPO, "<REPO>").replace(out, "<OUT>").replace(
                os.path.dirname(REPO), "<VENDOR_ROOT>").encode()
            man[os.path.relpath(p, out) + " (normalised)"] = hashlib.sha256(data).hexdigest()
            continue
        man[os.path.relpath(p, out)] = hashlib.sha256(data).hexdigest()
json.dump(man, open(os.path.join(out, "manifest.json"), "w"), indent=1, sort_keys=True)
print(len(man), "files")
