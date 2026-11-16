#!/usr/bin/env python3
"""t-2026-11-15-wmtm-sentence-feed: offline replay of the sentence feed on the 20 master-adopt-v2 notes, 0 parse calls.

The production path is exercised end to end except for the HTTP request: ParseCache(sent1).enqueue ->
semparse_sentence.process_queue_sentence -> gateway_parse_fn (upstream semantic-parse.py @24e37182 parse_sentence,
the provider class wrapped by the share gate) -> a REPLAY provider that answers each request with the cached
master-adopt-v2 reply of the same sentence made under the same context (sha256 of the context in the request), and
refuses anything else.  The share is a live share in a private temp dir (the real live dir is never opened for
writing; its ledger sha256 is recorded before and after).  Then build_snapshot (shadow_load_order=master_ops) on the
rebuilt parsed.jsonl, the shadow worker, and the shadow-wiring task's admit comparison.

Note text stays in a private temp dir (mode 700, removed at exit); only counts, ids-free booleans and the worker's
shadow.jsonl / admit.json (as in the shadow-wiring evidence) are written to OUT.
Usage: python3 reports/t-2026-11-15-wmtm-sentence-feed/tools/replay.py OUT"""
import atexit, collections, hashlib, json, os, shutil, subprocess, sys, tempfile, types

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, REPO)
from wmtm import runtime_config as rc, semparse_sentence as SS, pc_shadow as PS, master_loader as ML   # noqa: E402
from wmtm.parse_cache import ParseCache                                                               # noqa: E402

RAW = "/tmp/p3_out/ab/raw_spec.json"                    # the 20 notes (private, pop-os only)
CACHED = "/srv/hive-evidence/t-2026-11-12-wmtm-parser-master-adopt-v2/sentence_parse/parsed.jsonl"
SEL = os.path.expanduser("~/scratch/sp2/sel.jsonl")     # the offline split (sha b76cd0d4)
HITL_SRC = os.path.expanduser("~/scratch/pma/sph-24e37182")   # clone (a git worktree) at 24e37182
HITL = TPL = None                                         # set in main(): a copy made by scripts/fetch_semparse_hitl.sh
PETTA = os.path.expanduser("~/scratch/mh-rules-on-roman/PeTTa")
VENDOR = os.path.expanduser("~/scratch/ppv/pc")          # PeTTaChainer b6aacc68, as in the shadow-wiring run
REF_EV = "/srv/hive-evidence/t-2026-11-15-wmtm-master-shadow-wiring"
LIVE_LEDGER = ("/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory/_wmtm_shadow/"
               "semparse_cache/share_ledger.jsonl")
LIVE_FLAGS = "/home/openclaw/research-agent/projects/omegaclaw/protocosmo2/iter-port/repos/memory/_wmtm_flags.json"
TASK_LEDGER = os.path.expanduser("~/.wmtm/parse_budget/tasks/ledger.jsonl")


def sha(p):
    try:
        return hashlib.sha256(open(p, "rb").read()).hexdigest()
    except OSError:
        return None


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def strip_timing(x):
    if isinstance(x, dict):
        return {k: strip_timing(v) for k, v in x.items() if k not in ("s", "prequery_s", "warm_s", "total_s", "ts", "start_ts")}
    if isinstance(x, list):
        return [strip_timing(v) for v in x]
    return x


