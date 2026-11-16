"""Sentence mode of the live parse feed (t-2026-11-15-wmtm-sentence-feed; IMPROVEMENTS P-10, L-06).

The master-parser path (pc_shadow shadow_load_order=master_ops) reads a sentence-mode parsed.jsonl
(shadow_master_parsed).  Until this module, only the offline driver of master-adopt-v2 (sentence_parse/drive.py,
split by the scratch tool sp2/cleanup.py) wrote that file.  With semparse_mode = "sentence" the live feed writes it:

  item content --speaker_link (opt-in, same substitution as spk1)--> strip (C1-C4) --> sentences --> cap
     --> one parser call per sentence, sentence k with tmpl.blocks.context_section of sentences 1..k-1
     --> rows {id, dataset, doc=<item id>, sent, text, reply}, exactly the offline driver's rows.

Where things live (<semparse_dir>/sent1; the base, ctx1 and spk1 caches are never touched):
  queue.json / cache.jsonl / parse_log.jsonl / worker.pid / launch_decisions.jsonl / worker_runs.jsonl
                         the ParseCache files, as for every other cache version; cache.jsonl holds ONE entry per
                         finished note (status ok | failed | empty), never note text;
  work/<hash>.jsonl      the rows (every attempt) of a note that is not finished yet;
  parsed.jsonl           finished notes only.  A note's rows move here, all at once, only when every sentence has a
                         good reply made under the right context (tmpl.blocks.walk); the file is rewritten with
                         tmp + os.replace, so a reader never sees a partial note or a torn line;
  gave_up/<hash>.jsonl   the rows of a note one of whose sentences failed parse_max_attempts (<= 2) times.

Cost: every call goes through the cache's share (parse_budget.ParseBudget; parse_role live for the live feed).  The
gated provider reserves one counted call in the share ledger BEFORE the request, and each call leaves one
parse_log.jsonl row whose call_ids join that ledger row (no double count).  A full share stops the run with nothing
sent; the note stays queued with its finished sentences in work/ and resumes in the next run.

The cleanup and split are the sp2 cleanup.py rules (t-2026-11-11-wmtm-sentence-parse-v2), ported unchanged; the
call loop is the master-adopt-v2 drive.py loop (one call per sentence, at most 2 attempts, error rows kept).
"""
from __future__ import annotations

import collections
import json
import os
import re
import sys
import time

MODE = "sentence"                 # semparse_mode value
SENT_VERSION = "sent1"            # <semparse_dir>/sent1
DATASET = "wmtm-sp2"              # the rows' dataset: the offline driver's, so live and offline rows are interchangeable
SENTENCE_PIN = "24e37182e64a20981d423ed1d851da6de5e3b3e8"   # Man Hin's parser with the sentence-by-sentence mode
MAX_ATTEMPTS = 2                  # per sentence (order: at most 2)
SPEAKER_PREFIX = False            # spk1 also prefixes "Speaker: X." -- here that would be a sentence of its own, i.e.
                                  # one more paid call per linked note; the substitutions themselves (handles,
                                  # "the user", I/me/my) are applied exactly as spk1 applies them
LIMIT = re.compile(r"429|rate.?limit|usage.?limit|quota|too many requests|insufficient|credit", re.I)

# ---------------------------------------------------------------- cleanup + split (sp2 cleanup.py, unchanged rules)
# Strips ONLY: C1 trailing <!-- ... --> markup comment; C2 hex hashes/ids (7-64 hex chars, >=1 digit and >=1 a-f);
# C3 backtick-quoted shell commands (first word a shell command); C4 list numbers '(1)' used as markers.
# Heading labels ('NEXT:', 'Rec:' ...) and the content after them are KEPT.  Readable ids (task ids, paths) are KEPT.
SHELL = {"setfacl", "rm", "cp", "mv", "git", "ls", "cd", "chmod", "chown", "sha256sum", "python", "python3", "bash",
         "sh", "curl", "wget", "mkdir", "cat", "grep", "sed", "find", "tar", "sudo", "ssh", "scp", "pip", "npm",
         "systemctl", "kill"}
