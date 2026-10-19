"""rc4: speaker linking must not re-parse base-cached content unless a human speaker resolves."""
from wmtm import parse_cache as pc


class _Base:
    def __init__(self, contents):
        self._e = {pc.content_hash(c): {"status": "ok", "atoms": []} for c in contents}

    def entries(self):
        return self._e


CFG = {"speaker_link": True, "speaker_map": {"111": "alice", "alicex": "alice"}, "speaker_self": "agentx"}


def test_cached_without_speaker_is_skipped():
    c = "I checked the build and it passed."
    rows = [("n1", c, 1.0)]
    assert pc._spk_rows_worth_parsing(rows, CFG, _Base([c])) == []


def test_cached_with_resolved_speaker_is_kept():
    c = "the user asked for a cheaper hub."
    rows = [("n1", c, 1.0, {"user_id": 111})]
    assert pc._spk_rows_worth_parsing(rows, CFG, _Base([c])) == rows


def test_uncached_is_always_kept():
    rows = [("n2", "a brand new note", 1.0)]
    assert pc._spk_rows_worth_parsing(rows, CFG, _Base([])) == rows
