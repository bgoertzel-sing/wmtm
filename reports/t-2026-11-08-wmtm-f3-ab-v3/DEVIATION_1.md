# DEVIATION_1 (t-2026-11-08-wmtm-f3-ab-v3): W1 rule extended after results
PREREG t-2026-11-07-wmtm-f3-ab says W1-W4 exactly as P4. P4 W1: a conclusion about a note-scoped witness (sk_*) whose premises come from more than one source note (premise notes plus parser-rule note ids).
Change in v3 recompute.py: notes are also joined through shared nwdef_<cls>__nw_<hash> narrow-class symbols (extract.json nw_symbol_notes).
Why: native proofs reach the other note's facts through a shared deterministic nw symbol instead of naming its premises, so the P4 rule would miss the cross-note "config effective" pair (nwdef_config__nw_b1a247bbd8 joins 20261028T185132Z and 20261028T185959Z).
Direction: conservative, it can only turn verdicts into WRONG.
Effect: with the extension B is 8C/2W/1U; with the P4 rule as written B is 10C/0W/1U. A is 2C/2W either way. Gate 1 holds in both cases, in every run.
The policy question (is a deterministic nw-symbol cross-note join a W1?) is still open for a human, as it was in Nov7.
