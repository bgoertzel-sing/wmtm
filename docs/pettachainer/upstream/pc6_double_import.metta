; PC6: chainer/compile is imported twice (petta_chainer.metta:1 and context/context_generation.metta:16).
; PeTTa's import! is not idempotent, so compile's (= ...) definitions are added twice and each
; nondeterministic call doubles per nesting level (2^depth). Run from an UNPATCHED 36b3fe6 pettachainer/metta.
!(import! &self petta_chainer)
; EXPECTED: 1 definition of each compile function, and the query finishes quickly.
; ACTUAL (unpatched): the count below is 2, and the query is slow or hangs.
!(collapse (match &self (= (compile $k $s) $b) $b))
!(compileadd pc6kb (: f (Member grace pilot) (STV 1.0 0.99)))
!(collapse (query 30 pc6kb (: $prf (Member grace pilot) $tv)))
