; PC3 at rT 202b9379: And-elimination now DERIVES the conjuncts, but with confidence ~0.
; Run from pettachainer/metta/:  PATH=<swipl-9.3.36>/bin:$PATH <PeTTa>/run.sh <abs path>/pc3_and_elimination_202b9379.metta
; (the import needs the absolute path of pettachainer/metta/petta_chainer under 202b9379)
!(import! &self /home/openclaw/research-agent/projects/omegaclaw/p1-engine/opencog/PeTTaChainer/pettachainer/metta/petta_chainer)
!(compileadd pc3kb (: c (And (Member o offer) (Past o)) (STV 1.0 0.99)))
; EXPECTED: conjuncts with c clearly > 0 (true posterior c ~0.54); the And itself keeps ~0.99 (or at least > 0)
; ACTUAL (202b9379): (STV 0.99997475 3.66e-16) for each conjunct
!(collapse (query 30 pc3kb (: $prf (Member o offer) $tv)))
!(collapse (query 30 pc3kb (: $prf (Past o) $tv)))
; ACTUAL (202b9379): (STV 0.99996212 0.0) for the stored conjunction itself
!(collapse (query 30 pc3kb (: $prf (And (Member o offer) (Past o)) $tv)))
