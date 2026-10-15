#!/usr/bin/env bash
# Vendor PeTTaChainer upstream master 36b3fe6 + dedup-import patch into gitignored .vendor36/
set -euo pipefail
W="$(cd "$(dirname "$0")/../.." && pwd)"; SRC="${PETTACHAINER_SRC:-$HOME/research-agent/projects/petta-memory/repos/PeTTaChainer}"
PIN=36b3fe686db71f1470bdc22c5ae83702f2dd1247
rm -rf "$W/.vendor36"; mkdir -p "$W/.vendor36"
git -C "$SRC" archive "$PIN" pettachainer | tar -x -C "$W/.vendor36"
( cd "$W/.vendor36" && patch -p1 -s < "$W/patches/pettachainer-dedup-import.patch" )
echo "vendored ${PIN:0:7} + dedup patch -> $W/.vendor36"