C1 = re.compile(r"\s*<!--.*?-->\s*$", re.S)
C2 = re.compile(r"(?<![\w/.-])(?=[0-9a-f]*[0-9])(?=[0-9a-f]*[a-f])[0-9a-f]{7,64}(?![\w/-])")
C3 = re.compile(r"\x60([^\x60]+)\x60")
C4 = re.compile(r"(?<!\S)\(\d{1,2}\)(?=\s)")
ABBR = re.compile(r"\b(?:e\.g|i\.e|vs|etc|cf|approx|incl)\.$", re.I)


def strip(text):
    """-> (clean text, {category: count}).  Removal sites are tidied only where something was removed."""
    cnt = collections.Counter()
    text = text or ""
    m = C1.search(text)
    if m:
        cnt["C1_markup_comment"] += 1
        text = text[:m.start()]

    def c3(m):
        w = m.group(1).split()
        if w and w[0] in SHELL:
            cnt["C3_shell_command"] += 1
            return "\x00"
        return m.group(0)
    text = C3.sub(c3, text)

    def c2(m):
        cnt["C2_hash_id"] += 1
        return "\x00"
    text = C2.sub(c2, text)

    def c4(m):            # only an isolated short number marker followed by text, never '1.0' or 'review 1'
        cnt["C4_list_number"] += 1
        return "\x00"
    text = C4.sub(c4, text)
    text = re.sub(r"\(\s*\x00\s*\)", "\x00", text)          # an emptied paren pair
    text = re.sub(r"\s*\x00\s*(?=[,;:.)])", "", text)       # the space before following punctuation
    text = re.sub(r"\s*\x00\s*", " ", text)
    text = re.sub(r"[ ]{2,}", " ", text).strip()
    return text, dict(cnt)


def sentences(text):
    """Split after . ! ? + whitespace, never after a listed abbreviation; drop pieces with no letter or digit."""
    out, cur = [], ""
    for piece in re.split(r"(?<=[.!?])\s+", text or ""):
        cur = (cur + " " + piece).strip() if cur else piece
        if ABBR.search(cur):
            continue
        out.append(cur)
        cur = ""
    if cur:
        out.append(cur)
    return [s for s in out if re.search(r"[A-Za-z0-9]", s)]


def sentence_id(doc, k):
    return "%s.s%02d" % (doc, k)


def prepare(doc, content, source=None, cfg=None, cap=None, dataset=DATASET):
    """One note -> (rows, info).  rows: [{id, dataset, doc, sent, text}] (the offline driver's selection rows, same
    key order); info: speaker, speaker_source, subs, sentences_total, sentences, capped, strip_counts (counts only).

    Speaker linking (cfg speaker_link, speaker_map, speaker_self) runs BEFORE the cleanup and split, with the same
    wmtm.semparse_speaker.link the legacy spk1 path uses (prefix off, see SPEAKER_PREFIX).  cap (default
    cfg semparse_sentence_cap; 0 / None = none): only the first cap sentences of a longer note are parsed."""
    cfg = cfg or {}
    text = content if isinstance(content, str) else ""
    info = {"speaker": None, "speaker_source": None, "subs": 0}
    if cfg.get("speaker_link"):
        from .semparse_speaker import link
        text, li = link(text, source, cfg.get("speaker_map"), cfg.get("speaker_self") or "", prefix=SPEAKER_PREFIX)
        info.update(speaker=li.get("speaker"), speaker_source=li.get("speaker_source"), subs=li.get("subs", 0))
    clean, counts = strip(text)
    sents = sentences(clean)
    cap = cfg.get("semparse_sentence_cap") if cap is None else cap
    try:
        cap = max(0, int(cap or 0))
    except (TypeError, ValueError):
        cap = 0
    info["sentences_total"] = len(sents)
    info["capped"] = bool(cap and len(sents) > cap)
    if info["capped"]:
        sents = sents[:cap]
    info["sentences"] = len(sents)
    info["strip_counts"] = counts
    rows = [{"id": sentence_id(doc, k), "dataset": dataset, "doc": doc, "sent": k, "text": s}
            for k, s in enumerate(sents, 1)]
    return rows, info


