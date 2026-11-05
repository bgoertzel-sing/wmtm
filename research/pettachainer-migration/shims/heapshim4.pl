:- use_module(library(heaps), []).
pch_empty(H) :- heaps:empty_heap(H).
pch_add(H0,P,K,H) :- heaps:add_to_heap(H0,P,K,H).
pch_size(H,N) :- heaps:heap_size(H,N).
pch_pop(H,[P,V,R]) :- heaps:get_from_heap(H,P,V,R).
pch_isempty(H,E) :- ( heaps:empty_heap(H) -> E = true ; E = false ).
