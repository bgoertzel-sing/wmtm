#!/usr/bin/env bash
# Build the reasoner runtime that the background workers use, as plain directories under DEST:
#   DEST/petta-3681b9b/                 git archive of rTreutlein/PeTTa 3681b9b
#   DEST/pettachainer-bdae8d7e/         git archive of rTreutlein/PeTTaChainer bdae8d7e (pettachainer/ + third_party/), no patch
#   DEST/semparse-hitl-f44d7b74/        semantic-parsing-hitl templates/ + LICENSE (MIT) @f44d7b74
# Each dir gets VERSION and MANIFEST.sha256.  These are the default relative paths in wmtm/runtime_config.py when
# DEST is the directory that holds the vendored wmtm-<tag>/.  Nothing here is committed to this repo.
#   usage: PETTA_SRC=<PeTTa clone> PETTACHAINER_SRC=<PeTTaChainer clone> [SEMPARSE_SRC=<hitl clone>] vendor_runtime.sh DEST
set -euo pipefail
W="$(cd "$(dirname "$0")/.." && pwd)"; DEST="${1:?usage: vendor_runtime.sh DEST}"
: "${PETTA_SRC:?set PETTA_SRC to a clone of https://github.com/rTreutlein/PeTTa}"
: "${PETTACHAINER_SRC:?set PETTACHAINER_SRC to a clone of the rTreutlein PeTTaChainer (commit bdae8d7e)}"
PETTA_PIN=3681b9baa28d005dfbad21ad9b5d46b243b1e323       # rTreutlein/PeTTa
PC_PIN=bdae8d7ee0bc38ef93528ea3e9d3dcc47c5b8c95
mkdir -p "$DEST"
manifest() { (cd "$1" && find . -type f ! -name MANIFEST.sha256 | LC_ALL=C sort | xargs -d '\n' sha256sum > MANIFEST.sha256); }

d="$DEST/petta-3681b9b"; [ ! -e "$d" ] || { echo "exists: $d" >&2; exit 1; }
git -C "$PETTA_SRC" cat-file -e "$PETTA_PIN^{commit}"
mkdir "$d"; git -C "$PETTA_SRC" archive "$PETTA_PIN" | tar -x -C "$d"
printf "source=https://github.com/rTreutlein/PeTTa\ncommit=%s\n" "$PETTA_PIN" > "$d/VERSION"; manifest "$d"

d="$DEST/pettachainer-bdae8d7e"; [ ! -e "$d" ] || { echo "exists: $d" >&2; exit 1; }
git -C "$PETTACHAINER_SRC" cat-file -e "$PC_PIN^{commit}"
mkdir "$d"; git -C "$PETTACHAINER_SRC" archive "$PC_PIN" pettachainer third_party | tar -x -C "$d"
printf "source=https://github.com/rTreutlein/PeTTaChainer\ncommit=%s\npatch=none\n" "$PC_PIN" > "$d/VERSION"; manifest "$d"

d="$DEST/semparse-hitl-f44d7b74"; [ ! -e "$d" ] || { echo "exists: $d" >&2; exit 1; }
"$W/scripts/fetch_semparse_hitl.sh" "$d"; manifest "$d"
echo "runtime vendored under $DEST"
