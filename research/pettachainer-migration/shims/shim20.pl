
%shim20 (scratch, pcmig): forward Prolog calls to MeTTa-only functions.
'canon'(A0,A1) :- current_metta_module(M), M \== user, M:'canon'(A0,A1).
'complete-part?'(A0,A1,A2,A3) :- current_metta_module(M), M \== user, M:'complete-part?'(A0,A1,A2,A3).
'contextual-cpu?'(A0,A1) :- current_metta_module(M), M \== user, M:'contextual-cpu?'(A0,A1).
'derivation-proof?'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'derivation-proof?'(A0,A1,A2).
'implication-side-conjuncts'(A0,A1) :- current_metta_module(M), M \== user, M:'implication-side-conjuncts'(A0,A1).
'next-search-id'(A0,A1) :- current_metta_module(M), M \== user, M:'next-search-id'(A0,A1).
'positive-only-pattern?'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'positive-only-pattern?'(A0,A1,A2).
'premise-evidence-overlap?'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'premise-evidence-overlap?'(A0,A1,A2).
'proof-term-contains-negated?'(A0,A1) :- current_metta_module(M), M \== user, M:'proof-term-contains-negated?'(A0,A1).
'proof-term-evidence'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'proof-term-evidence'(A0,A1,A2).
'revision-merge-tv'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'revision-merge-tv'(A0,A1,A2).
'rule-application-proof?'(A0,A1) :- current_metta_module(M), M \== user, M:'rule-application-proof?'(A0,A1).
'rule-result-evidence'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'rule-result-evidence'(A0,A1,A2).
'set-positive-only-predicate'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'set-positive-only-predicate'(A0,A1,A2).
'sk-add-use!'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'sk-add-use!'(A0,A1,A2).
'sk-admits?'(A0,A1,A2,A3) :- current_metta_module(M), M \== user, M:'sk-admits?'(A0,A1,A2,A3).
'sk-leaf-view'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'sk-leaf-view'(A0,A1,A2).
'sk-open-filter?'(A0,A1) :- current_metta_module(M), M \== user, M:'sk-open-filter?'(A0,A1).
'sk-part-prior'(A0,A1,A2,A3) :- current_metta_module(M), M \== user, M:'sk-part-prior'(A0,A1,A2,A3).
'user-base-rate?'(A0,A1,A2) :- current_metta_module(M), M \== user, M:'user-base-rate?'(A0,A1,A2).
