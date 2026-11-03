"""Goal lifecycle (log only): stable goal IDs, near-duplicate merging and open/satisfied/superseded/stale states.

Offline only: nothing here is called by the live worker, the prompt or the flags.  Input = logged proposals
(``<runtime_dir>/goalchainer/proposals.jsonl`` rows) plus the journal notes; output = goal records and a per-proposal
verdict (kept / dropped with a reason).  docs/GOAL_LIFECYCLE.md states the rules; tests/test_goal_lifecycle.py tests them.

Rules (thresholds are module constants so a replay can report them):

* Goal text = the proposal text without its wrapper ("Self-task (log only, no message): ", "Remind X about: ") and
  without leading open markers ("Still open:", "PENDING:", "WAITING on ..."), terms = needs.norm(needs.keys(body)) plus
  short acronyms (LTM, CoS), minus the marker words.
* Same goal (same ID): same person (``who``) AND same action AND Jaccard(terms) >= MERGE_JACCARD AND equal anchor sets
  (anchors = "@x" entities / paths, track letters, commit hashes, task ids).  An anchor present on one side only means a
  different object, so it never merges.  The ID is that of the first goal in the cluster (sha1 of who|action|terms).
* superseded: a later goal (newer source note) for the same person either restates it (covers >= COVER of its terms)
  or it was split: later smaller goals each covered >= COVER by it, whose union covers >= SPLIT_COVER of its terms
  (one split-off item alone never retires the other items).
* satisfied: a journal note newer than the goal's newest source note reports a closure (a CLOSED / RESOLVED / DONE
  word, needs.res_hit, or "is done" / "deleted" / "trimmed" in one of its sentences) AND matches the goal: it names one
  of the goal's task ids, or it shares >= SAT_MIN distinctive terms (not among the journal's common closure terms) with
  at least one shared anchor, or it shares >= SAT_FRAC of the goal's distinctive terms (and >= 3).
* multi-item goals (needs.split_items: "a; b; c" or "a, and X hasn't ...") are satisfied only when EVERY item
  matches a closure on its own.
* stale: still open and its newest source note is older than STALE_DAYS when proposed, with no later journal note on
  the topic (>= SAT_FRAC shared terms, no closure needed) in between.
* otherwise open.  Precedence when several apply: superseded > satisfied > stale > open.
"""
from __future__ import annotations

import hashlib
import re

from . import needs

MERGE_JACCARD = 0.8
COVER = 0.8
SPLIT_COVER = 0.95   # a multi-item goal is superseded only when its split-off parts cover (almost) all of it
SAT_MIN = 4
SAT_FRAC = 0.5
STALE_DAYS = 7.0

_WRAP = re.compile(r"^\s*(?:Self-task \(log only, no message\)|Remind [\w.-]+ about|Suggest(?:ion)?[^:]{0,40})\s*:\s*",
                   re.I)
_LEAD = re.compile(r"^\s*(?:(?:still )?(?:open|pending)\s*:\s*|PENDING\s*:\s*|next step,? still pending\s*:\s*|"
                   r"(?:still )?waiting on\s+)", re.I)
_ACRO = re.compile(r"\b([A-Z][A-Za-z]{1,3})\b")
_ACRO_STOP = {"OK", "I", "A", "NOT", "NO", "AND", "OR", "THE", "PR"}
_TASK = re.compile(r"\b(t-\d{4}-\d{2}-\d{2}-[a-z0-9-]+|p-\d{4}-[a-z0-9-]+)\b")
_ENRICH = re.compile(r"\(MemoryCluster |wmtm-enrich-")
_LABEL_ANY = re.compile(r"^\s*(?:LINK|SUPPORTS|CONTRADICTS|CONTRAST|CORRECTION|LESSON|NOTE|ROOT CAUSE)\b", re.I)
_MARKER_WORDS = {"still", "open", "pending", "waiting", "self", "task", "remind"}
_CLOSE_EXTRA = re.compile(r"\b(CLOSED|DONE|is done|are done|deleted|trimmed|removed|merged|fixed)\b")


def body(text):
    b = _WRAP.sub("", text or "", count=1)
    prev = None
    while prev != b:
        prev, b = b, _LEAD.sub("", b, count=1)
    return b.strip()


def terms(text):
    b = body(text)
    t = {x for x in needs.norm(needs.keys(b)) if x not in _MARKER_WORDS}
    for m in _ACRO.finditer(b):
        w = m.group(1)
        if w.upper() == w and len(w) >= 2 and w not in _ACRO_STOP or (len(w) >= 3 and re.fullmatch(r"[A-Z][a-z][A-Z]", w)):
            t.add("@" + w.lower())
    t |= {"@" + x for x in _TASK.findall(b)}
    return t


