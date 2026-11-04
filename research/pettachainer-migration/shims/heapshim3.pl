:- use_module(library(heaps), []).
empty_heap(H) :- heaps:empty_heap(H).
add_to_heap(H0,P,K,H) :- heaps:add_to_heap(H0,P,K,H).
heap_size(H,N) :- heaps:heap_size(H,N).
heap_pop(H,[P,V,R]) :- heaps:get_from_heap(H,P,V,R).
'heap-empty?'(H,E) :- ( heaps:empty_heap(H) -> E = true ; E = false ).
