#!/usr/bin/env bash
# Fetch leungmanhin/semantic-parsing-hitl pinned by commit f44d7b74 (P4 re-pin) into DEST
# (default: <repo>/.semparse-hitl, gitignored).  Upstream is MIT-licensed at this pin; LICENSE is copied
# alongside and checked.  Copies templates/ (tmpl, catalog, generated/PROMPT_CATALOG.txt, rules.yaml), semantic-parse.py
# (the upstream providers, used by wmtm.semparse_provider / tools/measure_parse.py) + LICENSE,
# verifies sha256 of the catalog prompt, the seeded rules, semantic-parse.py and LICENSE, and writes VERSION (commit=<pin>), which
# wmtm.semparse_catalog checks before importing anything (wrong pin / missing licence -> refuse).
#   usage: fetch_semparse_hitl.sh [DEST]       (SEMPARSE_SRC=<existing clone> skips the network fetch)
set -euo pipefail
W="$(cd "$(dirname "$0")/.." && pwd)"; D="${1:-$W/.semparse-hitl}"
REPO=https://github.com/leungmanhin/semantic-parsing-hitl
PIN=f44d7b740aed240c834165672b6a862998ee4a12
SHA_PROMPT=645bff3f5c3a0670d98a463d60d18e178d899c08c58f17ea4b3ff5a53b1d25b6   # templates/generated/PROMPT_CATALOG.txt
SHA_SEEDED=c2ef51866d157e19245622ba0dcc2a357061134a8a6477001665aa9adb3f5e86   # templates/generated/seeded_rules.metta
SHA_LICENSE=586023696f36ad863849d2b96648022c589acdd12b27c7b15e51356343077d4c  # MIT, (c) 2026 leungmanhin
SHA_PARSER=f976114bc735f507ce7cd334fec2188c93f79e0681aa2dc809c52e2b5b4f899b   # semantic-parse.py (providers)
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
if [ -n "${SEMPARSE_SRC:-}" ]; then SRC="$SEMPARSE_SRC"; else
  git clone -q "$REPO" "$TMP/src"; SRC="$TMP/src"; fi
git -C "$SRC" cat-file -e "$PIN^{commit}" 2>/dev/null || git -C "$SRC" fetch -q origin "$PIN"
mkdir -p "$TMP/out"
git -C "$SRC" archive "$PIN" templates LICENSE semantic-parse.py | tar -x -C "$TMP/out"
echo "$SHA_PROMPT  $TMP/out/templates/generated/PROMPT_CATALOG.txt" | sha256sum -c --quiet
echo "$SHA_SEEDED  $TMP/out/templates/generated/seeded_rules.metta" | sha256sum -c --quiet
echo "$SHA_LICENSE  $TMP/out/LICENSE" | sha256sum -c --quiet
echo "$SHA_PARSER  $TMP/out/semantic-parse.py" | sha256sum -c --quiet
cp "$TMP/out/templates/generated/seeded_rules.metta" "$TMP/out/seeded_rules.metta"   # pc_fullkb / pc_timeout default path
printf 'source=%s\ncommit=%s\nPROMPT_CATALOG.txt=%s\nseeded_rules.metta=%s\nsemantic-parse.py=%s\nlicence=MIT LICENSE=%s\n' \
  "$REPO" "$PIN" "$SHA_PROMPT" "$SHA_SEEDED" "$SHA_PARSER" "$SHA_LICENSE" > "$TMP/out/VERSION"
printf '*\n' > "$TMP/out/.gitignore"          # self-ignoring: never lands in the enclosing repo
mkdir -p "$D"; cp -r "$TMP/out/." "$D/"
echo "semantic-parsing-hitl ${PIN:0:8} -> $D (licence: MIT)"
