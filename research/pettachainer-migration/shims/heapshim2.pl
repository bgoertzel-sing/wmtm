:- use_module(library(heaps)).
pc_eh(H) :- heaps:empty_heap(H).
pc_add(H0,P,K,H) :- heaps:add_to_heap(H0,P,K,H).
pc_size(H,N) :- heaps:heap_size(H,N).
pc_isempty(H,E) :- ( heaps:empty_heap(H) -> E = true ; E = false ).
pc_pop(H,[P,V,R]) :- heaps:get_from_heap(H,P,V,R).
pc_where2(R) :- ( current_predicate(Mod:'heap-empty?'/2), Mod \== heaps -> R=Mod ; R=absent ).
