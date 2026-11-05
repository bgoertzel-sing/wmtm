% pc_store_access: PeTTaChainer row access routed through the pymetta engine's
% native storage modules ('$metta_atoms:<space>', extra trailing token).
% Prototype for t-2026-11-03-pettachainer-migration-plan (in /tmp only).
pc_row(Space, Row) :-
    native_storage_module_ready(Space, M),
    metta_storage_term(Space, Row, _, T),
    catch(M:T, error(existence_error(procedure,_),_), fail).
pc_row_add(Space, Row) :- add_sexp(Space, Row).
pc_row_remove_all(Space, Pattern) :-
    (   native_storage_module_ready(Space, M)
    ->  metta_storage_term(Space, Pattern, _, T), retractall(M:T)
    ;   true ).
pc_row_ref(Space, Row, Stored, Ref) :-
    native_storage_module_ready(Space, M),
    metta_storage_term(Space, Row, _, T), copy_term_nat(T, L),
    catch(clause(M:L, true, Ref), error(existence_error(procedure,_),_), fail),
    clause(M:S, true, Ref), metta_storage_term(_, Stored, _, S).
% Direct-read facades for spaces PeTTaChainer reads as plain predicates.
'&kb'(A,B,C,D) :- pc_row('&kb',[A,B,C,D]).
'&kb_prefix'(A,B,C,D,E) :- pc_row('&kb_prefix',[A,B,C,D,E]).
'&kb_open'(A,B,C,D,E) :- pc_row('&kb_open',[A,B,C,D,E]).
