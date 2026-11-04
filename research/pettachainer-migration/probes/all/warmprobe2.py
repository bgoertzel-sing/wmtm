import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    a=orig(space, src, budget=budget)
    if "warm-up" in src:
        for q in ["!(chainer-reset!)",
                  "!(collapse (compileadd kbx (: f1 (A a) (STV 1.0 0.9))))",
                  "!(collapse (query 20 kbx (: $p (A a) $tv)))",
                  "!(collapse (query 20 kbx (: $p (A $y) $tv)))",
                  "!(collapse (compileadd kbx (: r1 (Implication (P $x) (B $x)) (STV 0.9 0.9))))",
                  "!(collapse (compileadd kbx (: f2 (P a) (STV 1.0 0.9))))",
                  "!(collapse (query 40 kbx (: $p (B a) $tv)))"]:
            try: print("Q", q[:90], [[str(x) for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q[:60], type(e).__name__, str(e)[:400], flush=True)
    return a
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b)
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
