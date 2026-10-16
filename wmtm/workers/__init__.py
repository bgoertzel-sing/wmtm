"""Background worker entry points (run as ``python -m wmtm.workers.<name>``; launched detached by the cycle hooks).

  pc_shadow      PeTTaChainer shadow run over one top-K snapshot (Track G)
  semparse_feed  drain the semantic-parse queue under the hourly cap (Track H)

They are started from the package's distribution directory with PYTHONPATH pointing at it, so they work the same
from a repo checkout and from a vendored copy (``<bot>/vendor/wmtm-<tag>/``).  Paths and limits come from the
resolved runtime config (wmtm/runtime_config.py) written next to the run as worker_config.json.
"""
