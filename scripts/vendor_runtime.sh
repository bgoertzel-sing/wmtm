#!/usr/bin/env bash
# Build the reasoner runtime that the background workers use, as plain directories under DEST:
#   DEST/petta-v1.0.6/                  git archive of trueagi-io/PeTTa tag v1.0.6 (ae66fa8)
#   DEST/pettachainer-36b3fe6-dedup/    git archive of MesTTo/PeTTaChainer 36b3fe6 (pettachainer/) + dedup-import patch
#   DEST/semparse-hitl-3ec15bd1/        semantic-parsing-hitl prompt + seeded rules (NOT redistributable; local only)
# Each dir gets VERSION and MANIFEST.sha256.  These are the default relative paths in wmtm/runtime_config.py when
# DEST is the directory that holds the vendored wmtm-<tag>/.  Nothing here is committed to this repo.
#   usage: PETTA_SRC=<PeTTa clone> PETTACHAINER_SRC=<PeTTaChainer clone> [SEMPARSE_SRC=<hitl clone>] vendor_runtime.sh DEST
set -euo pipefail
W="$(cd "$(dirname "$0")/.." && pwd)"; DEST="${1:?usage: vendor_runtime.sh DEST}"
: "${PETTA_SRC:?set PETTA_SRC to a clone of https://github.com/trueagi-io/PeTTa}"
: "${PETTACHAINER_SRC:?set PETTACHAINER_SRC to a clone of https://github.com/MesTTo/PeTTaChainer}"
PETTA_PIN=ae66fa8e41dcd5539d614706bd4e5cfb34f9608d       # v1.0.6
PC_PIN=36b3fe686db71f1470bdc22c5ae83702f2dd1247
mkdir -p "$DEST"
manifest() { (cd "$1" && find . -type f ! -name MANIFEST.sha256 | LC_ALL=C sort | xargs -d '\n' sha256sum > MANIFEST.sha256); }

d="$DEST/petta-v1.0.6"; [ ! -e "$d" ] || { echo "exists: $d" >&2; exit 1; }
git -C "$PETTA_SRC" cat-file -e "$PETTA_PIN^{commit}"
mkdir "$d"; git -C "$PETTA_SRC" archive "$PETTA_PIN" | tar -x -C "$d"
printf 'source=https://github.com/trueagi-io/PeTTa\ntag=v1.0.6\ncommit=%s\n' "$PETTA_PIN" > "$d/VERSION"; manifest "$d"

d="$DEST/pettachainer-36b3fe6-dedup"; [ ! -e "$d" ] || { echo "exists: $d" >&2; exit 1; }
git -C "$PETTACHAINER_SRC" cat-file -e "$PC_PIN^{commit}"
mkdir "$d"; git -C "$PETTACHAINER_SRC" archive "$PC_PIN" pettachainer | tar -x -C "$d"
(cd "$d" && patch -p1 -s < "$W/patches/pettachainer-dedup-import.patch")
cp "$W/patches/pettachainer-dedup-import.patch" "$d/"
printf 'source=https://github.com/MesTTo/PeTTaChainer\ncommit=%s\npatch=pettachainer-dedup-import.patch sha256=%s\n' \
  "$PC_PIN" "$(sha256sum "$W/patches/pettachainer-dedup-import.patch" | cut -d' ' -f1)" > "$d/VERSION"; manifest "$d"

d="$DEST/semparse-hitl-3ec15bd1"; [ ! -e "$d" ] || { echo "exists: $d" >&2; exit 1; }
"$W/scripts/fetch_semparse_hitl.sh" "$d"; manifest "$d"
echo "runtime vendored under $DEST"
