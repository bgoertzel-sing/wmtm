"""Generate the SYNTHETIC replay fixtures (journal.metta, wmtm_state.json).

Everything here is invented: topics, people, notes, ids and dates. The
journal mimics the structure of a real PeTTa medium-memory journal
(Episode clusters, writeback enrichment notes nested in an EventNote,
Supersedes links, promotion/fact ids, autonomous-loop heartbeats). The state
is produced by running the adapter + wmtm.api over a synthetic warm-up of
turns and derives, so it has recalled and derived items, utility records and
a forgetting log with the same schema as a live state file.

usage (from the repo root): python3 tests/fixtures/synthetic/make_fixtures.py
"""
import calendar, json, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))          # tests/
from replay import driver, scenarios                # noqa: E402

TOPICS = {
    "irrigation": [
        "Greenhouse irrigation controller is a garden device that opens valve 3 every morning",
        "Valve timing implies water savings when the soil probe reads above 40 percent",
        "The noisy irrigation item came from a duplicated sensor reading on bed B",
        "Irrigation controller firmware v2.3 has a watchdog that resets the pump relay",
        "Drip line pressure dropped after the filter swap; pressure is back to 1.4 bar",
    ],
    "telescope": [
        "Telescope mount calibration needs three alignment stars before tracking",
        "The telescope mount is a German equatorial mount with a worm gear",
        "Polar alignment error was 12 arcminutes; drift method reduced it to 3",
        "Telescope mount calibration request: redo the periodic error table next clear night",
    ],
    "sourdough": [
        "Sourdough hydration comparison: 75 percent loaves had a more open crumb than 68 percent",
        "Sourdough starter is fed twice a day with rye flour",
        "Higher hydration implies longer bulk fermentation at the same temperature",
    ],
    "compost": [
        "Compost pile temperature peaked at 63 C on the fourth day",
        "Compost temperature review: turning every five days keeps the core above 50 C",
        "Compost pile has too much carbon when the temperature stays below 40 C",
    ],
    "kayak": [
        "Kayak hull patch uses two layers of fiberglass cloth and marine epoxy",
        "The kayak hull is a rotomolded polyethylene shell",
    ],
    "chess": [
        "Chess opening study: the Caro-Kann is a solid defence against 1.e4",
        "Chess endgame drill: king and pawn versus king opposition practice",
    ],
    "library": [
        "Library catalog migration moved 4200 records to the new schema",
        "Library catalog has duplicate ISBN entries for reprinted editions",
    ],
    "solar": [
        "Solar inverter firmware update fixed the evening shutdown bug",
        "Solar panel output implies about 18 kWh on a clear day",
    ],
    "birds": [
        "Birdwatching log: a pair of kestrels nested on the old water tower",
        "The bird feeder is visited mostly by finches in the morning",
    ],
}

AUTOCYCLE = "AUTOCYCLE heartbeat: no new input, Nop"


def ts(y, mo, d, h, mi, s):
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


def cid(t):
    import time
    return "ep-note-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(t))


def iso(t):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def cluster(c, note, t, about="journal", ctype="Episode", extra=()):
    lines = [
        f";;; BEGIN MemoryCluster {c}",
        f"(MemoryCluster {c})",
        f"(SchemaVersion {c} medium-memory-v1)",
        f"(ClusterType {c} {ctype})",
        f"(ClusterSource {c} iter-experience)",
    ]
    if t is not None:
        lines.append(f"(ClusterOpenedAt {c} {iso(t)})")
    lines += [
        f"(Contains {c} ev-{c})",
        f"(ObservedEvent ev-{c})",
        f"(About {c} {about})",
        f'(EventNote ev-{c} "{note}")',
        *extra,
        f";;; END MemoryCluster {c}",
    ]
    return "\n".join(lines) + "\n"


def enrichment(target, text, util, age):
    e = f"wmtm-enrich-{target}"
    inner = "\n".join([
        f"(MemoryCluster {e})",
        f"(SchemaVersion {e} medium-memory-v1)",
        f"(ClusterType {e} EnrichmentNote)",
        f"(ClusterSource {e} wmtm-writeback)",
        f"(Contains {e} ev-{e})",
        f"(ObservedEvent ev-{e})",
        f"(About {e} {e})",
        f'(EventNote ev-{e} \\"{text}\\")',
        f"(WMTMUtility {e} {util:.2f})",
        f"(WMTMAge {e} {age})",
    ])
    return inner


