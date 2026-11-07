; PY1: pymetta 0.9.4+goalchainer.native.2 refuses a nested annotated arrow, so petta_chainer (rT 202b9379) cannot load.
; The same declaration is lib/collections.metta:2 in PeTTaChainer 202b9379.
; Command: <venv with pymetta==0.9.4+goalchainer.native.2>/bin/python -c "import metta,sys; print(metta.MeTTa().run(open(sys.argv[1]).read()))" py1_nested_annotated_arrow.metta
; EXPECTED: the declaration is stored, and (fold-semidet add 0 (Cons 1 (Cons 2 Nil))) gives 3
; ACTUAL: EngineError / PrologError: metta_add_atom/3: cannot honour the annotated arrow for fold-semidet
;   (arrow_products.pl:58 metta_require_arrow_product rejects nested products)
(: fold-semidet (-[semidet]-> (-[semidet]-> $acc $item $acc) $acc (List $item) $acc))
(= (fold-semidet $f $acc Nil) $acc)
(= (fold-semidet $f $acc (Cons $x $xs)) (fold-semidet $f ($f $acc $x) $xs))
(: add2 (-[semidet]-> Number Number Number))
(= (add2 $a $b) (+ $a $b))
!(fold-semidet add2 0 (Cons 1 (Cons 2 Nil)))
