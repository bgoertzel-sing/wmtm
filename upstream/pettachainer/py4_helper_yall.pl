% Helper for PY4: same directive as PeTTaChainer 202b9379 prolog/runtime_helpers.pl:6.
:- use_module(library(yall)).
'py4-a'(X, Y) :- call([A,B]>>(B = A), X, Y).