def make_journal():
    out = []
    t = ts(2026, 10, 12, 0, 0, 0)
    ids = []
    k = 0
    order = []
    for topic, notes in TOPICS.items():
        for n in notes:
            order.append((topic, n))
    # interleave topics deterministically
    order.sort(key=lambda x: (TOPICS[x[0]].index(x[1]), list(TOPICS).index(x[0])))
    for topic, note in order:
        t += 3600 * (1 + (k * 5) % 3)
        c = cid(t)
        about = topic if k % 3 else "journal"
        out.append(cluster(c, note, t, about=about))
        ids.append((c, topic, note))
        k += 1
        if k % 6 == 0:
            t += 900
            out.append(cluster(cid(t), AUTOCYCLE, t))
    # fixed id used by the replay scenario's derive step
    out.append(cluster("ep-note-20261012T101500Z",
                       "Valve timing fix for the irrigation controller was staged but not applied",
                       ts(2026, 10, 12, 10, 15, 0), about="irrigation"))
    # supersedes: a newer telescope note replaces an older one
    old = next(c for c, tp, n in ids if tp == "telescope")
    t += 3600
    out.append(cluster(cid(t), "Telescope mount calibration: periodic error table redone, tracking error under 2 arcseconds",
                       t, about="telescope", extra=(f"(Supersedes {cid(t)} {old})",)))
    # writeback enrichment notes (nested cluster inside the EventNote)
    tgt = ids[0][0]
    for i in range(3):
        t += 1800
        out.append(cluster(cid(t), enrichment(tgt, ids[0][2] + " (durable)", 40.0 + 2 * i, 10 + i), t))
    # other id formats seen in journals: promotion, fact, epoch-micros episode
    out.append(cluster("promo-sourdough-hydration", "Promoted: 75 percent hydration is the default for sourdough loaves",
                       None, about="sourdough", ctype="Promotion"))
    out.append(cluster("fact-solar-2026-10-01", "Solar inverter evening shutdown bug is fixed in firmware 1.8",
                       None, about="solar", ctype="Fact"))
    out.append(cluster("ep-20261003081500123456", "Birdwatching log: kestrel pair seen hunting over the meadow",
                       None, about="birds"))
    return "".join(out)


WARMUP_USER = [
    "how is the greenhouse irrigation controller doing?",
    "what did we learn about valve timing and water savings?",
    "remind me about the telescope mount calibration",
    "is the compost pile hot enough this week?",
    "what was the sourdough hydration result?",
    "any news on the solar inverter firmware?",
    "summarise the kayak hull patch plan",
    "what is in the library catalog migration notes?",
]
WARMUP_DERIVES = [
    ("Irrigation controller firmware v2.3 watchdog implies fewer stuck pump relays", None),
    ("Higher sourdough hydration implies longer bulk fermentation", None),
]


def make_state(journal_text):
    S = scenarios
    t = S.BASE - 40 * 3600
    steps = []
    prev = None
    for i, q in enumerate(WARMUP_USER):
        t += 4 * 3600
        msgs = [S.SYS]
        if prev:  # previous reply answered a real user message -> response feedback
            msgs += [S.U(t - 600, "[demo] " + prev), S.A("Here is what I found about " + prev)]
        msgs.append(S.U(t, "[demo] " + q))
        steps.append({"kind": "turn", "t": t, "messages": msgs})
        if i < len(WARMUP_DERIVES):
            note, src = WARMUP_DERIVES[i]
            steps.append({"kind": "derive", "t": t + 5, "note": note, "source_ids": src})
        if i % 3 == 2:
            steps.append({"kind": "turn", "t": t + 60, "messages": [S.SYS, S.U(t + 60, S.AUTO_NEW)]})
        prev = q
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "warmup"
        driver.build_new_tree(root)
        base = driver.seed_memory(root, None, journal_text)
        res = driver.run(root, steps, "fresh", str(driver.REPO), base)
        state = res[-1]["files"]["memory/_wmtm_state.json"]
        journal = (root / "memory" / "_journal" / "journal.metta").read_text(encoding="utf-8")
    return state, journal


def main():
    journal = make_journal()
    state, journal = make_state(journal)
    (HERE / "journal.metta").write_text(journal, encoding="utf-8")
    (HERE / "wmtm_state.json").write_text(state, encoding="utf-8")
    s = json.loads(state)
    kinds = {}
    for it in s["store"]["items"].values():
        kinds[it["source_type"]] = kinds.get(it["source_type"], 0) + 1
    print("journal bytes", len(journal), "state items", kinds, "cycle", s["cycle"])


if __name__ == "__main__":
    main()
