"""Synthetic Iter message lists for the replay-equivalence test.

All people, topics, message ids and notes are invented. Formats follow
iter.py at 83ea611: "Step <ts>: " prefixes, the three
autonomous/check-in prompts, tool-limit / runtime-error / thread-visibility
injections, Telegram group-context blocks, attached-document blocks, and
the WMTM block a previous transform appended.
"""
import calendar

BASE = calendar.timegm((2026, 10, 15, 19, 0, 0))  # arbitrary fixed clock


def _step(t):
    import datetime
    return "Step " + datetime.datetime.utcfromtimestamp(t - 7 * 3600).strftime("%Y-%m-%d %H:%M:%S") + ": "


def U(t, text):
    return {"role": "user", "content": _step(t) + text}


def A(text):
    return {"role": "assistant", "content": text}


SYS = {"role": "system", "content": "prompt.txt:\nYou are DemoBot..."}
OLD_WMTM = {"role": "user", "content": "[WMTM Active Working Memory (3 items, showing top 3, cycle 9)]\n  [recalled sti=1.0 util=0.0 age=2.0d] old block"}

AUTO_CONTINUE = "[NO ADDITIONAL USER INPUT. CONTINUE THE CURRENT USER TASK.]"
AUTO_NEW = "[NO NEW USER INPUT. CONTINUE AUTONOMOUS WORK. DO NOT REPEAT THE PREVIOUS RESPONSE. ONLY USE send FOR GENUINELY NEW INFORMATION OR WHEN USER INPUT IS NEEDED.]"
AUTO_DONE = "[TASK COMPLETED. DO NOT RE-SEND THE COMPLETED RESPONSE BUT SEND IN CASE YOU FORGOT. NOW QUERY FOR AND PICK A TASK BASED ON YOUR GOALS, PREFERABLY MEMORY CONSOLIDATION: FINDING EPISODES WHICH SUPPORT / CONTRADICT LTM ITEMS, LINKING EPISODES, PROMOTING USEFUL MEMORIES]"

GROUP = ("[demo] <external_untrusted_telegram_group_context>\n"
         "[Mira 11:58] the compost temperature review is long, see thread above\n"
         "[Tomas 11:59] ok, also check the kayak hull patch later\n"
         "</external_untrusted_telegram_group_context>\n"
         "[reply to your message 4242] what did you find about the noisy irrigation item and the valve timing fix?")

DOC = ("[demo] please summarise the attached irrigation report and tell me if the firmware pin is right\n"
       "<external_untrusted_document>{\"file_name\": \"irrigation_report.pdf\", \"text\": \"" + ("lorem ipsum firmware v2.3 " * 400) + "\"}</external_untrusted_document>")


def live_scenario(base=BASE):
    """~16 consecutive steps over 3 simulated days (time in epoch seconds).

    base: frozen clock at step 1; must not precede the timestamps in the
    seeded state (see clock_after)."""
    t = base
    steps = []

    def turn(dt, msgs):
        nonlocal t
        t += dt
        steps.append({"kind": "turn", "t": t, "messages": msgs})

    def derive(dt, note, src=None):
        nonlocal t
        t += dt
        steps.append({"kind": "derive", "t": t, "note": note, "source_ids": src})

    hist = [SYS, U(t - 3600, "[demo] How is the greenhouse irrigation work going?"), A("Working on it."), OLD_WMTM]
    # 1. autonomous check-in (old real question further back must NOT be used: F22)
    turn(0, hist + [U(t, AUTO_NEW)])
    # 2. direct message about irrigation / firmware
    turn(60, [SYS, U(t + 60, "[demo] How is the irrigation controller going? Did the valve timing fix for the noisy irrigation item land, and is the firmware v2.3 pin verified?")])
    # 3. tool registers a derived belief
    derive(5, "The valve timing fix was staged on day three but not applied; the trial used a scratch bed only.", ["ep-note-20261012T101500Z"])
    # 4. follow-up 90 s later (journal cache still fresh), previous reply references items
    turn(90, [SYS, U(t, "[demo] How is the irrigation controller going?"),
              A("The valve timing fix for the noisy irrigation item was STAGED on day three but not applied; the firmware v2.3 pin passed the bench check and the sensor loop."),
              U(t + 90, "[demo] ok. And what about the telescope mount calibration request from last week?")])
    # 5. continue-current-task tick
    turn(30, [SYS, U(t, "[demo] x"), A("Looking into it now, one moment please."), U(t + 30, AUTO_CONTINUE)])
    # 6. group chat with context block + reply marker
    turn(600, [SYS, U(t + 600, GROUP)])
    # 7. thread-visibility injection after a real message (skip to message before it)
    turn(120, [SYS, U(t + 120, "[demo] remind me what the sourdough hydration comparison concluded"),
               {"role": "user", "content": "[OTHER THREADS (visibility only, do not act on them)]\n- branch b2 asked: what is the capital of France?"}])
    # 8. runtime-error injection
    turn(60, [SYS, U(t + 60, "[RUNTIME ERROR in transformations/foo.py: ValueError: boom. Repair transformations/foo.py if needed.]")])
    # 9. attached document
    turn(300, [SYS, U(t + 300, DOC)])
    # 10. tool limit + memory capacity injections
    turn(900, [SYS, {"role": "user", "content": "[TOOL LIMIT REACHED: 3 tools are currently omitted. Consolidate or remove tools if they are needed.]"}])
    # 11. task-completed autonomous prompt
    turn(900, [SYS, U(t + 900, AUTO_DONE)])
    # 12. background-branch notice (F30b: not a channel tag)
    turn(60, [SYS, U(t + 60, "[BACKGROUND_BRANCH_ABANDONED] branch_id=b7 reason=timeout")])
    # 13. two days later: autonomous tick (fast-path stale cleanup)
    turn(2 * 86400, [SYS, U(t + 2 * 86400, AUTO_NEW)])
    # 14. real message after the gap (full-path cleanup, journal refresh)
    derive(10, "Telescope mount calibration moves to the observatory checklist at step 4.")
    turn(20, [SYS, U(t + 20, "[demo] Mira here. Summarise the telescope mount calibration status and the irrigation controller spec.")])
    # 15. reply on an automated tick must not feed back (F30), then real question
    turn(400, [SYS, U(t, AUTO_NEW), A("Telescope mount calibration status: final already sent; irrigation controller spec drafted."),
               U(t + 400, "[demo] thanks. Any open irrigation risks?")])
    # 16. one more day: check-in
    turn(86400, [SYS, U(t + 86400, AUTO_CONTINUE)])
    return steps


