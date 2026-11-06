; PC3: asserted (And A B) gives neither A nor B.
!(import! &self petta_chainer)
!(compileadd pc3kb (: c (And (Member o offer) (Past o)) (STV 1.0 0.99)))
; EXPECTED: proofs of (Member o offer) and (Past o) from c (And-elimination).  ACTUAL (36b3fe6): () ()
!(collapse (query 30 pc3kb (: $prf (Member o offer) $tv)))
!(collapse (query 30 pc3kb (: $prf (Past o) $tv)))
; control: the conjunction itself is retrievable
!(collapse (query 30 pc3kb (: $prf (And (Member o offer) (Past o)) $tv)))
