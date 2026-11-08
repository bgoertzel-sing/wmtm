#!/usr/bin/env python3
"""F2 negative controls: undo one fix at a time in a scratch copy of the committed tree and run its tests there.

    python3 reports/t-2026-11-06-wmtm-f2-context/controls.py <fix commit> <base commit> <out dir>

Every control must FAIL (pytest exit 1) for the reason named in the test docstrings; the same tests pass on the fix
commit (run with the same environment: WMTM_TEST_GC2_PYTHON for the real-v2 tie test).  Writes <out>/<name>.log and
<out>/summary.json.  The repository itself is never modified."""
import json, os, re, subprocess, sys, tempfile

FIX, BASE, OUT = sys.argv[1], sys.argv[2], os.path.abspath(sys.argv[3])
REPO = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
T = "tests/test_f2_context_goals.py"


def show(rev, path):
    return subprocess.check_output(["git", "-C", REPO, "show", "%s:%s" % (rev, path)], text=True)


def func(src, name):
    """Source of a top-level def (up to the next top-level statement)."""
    m = re.search(r"^def %s\(.*?(?=^\S)" % re.escape(name), src, re.S | re.M)
    assert m, name
    return m.group(0)


def swap_funcs(fixed, base, names):
    out = fixed
    for n in names:
        out = out.replace(func(fixed, n), func(base, n))
    return out


def ctl_s5_recall(fx, bs):
    p = "wmtm/context.py"
    return {p: fx[p].replace(func(fx[p], "is_duplicate_topic"), func(bs[p], "is_duplicate_topic"))}


def ctl_s5_goals(fx, bs):
    p = "wmtm/goals/needs.py"
    s = fx[p].replace('                        and not (g["who"] and c["who"] and g["who"] != c["who"])\n', "")
    assert s != fx[p]
    return {p: s}


def ctl_s7(fx, bs):
    """Base context.py (attention-only lines, STI-scored floor, top-15/top-N by attention) with only the section-5
    fix kept."""
    p = "wmtm/context.py"
    s = bs[p].replace(func(bs[p], "is_duplicate_topic"),
                      func(fx[p], "proposition_key") + "\n\n" + func(fx[p], "_canon_atoms") + "\n\n"
                      + func(fx[p], "same_proposition") + "\n\n" + func(fx[p], "is_duplicate_topic"))
    return {p: s}


def ctl_s10_feed(fx, bs):
    return {"wmtm/api.py": bs["wmtm/api.py"], "wmtm/goalchainer_bridge.py": bs["wmtm/goalchainer_bridge.py"]}


def ctl_s10_ties(fx, bs):
    return {"wmtm/goals/v2.py": bs["wmtm/goals/v2.py"]}


def ctl_stem(fx, bs):
    p = "wmtm/goals/needs.py"
    return {p: fx[p].replace(func(fx[p], "stem"), func(bs[p], "stem"))}


CONTROLS = [
    ("s5_recall_word_overlap_restored", ctl_s5_recall, "test_s5_five or test_s5_two_cpu"),
    ("s5_goal_merge_across_people_restored", ctl_s5_goals, "test_s5_goal_engine"),
    ("s7_attention_only_lines_restored", ctl_s7, "test_s7_belief"),
    ("s10_v1_feed_restored", ctl_s10_feed, "test_s10_decide or test_s10_orchestrator"),
    ("s10_tie_step_restored", ctl_s10_ties, "test_s10_tied or test_s10_real"),
    ("stemmer_old_restored", ctl_stem, "test_stemmer"),
]
FILES = ["wmtm/context.py", "wmtm/goals/needs.py", "wmtm/api.py", "wmtm/goalchainer_bridge.py", "wmtm/goals/v2.py"]


def main():
    os.makedirs(OUT, exist_ok=True)
    fx = {p: show(FIX, p) for p in FILES}
    bs = {p: show(BASE, p) for p in FILES}
    summary = {"fix": FIX, "base": BASE, "controls": []}
    for name, mk, sel in CONTROLS:
        with tempfile.TemporaryDirectory(prefix="f2ctl-") as d:
            subprocess.run("git -C %s archive %s | tar -x -C %s" % (REPO, FIX, d), shell=True, check=True)
            changed = mk(fx, bs)
            for p, s in changed.items():
                assert s != fx[p], (name, p)
                open(os.path.join(d, p), "w").write(s)
            r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", "-p", "no:cacheprovider", T, "-k", sel],
                               cwd=d, capture_output=True, text=True)
            log = r.stdout + r.stderr
            open(os.path.join(OUT, name + ".log"), "w").write(log.replace(d, "<scratch>"))
            tail = [l for l in log.splitlines() if re.search(r"\d+ (passed|failed|skipped)", l)]
            summary["controls"].append({"name": name, "undone": sorted(changed), "tests": sel, "exit": r.returncode,
                                        "result": tail[-1] if tail else "", "control_fails": r.returncode == 1})
            print(name, r.returncode, tail[-1] if tail else "")
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    return 0 if all(c["control_fails"] for c in summary["controls"]) else 1


if __name__ == "__main__":
    sys.exit(main())
