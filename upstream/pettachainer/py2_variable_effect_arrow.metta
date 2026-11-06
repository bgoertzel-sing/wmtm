;; PY2: pymetta 0.9.4+goalchainer.native.2 refuses an effect variable in an annotated arrow.
;; Same declaration as PeTTaChainer 202b9379 lib/collections.metta:14 (foreach-flat).
;; Command (run in this directory): <venv with pymetta==0.9.4+goalchainer.native.2>/bin/python -c "import metta,sys; print(metta.MeTTa().run(open(sys.argv[1]).read()))" py2_variable_effect_arrow.metta
;; EXPECTED: the declaration is stored and the call returns ()
;; ACTUAL: see README (EngineError while adding the declaration)
(: foreach-flat (-[$e]-> (-[$e]-> $item $effect) (List $item) (List $none)))
(= (foreach-flat $f ()) ())
(= (foreach-flat $f (cons $x $xs)) (progn ($f $x) (foreach-flat $f $xs)))
!(foreach-flat id ())
