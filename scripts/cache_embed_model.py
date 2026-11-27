#!/usr/bin/env python3
"""M-09: cache the pinned sentence-embedding model for recall_semantic (run once per machine, online).

recall_semantic loads the model with local_files_only=True, so it never downloads at run time; without this cache
it falls back to keyword-only recall (logged once).  Needs the optional extra, with CPU-only torch:

    pip install torch --index-url https://download.pytorch.org/whl/cpu
    pip install -e .[embed]
    python scripts/cache_embed_model.py            # model and revision from wmtm/embed_index.py

The cache location is the standard Hugging Face cache (HF_HOME / HF_HUB_CACHE).  Exit 0 = cached and loadable
offline; 1 = failed.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from wmtm import embed_index
    name, rev = embed_index.MODEL_NAME, embed_index.MODEL_REVISION
    try:
        from huggingface_hub import snapshot_download
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        print(f"missing optional extra ({e}); install it as described in this script's docstring", file=sys.stderr)
        return 1
    path = snapshot_download(repo_id=name, revision=rev)
    print(f"cached {name}@{rev} at {path}")
    # verify the run-time path: offline load of exactly that revision
    m = SentenceTransformer(name, device="cpu", revision=rev, local_files_only=True)
    dim = m.get_sentence_embedding_dimension()
    print(f"offline load ok, dim={dim}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