# ---------------------------------------------------------------- upstream (semantic-parsing-hitl, MIT; imported)
def upstream(hitl):
    """-> (tmpl.blocks, tmpl.suite, tmpl.manifest) of a hitl checkout (imported, never copied)."""
    tdir = os.path.join(os.path.expanduser(hitl), "templates")
    if tdir not in sys.path:
        sys.path.insert(0, tdir)
    from tmpl import blocks as B, suite as S, manifest as MF   # noqa: E402
    return B, S, MF


def require_pin(hitl):
    """The sentence mode needs the parser with the sentence-by-sentence mode: the hitl checkout must pass
    semparse_catalog.verify_checkout AND be at SENTENCE_PIN.  -> root; raises semparse_catalog.HitlPinError."""
    from . import semparse_catalog as SC
    root = SC.hitl_root(hitl)
    got = SC.checkout_commit(root)
    if got != SENTENCE_PIN:
        raise SC.HitlPinError("sentence mode needs semantic-parsing-hitl %s, checkout %r is at %r"
                              % (SENTENCE_PIN[:8], root, got))
    return root


def _read_env(env_file):
    env = {}
    env_file = env_file or os.environ.get("WMTM_LLM_ENV_FILE", "")
    if env_file and os.path.exists(os.path.expanduser(env_file)):
        for line in open(os.path.expanduser(env_file), encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.rstrip("\n").split("=", 1)
                env[k.strip().replace("export ", "", 1).strip()] = v.strip().strip('"').strip("'")
    return env


def gateway_parse_fn(hitl, prompt, budget, env_file=None, workdir=None, timeout=300.0, meta=None, module=None):
    """The production parse_fn(text, item_id, context) -> run record: upstream parse_sentence (the function the
    offline driver calls, so the record is the same) with upstream's chat-completions provider and the offline
    driver's flags (temperature 0, timeout 300, effort default) -- but the provider class is wrapped so that every
    request first reserves one counted call in budget (ParseBudget.acquire, no waiting): a full share raises
    parse_budget.ShareFull and sends nothing.  parse_fn.call_ids collects the reserved ids (the caller resets it
    per sentence).  BASE_URL / LLM_MODEL / AI_API_KEY as in parse_cache.gateway_llm_usage (environment, else
    env_file, only read).  module: an already loaded semantic-parse.py (tests)."""
    import argparse
    env = _read_env(env_file)
    base = os.environ.get("BASE_URL") or env.get("BASE_URL")
    model = os.environ.get("LLM_MODEL") or env.get("LLM_MODEL")
    if not os.environ.get("AI_API_KEY") and env.get("AI_API_KEY"):
        os.environ["AI_API_KEY"] = env["AI_API_KEY"]
    if not base:
        raise RuntimeError("BASE_URL not set (environment or llm_env_file)")
    if module is None:
        from .semparse_provider import load_upstream
        module = load_upstream(hitl, workdir)
    if not hasattr(module, "parse_sentence"):
        raise RuntimeError("semantic-parse.py has no parse_sentence (the sentence mode needs %s)" % SENTENCE_PIN[:8])
    ap = argparse.ArgumentParser(add_help=False)
    module.add_provider_args(ap)
    flags = ["--provider", "chat-completions", "--base-url", base, "--api-key-env", "AI_API_KEY",
             "--timeout", str(float(timeout)), "--temperature", "0", "--prompt", prompt]
    if model:
        flags += ["--model", model]
    args = ap.parse_args(flags)
    args.dry_run = False
    inner = module.PROVIDERS["chat-completions"]
    ids = []
    tag = dict(meta or {}, provider="chat-completions")

    class Gated(inner):          # same provider name, so the run record is unchanged
        def complete(self, system, user, model):
            ids.append(budget.acquire(dict(tag, model=model), wait=False))   # counted before any request
            return super().complete(system, user, model)

    module.PROVIDERS = dict(module.PROVIDERS)
    module.PROVIDERS["chat-completions"] = Gated

    def parse_fn(text, item_id, context=None):
        return module.parse_sentence(text, args, item_id, context=context or None)

    parse_fn.call_ids, parse_fn.model, parse_fn.args = ids, model, args
    return parse_fn


# ---------------------------------------------------------------- the sentence cache (files in <semparse_dir>/sent1)
def sentence_dir(cfg):
    base = cfg["semparse_dir"]
    return base if os.path.basename(os.path.normpath(base)) == SENT_VERSION else os.path.join(base, SENT_VERSION)


def parsed_path(cfg_or_dir):
    """The parsed.jsonl the sentence feed writes: the value for the flag shadow_master_parsed."""
    d = cfg_or_dir if isinstance(cfg_or_dir, str) else sentence_dir(cfg_or_dir)
    return os.path.join(d, "parsed.jsonl")


def _rows(path):
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict):
                    out.append(r)
    except OSError:
        pass
    return out


