:- use_module(library(heaps), []).
pqa_empty(H) :- heaps:empty_heap(H).
pqa_isempty(H,E) :- ( heaps:empty_heap(H) -> E = true ; E = false ).
pqb_empty(H) :- heaps:empty_heap(H).
pqb_isempty(H,E) :- ( heaps:empty_heap(H) -> E = true ; E = false ).
pqc_empty(H) :- heaps:empty_heap(H).
pqc_isempty(H,E) :- ( heaps:empty_heap(H) -> E = true ; E = false ).
pqd_empty(H) :- heaps:empty_heap(H).
pqd_isempty(H,E) :- ( heaps:empty_heap(H) -> E = true ; E = false ).
