import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    if "warm-up" in src:
        orig(space,"(= (one-fn) 1)\n(= (two-fn) 2)",budget=budget)
        for q in ["!(chainer-reset!)", "!(gc-pettachainer-grade ((: gc_warm_rule (Implication (GcWarmPremise $x) (Acceptable $x)) (STV 0.9 0.9)) (: gc_warm_fact (GcWarmPremise gc_warm_action) (STV 1.0 0.9))) ((Acceptable gc_warm_action)) 20 True)", "!(gc-pettachainer-grade ((: gc_warm_direct (Acceptable gc_warm_action) (STV 0.6 0.8))) ((Acceptable gc_warm_action)) 20 True)", "!(gc-pettachainer-warm-up)"]:
            try: print("Q", q, [[str(x)[:200] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q, type(e).__name__, str(e)[:300], flush=True)
    return orig(space, src, budget=budget)
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b); print("PREPDONE")
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
