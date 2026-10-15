"""Reference Iter adapter: what transformations/wmtm_context.py becomes.

NOT installed anywhere. Drop-in replacement for the 1035-line glue at
ProtoCosmo2 snapshot 83ea611 once Iter imports the pinned `wmtm` package.
Glue = the last ~40 lines. Everything above them is Iter's own message
parsing, moved verbatim (it is Iter-format specific, so it stays in Iter):
automated/check-in prompt detection, channel/group-context stripping,
attached-document trimming, last-real-user-message selection.
"""
import threading
from pathlib import Path

from wmtm.api import WMTM, WMTMConfig

_STATE_DIR = Path(__file__).resolve().parent.parent / 'memory'   # repos/memory (unchanged)

# ── Iter message parsing (verbatim from the 83ea611 glue) ──────────
# Automated prompt patterns that should not drive WMTM recall
_AUTOMATED_PATTERNS = [
    "NO ADDITIONAL USER INPUT",
    "CONTINUE THE CURRENT USER TASK",
    "HEARTBEAT_OK",
    "HEARTBEAT",
    "RUNTIME ERROR",
    "RUNTIMEERROR",       # Python class name (no space) after step-prefix stripping
    "TIMEOUT AFTER 30S",  # iter timeout injection
    "YOUR PREVIOUS RESPONSE CONTAINED NO TOOL CALL",  # F24: iter non-delivery injection
    "NOT DELIVERED",       # F24: iter delivery failure injection
    "CALL AT LEAST ONE TOOL",  # F24: iter tool-call enforcement
    "WAS NOT DELIVERED",   # F24: alternate delivery failure phrasing
    "IF YOU INTENDED THIS CONTENT AS COMMUNICATION",  # F24: iter send suggestion
    # F30: remaining iter.py injections that were misread as real user input
    # (iter.py lines ~1035-1105). They drove the full path on autonomous
    # ticks, so passive/feedback utility inflated items endlessly.
    "NO NEW USER INPUT",
    "CONTINUE AUTONOMOUS WORK",
    "TASK COMPLETED. DO NOT RE-SEND",
    "OUTPUT TOKEN LIMIT REACHED",
    "TOOL LIMIT REACHED",
    "MEMORY FOLDER TOTAL CHARACTER CAPACITY",
    "[BACKGROUND_BRANCH_",
    # F35: thread-visibility injections (iter.py sibling_view / take_branch_inbox)
    "[OTHER THREADS (VISIBILITY ONLY",
    "[NEW USER MESSAGE(S) ARRIVED WHILE YOU WORKED",
]

def _is_automated_prompt(text):
    """Return True if text is an automated iter-loop prompt, not real user input."""
    upper = text.upper().strip()
    for pat in _AUTOMATED_PATTERNS:
        if pat in upper:
            return True
    # Also detect the bracketed form: [NO ADDITIONAL USER INPUT. CONTINUE...]
    if upper.startswith("[NO ADDITIONAL") or upper.startswith("[CONTINUE"):
        return True
    return False

_GROUP_CTX_CLOSE = "</external_untrusted_telegram_group_context>"
_REPLY_MARKER_RE = __import__("re").compile(r"^\s*\[reply to your message \d+\]\s*")


def _extract_direct_request(content):
    """F30: Return only the text addressed to us, without channel context.

    Channel messages embed the recent group chat in an
    <external_untrusted_telegram_group_context> block before the actual
    request. Recall used the whole thing as the query, so a short question
    ("what is the status?") was drowned out by pages of unrelated
    review text. Keep only what follows the closing tag, and drop the
    "[reply to your message N]" marker. Fall back to the full text when
    nothing follows the block.
    """
    if _GROUP_CTX_CLOSE in content:
        tail = content.rsplit(_GROUP_CTX_CLOSE, 1)[1].strip()
        if tail:
            content = tail
    # F35: attached documents (PDF/zip text, up to ~140k chars) made recall,
    # response feedback and relevance stimulus tokenize and score the whole
    # attachment -> 30 s TIMEOUT (large report attachment). Keep only the
    # document file names and cap the query text.
    content = _DOC_BLOCK_RE.sub(_doc_placeholder, content)
    if len(content) > _DIRECT_REQUEST_MAX_CHARS:
        content = content[:_DIRECT_REQUEST_MAX_CHARS]
    return _REPLY_MARKER_RE.sub("", content).strip()


_DIRECT_REQUEST_MAX_CHARS = 2000
_DOC_BLOCK_RE = __import__("re").compile(
    r"<external_untrusted_document>.*?(?:</external_untrusted_document>|\Z)",
    __import__("re").S)
