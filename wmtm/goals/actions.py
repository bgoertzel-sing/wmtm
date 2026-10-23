"""Track R / R2: candidate actions from templates.  Effects drive the legitimacy veto: 'message' (says something to a
human), 'read' (read-only look-up), 'log' (self-task: logged only, no message), 'write' / 'live_change' / 'git_memory' /
'push' (never allowed in phase 1).

R2 rules: 3. messages go to a resolved person only (never "user"); the bot's own to-dos become SelfTask; LookUp only for
factual gaps, not human decisions.  4. RemindPending only after >= remind_after_s with no reply from the addressee; no
proposal on a topic already proposed to the same person within reask_s unless something new happened.  Status
summaries list at most 3 deduped items as whole sentences."""
from __future__ import annotations

import hashlib
import re

from . import needs

TEMPLATES = {
    "ClarifyQuestion": {"need": "unc", "effects": ("message",), "text": "Ask {who}: {q}"},
    "FlagUncertainty": {"need": "unc", "effects": ("message",), "text": "In the next reply to {who}, say this is still open: {q}"},
    "LookUp":          {"need": "unc", "effects": ("read",), "text": "Read-only look-up (journal, WMTM, KB) to settle: {q}"},
    "SummarizeStatus": {"need": "comp", "effects": ("message",), "text": "Send {who} a short status of {n} open items: {q}"},
    "RemindPending":   {"need": "comp", "effects": ("message",), "text": "Remind {who} about: {q}"},
    "SelfTask":        {"need": "comp", "effects": ("log",), "text": "Self-task (log only, no message): {q}"},
}
MESSAGE_ACTIONS = ("ClarifyQuestion", "FlagUncertainty", "SummarizeStatus", "RemindPending")
SUMMARY_MAX = 3
SUMMARY_SENT_MAX = 220
_LOOKUPABLE = re.compile(r"\b([0-9a-f]{7,40}|branch|file|commit|log|path|where|which|version|tag|flag|cache)\b", re.I)
_FACTUAL = re.compile(r"^\W*(who|where|what|which|when|how many|how much|is there|does|did|has|have)\b|"
                      r"\b(which (branch|commit|file|version|repo)|where (is|are|does)|what (is|are|was))\b", re.I)
_CHOICE = re.compile(r"\b(should|whether|approve[sd]?|approval|choose|choice|decide|decision|prefer|want[s]?|"
                     r"OK to|go ahead|or not)\b", re.I)
_ASKY = re.compile(r"\?|\b(ask(ed)?|approve|approval|decide|want|should)\b", re.I)
_PROMISE = re.compile(r"\b(will|promised|next|follow up|report|deliver)\b", re.I)


_THE_USER = re.compile(r"\b[Tt]he user('s)?\b")
_OWN_PROMISE = re.compile(r"\b(I said I'?ll|I'll|I will|I promised|I'd|I would|I said I would)\b")
_CLAUSE = re.compile(r",\s*and\s+|;\s*|,\s*plus\s+")
DEDUPE_ACTIONS = ("ClarifyQuestion", "FlagUncertainty", "RemindPending", "LookUp")


def named(text, sig):
    """R2.1: replace 'the user' with the resolved person (the item's addressee, else the requester at note time)."""
    who = sig.get("who") if sig.get("who") not in (None, "", needs.SELF) else sig.get("req")
    if not who:
        return text
    return _THE_USER.sub(lambda m: who + ("'s" if m.group(1) else ""), text)


def split_promises(text):
    """-> (text without the bot's own promise clauses, [promise clauses]).  R2.1: own promises are self-tasks."""
    parts = _CLAUSE.split(text)
    keep = [p for p in parts if not _OWN_PROMISE.search(p)]
    own = [p.strip() for p in parts if _OWN_PROMISE.search(p)]
    if not own:
        return text, []
    out = ", and ".join(x.strip() for x in keep if x.strip())
    if out and not out.rstrip().endswith((".", "?", "!")):
        out = out.rstrip(" ,") + "."
    return out, own


def ckey(action, sig_texts):
    return hashlib.sha1((action + "|" + "|".join(sorted(sig_texts))).encode()).hexdigest()[:16]


def factual(sig):
    """LookUp is only for factual gaps (who/where/what/which), never for a human choice."""
    q = sig.get("body") or sig["text"]
    if sig.get("origin") == "parser":
        return True
    return bool(_FACTUAL.search(q)) and not _CHOICE.search(q)


