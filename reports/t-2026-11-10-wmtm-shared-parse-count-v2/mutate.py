
import os, shutil, subprocess, sys
SRC = os.path.expanduser("~/research-agent/projects/omegaclaw/shared-parse-v2/wmtm-wt")
MUT = [
 ("M0 no mutation (harness check)", "wmtm/parse_budget.py", "HOUR = 3600.0", "HOUR = 3600.0", "tests/test_parse_budget.py tests/test_measure_parse.py"),
 ("M1 task counts only its own log", "wmtm/parse_budget.py",
  'return ParseBudget(role, cfg=cfg, own_log=own_log or os.path.join(cache_dir, "parse_log.jsonl"),\n                       cache_dir=cache_dir)',
  'return ParseBudget(role, cfg=cfg, own_log=own_log or os.path.join(cache_dir, "parse_log.jsonl"),\n                       cache_dir=cache_dir, budget_dir=os.path.join(cache_dir, "_own"))',
  "tests/test_parse_budget.py::test_two_task_callers_never_exceed_task_share tests/test_parse_budget.py::test_two_task_callers_interleaved_and_concurrent"),
 ("M2 live logs counted in the task share", "wmtm/parse_budget.py",
  '            if self.own_log and self.own_log not in out:\n                out.append(self.own_log)',
  '            if self.own_log and self.own_log not in out:\n                out.append(self.own_log)\n            if self.live_dir:\n                out += [os.path.join(self.live_dir, s, "parse_log.jsonl") for s in SUBCACHES]',
  "tests/test_parse_budget.py::test_live_calls_do_not_use_task_share"),
 ("M3 measure_parse writes no counted row", "tools/measure_parse.py",
  'with open(plog, "a", encoding="utf-8") as fh:',
  'with open(os.devnull, "a", encoding="utf-8") as fh:',
  "tests/test_measure_parse.py::test_main_writes_a_counted_row_per_call"),
 ("M4 provider not gated", "wmtm/semparse_provider.py",
  'call.last_call_id = gate.acquire(tag, wait=wait, max_wait_s=max_wait_s)',
  'call.last_call_id = None',
  "tests/test_measure_parse.py::test_main_writes_a_counted_row_per_call tests/test_measure_parse.py::test_main_stops_when_task_share_is_full tests/test_measure_parse.py::test_gateway_llm_without_budget_is_still_counted"),
]
env = dict(os.environ, WMTM_SEMPARSE_HITL="/tmp/spc2/hitl-1f1a7a6f")
for name, f, old, new, tests in MUT:
    d = "/tmp/spc2/mut"
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(SRC, d, ignore=shutil.ignore_patterns(".git", "__pycache__", "worktrees", "reports", "research"))
    p = os.path.join(d, f); s = open(p).read()
    assert s.count(old) == 1, (name, s.count(old))
    open(p, "w").write(s.replace(old, new))
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + tests.split(), cwd=d, env=env,
                       capture_output=True, text=True)
    last = [l for l in r.stdout.splitlines() if " passed" in l or " failed" in l][-1:]
    errs = sorted({l.split(":")[0][:90] for l in r.stdout.splitlines() if l.startswith("E   ")})[:2]
    print(name, "->", "exit", r.returncode, last, errs)
