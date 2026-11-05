import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    if "warm-up" in src:
        orig(space,"(= (the $t $x) $x)\n(= (brand $t $x) $x)\n(= (one-fn) 1)\n(= (two-fn) 2)",budget=budget)
        for q in ["!(chainer-reset!)", "!(collapse (compileadd gc_t (: f1 (GcWarmPremise a) (STV 1.0 0.9))))", "!(collapse (query 20 gc_t (: $p (GcWarmPremise a) $tv)))", "!(collapse (compileadd gc_t (: r1 (Implication (GcWarmPremise $x) (Acceptable $x)) (STV 0.9 0.9))))", "!(collapse (query 20 gc_t (: $p (Acceptable a) $tv)))", "!(set-backward-premise-prefilter gc_t True)", "!(collapse (query 20 gc_t (: $p (Acceptable a) $tv)))"]:
            try: print("Q", q, [[str(x)[:200] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q, type(e).__name__, str(e)[:300], flush=True)
    return orig(space, src, budget=budget)
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b); print("PREPDONE")
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
