;; PY3: import_prolog_functions_from_file with a quoted name list, as in PeTTaChainer 202b9379 bootstrap.metta:33-37.
;; Command (run in this directory): <venv with pymetta==0.9.4+goalchainer.native.2>/bin/python -c "import metta,sys; print(metta.MeTTa().run(open(sys.argv[1]).read()))" py3_quoted_import_list.metta
;; EXPECTED: py3-a and py3-b are imported; (py3-a 7) gives 7
;; ACTUAL: see README (Type error: atom expected, found a list)
!(import! &self (library lib_import))  ; as in PeTTaChainer bootstrap.metta:6
!(import_prolog_functions_from_file "py3_helper.pl" (quote (py3-a py3-b)))
!(py3-a 7)
