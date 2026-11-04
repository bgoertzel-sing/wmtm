import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
S="(: f1 (A a) (STV 1.0 0.9))"
def rb(space, src, budget):
    a=orig(space, src, budget=budget)
    if "warm-up" in src:
        for q in ["!(chainer-reset!)",
                  "!(collapse (source-rule? (A a)))",
                  "!(collapse (implication-type? (A a)))",
                  "!(collapse (explicit-exists-term? (A a)))",
                  "!(collapse (source-exists? (A a)))",
                  "!(collapse (bidirectional-implication-type? (A a)))",
                  "!(collapse (compile-ordinary-fact kbz f1 (A a) (STV 1.0 0.9)))",
                  f"!(collapse (compile_ kbz {S}))",
                  f"!(collapse (let $c (compile_ kbz {S}) (source-plan-parts $c)))",
                  f"!(collapse (let $c (compile_ kbz {S}) (mm2stmt $c)))"]:
            try: print("Q", q[:100], [[str(x)[:500] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q[:80], type(e).__name__, str(e)[:500], flush=True)
    return a
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b)
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
