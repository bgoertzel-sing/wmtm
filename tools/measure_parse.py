#!/usr/bin/env python3
"""Measure the P2 parser (catalog mode + configurable provider) on N notes of a wmtm state dir.

    python tools/measure_parse.py --state-dir <sd> [-n 30] [--seed 0] [--hashes h1,h2|@file]
                                  [--out <dir>] [--mock-replies <jsonl>] [--per-hour 20]
                                  [--provider openclaw --base-url http://127.0.0.1:18789/v1 --model openclaw/<agent>]

* notes: <sd>/_wmtm_state.json -> store.items[*].content; sample seeded (reproducible) or given content hashes
  (content_hash = sha256(text)[:24], the parse cache's key).
* live baseline: <semparse_dir>/{spk1,ctx1,.}/parse_log.jsonl (+ rotated .1), joined by content hash; semparse_dir
  comes from wmtm.runtime_config.resolve(sd) (default <sd>/_wmtm_shadow/semparse_cache, or _wmtm_flags.json).
* output <out>/per_note.jsonl and <out>/summary.json: ids, hashes and numbers only, never note text.
  Bad parses (rejected atoms, reasons, note text) go to <out>/bad_parses.local.jsonl: local only, never commit
  (``*.local.jsonl`` is git-ignored).
* weighted usage = uncached*w_in + cache_write*w_cw + cache_read*w_cr + output*w_out, Anthropic price ratios
  relative to base input (WEIGHTS); computed the same way for the live baseline.  429 / 529 / usage-limit errors
  are counted.  Medians, ratios and budget verdicts need EVERY parsed note measured (measured_rows gives the
  coverage); the usage ratio pairs new and live on the same notes.  Notes longer than --max-chars (default
  parse_max_chars, as the live feed) are skipped and reported, never truncated.  --mock-replies {"hash": ..., "reply": ...} lines replace the provider (no network, tokens null).
* provider (answer 7): --provider openclaw (default) = OpenAI-compatible Chat Completions at --base-url
  (default http://127.0.0.1:18789/v1), --model an agent target such as openclaw/protocosmo2, bearer token from
  $OPENCLAW_GATEWAY_TOKEN (--token-env); built on upstream semantic-parse.py's DeepSeek client (wmtm.semparse_provider
  .gateway_llm).  --provider anthropic = upstream PROVIDERS["anthropic"] (our upstream PR patch applied to a scratch
  copy while the 1f1a7a6f pin still has the placeholder); --effort is upstream's flag (anthropic only).
"""
import argparse, hashlib, json, os, random, statistics, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from wmtm import runtime_config as rc                       # noqa: E402
from wmtm import semparse_adapter as sp                     # noqa: E402
from wmtm.semparse_provider import upstream_llm, gateway_llm, GATEWAY_TOKEN_ENV  # noqa: E402  (upstream providers)

DEFAULT_BASE_URL = "http://127.0.0.1:18789/v1"

# Anthropic price ratios vs base input (Sonnet-class: $3 in, $3.75 5-min cache write, $0.30 cache read, $15 out)
WEIGHTS = {"uncached_input": 1.0, "cache_write": 1.25, "cache_read": 0.1, "output": 5.0}
LIMIT_MARKERS = ("429", "529", "rate_limit", "usage limit", "usage_limit", "overloaded")


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:24]


def weighted(t):
    if not t or any(t.get(k) is None for k in WEIGHTS):
        return None
    return round(sum(t[k] * w for k, w in WEIGHTS.items()), 1)


def load_notes(sd):
    snap = json.load(open(os.path.join(sd, "_wmtm_state.json"), encoding="utf-8"))
    items = (snap.get("store") or {}).get("items") or {}
    out = {}
    for iid, it in sorted(items.items()):
        txt = it.get("content") if isinstance(it, dict) else None
        if isinstance(txt, str) and txt.strip():
            out.setdefault(content_hash(txt), (iid, txt))
    return out                                               # hash -> (item id, text)


