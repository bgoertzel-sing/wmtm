;; R9 (candidate, for LIST-roman next to R2). PeTTaChainer bdae8d7e + PeTTa 3681b9b, run with LIST-roman repro.py.
;; Without mem_inh/inh_trans loaded: (by r1 f1) at (STV 0.9 0.70). With them loaded (as the wmtm shadow worker does):
;; (specializes (by mem_inh (conjunction f1 r1)) (by r1 f1) ...) at (STV 0.977 0.018): the engine reads the Implication r1
;; as the Inheritance premise of mem_inh, and the specializes combination returns a lower confidence than the direct
;; modus-ponens proof (0.70) it contains. Measured 2026-11-06 00:11 PDT. In the P4 B flag-off run the same shape gives acl_d c=0.042.
(: mem_inh (Implication (And (Member $x $a) (Inheritance $a $b)) (Member $x $b)) (STV 1.0 0.99))
(: inh_trans (Implication (And (Inheritance $a $b) (Inheritance $b $c)) (Inheritance $a $c)) (STV 1.0 0.99))
(: f1 (Member b1 cls_a) (STV 1.0 0.99))
(: r1 (Implication (Member b1 cls_a) (Member b1 acl_d)) (STV 0.9 0.7))
;; QUERY (Member b1 acl_d) STEPS 30
