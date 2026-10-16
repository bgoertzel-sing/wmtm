#!/usr/bin/env bash
# Fetch leungmanhin/semantic-parsing-hitl pinned by commit and copy prompt.txt + seeded_rules.metta into DEST
# (default: <repo>/.semparse-hitl, gitignored).  NEVER commit the result: the upstream repo has no licence at this
# commit, so it is not redistributed.  Verifies sha256 of both files.
#   usage: fetch_semparse_hitl.sh [DEST]       (SEMPARSE_SRC=<existing clone> skips the network fetch)
set -euo pipefail
W="$(cd "$(dirname "$0")/.." && pwd)"; D="${1:-$W/.semparse-hitl}"
REPO=https://github.com/leungmanhin/semantic-parsing-hitl
PIN=3ec15bd1f53ede63f3333dbb5092f13413ceda3e
SHA_PROMPT=2ed18b934e28afac75b1d6c7c47b7b7413ed778c4c2916441274fb42933d9d1e
SHA_SEEDED=b7e25b96347848cc86b156dfa6294e0d8eb08c247bf66651631be2ced22a7078
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
if [ -n "${SEMPARSE_SRC:-}" ]; then SRC="$SEMPARSE_SRC"; else
  git clone -q "$REPO" "$TMP/src"; SRC="$TMP/src"; fi
git -C "$SRC" cat-file -e "$PIN^{commit}" 2>/dev/null || git -C "$SRC" fetch -q origin "$PIN"
mkdir -p "$TMP/out"
git -C "$SRC" show "$PIN:prompt.txt" > "$TMP/out/prompt.txt"
git -C "$SRC" show "$PIN:seeded_rules.metta" > "$TMP/out/seeded_rules.metta"
echo "$SHA_PROMPT  $TMP/out/prompt.txt" | sha256sum -c --quiet
echo "$SHA_SEEDED  $TMP/out/seeded_rules.metta" | sha256sum -c --quiet
if git -C "$SRC" ls-tree --name-only "$PIN" | grep -qiE '^(licen[cs]e|copying)'; then lic=present; else lic="NONE (do not redistribute)"; fi
printf 'source=%s\ncommit=%s\nprompt.txt=%s\nseeded_rules.metta=%s\nlicence=%s\n' "$REPO" "$PIN" "$SHA_PROMPT" "$SHA_SEEDED" "$lic" > "$TMP/out/VERSION"
printf '*\n' > "$TMP/out/.gitignore"          # self-ignoring: never lands in the enclosing repo
mkdir -p "$D"; cp "$TMP/out/prompt.txt" "$TMP/out/seeded_rules.metta" "$TMP/out/VERSION" "$TMP/out/.gitignore" "$D/"
echo "semantic-parsing-hitl ${PIN:0:8} -> $D (licence: $lic)"
