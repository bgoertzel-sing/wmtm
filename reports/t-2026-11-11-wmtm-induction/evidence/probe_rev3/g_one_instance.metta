; rev3 negative control: one shared instance
!(import! &self ../../pettachainer/metta/petta_chainer)
!(compileadd K (: a1 (Member i1 A) (STV 1.0 0.9)))
!(compileadd K (: b1 (Member i1 B) (STV 1.0 0.9)))
!(println! (collapse (query 200 K (: $prf (Inheritance A B) $tv))))