def _jsonl(p):
    try:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                try:
                    yield json.loads(line)
                except ValueError:
                    continue
    except OSError:
        return


def baseline_tokens(row):
    """Live parse-log row -> split tokens (None where the log doesn't say)."""
    u = row.get("usage") if isinstance(row.get("usage"), dict) else row
    det = u.get("prompt_tokens_details") or {}
    rd = u.get("cache_read") if u.get("cache_read") is not None else \
        u.get("cache_read_input_tokens", det.get("cached_tokens"))
    wr = u.get("cache_write") if u.get("cache_write") is not None else u.get("cache_creation_input_tokens")
    pt, out = u.get("prompt_tokens"), u.get("completion_tokens", u.get("output"))
    if u.get("uncached_input") is not None:
        unc = u["uncached_input"]
    elif pt is not None:
        unc = max(0, pt - (rd or 0) - (wr or 0))
    else:
        unc = None
    return {"uncached_input": unc, "cache_read": rd, "cache_write": wr, "output": out}


def load_baseline(semparse_dir):
    base = {}
    for sub in ("spk1", "ctx1", ""):
        for name in ("parse_log.jsonl.1", "parse_log.jsonl"):
            for r in _jsonl(os.path.join(semparse_dir, sub, name)):
                if r.get("hash") and r.get("status") in ("ok", "empty"):
                    t = baseline_tokens(r)
                    base[r["hash"]] = {"log": sub or "base", "secs": r.get("secs"), **t,
                                       "cache_split_known": t["cache_read"] is not None and t["cache_write"] is not None,
                                       "weighted": weighted({k: (v or 0) for k, v in t.items()})
                                       if t["uncached_input"] is not None and t["output"] is not None else None}
    return base


def live_weighted(b, prompt_as):
    """Weighted live usage.  The live parse log has no cache split (prompt_tokens only), so the whole prompt is
    counted as `prompt_as` ("uncached_input" = lower bound, "cache_write" = upper bound) unless the split is known."""
    if not b or b.get("output") is None or b.get("uncached_input") is None:
        return None
    if b.get("cache_split_known"):
        return b.get("weighted")
    t = {"uncached_input": 0, "cache_read": 0, "cache_write": 0, "output": b["output"]}
    t[prompt_as] = b["uncached_input"]
    return weighted(t)


def select(notes, n, seed, hashes):
    """hashes=None -> seeded random sample of n; a list (even empty) -> exactly those hashes that are in notes.
    review-6: an explicit sample whose hashes were all skipped stays empty; it never falls back to sampling."""
    if hashes is not None:
        return [h for h in hashes if h in notes], [h for h in hashes if h not in notes]
    keys = sorted(notes)
    return random.Random(seed).sample(keys, min(n, len(keys))), []


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _med(xs):
    """Median of the known values (live baseline columns only: their coverage is reported alongside)."""
    xs = [x for x in xs if _num(x)]
    return round(statistics.median(xs), 3) if xs else None