def anchors(ts):
    return {x for x in ts if x.startswith("@") or x.startswith("track_") or
            (re.fullmatch(r"[0-9a-f]{7,40}", x) and re.search(r"\d", x) and re.search(r"[a-f]", x))}


def task_ids(text):
    return set(_TASK.findall(text or ""))


def jaccard(a, b):
    return len(a & b) / float(len(a | b)) if (a or b) else 0.0


def same_goal(a, b):
    """a, b: dicts with who, action, terms.  -> (bool, reason)."""
    if (a.get("who") or "") != (b.get("who") or ""):
        return False, "different person"
    if (a.get("action") or "") != (b.get("action") or ""):
        return False, "different action"
    ta, tb = a["terms"], b["terms"]
    if anchors(ta) != anchors(tb):
        return False, "different anchors %s" % sorted(anchors(ta) ^ anchors(tb))
    j = jaccard(ta, tb)
    if j < MERGE_JACCARD:
        return False, "jaccard %.2f < %.2f" % (j, MERGE_JACCARD)
    return True, "jaccard %.2f, same anchors" % j


def goal_id(who, action, ts):
    return hashlib.sha1(("%s|%s|%s" % (who or "", action or "", " ".join(sorted(ts)))).encode()).hexdigest()[:12]


def cover(small, big):
    return len(small & big) / float(len(small)) if small else 0.0


def supersedes(new, old):
    """Does goal ``new`` (newer source) supersede ``old``?  -> reason or ''."""
    if new["who"] != old["who"] or new is old:
        return ""
    if (new["src_ts"], new["first_ts"]) <= (old["src_ts"], old["first_ts"]):
        return ""
    if cover(old["terms"], new["terms"]) >= COVER:
        return "restated by %s" % new["gid"]
    if len(new["terms"]) < len(old["terms"]) and cover(new["terms"], old["terms"]) >= COVER:
        return "split: item %s taken over by %s" % (" ".join(sorted(new["terms"]))[:60], new["gid"])
    return ""


def closing_sentences(note_text):
    """Sentences of a note that report a closure: a non-negated resolution word (needs.res_hit) or CLOSED / DONE /
    is done / deleted / trimmed / removed / merged / fixed, not preceded by an open marker ("still open:",
    "waiting on", "pending:") and not negated."""
    out = []
    if _ENRICH.search(note_text or ""):
        return out                      # WMTM enrichment clusters restate older notes: never evidence
    for s in needs.sentences(note_text):
        if needs._LABEL.match(s) or _LABEL_ANY.match(s):
            continue                    # LINK / SUPPORTS / CORRECTION / LESSON sentences relate notes, they close nothing
        p = needs.res_hit(s)
        if p < 0:
            m = _CLOSE_EXTRA.search(s)
            if m and not needs._NEG_BEFORE.search(s[max(0, m.start() - 8):m.start()]):
                p = m.start()
        if p < 0:
            continue
        mk = needs.marker(s)
        if mk and mk[2].start() <= p:
            continue
        out.append(s)
    return out


def note_closes(note_text):
    return bool(closing_sentences(note_text))


def closure_match(goal, note_terms, note_text, common=()):
    """-> reason string if a closure sentence of the note matches the goal, else ''.  Sentence level: the closing
    sentence itself must carry the match.  (a) it names one of the goal's task ids; (b) it shares >= 2 distinctive
    terms with the goal, one of them an anchor, and the whole note shares >= SAT_MIN - 1 distinctive terms; (c) it
    alone shares >= 3 distinctive terms and >= SAT_FRAC of them."""
    g = {x for x in goal["terms"] if x.lstrip("@") not in common}
    gt = task_ids(goal["text"])
    for s in closing_sentences(note_text):
        tids = gt & task_ids(s)
        if tids:
            return "closing sentence names task %s" % sorted(tids)[0]
        sh = g & terms(s)
        if len(sh) >= 2 and anchors(sh) and len(g & note_terms) >= SAT_MIN - 1:
            return "closing sentence shares %s (anchor %s), note shares %d" % (
                " ".join(sorted(sh)), sorted(anchors(sh))[0], len(g & note_terms))
        if g and len(sh) >= 3 and len(sh) >= SAT_FRAC * len(g):
            return "closing sentence shares %d of %d terms (%s)" % (len(sh), len(g), " ".join(sorted(sh)))
        nsh = g & note_terms
        if g and len(sh) >= 2 and len(nsh) >= 3 and len(nsh) >= SAT_FRAC * len(g):
            return "closing sentence shares %s, note shares %d of %d terms" % (" ".join(sorted(sh)), len(nsh), len(g))
    return ""


def topic_touch(goal, note_terms, common=()):
    g = {x for x in goal["terms"] if x.lstrip("@") not in common}
    sh = g & note_terms
    return bool(g) and len(sh) >= 3 and len(sh) >= SAT_FRAC * len(g)


