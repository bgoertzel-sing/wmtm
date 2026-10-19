"""Track O: coreference via CONTEXT.

When a note is parsed, the atoms of related earlier notes go verbatim under ``CONTEXT:`` and the new note (or one
short passage of it) under ``TEXT:``.  The prompt (section "Input - TEXT and optional CONTEXT") then reuses
existing symbols for definites / pronouns / names, and continues sk_* witness numbering past the context.

Pure helpers, no I/O: related-note selection, passage splitting, the CONTEXT/TEXT message, and post-filters
(context atoms re-emitted by the model are dropped; context witnesses keep their existing scope).
"""
import re

STOP = set("""the a an and or but of to in on at for with by from as is are was were be been being it its this that these
those there here then than so not no yes do does did done have has had will would can could should may might must
i you he she we they them his her our their my your me us him what which who whom when where why how all any some
each every more most other into over under about after before again also just only very via per vs etc""".split())
WORD = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,}")
SYM = re.compile(r"[A-Za-z_][A-Za-z0-9_\-]*")
HEADS = {"Member", "Inheritance", "Implies", "Implication", "Premises", "Conclusions", "And", "Or", "Not", "STV",
         "Name", "Agent", "Patient", "Theme", "Past", "Time", "Interpretation", "Day", "Month", "Year", "Hour"}


def text_terms(text: str) -> set:
    return {w.lower().replace("-", "_") for w in WORD.findall(text or "")} - STOP


def atom_body(atom: str) -> str:
    """'(: name BODY TV)' -> 'BODY TV' (the proof name differs per item; the statement is what repeats)."""
    s = atom.strip()
    if s.startswith("(:"):
        rest = s[2:].lstrip()
        i = 0
        while i < len(rest) and not rest[i].isspace():
            i += 1
        return re.sub(r"\s+", " ", rest[i:].strip()[:-1].strip())
    return re.sub(r"\s+", " ", s)


def atom_terms(atoms) -> set:
    out = set()
    for a in atoms:
        for t in SYM.findall(atom_body(a)):
            if t in HEADS or t.startswith("i_"):
                continue
            if t.startswith("sk_"):                      # sk_report_1__i_x -> report
                t = re.sub(r"_\d+$", "", t.split("__")[0][3:])
            t = t.lower()
            if len(t) >= 3 and t not in STOP:
                out.add(t)
    return out


def select_context(text: str, earlier, max_notes=3, max_atoms=40, max_chars=4000):
    """earlier: list of dicts {item_id, atoms, ts, content?} (any order).  Pick related notes by shared terms
    (note text + atom symbols), ties by recency; then fill with the most recent notes if nothing is shared.
    Returns (atoms, picked_item_ids, shared_terms) capped at max_notes / max_atoms / max_chars."""
    want = text_terms(text)
    scored = []
    for e in earlier:
        if not e.get("atoms"):
            continue
        terms = atom_terms(e["atoms"]) | text_terms(e.get("content") or "")
        shared = want & terms
        scored.append((len(shared), float(e.get("ts") or 0), e, shared))
    rel = sorted([s for s in scored if s[0] > 0], key=lambda s: (-s[0], -s[1]))
    if not rel:
        rel = sorted(scored, key=lambda s: -s[1])[:1]          # recency fallback: the latest note only
    atoms, ids, shared_all, chars = [], [], set(), 0
    for _, _, e, shared in rel[:max_notes]:
        took = False
        for a in e["atoms"]:
            if len(atoms) >= max_atoms or chars + len(a) + 1 > max_chars:
                break
            atoms.append(a); chars += len(a) + 1; took = True
        if took:
            ids.append(e["item_id"]); shared_all |= shared
    return atoms, ids, sorted(shared_all)


TAG = re.compile(r"<!--.*?-->", re.S)


def split_passages(text: str, max_chars=600):
    """Sentence-ish passages of <= max_chars (a single longer sentence is hard-wrapped).  Markup-only tails
    (e.g. a trailing ``<!-- project: ... -->`` tag) are removed first so they never become a passage."""
    text = TAG.sub(" ", text or "").strip()
    if len(text) <= max_chars:
        return [text] if text else []
    sents = re.split(r"(?<=[.!?;])\s+|\n{2,}", text)
    out, cur = [], ""
    for s in sents:
        s = s.strip()
        while len(s) > max_chars:
            if cur:
                out.append(cur); cur = ""
            cut = s.rfind(" ", 0, max_chars)
            cut = cut if cut > max_chars // 2 else max_chars
            out.append(s[:cut].strip()); s = s[cut:].strip()
        if not s:
            continue
        if cur and len(cur) + 1 + len(s) > max_chars:
            out.append(cur); cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def user_message(text: str, context_atoms=()) -> str:
    if not context_atoms:
        return f"TEXT: {text}"
    return "CONTEXT:\n" + "\n".join(context_atoms) + "\n\nTEXT:\n" + text