def _med_all(xs):
    """review-5 #1: median of the new parser's measurements only when EVERY row has one; any unknown -> None
    (unmeasured), so a partial sample never yields a median, a ratio or a budget verdict."""
    xs = list(xs)
    if not xs or not all(_num(x) for x in xs):
        return None
    return round(statistics.median(xs), 3)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--state-dir", required=True)
    ap.add_argument("-n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hashes", default="", help="comma list, or @file with one hash per line")
    ap.add_argument("--out", default="measure_out")
    ap.add_argument("--provider", choices=("openclaw", "anthropic"), default="openclaw",
                    help="openclaw: OpenAI-compatible gateway at --base-url (answer 7, default); "
                         "anthropic: upstream Anthropic provider (ANTHROPIC_API_KEY)")
    ap.add_argument("--base-url", default=os.environ.get("WMTM_SEMPARSE_BASE_URL", DEFAULT_BASE_URL),
                    help="gateway /v1 base (default $WMTM_SEMPARSE_BASE_URL or %(default)s)")
    ap.add_argument("--token-env", default=GATEWAY_TOKEN_ENV, help="env var holding the gateway bearer token")
    ap.add_argument("--model", default=None, help="e.g. openclaw/protocosmo2 (gateway agent target)")
    ap.add_argument("--effort", default="low", help="upstream semantic-parse.py --effort (default: low)")
    ap.add_argument("--mock-replies", default="", help="jsonl of {hash, reply}: no network, tokens not measured")
    ap.add_argument("--per-hour", type=float, default=20.0, help="parse cap (0 = no pacing)")
    ap.add_argument("--max-chars", type=int, default=None,
                    help="notes longer than this are skipped and reported, never truncated "
                         "(default: the state dir's parse_max_chars, as the live feed uses)")
    a = ap.parse_args(argv)
    sd = os.path.abspath(a.state_dir)
    os.makedirs(a.out, exist_ok=True)
    hashes = None                                           # None = random sample; a list = explicit sample
    if a.hashes:
        src = open(a.hashes[1:]).read().split() if a.hashes.startswith("@") else a.hashes.split(",")
        hashes = [h.strip() for h in src if h.strip()]
    cfg = rc.resolve(sd)
    semparse_dir = cfg["semparse_dir"]
    # review-5 #2: like the live feed (parse_cache skips items > parse_max_chars), a note longer than the limit
    # is skipped and reported, never measured as a truncated prefix under the full note's hash.
    max_chars = a.max_chars if a.max_chars is not None else int(cfg["parse_max_chars"])
    notes = load_notes(sd)
    too_long = {h for h, (_, t) in notes.items() if len(t) > max_chars}
    skipped_long = [h for h in (hashes or []) if h in too_long]
    chosen, missing = select({h: v for h, v in notes.items() if h not in too_long}, a.n, a.seed,
                             None if hashes is None else [h for h in hashes if h not in too_long])
    base = load_baseline(semparse_dir)
    mock = None
    if a.mock_replies:
        mock = {r["hash"]: r["reply"] for r in _jsonl(a.mock_replies) if "hash" in r}
        llm = lambda s, u: mock.get(llm.cur, "")              # noqa: E731
        llm.last_usage, model = None, "mock"
    else:
        if a.provider == "openclaw":                        # answer 7: the OpenClaw gateway (OpenAI-compatible)
            llm = gateway_llm(a.base_url, model=a.model, token_env=a.token_env)
        else:
            llm = upstream_llm("anthropic", model=a.model, flags=["--effort", a.effort],
                               workdir=os.path.join(a.out, "_provider"))
        model = llm.model
    ad = sp.SemParseAdapter(llm, mode="catalog", reject_log=os.path.join(a.out, "rejects.local.jsonl"),
                            max_chars=max_chars)
    gap = 0 if (mock is not None or not a.per_hour) else 3600.0 / a.per_hour
    rows, limit_errors, last = [], 0, None
    bad = open(os.path.join(a.out, "bad_parses.local.jsonl"), "w", encoding="utf-8")
    for i, h in enumerate(chosen):
        if gap and last is not None:
            time.sleep(max(0.0, gap - (time.monotonic() - last)))
        last = time.monotonic()
        iid, txt = notes[h]
        llm.cur = h
        res = ad.parse_item(iid, {"text": txt})
        if res.truncated_chars:                             # structural check: never report a prefix
            raise RuntimeError(f"note {h} was truncated by {res.truncated_chars} chars; refusing the measurement")
        err = res.error or ""
        is_limit = any(m in err.lower() for m in LIMIT_MARKERS)
        limit_errors += is_limit
        status = ("rejected" if not res.accepted else "partial" if res.rejected else "admitted")
        tok = {k: res.usage.get(k) for k in WEIGHTS} if res.usage else {k: None for k in WEIGHTS}
        b = base.get(h)
        row = {"i": i, "item_id": iid, "hash": h, "status": status, "catalog_status": res.catalog_status,
               "accepted": len(res.accepted), "rejected": len(res.rejected), "declarations": len(res.declarations),
               "error_kind": ("limit" if is_limit else "error" if err else None),
               **tok, "weighted": weighted(tok),
               "chars": len(txt),
               "latency_s": None if (mock is not None or res.latency_s is None) else round(res.latency_s, 3),
               "live_log": b and b["log"], "live_secs": b and b.get("secs"),
               "live_weighted_lo": live_weighted(b, "uncached_input"),
               "live_weighted_hi": live_weighted(b, "cache_write")}
        rows.append(row)
        if status != "admitted" or err:
            bad.write(json.dumps({"hash": h, "item_id": iid, "text": txt, "error": err,
                                  "rejected": [[x, str(w)] for x, w in res.rejected][:50]}) + "\n")
    bad.close()
    with open(os.path.join(a.out, "per_note.jsonl"), "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    summary = summarize(rows, model, mock is not None, semparse_dir, len(notes), missing, limit_errors, a,
                        {"max_chars": max_chars, "notes_over_max_chars_in_state": len(too_long),
                         "hashes_skipped_long": skipped_long})
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps(summary, indent=1))
    return 0


