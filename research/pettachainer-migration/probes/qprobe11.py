import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    if "warm-up" in src:
        orig(space,"(= (the $t $x) $x)\n(= (brand $t $x) $x)\n(= (one-fn) 1)\n(= (two-fn) 2)",budget=budget)
        for q in ["!(chainer-reset!)", "!(collapse (compileadd kbx (: f1 (C c) (STV 1.0 0.9))))", "!(collapse (execute-backward 20 (((C c) (kbx MAIN Nil) $p $tv)) false))", "!(collapse (kb-publish-fact! live source ((D d) (kbx MAIN Nil) f2 (STV 1.0 0.9))))", "!(collapse (execute-backward 20 (((D d) (kbx MAIN Nil) $p $tv)) false))", "!(collapse (kb-publish-fact! live source ((GcWarmPremise a) (gc_t MAIN Nil) f3 (STV 1.0 0.9))))", "!(collapse (execute-backward 20 (((GcWarmPremise a) (gc_t MAIN Nil) $p $tv)) false))"]:
            try: print("Q", q, [[str(x)[:200] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q, type(e).__name__, str(e)[:300], flush=True)
    return orig(space, src, budget=budget)
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b); print("PREPDONE")
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