def note_terms(text):
    """Terms of a whole journal note (same normalisation as goal terms)."""
    return terms(text)


def item_goals(goal):
    """A multi-item goal ("a; b; c", or "a, and X hasn't ...", needs.split_items) -> one pseudo-goal per item, so
    that closing one item never satisfies the whole goal.  A single item -> [goal]."""
    its = needs.split_items(body(goal["text"]))
    if len(its) < 2:
        return [goal]
    out = []
    for x in its:
        t = terms(x)
        if t:
            out.append({"text": x, "terms": t})
    return out or [goal]


class Lifecycle:
    """Feed proposals in time order with ``observe``; ``notes`` = [(id, ts, text)] sorted by ts."""

    def __init__(self, notes, common=()):
        self.notes = list(notes)
        self.note_ts = {i: t for i, t, _ in self.notes}
        self.common = set(common)
        self.goals = []            # goal records
        self._nt = {}

    def _terms_of(self, i, text):
        if i not in self._nt:
            self._nt[i] = note_terms(text)
        return self._nt[i]

    def _goal_for(self, p):
        ts = terms(p.get("text"))
        cand = {"who": p.get("who") or "", "action": p.get("action") or "", "terms": ts}
        for g in self.goals:
            ok, why = same_goal(cand, g)
            if ok:
                if p.get("id") not in g["engine_ids"]:
                    g["engine_ids"].append(p.get("id"))
                    g["merges"].append({"engine_id": p.get("id"), "rule": why})
                return g, False
        src = [self.note_ts.get(x) for x in (p.get("items") or []) if self.note_ts.get(x)]
        g = {"gid": goal_id(cand["who"], cand["action"], ts), "who": cand["who"], "action": cand["action"],
             "terms": ts, "text": p.get("text") or "", "engine_ids": [p.get("id")], "merges": [],
             "items": list(p.get("items") or []), "src_ts": max(src) if src else float(p.get("ts") or 0),
             "first_ts": float(p.get("ts") or 0), "state": "open", "why": ""}
        self.goals.append(g)
        return g, True

    def state_at(self, g, now):
        """State of goal g as known at time ``now`` (only notes and goals before now count).  Precedence:
        superseded (its parts / restatement carry their own states) > satisfied > stale > open."""
        parts, union = [], set()
        for h in self.goals:
            if h is g or h["first_ts"] > now:
                continue
            why = supersedes(h, g)
            if why.startswith("restated"):
                return "superseded", "superseded: %s" % why
            if why:
                parts.append(h["gid"]); union |= h["terms"]
        if parts and cover(g["terms"], union) >= SPLIT_COVER:
            return "superseded", "superseded: split into %s (parts cover %.2f of its terms)" % (
                ", ".join(parts), cover(g["terms"], union))
        parts = item_goals(g)
        found = []
        for part in parts:
            hit = ""
            for i, t, c in self.notes:
                if t <= g["src_ts"] or t > now:
                    continue
                why = closure_match(part, self._terms_of(i, c), c, self.common)
                if why:
                    hit = "%s (%s)" % (i, why)
                    break
            if not hit:
                break                    # one item still open: the goal is not satisfied
            found.append(hit)
        if found and len(found) == len(parts):
            if len(parts) == 1:
                return "satisfied", "satisfied by " + found[0]
            return "satisfied", "satisfied: all %d items closed: %s" % (len(parts), "; ".join(found))
        if now - g["src_ts"] > STALE_DAYS * 86400.0:
            for i, t, c in self.notes:
                if g["src_ts"] < t <= now and i not in g["items"] and topic_touch(g, self._terms_of(i, c), self.common):
                    break
            else:
                return "stale", "stale: newest source note %.1f d old, no later note on the topic" % (
                    (now - g["src_ts"]) / 86400.0)
        return "open", ""

    def observe(self, p):
        """-> verdict dict for proposal p: {gid, keep, reason}."""
        now = float(p.get("ts") or 0)
        g, new = self._goal_for(p)
        st, why = self.state_at(g, now)
        g["state"], g["why"] = st, why
        if st != "open":
            return {"gid": g["gid"], "keep": False, "state": st, "reason": why}
        if not new:
            if p.get("id") != g["engine_ids"][0]:
                return {"gid": g["gid"], "keep": False, "state": "open",
                        "reason": "near-duplicate of goal %s (%s)" % (g["gid"], g["merges"][-1]["rule"])}
            if g.get("_kept"):
                return {"gid": g["gid"], "keep": False, "state": "open", "reason": "duplicate of goal %s" % g["gid"]}
        g["_kept"] = True
        return {"gid": g["gid"], "keep": True, "state": "open", "reason": "first proposal of goal"}
