; PC5 at rT 202b9379: modus ponens from a premise with strength < 1 roughly halves the conclusion confidence.
; Copy into pettachainer/metta/ of a PeTTaChainer 202b9379 checkout and run there (PeTTa 3681b9b; the import is relative):
;   cd <PeTTaChainer>/pettachainer/metta && cp <this file> ./_pc5.metta && PATH=<swipl-9.3.36>/bin:$PATH <PeTTa>/run.sh ./_pc5.metta
!(import! &self petta_chainer)
!(import! &self core/logic_configs/pln)
!(compileadd pc5kb (: r (Implication (P $x) (Q $x)) (STV 0.85 0.92)))
!(compileadd pc5kb (: f (P x) (STV 0.95 0.92)))
; EXPECTED: (Q x) with s ~0.81 and c close to the premise confidence (~0.88, as on rT 38b1473)
; ACTUAL (202b9379, verified 2026-11-04): ((: (by r f) (Q x) (STV 0.8325 0.43954122285972896)))
!(collapse (query 30 pc5kb (: $prf (Q x) $tv)))
!(compileadd pc5kb1 (: r (Implication (P $x) (Q $x)) (STV 0.85 0.92)))
!(compileadd pc5kb1 (: f (P x) (STV 1.0 0.92)))
; CONTROL: premise strength 1.0 -> c ~0.92
; ACTUAL (202b9379): ((: (by r f) (Q x) (STV 0.85 0.9199998811609185)))
!(collapse (query 30 pc5kb1 (: $prf (Q x) $tv)))
