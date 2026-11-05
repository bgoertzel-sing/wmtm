import goal_chainer.runtime.evaluator as ev
from goal_chainer.evidence_chainer import grading_group
from goal_chainer.runtime.budget import RunBudget
orig=ev.run_bounded
def rb(space, src, budget):
    if "warm-up" in src:
        a=None
        try: print('Q warmup-skipped', flush=True)
        except: pass
        for q in ["!(add-atom &self (= (wk $x $u) (+ $x 1)))", "!(add-atom &self (= (cl $u) done))", "!(add-atom &self (= (apply-unit $f) (if (== (get-metatype $f) Expression) (union-atom $f (u)) ($f u))))", "!(add-atom &self (= (finally $w $c) (let $r (metta (apply-unit $w) %Undefined% &self) (let $_ (metta (apply-unit $c) %Undefined% &self) $r))))", "!(add-atom &self (= (brand $t $x) $x))", "!(add-atom &self (= (the $t $x) $x))", "!(add-atom &self (= (data $a $b $c $d) ($a $b $c $d)))", "!(add-atom &self (= (data $a) ($a)))", "!(add-atom &self (= (data $a $b) ($a $b)))", "!(add-atom &self (= (data $a $b $c) ($a $b $c)))", "!(add-atom &self (= (data $a $b $c $d $e) ($a $b $c $d $e)))", "!(chainer-reset!)", "!(collapse (kb-publish-fact! live source ((B b) (kbx MAIN Nil) f2 (STV 1.0 0.9))))", "!(collapse (fold-flat (sk-leaves-out-step ()) (== 1 2) ((foo))))", "!(collapse (let $f (== 1 2) (fold-flat (sk-leaves-out-step ()) $f ((foo)))))", "!(collapse (foldl-atom ((foo)) false $acc $x (sk-leaves-out-step () $acc $x)))", "(: fold-any (-[det]-> Expression Expression Expression Bool))", "(= (fold-any $f $arg $xs) (if (== $xs ()) false (let* (($h (car-atom $xs)) ($t (cdr-atom $xs)) ($c (cons-atom $f (cons-atom $arg (cons-atom false (cons-atom $h ())))))) (if (eval $c) true (fold-any $f $arg $t)))))", "!(collapse (fold-any sk-leaves-out-step () ((foo))))", "!(collapse (fold-any sk-gives-way-step f2 (x)))"]:
            try: print("Q", q[:90], [[str(x)[:400] for x in r] for r in orig(space,q,budget=budget)[0]][:3], flush=True)
            except Exception as e: print("QERR", q[:60], type(e).__name__, str(e)[:400], flush=True)
    else: a=orig(space, src, budget=budget)
    return a
ev.run_bounded=rb
b=RunBudget(inference_budget=None, timeout_seconds=300)
try: ev.prepare(grading_group(budget=b), budget=b); print('PREPDONE')
except Exception as e: print("PREP", type(e).__name__, str(e)[:200])
