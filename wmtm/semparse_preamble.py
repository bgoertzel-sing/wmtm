"""Track M: instruction block placed BEFORE the pinned semantic-parsing prompt.

The hitl prompt file is pinned by sha256 (runtime_config.SEMPARSE_PROMPT_SHA256) and is not edited; this block is
prepended in code (SemParseAdapter) when ``semparse_preamble`` is on (default).  The worker still checks the pin
against the unmodified file.  Motivation: Track K replay, where commit hashes were typed as branches
("0a1b2c3 is a topic_branch", "id_4d5e6f7 is a release_branch").  parse_gate's identifier_category rule is the hard
backstop; this block lowers how often the parser produces such facts in the first place.
"""
PREAMBLE = """\
PRE-INSTRUCTIONS (read before the main instructions below; they take precedence on these points):
1. Identifiers are names, not categories. Commit hashes (e.g. 0a1b2c3, 7c8d9e0), hex ids, process ids, uuids and
   similar opaque tokens must never appear as the CATEGORY (second argument) of Member or Inheritance.
2. Do not type an identifier as the thing it points to. "commit 4d5e6f7 on branch release" is NOT
   (Member 4d5e6f7 branch); if you need it, state (Member 4d5e6f7 commit) and relate it to the branch with a
   separate predicate (e.g. (OnBranch 4d5e6f7 release)).
3. Prefer meaningful categories (a kind of thing a reader would recognise) over bookkeeping labels; when no such
   category is stated in the text, emit no Member/Inheritance fact for that entity.

"""


def apply(system: str, on: bool = True) -> str:
    return (PREAMBLE + system) if on else system
