"""README "Runtime flags reference" table must list exactly the keys of runtime_config.SPEC.

Both sides are read at test time (no hardcoded flag names).

README parsing is anchored as follows. The whole README is first classified line by line, and
lines inside fenced code blocks (``` or ~~~, closed by the same character with at least as many
marks, CommonMark style), inside HTML comments (<!-- ... -->) and indented code (4+ leading
spaces) are "hidden" and never used as an anchor. Then:
  1. exactly one visible line must be "## Runtime flags reference" (zero or several fail);
  2. the section ends at the next visible "## " or "# " heading;
  3. inside the section exactly one visible line must start with "| key | env var |",
     followed by a "|---" separator row;
  4. rows are read until the first line that does not start with "|"; each row's key is the
     backticked first cell, and a row without one fails.
Other tables, bullet lists (e.g. the live-file audit) and code examples are therefore never read.
"""
import re
from pathlib import Path

from wmtm import runtime_config as rc

README = Path(__file__).resolve().parent.parent / "README.md"
HEADING = "## Runtime flags reference"
HEADER_PREFIX = "| key | env var |"
ROW_KEY = re.compile(r"^\|\s*`([^`]+)`\s*\|")
FENCE_OPEN = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def visible_lines(lines):
    """Return a list of booleans: True if the line is ordinary Markdown, False if it is inside
    a fenced code block (including the fence lines), an HTML comment, or indented code."""
    vis, fence, comment = [], None, False
    for line in lines:
        if fence is not None:
            vis.append(False)
            m = FENCE_OPEN.match(line)
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                    and not line.strip().lstrip(fence[0]):
                fence = None
            continue
        if comment:
            vis.append(False)
            if "-->" in line:
                comment = False
            continue
        m = FENCE_OPEN.match(line)
        if m:
            fence = m.group(1)
            vis.append(False)
            continue
        if line.lstrip().startswith("<!--"):
            vis.append(False)
            comment = "-->" not in line.split("<!--", 1)[1]
            continue
        vis.append(not line.startswith("    ") and not line.startswith("\t"))
    assert fence is None, "README has an unclosed code fence"
    assert not comment, "README has an unclosed HTML comment"
    return vis


def readme_flag_keys(text):
    lines = text.splitlines()
    vis = visible_lines(lines)
    starts = [i for i, l in enumerate(lines) if vis[i] and l.rstrip() == HEADING]
    assert starts, f"README has no {HEADING!r} heading outside code blocks/comments"
    assert len(starts) == 1, (f"README has {len(starts)} {HEADING!r} headings outside code "
                              f"blocks/comments (lines {[s + 1 for s in starts]}); expected exactly one")
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines))
                if vis[i] and (lines[i].startswith("## ") or lines[i].startswith("# "))), len(lines))
    headers = [i for i in range(start + 1, end) if vis[i] and lines[i].startswith(HEADER_PREFIX)]
    assert headers, f"no table starting {HEADER_PREFIX!r} (outside code blocks) under {HEADING!r}"
    assert len(headers) == 1, (f"{len(headers)} tables starting {HEADER_PREFIX!r} outside code blocks "
                               f"under {HEADING!r}; expected exactly one")
    h = headers[0]
    assert h + 1 < end and lines[h + 1].startswith("|---"), \
        "flags table header is not followed by a separator row"
    keys = []
    for line in lines[h + 2:end]:
        if not line.startswith("|"):
            break
        m = ROW_KEY.match(line)
        assert m, f"flags table row without a `key` first cell: {line[:80]!r}"
        keys.append(m.group(1))
    return keys


def test_readme_flags_table_matches_spec():
    keys = readme_flag_keys(README.read_text(encoding="utf-8"))
    dups = sorted({k for k in keys if keys.count(k) > 1})
    spec = set(rc.SPEC)
    doc = set(keys)
    missing = sorted(spec - doc)
    extra = sorted(doc - spec)
    msg = []
    if missing:
        msg.append(f"in runtime_config.SPEC but not in the README flags table: {missing}")
    if extra:
        msg.append(f"in the README flags table but not in runtime_config.SPEC: {extra}")
    if dups:
        msg.append(f"listed more than once in the README flags table: {dups}")
    assert not msg, "; ".join(msg)
