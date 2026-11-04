import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget, run_bounded
orig=ev.run_bounded
def rb(space, src, budget):
    a=orig(space, src, budget=budget)
    if "warm-up" in src:
        print("WARM", src, [[str(x) for x in r] for r in a[0]], flush=True)
        for q in ["!(chainer-reset!)",
                  "!(gc-pettachainer-grade ((: r1 (Implication (P $x) (A $x)) (STV 0.9 0.9)) (: f1 (P a) (STV 1.0 0.9))) ((A a)) 20 True)",
                  "!(gc-pettachainer-grade ((: f1 (A a) (STV 1.0 0.9))) ((A a)) 20 True)",
                  "!(gc-pettachainer-grade ((: f1 (A a) (STV 1.0 0.9))) ((A a)) 20 False)"]:
            try: print("Q", q[:90], [[str(x) for x in r] for r in orig(space,q,budget=budget)[0]], flush=True)
            except Exception as e: print("QERR", q[:60], e, flush=True)
    return a
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b)
except Exception as e: print("PREP", type(e).__name__, str(e)[:300])
