:- use_module(library(heaps)).
pc_eh(H) :- heaps:empty_heap(H).
pc_add(H0,P,K,H) :- heaps:add_to_heap(H0,P,K,H).
pc_size(H,N) :- heaps:heap_size(H,N).
pc_probe(R) :- ( catch(heaps:empty_heap(_),E,(R=err(E))) -> (var(R)->R=ok;true) ; R=fail ).
pc_where(R) :- ( predicate_property(user:empty_heap(_),imported_from(M)) -> R=M ; current_predicate(user:empty_heap/1) -> R=user_local ; R=absent ).
