; PC4: compileadd accepts out-of-range STVs (s must be in [0,1], c in [0,1)).
!(import! &self petta_chainer)
!(compileadd pc4kb (: bad1 (Member a b) (STV 1.0 1.5)))
!(compileadd pc4kb (: bad2 (Member c d) (STV -0.5 0.9)))
!(compileadd pc4kb (: bad3 (Member e f) (STV 2.0 0.5)))
; EXPECTED: rejection (error) at add time.  ACTUAL (36b3fe6): accepted and returned by query
!(collapse (query 30 pc4kb (: $prf (Member a b) $tv)))
!(collapse (query 30 pc4kb (: $prf (Member c d) $tv)))
!(collapse (query 30 pc4kb (: $prf (Member e f) $tv)))