def _kb_hit(sig, kb):
    for p in kb or ():
        terms = set(re.findall(r"[a-z0-9_]{4,}", str(p).lower()))
        if len(sig["keys"] & terms) >= 2:
            return str(p)[:300]
    return None


def _base(action, sigs, who, q, n=1):
    t = TEMPLATES[action]
    if len(sigs) == 1:
        q = named(q, sigs[0])
    return {"action": action, "need": t["need"], "effects": list(t["effects"]), "who": who,
            "text": t["text"].format(who=who, q=q, n=n), "signals": sigs, "key": ckey(action, [s["text"] for s in sigs]),
            "items": sorted({i for s in sigs for i in s["items"] if i}),
            "topic": sorted(set().union(*[s.get("ckeys") or s["keys"] for s in sigs])) if sigs else []}


def drop_own_wait(text, who):
    """rc2: "..., waiting on <who>." is redundant in a line addressed to <who> -> removed (whole sentence kept)."""
    if not who or who == needs.SELF:
        return text
    t = re.sub(r"[,;]?\s*\(?(?:still\s+)?(?:waiting|blocked)\s+on\s+%s(?:'s\s+\w+)?\)?(?=\s*[.;!?]?\s*$)" % re.escape(who),
               "", text, flags=re.I)
    if t != text and t.strip() and not t.rstrip().endswith((".", "?", "!")):
        t = t.rstrip(" ,;") + "."
    return t if len(needs.keys(t)) >= 2 else text


def recently_proposed(who, ks, ts_last, history, now, reask_s, thr=None):
    """-> the history entry that blocks a re-proposal (same person, same topic CLUSTER (rc2: paraphrases under a new
    id count), within reask_s, nothing new), else None.
    'Something new' = a note on the topic newer than that proposal that adds >= 2 new topic words."""
    for h in history or ():
        if now - float(h.get("ts", 0)) >= reask_s or h.get("who") != who:
            continue
        hk = set(h.get("topic") or ())
        if not needs.cluster_match(ks, hk, thr):
            continue
        if ts_last > float(h["ts"]) and len(ks - hk) >= 2:
            continue
        return h
    return None


