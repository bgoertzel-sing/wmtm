; PC2: a rule with several Conclusions derives nothing.
!(import! &self petta_chainer)
!(compileadd pc2kb (: r_multi (Implication (Premises (Member $x pilot)) (Conclusions (Member $x person) (Member $x flyer))) (STV 1.0 0.99)))
!(compileadd pc2kb (: f (Member grace pilot) (STV 1.0 0.99)))
; EXPECTED: proofs via r_multi for both.  ACTUAL (36b3fe6): () ()
!(collapse (query 30 pc2kb (: $prf (Member grace person) $tv)))
!(collapse (query 30 pc2kb (: $prf (Member grace flyer) $tv)))
; control: single-conclusion rule -> derived
!(compileadd pc2ctl (: r_one (Implication (Premises (Member $x pilot)) (Conclusions (Member $x person))) (STV 1.0 0.99)))
!(compileadd pc2ctl (: f (Member grace pilot) (STV 1.0 0.99)))
!(collapse (query 30 pc2ctl (: $prf (Member grace person) $tv)))
