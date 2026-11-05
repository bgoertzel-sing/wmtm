;; PY5: two Prolog sources register the same native name (declare-natives! in PeTTaChainer 202b9379).
;; Command (run in this directory): <venv with pymetta==0.9.4+goalchainer.native.2>/bin/python -c "import metta,sys; print(metta.MeTTa().run(open(sys.argv[1]).read()))" py5_two_sources_one_name.metta
;; EXPECTED: second import accepted (or last-wins); (py3-a 7) gives 7
;; ACTUAL: see README (refuse_other_sources_name/2 ... two Prolog sources claim one name)
!(import! &self (library lib_import))  ; as in PeTTaChainer bootstrap.metta:6
!(import_prolog_functions_from_file "py3_helper.pl" (py3-a))
!(import_prolog_functions_from_file "py5_helper_second.pl" (py3-a))
!(py3-a 7)
