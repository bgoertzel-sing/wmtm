#!/usr/bin/env python3
"""Build sel.jsonl (the sentence rows) from notes.json with the production split (wmtm.semparse_sentence.prepare).
Usage: make_sel.py NOTES_JSON REPO OUT"""
import json, sys
sys.path.insert(0, sys.argv[2])
from wmtm import semparse_sentence as SS
cases = json.load(open(sys.argv[1]))["cases"]
with open(sys.argv[3], "w") as out:
    for c in cases:
        rows, info = SS.prepare(c["doc"], c["text"], cfg={})
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(c["case"], info["sentences"], "sentences")