def fetch_hitl(tmp):
    """The parser checkout as production gets it: scripts/fetch_semparse_hitl.sh DEST 24e37182 (local clone, no network)."""
    global HITL, TPL
    d = os.path.join(tmp, "semparse-hitl-24e37182")
    r = subprocess.run(["bash", os.path.join(REPO, "scripts", "fetch_semparse_hitl.sh"), d, "24e37182"],
                       env=dict(os.environ, SEMPARSE_SRC=HITL_SRC), capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise SystemExit("fetch_semparse_hitl.sh failed: " + r.stderr[-300:])
    HITL, TPL = d, os.path.join(d, "templates")
    return {"rc": r.returncode, "version_commit": [l for l in open(os.path.join(d, "VERSION")) if l.startswith("commit=")][0].strip()}


def replay_module(cached_rows):
    """Upstream semantic-parse.py @24e37182, loaded as the worker loads it, with chat-completions answered from
    the cache (keyed by item id, text and context sha256).  Counts what it served and what it refused."""
    from wmtm.semparse_provider import load_upstream
    mod = load_upstream(SS.require_pin(HITL))
    good = {}
    for r in cached_rows:
        rep = r["reply"]
        if SS._good(rep):
            it = rep["item"]
            good[(it["id"], it["text"], it.get("context_sha256"))] = rep
    stats = collections.Counter()
    prompt_text = open(os.path.join(TPL, "generated", "PROMPT_CATALOG.txt"), encoding="utf-8").read()

    class Replay(mod.PROVIDERS["chat-completions"]):
        def __init__(self, args):
            self.args = args

        def complete(self, system, user, model):
            stats["requests"] += 1
            if system != prompt_text:
                stats["system_mismatch"] += 1
            head, sep, item = user.rpartition("\n\nItem id: ")
            if not sep:
                head, item = "", user[len("Item id: "):]
            iid, rest = item.split("\nTEXT: ", 1)
            text = rest.rsplit("\n\nWrite the JSON object for this item.", 1)[0]
            if mod.item_message(iid, text, head or None) != user:
                stats["request_shape_mismatch"] += 1
            key = (iid, text, hashlib.sha256(head.encode("utf-8")).hexdigest() if head else None)
            rep = good.get(key)
            if rep is None:
                stats["replay_miss"] += 1
                raise mod.ProviderError("replay miss (no cached reply for this sentence under this context)")
            stats["served"] += 1
            return types.SimpleNamespace(text=rep["raw_text"], usage=rep["usage"], config=rep["request_config"],
                                         raw_usage=rep["raw_usage"])
    mod.PROVIDERS = dict(mod.PROVIDERS)
    mod.PROVIDERS["chat-completions"] = Replay
    return mod, stats, good


class It:
    def __init__(s, i, c=None):
        s.id, s.content, s.source_type = i, c, "note"


class St:
    def __init__(s, ids):
        s.ids = ids

    def get_active_set(s):
        return [It(i) for i in s.ids]


def admit_compare(rd):
    """The shadow-wiring task's admit comparison (tools/admit_compare.py), with goal ids b01.. taken from the
    REFERENCE run's query order (the feed may load notes in another order, which renumbers the goals)."""
    from wmtm import pc_admit as PA
    sys.path.insert(0, os.path.join(REPO, "reports", "t-2026-11-14-wmtm-trivial-filter-coref", "tools"))
    import rescore as RS
    I = os.path.join(REF_EV, "inputs")
    base, _ = RS.compute("/srv/hive-evidence/t-2026-11-14-wmtm-render-master-goals")
    vd = {r["goal"]: r["verdict"] for f in ("verdicts_restate.tsv", "verdicts23.tsv", "verdicts_sens_impl.tsv")
          for r in RS.tsv(os.path.join(I, "verdicts", f))}
    aC, aW = [int(x[:-1]) for x in base["inputs"]["A_v3"].split("/")]
    refq = json.loads(open(os.path.join(REF_EV, "run_apply", "shadow.jsonl")).readlines()[-1])["queries"]
    gid = {RS.norm(q["goal"]): "b%02d" % (i + 1) for i, q in enumerate(refq)}
    adm = json.load(open(os.path.join(rd, "admit.json")))
    sd = tempfile.mkdtemp(prefix="sfd_lc_")
    try:
        json.dump(adm, open(os.path.join(sd, PA.ADMIT_FILE), "w"))
        notes = [l.strip() for l in open(os.path.join(I, "note_ids.txt")) if l.strip()]
        c, info = PA.load_candidates({"shadow_dir": sd, "reasoner_max_admit": 1000, "gate_max_per_fact": 0}, None,
                                     now=float(adm.get("spec_ts") or adm["ts"]) + 1, live_ids=notes)
    finally:
        shutil.rmtree(sd, ignore_errors=True)
    c = c or []
    ag = [gid.get(RS.norm(x.provenance["goal"]), "?") for x in c]
    cv = collections.Counter(vd.get(g, "unjudged") for g in ag)
    return {"results": len(adm["results"]), "dropped": info["dropped"],
            "refused_by_reason": dict(sorted(collections.Counter(e["reason"] for e in info.get("trivial_refused") or []).items())),
            "admitted": len(c), "C": cv["correct"], "W": cv["wrong"], "U": cv["unclear"], "unjudged": cv["unjudged"],
            "unmapped_goal": ag.count("?"), "admitted_wrong_ids": sorted(g for g in ag if vd.get(g) == "wrong"),
            "vs_A_v3": RS.rule_verdict(cv["correct"], cv["wrong"], aC, aW)}


def arm(tmp, out, order, notes, cached, ids):
    """Replay through the feed (production path minus HTTP) in runs of at most 20 calls (the hourly cap), then the
    master path.  order: offline_order = notes queued one after another in the offline driver's order (first_seen
    0, 1, ...), so the cache order equals the offline file's; feed_order = all queued in one cycle, ranked by STI as
    the feed ranks them (the master path then loads notes in that order)."""
    C = {}
    live = os.path.join(tmp, order, "live")
    cfg = rc.resolve()
    cfg.update(semparse_dir=live, parse_role="live", parse_live_dir=live, parse_share_live_per_hour=1000,
               parse_cap_per_hour=1000, parse_budget_dir=os.path.join(tmp, order, "pb"), semparse_mode="sentence",
               semparse_feed=True, speaker_link=False, semparse_hitl=HITL, parse_max_chars=10 ** 6)
    cache = ParseCache(os.path.join(live, SS.SENT_VERSION), cfg=cfg)
    if order == "offline_order":
        st = collections.Counter()
        for i, n in enumerate(notes):
            st.update({k: v for k, v in cache.enqueue([(n["id"], n["content"], float(n.get("sti") or 0))], now=float(i)).items()
                       if k in ("queued_new", "skipped_long", "cached")})
        st = dict(st)
    else:
        st = cache.enqueue([(n["id"], n["content"], float(n.get("sti") or 0)) for n in notes], now=1.0)
    mod, stats, good = replay_module(cached)
    B, S, MF = SS.upstream(HITL)
    pfile = os.path.join(TPL, "generated", "PROMPT_CATALOG.txt")
    fn = SS.gateway_parse_fn(HITL, pfile, cache.share, module=mod,
                             meta={"tool": "semparse_feed", "mode": "sentence", "replay": True})
    body = S.prompt_body_sha(open(pfile, encoding="utf-8").read())
    runs, never_partial = [], True
    while cache.pending():
        res = SS.process_queue_sentence(cache, fn, cfg=cfg, n=20, B=B, prompt_body_sha=body, manifest_id=MF.current_id())
        runs.append({"calls": len(res["calls"]), **res["notes"], "stop": res["stop"]})
        _, info = ML.notes_from_parsed(TPL, SS.parsed_path(cache.d), ids)
        never_partial &= not info["incomplete"]                     # the master path never sees a partial note
        if not res["calls"] and not any(res["notes"].values()):
            break
    parsed = jl(SS.parsed_path(cache.d))
    led = jl(cache.share.ledger)
    logs = jl(cache.log_path)
    C["enqueue"] = st
    C["replay"] = {"runs": runs, "calls": sum(r["calls"] for r in runs), "provider": dict(stats),
                   "ledger_rows": len(led), "ledger_roles": sorted({r["role"] for r in led}),
                   "log_rows": len(logs),
                   "log_call_ids_joined": sorted(i for r in logs for i in r["call_ids"]) == sorted(r["call_id"] for r in led),
                   "share_used": cache.share.used(), "notes_ok": sum(r["ok"] for r in runs),
                   "master_path_never_saw_a_partial_note": never_partial}
    # rows: the offline driver's format exactly
    gk = {r["reply"]["item"]["id"]: r for r in cached if SS._good(r["reply"])}
    same_bytes = sum(json.dumps(r, ensure_ascii=False) == json.dumps(gk[r["id"]], ensure_ascii=False) for r in parsed)
    diff_keys = collections.Counter()
    for r in parsed:
        o = gk[r["id"]]
        for k in set(r["reply"]) | set(o["reply"]):
            if r["reply"].get(k) != o["reply"].get(k):
                diff_keys[k] += 1
    good_order = [r["id"] for r in cached if SS._good(r["reply"])]
    C["rows"] = {"rebuilt": len(parsed), "row_keys": sorted({tuple(r) for r in parsed}),
                 "reply_keys_equal_to_cached_good": {tuple(sorted(r["reply"])) for r in parsed} == {tuple(sorted(o["reply"])) for o in gk.values()},
                 "byte_identical_to_cached_good_row": same_bytes, "reply_fields_differing": dict(diff_keys),
                 "same_row_order_as_cached_good_rows": [r["id"] for r in parsed] == good_order,
                 "cached_error_rows_not_replayed": len(cached) - len(gk)}
    # the master path on the rebuilt file vs the stored shadow-wiring spec
    scfg = rc.resolve()
    scfg.update(shadow_load_order="master_ops", shadow_sph_templates=TPL, shadow_master_parsed=SS.parsed_path(cache.d),
                shadow_max_goals=0)
    sp = PS.build_snapshot(St(ids), k=len(ids), cfg=scfg)
    ref = json.load(open(os.path.join(REF_EV, "run", "spec.json")))
    rt = json.loads(json.dumps(sp))
    C["spec"] = {"master_ops": len(sp["master_ops"]), "goals": len(sp["goals"]), "semparse_items": sp["semparse_items"],
                 "unparsed_items": sp["unparsed_items"], "master_ops_equal_ref": rt["master_ops"] == ref["master_ops"],
                 "master_ops_same_multiset_as_ref": collections.Counter(map(json.dumps, rt["master_ops"])) == collections.Counter(map(json.dumps, ref["master_ops"])),
                 "goals_equal_ref": rt["goals"] == ref["goals"],
                 "goals_same_set_as_ref": sorted(map(json.dumps, rt["goals"])) == sorted(map(json.dumps, ref["goals"]))}
    rd = os.path.join(out, order)
    os.makedirs(rd, exist_ok=True)
    spec_p = os.path.join(tmp, order, "spec.json")
    json.dump(sp, open(spec_p, "w"))
    wcfg = dict(scfg, petta_dir=PETTA, pettachainer_dir=VENDOR, shadow_dir=rd)
    wc = os.path.join(tmp, order, "worker_config.json")
    rc.write_json_atomic(wc, wcfg)
    r = subprocess.run([sys.executable, "-m", "wmtm.workers.pc_shadow", "--spec", spec_p, "--out",
                        os.path.join(rd, "shadow.jsonl"), "--config", wc, "--petta", PETTA, "--vendor", VENDOR],
                       env=rc.worker_env(wcfg), cwd=REPO, timeout=900, capture_output=True, text=True)
    s = json.loads(open(os.path.join(rd, "shadow.jsonl")).readlines()[-1])
    refs = json.loads(open(os.path.join(REF_EV, "run_apply", "shadow.jsonl")).readlines()[-1])
    key = lambda q: json.dumps(strip_timing(q), sort_keys=True)
    C["shadow"] = {"rc": r.returncode, "status": s["status"], "load_order": s.get("load_order"), "goals_n": s["goals_n"],
                   "pc_proved": s["pc_proved"], "add_fail": s["add_fail"], "pred_fail": s["pred_fail"],
                   "timeouts": s["timeouts"], "skipped_budget": s["skipped_budget"],
                   "queries_equal_ref_excl_timing": strip_timing(s["queries"]) == strip_timing(refs["queries"]),
                   "queries_same_set_as_ref_excl_timing": sorted(map(key, s["queries"])) == sorted(map(key, refs["queries"])),
                   "canary_equal_ref_excl_timing": strip_timing(s["canary"]) == strip_timing(refs["canary"]),
                   "neg_equal_ref_excl_timing": strip_timing(s["neg"]) == strip_timing(refs["neg"])}
    C["admit"] = admit_compare(rd)
    return C


def main(out):
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="sfd_replay_")           # mode 700
    atexit.register(shutil.rmtree, tmp, True)
    before = {"live_ledger": sha(LIVE_LEDGER), "task_ledger": sha(TASK_LEDGER), "live_flags": sha(LIVE_FLAGS)}
    notes = json.load(open(RAW))["raw_items"]
    ids = [n["id"] for n in notes]
    cached = jl(CACHED)
    C = {"notes": len(notes), "cached_rows": len(cached), "cached_good_rows": sum(SS._good(r["reply"]) for r in cached)}
    C["fetch"] = fetch_hitl(tmp)

    # 1. the ported split = the offline split (sp2 sel.jsonl) = the cached rows' selection part
    mine = [r for n in notes for r in SS.prepare(n["id"], n["content"], cfg={})[0]]
    sel = jl(SEL)
    first = list({r["id"]: {k: r[k] for k in ("id", "dataset", "doc", "sent", "text")} for r in reversed(cached)}.values())[::-1]
    by_id = {r["id"]: r for r in first}
    C["split"] = {"sentences": len(mine), "sel_sha256": sha(SEL), "equal_to_sel_jsonl": mine == sel,
                  "equal_to_cached_rows": [by_id.get(r["id"]) for r in mine] == mine and len(by_id) == len(mine),
                  "per_note_max": max(collections.Counter(r["doc"] for r in mine).values())}

    # 2. speaker linking on these notes with the live map (counts only; the cached replies were made without it)
    try:
        lf = json.load(open(LIVE_FLAGS))
        lcfg = {"speaker_link": True, "speaker_map": lf.get("speaker_map") or {}, "speaker_self": lf.get("speaker_self") or ""}
        ch = res = 0
        for n in notes:
            r, info = SS.prepare(n["id"], n["content"], cfg=lcfg)
            ch += [x["text"] for x in r] != [x["text"] for x in SS.prepare(n["id"], n["content"], cfg={})[0]]
            res += bool(info["speaker"])
        C["speaker_link_live_map"] = {"notes_text_changed": ch, "notes_speaker_resolved": res}
    except OSError:
        C["speaker_link_live_map"] = None

    os.environ["BASE_URL"] = "http://127.0.0.1:9/v1"                 # never contacted (replay provider)
    os.environ["LLM_MODEL"] = cached[0]["reply"]["model"]
    os.environ.pop("WMTM_SEMPARSE_HITL", None)
    for order in ("offline_order", "feed_order"):
        C[order] = arm(tmp, out, order, notes, cached, ids)
    after = {"live_ledger": sha(LIVE_LEDGER), "task_ledger": sha(TASK_LEDGER), "live_flags": sha(LIVE_FLAGS)}
    C["untouched"] = {"before": before, "after": after, "equal": before == after}
    return C


if __name__ == "__main__":
    o = main(sys.argv[1])
    json.dump(o, open(os.path.join(sys.argv[1], "counts.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(o, indent=1, sort_keys=True))
