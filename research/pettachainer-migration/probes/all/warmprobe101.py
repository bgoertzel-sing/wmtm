import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    if "warm-up" in src:
        a=None
        try: print('Q warmup-skipped', flush=True)
        except: pass
        for q in ["!(add-atom &self (= (wk $x $u) (+ $x 1)))", "!(add-atom &self (= (cl $u) done))", "!(add-atom &self (= (apply-unit $f) (if (== (get-metatype $f) Expression) (union-atom $f (u)) ($f u))))", "!(add-atom &self (= (finally $w $c) (let $r (metta (apply-unit $w) %Undefined% &self) (let $_ (metta (apply-unit $c) %Undefined% &self) $r))))", "!(add-atom &self (= (brand $t $x) $x))", "!(add-atom &self (= (the $t $x) $x))", "!(add-atom &self (= (data $a $b $c $d) ($a $b $c $d)))", "!(add-atom &self (= (data $a) ($a)))", "!(add-atom &self (= (data $a $b) ($a $b)))", "!(add-atom &self (= (data $a $b $c) ($a $b $c)))", "!(add-atom &self (= (data $a $b $c $d $e) ($a $b $c $d $e)))", "!(chainer-reset!)", "!(collapse (kb-publish-fact! live source ((B b) (kbx MAIN Nil) f2 (STV 1.0 0.9))))", "!(collapse (sk-clear-query-values!))", "!(collapse (change-state! sk_representative_budget 256))", "!(collapse (execution-reset-frames!))", "!(collapse (map-semidet execution-search-goal (((B b) (kbx MAIN Nil) $p $tv))))", "!(collapse (remove-data-rows! &sk_seen (quote ($hash $node))))", "!(collapse (remove-data-rows! &sk_fresh (quote ($fhash $node))))", "!(collapse (sk-park-deliveries!))", "!(collapse (remove-data-rows! &sk_roots (quote ($hash $root))))", "!(collapse (current-time))", "!(collapse (change-state! sk_row_budget 200))", "!(collapse (sk-activate-facts!))", "!(collapse (fold-semidet sk-root-score-step () (((B b) (kbx MAIN Nil) $p $tv))))", "!(collapse (sk-activate-rules!))", "!(collapse (sk-activate-thawed!))", "!(collapse (sk-drain!))", "!(collapse (change-state! sk_budget 20))", "!(collapse (execution-allowances! (* (sk-evaluation-per-step) 20) true))", "!(collapse (change-state! sk_walk_budget (* (sk-walk-per-step) 20)))", "!(collapse (map-semidet execution-start-seed! (context-seeds $any-context)))", "!(collapse (fold-semidet sk-root-reader-step () (((B b) (kbx MAIN Nil) $p $tv))))", "!(collapse (sk-walk! (((B b) (kbx MAIN Nil) $p $tv))))", "!(collapse (sk-invalidate-world!))", "!(collapse (sk-need-roots! (fold-semidet sk-root-keys-step () (((B b) (kbx MAIN Nil) $p $tv)))))", "!(collapse (search-id-value sk_near_reserve))", "!(collapse (sk-evaluate!))", "!(collapse (inference-add! 0))", "!(collapse (map-semidet (sk-root-results false) (((B b) (kbx MAIN Nil) $p $tv))))", "!(collapse (sk-stale-held!))"]:
            try: print("Q", q[:90], [[str(x)[:400] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q[:60], type(e).__name__, str(e)[:400], flush=True)
    else: a=orig(space, src, budget=budget)
    return a
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b); print('PREPDONE')
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