def summarize(rows, model, mocked, semparse_dir, n_notes, missing, limit_errors, a, extra=None):
    st = {k: sum(1 for r in rows if r["status"] == k) for k in ("admitted", "partial", "rejected")}
    keys = list(WEIGHTS) + ["weighted", "latency_s"]
    nm = "not measured (no credential)" if mocked else None
    measured = {k: sum(1 for r in rows if _num(r[k])) for k in keys}
    med = {k: (nm or _med_all([r[k] for r in rows])) for k in keys}      # None unless every row measured it
    complete = (not mocked) and bool(rows) and measured["weighted"] == len(rows)
    lo = _med([r["live_weighted_lo"] for r in rows]); hi = _med([r["live_weighted_hi"] for r in rows])

    def paired(col):                                    # new vs live on the SAME notes (those with a baseline)
        pr = [r for r in rows if _num(r[col])]
        if not complete or not pr:
            return None, len(pr)
        new, live = _med_all([r["weighted"] for r in pr]), _med_all([r[col] for r in pr])
        return (round(new / live, 3) if live else None), len(pr)
    r_lo, n_lo = paired("live_weighted_lo"); r_hi, n_hi = paired("live_weighted_hi")
    lat = med["latency_s"] if (not mocked and measured["latency_s"] == len(rows)) else None
    return {"model": model, "mocked": mocked, "notes_in_state": n_notes, "parsed": len(rows),
            "seed": a.seed, "hashes_given": bool(a.hashes), "hashes_missing": missing, **(extra or {}),
            "semparse_dir_set": bool(semparse_dir), "status": st,
            "statements_accepted": sum(r["accepted"] for r in rows),
            "statements_rejected": sum(r["rejected"] for r in rows),
            "errors": sum(1 for r in rows if r["error_kind"]), "limit_errors_429_or_usage": limit_errors,
            "weights": WEIGHTS, "measured_rows": measured, "usage_complete": complete, "median": med,
            "live_baseline": {"joined": sum(1 for r in rows if r["live_log"]),
                              "median_weighted_lo_prompt_as_uncached": lo,
                              "median_weighted_hi_prompt_as_cache_write": hi,
                              "median_secs": _med([r["live_secs"] for r in rows])},
            "ratio_new_over_live": {"vs_lo": r_lo, "vs_hi": r_hi, "paired_rows_lo": n_lo, "paired_rows_hi": n_hi,
                                    "basis": "medians over the notes that have a live baseline; only when every "
                                             "parsed note reported full usage (else null)"},
            "budget": {"usage_ratio_max": 2.0, "median_latency_max_s": 180, "per_hour_cap": a.per_hour,
                       "usage_ok": (None if r_hi is None else r_hi <= 2.0),
                       "latency_ok": (None if lat is None else lat <= 180)}}

if __name__ == "__main__":
    sys.exit(main())
