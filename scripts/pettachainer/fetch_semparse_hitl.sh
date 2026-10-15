#!/usr/bin/env bash
# Fetch leungmanhin/semantic-parsing-hitl pinned by commit into gitignored .semparse-hitl/ (never committed).
# Verifies sha256 of prompt.txt + seeded_rules.metta; reports licence status.
set -euo pipefail
W="$(cd "$(dirname "$0")/../.." && pwd)"; D="$W/.semparse-hitl"
REPO=https://github.com/leungmanhin/semantic-parsing-hitl
PIN=3ec15bd1f53ede63f3333dbb5092f13413ceda3e
SHA_PROMPT=2ed18b934e28afac75b1d6c7c47b7b7413ed778c4c2916441274fb42933d9d1e
SHA_SEEDED=b7e25b96347848cc86b156dfa6294e0d8eb08c247bf66651631be2ced22a7078
[ -d "$D/.git" ] || git clone -q "$REPO" "$D"
git -C "$D" fetch -q origin "$PIN" 2>/dev/null || git -C "$D" fetch -q origin
git -C "$D" checkout -q --detach "$PIN"
echo "$SHA_PROMPT  $D/prompt.txt" | sha256sum -c --quiet
echo "$SHA_SEEDED  $D/seeded_rules.metta" | sha256sum -c --quiet
if git -C "$D" ls-files | grep -qiE '^(licen[cs]e|copying)'; then echo "licence file: present"; else echo "licence: NONE at $PIN (public repo, no LICENSE; GitHub license=null) - do not redistribute"; fi
echo "export SEMPARSE_PROMPT=$D/prompt.txt SEMPARSE_SEEDED=$D/seeded_rules.metta"