_DOC_NAME_RE = __import__("re").compile(r'"file_name":\s*"([^"]{1,200})"')


def _doc_placeholder(m):
    names = _DOC_NAME_RE.findall(m.group(0)[:2000])
    return "[attached document: " + (", ".join(names) or "unnamed") + "]"


def _classify_user_content(content):
    """Return "" for automated/injected content, else the direct request text."""
    # ── normalise: strip "Step YYYY-MM-DD HH:MM:SS: " prefix ──
    if content.startswith("Step "):
        parts = content.split(": ", 1)
        if len(parts) == 2:
            content = parts[1]
    # F30b: check injections BEFORE stripping the [channel] tag, otherwise
    # "[BACKGROUND_BRANCH_ABANDONED] ..." is mistaken for a channel tag and
    # its remainder ("branch_id=...") is treated as a real user request.
    if _is_automated_prompt(content):
        return ""
    # ── strip optional [channel] tag (e.g. "[protocosmo2] ") ──
    if content.startswith("[") and "] " in content[:40]:
        bracket_end = content.index("] ")
        content = content[bracket_end + 2:]
    if _is_automated_prompt(content):
        return ""
    for prefix in ("[RUNTIME ERROR", "RuntimeError", "[YOUR PREVIOUS RESPONSE", "[NOT DELIVERED"):
        if content.startswith(prefix):
            return ""
    return _extract_direct_request(content)


def _get_last_user_message(messages):
    """Extract the most recent real user message.

    Returns empty string for automated prompts / runtime errors so the
    fast path (no wmtm imports) is used.

    F22 FIX: Only inspect the SINGLE most-recent non-injection user
    message.  The old code skipped automated messages but then scanned
    backwards through the entire conversation history, eventually finding
    an old real user question.  That triggered the full slow path (wmtm
    import + journal parsing = 10-25 s) on every automated tick, causing
    the 30 s TIMEOUT loop.

    Now: skip our own WMTM context injections, then the FIRST non-
    injection user message we find is the decision point.  If it is
    automated or a runtime-error injection → return "".  If it is real
    → return the content.  We never look any further back.
    """
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")

            # Skip our own WMTM context injections (these are not user input)
            if "[WMTM Active Working Memory" in content:
                continue
            # F35: skip thread-visibility injections; they quote other threads'
            # requests/sends and were misread as real input -> slow path -> 30 s TIMEOUT.
            # The real decision is the message before them.
            head = content[:200]
            if "[OTHER THREADS (visibility only" in head or "[NEW USER MESSAGE(S) ARRIVED WHILE YOU WORKED" in head:
                continue

            # F30: normalisation + decision shared with response feedback
            return _classify_user_content(content)
    return ""


def _response_answered_real_message(messages, assistant_idx):
    """F30: True if the assistant message at assistant_idx replied to a real
    user message (not an automated tick). Walks back to the nearest user
    message, skipping our own WMTM context injections."""
    for msg in reversed(messages[:assistant_idx]):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "") or ""
        if "[WMTM Active Working Memory" in content:
            continue
        return bool(_classify_user_content(content))
    return False


def _last_reply_to_real_message(messages):
    """The last assistant message, if it answered a real user message (F30)."""
    for idx in range(len(messages) - 1, -1, -1):
        if messages[idx].get("role") == "assistant":
            resp = messages[idx].get("content", "") or ""
            if resp and len(resp) >= 20 and _response_answered_real_message(messages, idx):
                return resp
            return None
    return None


# ── glue ───────────────────────────────────────────────────────────
_MEM = None
_MEM_LOCK = threading.Lock()


def _mem():
    global _MEM
    if _MEM is None:
        with _MEM_LOCK:
            if _MEM is None:
                _MEM = WMTM(WMTMConfig(state_dir=_STATE_DIR))
    return _MEM


def transform(messages, tools):
    """Inject the WMTM context block as a user message before the LLM call."""
    try:
        mem = _mem()
        user_msg = _get_last_user_message(messages)   # "" = automated tick -> fast path
        if user_msg:
            mem.observe({"user": user_msg, "assistant": _last_reply_to_real_message(messages)})
        context = mem.context_for(user_msg)
        if context:
            messages.append({"role": "user", "content": context})
    except Exception as e:
        import sys
        print(f"[wmtm_context] WARNING: {type(e).__name__}: {e}", file=sys.stderr)
    return messages, tools
