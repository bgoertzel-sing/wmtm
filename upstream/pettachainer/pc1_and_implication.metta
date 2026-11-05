; PC1: (Implication (And A B) C) derives nothing; same rule in Premises/Conclusions form works.
; Run from PeTTaChainer/pettachainer/metta: <PeTTa>/run.sh <this file>
!(import! &self petta_chainer)
!(compileadd pc1kb (: r_and (Implication (And (Inheritance $x $y) (Inheritance $y $z)) (Inheritance $x $z)) (STV 1.0 0.99)))
!(compileadd pc1kb (: f1 (Inheritance pilot person) (STV 1.0 0.99)))
!(compileadd pc1kb (: f2 (Inheritance person animal) (STV 1.0 0.99)))
; EXPECTED: a proof of (Inheritance pilot animal) via r_and.  ACTUAL (36b3fe6): ()
!(collapse (query 30 pc1kb (: $prf (Inheritance pilot animal) $tv)))
; control: Premises/Conclusions form in a separate KB -> derived
!(compileadd pc1ctl (: r_pc (Implication (Premises (Inheritance $x $y) (Inheritance $y $z)) (Conclusions (Inheritance $x $z))) (STV 1.0 0.99)))
!(compileadd pc1ctl (: f1 (Inheritance pilot person) (STV 1.0 0.99)))
!(compileadd pc1ctl (: f2 (Inheritance person animal) (STV 1.0 0.99)))
!(collapse (query 30 pc1ctl (: $prf (Inheritance pilot animal) $tv)))
