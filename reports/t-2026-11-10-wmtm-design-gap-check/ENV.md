# Environment for t-2026-11-10-wmtm-design-gap-check (user space, no sudo)

| tool | version | source |
|---|---|---|
| git | 2.56.0 | conda-forge, /hive/protocosmo/toolchain/env (micromamba 2.0.5) |
| python | 3.10.22 | same env; venv at projects/wmtm/env-gapcheck/venv310 |
| SWI-Prolog | 9.2.9 (x86_64-linux) | conda-forge, /hive/protocosmo/opt/swipl929 |
| janus_swi | 1.5.3 | pip install janus-swi in venv310, built against swipl 9.2.9 with the toolchain gcc 11.4.0 |
| pytest | 9.2.0 | pip, venv310 |
| PeTTa | 3681b9baa28d005dfbad21ad9b5d46b243b1e323 | env-gapcheck/petta-3681b9b (diff -rq identical to codeload tarball) |
| PeTTaChainer | b6aacc686675c2c3fd5758adbd2ee245e3e7a5a5 | env-gapcheck/pettachainer-b6aacc68 (diff -rq identical to codeload tarball) |

env.sh:
```
E=/hive/protocosmo/workspace/projects/wmtm/env-gapcheck
export PATH=$E/venv310/bin:/hive/protocosmo/opt/swipl929/bin:/hive/protocosmo/toolchain/env/bin:$PATH
export WMTM_PC_PETTA=$E/petta-3681b9b
export WMTM_PC_VENDOR=$E/pettachainer-b6aacc68
export WMTM_SWIPL_BIN=/hive/protocosmo/opt/swipl929/bin
export PETTA_PATH=$E/petta-3681b9b
export SWIPL=/hive/protocosmo/opt/swipl929/bin/swipl
```
Check: `python -c "import janus_swi as j; print(j.query_once('X is 1+2'))"` -> `{'truth': True, 'X': 3}`.
