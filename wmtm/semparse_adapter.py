"""wmtm/semparse_adapter.py - WMTM items / journal notes -> PeTTaChainer atoms.

Pipeline per item:
  text -> LLM(system=semantic-parsing-hitl prompt.txt, user=TEXT) -> raw reply
       -> split into top-level s-expressions -> structural check -> normalise
       -> load-check in PeTTa (any loader exposing add_atom) -> accepted atoms.
Every rejected atom or reply is written to a JSONL reject log with a reason.
Nothing is dropped silently.

The LLM is a plain callable ``llm(system: str, user: str) -> str`` so tests can
mock it. ``gateway_llm`` builds a callable for the local OpenAI-compatible
gateway (BASE_URL / AI_API_KEY / LLM_MODEL).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

# semantic-parsing-hitl prompt.txt (not redistributed here; see scripts/fetch_semparse_hitl.sh)
DEFAULT_PROMPT = os.environ.get("SEMPARSE_PROMPT", "")

LLM = Callable[[str, str], str]


# ---------------------------------------------------------------- s-expressions
class SexprError(ValueError):
    pass


def tokenize(text: str) -> list:
    """Tokens: '(' ')' string literals (kept quoted) and bare symbols."""
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c == ';':                      # MeTTa line comment
            while i < n and text[i] != '\n':
                i += 1
        elif c in '()':
            toks.append(c)
            i += 1
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == '\\' else 1
            if j >= n:
                raise SexprError("unterminated string literal")
            toks.append(text[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '()";':
                j += 1
            toks.append(text[i:j])
            i = j
    return toks


def parse_one(toks: list, pos: int):
    if pos >= len(toks):
        raise SexprError("unexpected end of input")
    t = toks[pos]
    if t == ')':
        raise SexprError("unexpected ')'")
    if t != '(':
        return t, pos + 1
    out, pos = [], pos + 1
    while True:
        if pos >= len(toks):
            raise SexprError("unbalanced parentheses: missing ')'")
        if toks[pos] == ')':
            return out, pos + 1
        node, pos = parse_one(toks, pos)
        out.append(node)


def to_str(node) -> str:
    if isinstance(node, list):
        return "(" + " ".join(to_str(x) for x in node) + ")"
    return node


def split_toplevel(text: str):
    """Yield (source_text, node_or_None, error_or_None) per top-level form.

    A form that fails to parse is reported (not dropped) and the scan resumes
    on the next line so one bad line does not lose the rest of the reply."""
    text = re.sub(r"^```[a-zA-Z]*\s*$", "", text, flags=re.M)
    for line_block in _blocks(text):
        try:
            toks = tokenize(line_block)
            pos = 0
            while pos < len(toks):
                start = pos
                node, pos = parse_one(toks, pos)
                yield to_str(node), node, None
        except SexprError as e:
            yield line_block.strip(), None, str(e)


def _blocks(text: str):
    """Group lines into balanced blocks (atoms may span lines)."""
    buf, depth = [], 0
    for line in text.splitlines():
        if not line.strip() and depth == 0:
            continue
        buf.append(line)
        try:
            depth += sum(1 if t == '(' else -1 if t == ')' else 0 for t in tokenize(line))
        except SexprError:
            depth = 0
        if depth <= 0:
            yield "\n".join(buf)
            buf, depth = [], 0
    if buf:
        yield "\n".join(buf)


# ---------------------------------------------------------------- validation
_SYM = re.compile(r"^[A-Za-z_$][A-Za-z0-9_\-$']*$")


def _num(s) -> Optional[float]:
    try:
        return float(s) if isinstance(s, str) else None
    except ValueError:
        return None


def check_statement(node) -> Optional[str]:
    """Return None if `node` is a well-formed (: name content (STV s c)), else a reason."""
    if not isinstance(node, list):
        return "not a list"
    if node and node[0] == "Interpretation":
        if len(node) != 3 or not isinstance(node[1], str):
            return "Interpretation must be (Interpretation <label> <statement>)"
        return check_statement(node[2])
    if len(node) != 4 or node[0] != ":":
        return "not of the form (: <name> <content> (STV s c))"
    name, content, tv = node[1], node[2], node[3]
    if not isinstance(name, str) or not _SYM.match(name) or name.startswith("$"):
        return f"bad proof name {to_str(name)!r}"
    if not isinstance(content, list) or not content:
        return "content must be a non-empty expression"
    if not (isinstance(tv, list) and len(tv) == 3 and tv[0] == "STV"):
        return "truth value must be (STV s c)"
    s, c = _num(tv[1]), _num(tv[2])
    if s is None or c is None:
        return "STV values must be numbers"
    if not 0.0 <= s <= 1.0:
        return f"strength {s} outside [0,1]"
    if not 0.0 <= c < 1.0:
        return f"confidence {c} outside [0,1)"
    if _or_inside_and(content):
        return ("unsupported nesting: Or inside And (PeTTaChainer ccae5ad add_atom "
                "grows >1.2 GB RSS on this shape; canary 2026-10-15)")
    return None


def _or_inside_and(node, under_and=False) -> bool:
    """True if an (Or ...) occurs anywhere below an (And ...)."""
    if not isinstance(node, list) or not node:
        return False
    head = node[0]
    if head == "Or" and under_and:
        return True
    nxt = under_and or head == "And"
    return any(_or_inside_and(x, nxt) for x in node[1:])


def is_query(node) -> bool:
    return (isinstance(node, list) and len(node) == 4 and node[0] == ":"
            and isinstance(node[1], str) and node[1].startswith("$"))


# ---------------------------------------------------------------- normalisation
def normalise(node) -> list:
    """Rewrite rule forms this PeTTaChainer build does not chain on.

    Canary (2026-10-15): (Implication (And p q) c) derives nothing and rules with
    several conclusions derive nothing; (Implication (Premises ...) (Conclusions c))
    with ONE conclusion does. So: And -> Premises, multi-conclusion -> one rule per
    conclusion (names suffixed _c1, _c2 ...). Returns a list of statements."""
    if node[0] == "Interpretation":
        return [["Interpretation", node[1], n] for n in normalise(node[2])]
    _, name, content, tv = node
    if not (isinstance(content, list) and len(content) == 3 and content[0] == "Implication"):
        return [node]
    pre, con = content[1], content[2]
    if isinstance(pre, list) and pre and pre[0] == "And":
        pre = ["Premises"] + pre[1:]
    elif not (isinstance(pre, list) and pre and pre[0] == "Premises"):
        pre = ["Premises", pre]
    if isinstance(con, list) and con and con[0] == "Conclusions":
        cons = con[1:]
    else:
        cons = [con]
    if len(cons) == 1:
        return [[":", name, ["Implication", pre, ["Conclusions", cons[0]]], tv]]
    return [[":", f"{name}_c{i}", ["Implication", pre, ["Conclusions", c]], tv]
            for i, c in enumerate(cons, 1)]


def _scope_skolems(node, prefix: str):
    """sk_* witnesses are per-item: sk_request_1 in two notes is NOT one entity."""
    if isinstance(node, list):
        return [_scope_skolems(x, prefix) for x in node]
    if isinstance(node, str) and node.startswith("sk_"):
        if "__i_" in node:                 # Track O: a context witness (already scoped by its own note) is reused
            return node
        return f"{node}__{prefix}"
    return node


def _rescope(node, prefix: str, sprefix: str):
    """Passage parses: witnesses are scoped to the note so passages share them."""
    if isinstance(node, list):
        return [_rescope(x, prefix, sprefix) for x in node]
    if isinstance(node, str) and node.startswith("sk_") and node.endswith("__" + prefix):
        return node[: -len(prefix)] + sprefix
    return node


def prefix_names(node, prefix: str):
    """Make proof names and skolem symbols unique across items."""
    if node[0] == "Interpretation":
        return ["Interpretation", node[1], prefix_names(node[2], prefix)]
    return [":", f"{prefix}__{node[1]}", _scope_skolems(node[2], prefix), node[3]]


# ---------------------------------------------------------------- items
def item_text(item) -> str:
    if isinstance(item, str):
        return item
    for k in ("content", "text", "note", "summary"):
        v = item.get(k) if isinstance(item, dict) else None
        if isinstance(v, str) and v.strip():
            return v
    raise ValueError("item has no text field")


def safe_id(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9_]", "_", str(s))
    return ("i_" + s)[:40]


# ---------------------------------------------------------------- adapter
@dataclass
class ParseResult:
    item_id: str
    text: str
    accepted: list = field(default_factory=list)
    queries: list = field(default_factory=list)
    rejected: list = field(default_factory=list)   # (atom_text, reason)
    error: Optional[str] = None


class SemParseAdapter:
    def __init__(self, llm: LLM, loader=None, prompt_path: str = DEFAULT_PROMPT,
                 reject_log: Optional[str] = None, system: Optional[str] = None,
                 max_chars: int = 2000, reject_log_max_bytes: Optional[int] = None,
                 preamble: Optional[bool] = None):
        self.llm = llm
        self.loader = loader          # object with add_atom(str); None = no PeTTa check
        if system is None:
            with open(prompt_path, encoding="utf-8") as fh:
                system = fh.read()
            if preamble is None:      # Track M: file-based prompts get the pre-instruction block by default
                from .runtime_config import SPEC
                preamble = bool(SPEC["semparse_preamble"][2]) if os.environ.get("WMTM_SEMPARSE_PREAMBLE") is None \
                    else os.environ["WMTM_SEMPARSE_PREAMBLE"].strip().lower() in ("1", "true", "yes", "on")
        self.file_sha256 = hashlib.sha256(system.encode()).hexdigest()   # = pinned sha of the unedited prompt file
        if preamble:
            from .semparse_preamble import apply
            system = apply(system, True)
        self.preamble = bool(preamble)
        self.system = system
        self.prompt_sha256 = hashlib.sha256(system.encode()).hexdigest()
        self.reject_log = reject_log
        self.max_chars = max_chars
        self.reject_log_max_bytes = reject_log_max_bytes

    def _log(self, res: ParseResult, atom: str, reason: str, stage: str):
        res.rejected.append((atom, reason))
        if self.reject_log:
            rec = {"ts": time.time(), "item_id": res.item_id, "stage": stage,
                   "atom": atom, "reason": reason, "prompt_sha256": self.prompt_sha256,
                   "text": res.text[:500]}
            if self.reject_log_max_bytes:
                from .runtime_config import rotate_jsonl
                rotate_jsonl(self.reject_log, self.reject_log_max_bytes)
            with open(self.reject_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")

    def parse_item_ctx(self, item_id, item, context_atoms=(), passage_chars=600, max_context_atoms=60):
        """Track O: parse with CONTEXT (atoms of related earlier notes, verbatim) and TEXT; long notes are parsed
        per short passage, each passage seeing the context plus the atoms accepted from earlier passages."""
        from .semparse_context import split_passages
        text = item_text(item)[: self.max_chars]
        total = ParseResult(str(item_id), text)
        own = []
        for k, p in enumerate(split_passages(text, passage_chars) or [text]):
            ctx = (list(context_atoms) + own)[-max_context_atoms:] if (context_atoms or own) else []
            pid = item_id if k == 0 else f"{item_id}_p{k}"
            r = self.parse_item(pid, p, context_atoms=ctx, scope_id=item_id)
            own += r.accepted
            total.accepted += r.accepted; total.queries += r.queries; total.rejected += r.rejected
            if r.error and not total.error:
                total.error = r.error
        if total.accepted and total.error == "empty reply":
            total.error = None
        return total

    def parse_item(self, item_id, item, context_atoms=(), scope_id=None) -> ParseResult:
        from .semparse_context import user_message, atom_body
        text = item_text(item)[: self.max_chars]
        res = ParseResult(str(item_id), text)
        ctx_bodies = {atom_body(a) for a in context_atoms}
        try:
            reply = self.llm(self.system, user_message(text, list(context_atoms)))
        except Exception as e:                       # noqa: BLE001
            res.error = f"llm error: {e}"
            self._log(res, "", res.error, "llm")
            return res
        if not reply or not reply.strip():
            res.error = "empty reply"
            self._log(res, "", res.error, "llm")
            return res
        prefix = safe_id(item_id)
        sprefix = safe_id(scope_id if scope_id is not None else item_id)   # sk_* scope = the note, not the passage
        for src, node, err in split_toplevel(reply):
            if err:
                self._log(res, src, f"syntax: {err}", "syntax")
                continue
            if is_query(node):
                res.queries.append(src)
                continue
            reason = check_statement(node)
            if reason:
                self._log(res, src, f"structure: {reason}", "structure")
                continue
            for n in normalise(node):
                pn = prefix_names(n, prefix)
                if sprefix != prefix:
                    pn = _rescope(pn, prefix, sprefix)
                atom = to_str(pn)
                if ctx_bodies and atom_body(atom) in ctx_bodies:
                    self._log(res, atom, "context atom re-emitted", "context")
                    continue
                if self.loader is not None:
                    try:
                        out = self.loader.add_atom(atom)
                        if _looks_like_error(out):
                            raise RuntimeError(str(out)[:200])
                    except Exception as e:           # noqa: BLE001
                        self._log(res, atom, f"petta load: {str(e)[:200]}", "petta")
                        continue
                res.accepted.append(atom)
        if not res.accepted and not res.queries and not res.rejected:
            self._log(res, reply[:300], "reply contained no atoms", "syntax")
        return res

    def parse_items(self, items: Iterable) -> list:
        return [self.parse_item(i, it) for i, it in items]


def _looks_like_error(out) -> bool:
    s = str(out) if out is not None else ""
    return bool(re.search(r"\(Error\b|Exception|syntax error", s))


# ---------------------------------------------------------------- real LLM
def gateway_llm(base_url=None, model=None, key=None, timeout=300.0,
                env_file=os.environ.get("WMTM_LLM_ENV_FILE", "")) -> LLM:
    env = {}
    if env_file and os.path.exists(os.path.expanduser(env_file)):
        env_file = os.path.expanduser(env_file)
        for line in open(env_file, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.rstrip("\n").split("=", 1)
                env[k.strip().replace("export ", "", 1).strip()] = v.strip().strip('"').strip("'")
    base_url = base_url or os.environ.get("BASE_URL") or env.get("BASE_URL")
    model = model or os.environ.get("LLM_MODEL") or env.get("LLM_MODEL")
    key = key or os.environ.get("AI_API_KEY") or env.get("AI_API_KEY")

    def call(system: str, user: str) -> str:
        body = {"model": model, "temperature": 0,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}]}
        req = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        r = json.loads(urllib.request.urlopen(req, timeout=timeout).read())
        return r["choices"][0]["message"]["content"]
    return call
