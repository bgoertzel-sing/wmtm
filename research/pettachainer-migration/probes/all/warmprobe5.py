import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    a=orig(space, src, budget=budget)
    if "warm-up" in src:
        for q in ["!(collapse (source-plan-parts (() |- (: kb f1 (A a) (STV 1.0 0.9)))))",
                  "!(collapse (brand Foo (x y)))",
                  "!(get-type brand)",
                  "!(collapse (source-plan-parts (brand CompiledAddition (() |- (: kb f1 (A a) (STV 1.0 0.9))))))"]:
            try: print("Q", q[:100], [[str(x)[:400] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q[:80], type(e).__name__, str(e)[:400], flush=True)
    return a
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b)
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