def candidates(est, kb=None, now=None, age_cap_d=7.0, st=None, ctx=None):
    """-> (candidates, suppressed); suppressed = [(signal text, reason)] for timing / addressee rules."""
    st = st or {}; ctx = ctx or {}
    now = 0.0 if now is None else now
    hist = ctx.get("history") or ()
    reask_s = float(st.get("reask_s", 3 * 86400.0)); remind_s = float(st.get("remind_after_s", 86400.0))
    thr = st.get("topic_overlap")
    max_age_s = float(st.get("max_item_age_s", 7 * 86400.0))
    out, supp = [], []

    def blocked(s, who):
        h = recently_proposed(who, s.get("ckeys") or s["keys"], s["ts_last"], hist, now, reask_s, thr)
        if h:
            supp.append((s["text"], "fix4_reask_within_%gd" % (reask_s / 86400.0)))
        return bool(h)

    def too_old(s):
        """rc2: no message about an item last raised more than goal_max_item_age_days ago (a newer note re-raising
        it moves ts_last)."""
        if max_age_s > 0 and now - float(s["ts_last"]) > max_age_s:
            supp.append((s["text"], "rc2_item_older_than_%gd" % (max_age_s / 86400.0)))
            return True
        return False

    for s in est["unc"]["signals"]:
        sal = 0.2 + 0.8 * s["sal"]
        spec = 1.0 if len(s["keys"]) >= 4 else 0.6
        age_d = max(0.0, (now - s["ts"]) / 86400.0)
        age = 0.4 + 0.6 * min(age_d, age_cap_d) / age_cap_d
        human = s["who"] and s["who"] != needs.SELF
        if human and not too_old(s) and not blocked(s, s["who"]):
            q = s.get("body") or s["text"]
            c = _base("ClarifyQuestion", [s], s["who"], q)
            c["cons"] = {"salience": sal, "specificity": spec, "fit": 1.0 if _ASKY.search(s["text"]) else 0.6, "age": age}
            out.append(c)
            c = _base("FlagUncertainty", [s], s["who"], q)
            c["cons"] = {"salience": sal, "specificity": spec, "fit": 0.7, "age": age}
            out.append(c)
        elif not human and s.get("origin") != "parser":
            supp.append((s["text"], "fix3_no_addressee"))
        if factual(s):
            hit = _kb_hit(s, kb)
            c = _base("LookUp", [s], s["who"] or "self", s.get("body") or s["text"])
            c["cons"] = {"salience": sal, "specificity": spec, "fit": 1.0 if _LOOKUPABLE.search(s["text"]) else 0.5,
                         "kb_support": 1.0 if hit else 0.6}
            if hit:
                c["proof"] = hit
            out.append(c)
        elif not human:
            supp.append((s["text"], "fix3_lookup_not_factual"))
    comp = est["comp"]["signals"]
    for s in comp:
        cons = {"salience": 0.2 + 0.8 * s["sal"], "specificity": 1.0 if len(s["keys"]) >= 4 else 0.6,
                "fit": 1.0 if _PROMISE.search(s["text"]) else 0.8}
        if s["who"] == needs.SELF:
            if blocked(s, needs.SELF):
                continue
            c = _base("SelfTask", [s], needs.SELF, s["text"]); c["cons"] = cons; out.append(c)
            continue
        if too_old(s):
            continue
        lc = s.get("last_contact") or 0.0
        quiet_since = max(s["ts"], lc if lc > s["ts"] else 0.0)
        if now - quiet_since < remind_s:
            supp.append((s["text"], "fix4_remind_before_%gd_quiet" % (remind_s / 86400.0)))
            continue
        txt, own = split_promises(named(s["text"], s))   # R2.1: the bot's own promises never go into a message
        for o in own:
            supp.append((o, "r21_own_promise_to_selftask"))
            ss = dict(s, who=needs.SELF, kind="self", text=o, body=o, keys=needs.keys(o), ckeys=needs.keys(o))
            if not blocked(ss, needs.SELF) and len(ss["keys"]) >= 2:
                c = _base("SelfTask", [ss], needs.SELF, o); c["cons"] = dict(cons, specificity=0.6); out.append(c)
        txt = drop_own_wait(txt, s["who"])
        if len(needs.keys(txt)) < 2 or blocked(s, s["who"]):
            continue
        c = _base("RemindPending", [dict(s, text=txt)], s["who"], txt); c["cons"] = cons; out.append(c)
    to = ctx.get("requester")
    human = []
    for s in est["unc"]["signals"] + comp:
        if not (s["who"] and s["who"] == to and len(s["text"]) <= SUMMARY_SENT_MAX):
            continue                                       # a status goes to one person, about that person's items
        if too_old(s):
            continue
        lc = s.get("last_contact") or 0.0
        if now - max(s["ts_last"], lc if lc > s["ts_last"] else 0.0) < remind_s:
            supp.append((s["text"], "r21_summary_item_too_fresh"))      # R2.1: >= 1 day no-reply per item
            continue
        txt, own = split_promises(named(s["text"], s))
        for o in own:                                      # R2.1: the bot's own promises are self-tasks
            supp.append((o, "r21_own_promise_to_selftask"))
            ss = dict(s, who=needs.SELF, kind="self", text=o, body=o, keys=needs.keys(o), ckeys=needs.keys(o))
            if not blocked(ss, needs.SELF) and len(ss["keys"]) >= 2:
                c = _base("SelfTask", [ss], needs.SELF, o)
                c["cons"] = {"salience": 0.2 + 0.8 * s["sal"], "specificity": 0.6, "fit": 1.0}
                out.append(c)
        if len(needs.keys(txt)) < 2:
            continue
        human.append(dict(s, text=drop_own_wait(txt, to)))
    if len(human) >= 2 and to:
        top, seen = [], []
        for s in sorted(human, key=lambda x: (-x["sal"], -x["ts_last"])):
            if any(needs.cluster_match(s["keys"], k, thr) for k in seen):
                continue
            seen.append(s["keys"]); top.append(s)
            if len(top) == SUMMARY_MAX:
                break
        if len(top) >= 2:
            ks = set().union(*[s["keys"] for s in top])
            if not recently_proposed(to, ks, max(s["ts_last"] for s in top), hist, now, reask_s, thr):
                q = " ".join("(%d) %s" % (i + 1, s["text"].rstrip()) for i, s in enumerate(top))
                c = _base("SummarizeStatus", top, to, q, n=len(top))
                c["cons"] = {"salience": 0.2 + 0.8 * max(x["sal"] for x in top), "fit": min(1.0, len(top) / 3.0)}
                out.append(c)
            else:
                supp.append(("summary", "fix4_reask_within_%gd" % (reask_s / 86400.0)))
    return out, supp
