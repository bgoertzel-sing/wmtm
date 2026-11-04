import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    a=orig(space, src, budget=budget)
    if "warm-up" in src:
        for q in ["!(get-type finally)", "!(add-atom &self (= (wk $x $u) (+ $x 1)))", "!(add-atom &self (= (cl $u) done))", "!(collapse (finally (wk 41) cl))", "!(collapse (wk 41 u))", "!(add-atom &self (= (brand $t $x) $x))", "!(add-atom &self (= (the $t $x) $x))", "!(chainer-reset!)", "!(collapse (compileadd kbx (: f1 (A a) (STV 1.0 0.9))))", "!(collapse (materialize-stmt-lambdas (: $p (A a) $tv)))", "!(collapse (member-canon (A a)))", "!(collapse (query-root (: $p (A a) $tv)))", "!(collapse (mm2compileQuery kbx (query-root (: $p (A a) $tv))))", "!(collapse (let $c (mm2compileQuery kbx (query-root (: $p (A a) $tv))) (run-query-execution-plan 20 (compiled-query-execution-plan 0 (A a) (: $p (A a) $tv) $c) false true)))", "!(collapse (query 20 kbx (: $p (A a) $tv)))","!(add-atom &self (= (brand $t $x) $x))", "!(add-atom &self (= (the $t $x) $x))", "!(space-row-present? &context_polymorphic_facts (quote (kb1 true)))", "!(collapse (compile-ordinary-fact kb1 p1 (Rain) (STV 1.0 0.9)))", "!(collapse (compile_ kb1 (: p1 (Rain) (STV 1.0 0.9))))", "!(collapse (let $a (compile_ kb1 (: p1 (Rain) (STV 1.0 0.9))) (mm2stmt $a)))", "!(collapse (compile-outputs (: kb1 p1 (Rain) (STV 1.0 0.9))))", "!(collapse (compile-specialization-fact-triggers kb1 (Rain)))","!(add-atom &self (= (brand $t $x) $x))",
                  "!(add-atom &self (= (the $t $x) $x))",
                  "!(collapse (the Foo (x y)))",
                  "!(chainer-reset!)",
                  "!(collapse (compileadd kbx (: f1 (A a) (STV 1.0 0.9))))",
                  "!(collapse (query 20 kbx (: $p (A a) $tv)))",
                  "!(gc-pettachainer-warm-up)"]:
            try: print("Q", q[:90], [[str(x)[:400] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q[:60], type(e).__name__, str(e)[:400], flush=True)
    return a
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b)
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