def _good(rec):
    return bool(rec) and not rec.get("error") and isinstance(rec.get("response"), dict)


def _replies(rows):
    """The last good reply per sentence id (tmpl.blocks.read_replies' rule) from rows already read."""
    out = {}
    for r in rows:
        if _good(r.get("reply")):
            out[r["id"]] = r["reply"]
    return out


def _write_atomic(path, lines):
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def promote(d, doc, rows):
    """Move one finished note's rows into parsed.jsonl, all at once (tmp + os.replace).  Rows of an earlier version
    of the same doc are dropped first, so each doc has exactly one complete block.  Caller holds the cache lock."""
    p = parsed_path(d)
    keep = []
    try:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get("doc") != doc:
                    keep.append(line if line.endswith("\n") else line + "\n")
    except OSError:
        pass
    _write_atomic(p, keep + [json.dumps(r, ensure_ascii=False) + "\n" for r in rows])


def _record_note(cache, h, q, status, info, extra=None, now=None):
    """One cache.jsonl entry per finished note (no text); the note leaves the queue.  Caller holds the lock."""
    e = {"hash": h, "item_id": q["item_id"], "status": status, "atoms": [], "ts": now,
         "cache_version": SENT_VERSION, "sentences": info.get("sentences"),
         "sentences_total": info.get("sentences_total"), "capped": info.get("capped"),
         "speaker": info.get("speaker"), "speaker_source": info.get("speaker_source")}
    e.update(extra or {})
    with open(cache.entries_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(e) + "\n")
    qq = cache._queue()
    qq.pop(h, None)
    cache._save_queue(qq)


def _log_call(cache, cost):
    with cache._lock():
        cache._trim_log(cost["ts"])
        with open(cache.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(cost) + "\n")


