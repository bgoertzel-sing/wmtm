"""Minimal CLI over wmtm.api (stub for non-Python agents).

  python -m wmtm context --state-dir DIR [--journal-dir DIR] [--automated] < turn.json
      turn.json: {"user": "...", "assistant": "..."}  -> prints the context block
  python -m wmtm derive --state-dir DIR NOTE [SOURCE_ID ...]
"""
import argparse, json, sys

from .api import WMTM, WMTMConfig
from .journal import PettaJournal


def main(argv=None):
    ap = argparse.ArgumentParser(prog="wmtm")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("context")
    c.add_argument("--state-dir", required=True)
    c.add_argument("--journal-dir")
    c.add_argument("--automated", action="store_true")
    d = sub.add_parser("derive")
    d.add_argument("--state-dir", required=True)
    d.add_argument("note")
    d.add_argument("source_ids", nargs="*")
    a = ap.parse_args(argv)
    if a.cmd == "derive":
        print(WMTM(WMTMConfig(state_dir=a.state_dir)).derive(a.note, a.source_ids))
        return 0
    journal = PettaJournal(a.journal_dir) if a.journal_dir else None
    mem = WMTM(WMTMConfig(state_dir=a.state_dir, journal=journal))
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    turn = json.loads(raw) if raw.strip() else {}
    user = "" if a.automated else (turn.get("user") or "")
    if user:
        mem.observe({"user": user, "assistant": turn.get("assistant")})
    ctx = mem.context_for(user)
    if ctx:
        print(ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
