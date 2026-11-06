;; PY4: a Prolog helper that runs :- use_module(library(yall)) (PeTTaChainer 202b9379 prolog/runtime_helpers.pl:6).
;; Command (run in this directory): <venv with pymetta==0.9.4+goalchainer.native.2>/bin/python -c "import metta,sys; print(metta.MeTTa().run(open(sys.argv[1]).read()))" py4_reimport_yall.metta
;; EXPECTED: helper loads; (py4-a 7) gives 7
;; ACTUAL: see README (No permission to import yall:(/)/3 into user)
!(import! &self (library lib_import))  ; as in PeTTaChainer bootstrap.metta:6
!(import_prolog_functions_from_file "py4_helper_yall.pl" (py4-a))
!(py4-a 7)