def process_queue_sentence(cache, parse_fn, cfg=None, n=None, now=time.time, B=None, prompt_body_sha=None,
                           manifest_id=None, max_attempts=None):
    """Drain the sentence queue: oldest note first, each note sentence by sentence until it is finished, the run's
    call limit n (default the cache's hourly cap) is reached, or the cache's budget (own cap AND share) is spent.

    parse_fn(text, item_id, context) -> upstream run record (parse_sentence shape); its call_ids list (if any) is
    reset per sentence and copied into the parse_log row.  B: tmpl.blocks (walk, context_section).
    -> {"calls": [cost rows], "notes": {"ok", "failed", "empty", "partial"}, "stop": None | status}.  Never sends a
    call when cache.budget() is 0; a ShareFull from the gate stops the run with nothing recorded for that call."""
    from .frozen_parse import refuse_if_evaluating as _rie; _rie("process_queue_sentence")
    from .parse_budget import ShareFull, is_share_full
    cfg = cfg or {}
    if max_attempts is None:
        max_attempts = cfg.get("parse_max_attempts", MAX_ATTEMPTS)
    max_attempts = max(1, min(MAX_ATTEMPTS, int(max_attempts or MAX_ATTEMPTS)))
    n = cache.per_hour if n is None else n
    work_d, gave_d = os.path.join(cache.d, "work"), os.path.join(cache.d, "gave_up")
    os.makedirs(work_d, exist_ok=True)
    out = {"calls": [], "notes": {"ok": 0, "failed": 0, "empty": 0, "partial": 0}, "stop": None}
    cache.begin()
    ids = getattr(parse_fn, "call_ids", None)

    def stop(status, err=None):
        if status == "share_full":
            cache.share_full_stop(now(), err)
        else:
            cache.last_stop = {"status": status, "error": str(err or "")[:160]}
        out["stop"] = status

    for h, q in cache.next_batch(10 ** 9):
        if out["stop"] or len(out["calls"]) >= n:
            break
        rows, info = prepare(q["item_id"], q.get("content"), q.get("source"), cfg)
        if not rows:
            with cache._lock():
                _record_note(cache, h, q, "empty", info, now=now())
            out["notes"]["empty"] += 1
            continue
        wpath = os.path.join(work_d, h + ".jsonl")
        work = _rows(wpath)
        while True:
            prior, row = B.walk(rows, _replies(work))
            if row is None:                                   # every sentence has a good reply: the note is done
                with cache._lock():
                    promote(cache.d, q["item_id"], work)
                    _record_note(cache, h, q, "ok", info, {"rows": len(work)}, now=now())
                try:
                    os.unlink(wpath)
                except OSError:
                    pass
                out["notes"]["ok"] += 1
                break
            k = len(prior) + 1
            tried = sum(1 for r in work if r.get("id") == row["id"])
            if tried >= max_attempts:                         # gave up: never fed, never retried for this content
                with cache._lock():
                    os.makedirs(gave_d, exist_ok=True)
                    try:
                        os.replace(wpath, os.path.join(gave_d, h + ".jsonl"))
                    except OSError:
                        pass
                    _record_note(cache, h, q, "failed", info, {"failed_sentence": k, "attempts": tried}, now=now())
                out["notes"]["failed"] += 1
                break
            if len(out["calls"]) >= n:
                out["notes"]["partial"] += 1
                break
            if cache.budget(now()) <= 0:
                stop("share_full" if cache.share.remaining(now()) <= 0 else "cap_full")
                out["notes"]["partial"] += 1
                break
            context = B.context_section([{"k": p["k"], "text": p["text"], "instances": p["instances"]} for p in prior])
            if ids is not None:
                del ids[:]
            t0 = time.time()
            err = None
            try:
                rec = parse_fn(row["text"], row["id"], context or None)
            except ShareFull as e:                            # the gate refused: nothing was sent
                stop("share_full", e)
                out["notes"]["partial"] += 1
                break
            except Exception as e:                            # noqa: BLE001  (the offline driver's error row)
                err = (str(e).splitlines() or [type(e).__name__])[0][:300]
                if is_share_full(err):
                    stop("share_full", err)
                    out["notes"]["partial"] += 1
                    break
                rec = {"item": {"id": row["id"], "text": row["text"]}, "response": None, "error": "request failed: " + err}
            rec["prompt_body_sha256"] = prompt_body_sha
            rec["manifest_id"] = manifest_id
            rec["block"] = {"doc": row.get("doc"), "k": k, "available_from": k}
            line = {**row, "reply": rec}
            with open(wpath, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            work.append(line)
            ok = _good(rec)
            u = rec.get("usage") or {}
            ru = rec.get("raw_usage") or {}
            cost = {"ts": now(), "hash": h, "item_id": q["item_id"], "id": row["id"], "k": k,
                    "secs": round(time.time() - t0, 3), "status": "ok" if ok else "failed",
                    "context_chars": len(context or ""), "prompt_sha": (rec.get("prompt_sha256") or "")[:16] or None,
                    "prompt_tokens": ru.get("prompt_tokens", u.get("input")), "cached": u.get("cached"),
                    "completion_tokens": ru.get("completion_tokens", u.get("output")),
                    "total_tokens": ru.get("total_tokens", u.get("total")), "cache_version": SENT_VERSION}
            if ids is not None:
                cost["call_ids"] = list(ids)
            if not ok:
                cost["error"] = str(rec.get("error") or "")[:160]
            _log_call(cache, cost)
            out["calls"].append(cost)
            if err and LIMIT.search(err):
                stop("limit", err)
                out["notes"]["partial"] += 1
                break
    if out["stop"] is None and cache.share.remaining(now()) <= 0 and cache.pending():
        stop("share_full")
    return out


def sentence_cache(cfg=None, base=None):
    """The sentence feed's ParseCache (<semparse_dir>/sent1); the other caches are never rewritten."""
    from . import runtime_config as rc
    from .parse_cache import ParseCache
    cfg = cfg or rc.resolve()
    base = base or ParseCache(cfg=cfg)
    return ParseCache(os.path.join(base.d, SENT_VERSION), cfg=cfg)