CANARY_NOTE = "CANARY-7Q: the wmtm replay canary codeword is zebra-quartz-41 and it lives in the kestrel archive"
CANARY_CLUSTER = (
    ";;; BEGIN MemoryCluster ep-note-20261015T180000Z\n"
    "(MemoryCluster ep-note-20261015T180000Z)\n"
    "(SchemaVersion ep-note-20261015T180000Z medium-memory-v1)\n"
    "(ClusterType ep-note-20261015T180000Z Episode)\n"
    "(ClusterSource ep-note-20261015T180000Z iter-experience)\n"
    "(ClusterOpenedAt ep-note-20261015T180000Z 2026-10-15T18:00:00Z)\n"
    "(Contains ep-note-20261015T180000Z ev-ep-note-20261015T180000Z)\n"
    "(ObservedEvent ev-ep-note-20261015T180000Z)\n"
    "(About ep-note-20261015T180000Z journal)\n"
    f'(EventNote ev-ep-note-20261015T180000Z "{CANARY_NOTE}")\n'
    ";;; END MemoryCluster ep-note-20261015T180000Z\n"
)
DECOY_CLUSTER = CANARY_CLUSTER.replace("20261015T180000Z", "20261015T170000Z").replace(
    CANARY_NOTE, "Gardening log: the tomato seedlings were moved to the greenhouse on Tuesday")
DERIVE_CANARY = "CANARY-DERIVED: kestrel archive codeword confirmed by derive tool"


def canary_steps():
    t = BASE
    return [
        {"kind": "turn", "t": t, "messages": [SYS, U(t, "[demo] what is the canary codeword in the kestrel archive?")]},
        {"kind": "derive", "t": t + 5, "note": DERIVE_CANARY, "source_ids": ["ep-note-20261015T180000Z"]},
        {"kind": "turn", "t": t + 60, "messages": [SYS, U(t + 60, AUTO_NEW)]},
        {"kind": "turn", "t": t + 120, "messages": [SYS, U(t + 120, "[demo] and the kestrel codeword again?")]},
    ]


def clock_after(state_text):
    """A scenario base clock no earlier than BASE and at least one hour after
    every timestamp in the state (real data may be newer than BASE)."""
    import json, math
    if not state_text:
        return BASE
    ts = [BASE - 3600]
    for i in json.loads(state_text)["store"]["items"].values():
        ts += [i.get("created_at") or 0, i.get("origin_timestamp") or 0]
    return max(BASE, int(math.ceil(max(ts) / 3600.0)) * 3600 + 3600)


def writeback_state(state_text):
    """Variant of a state that makes the orchestrator write back to the
    journal on the next full cycle (one recalled + one derived candidate)."""
    import json
    s = json.loads(state_text)
    items = s["store"]["items"]
    rec = max((i for i in items.values() if i["source_type"] == "recalled"), key=lambda i: i["utility"])
    rec["age"] = 40
    der = next((i for i in items.values() if i["source_type"] == "derived"), None)
    if der is not None:
        der["age"], der["utility"] = 20, 5.0
    return json.dumps(s)
