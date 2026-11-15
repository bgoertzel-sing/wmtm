#!/usr/bin/env bash
# Fetch leungmanhin/semantic-parsing-hitl pinned by commit (default f44d7b74, P4 re-pin) into DEST
# (default: <repo>/.semparse-hitl, gitignored).  Upstream is MIT-licensed at these pins; LICENSE is copied
# alongside and checked.  Copies templates/ (tmpl, catalog, generated/PROMPT_CATALOG.txt, rules.yaml), semantic-parse.py
# (the upstream providers, used by wmtm.semparse_provider / tools/measure_parse.py) + LICENSE,
# verifies sha256 of the catalog prompt, the seeded rules, semantic-parse.py and LICENSE, and writes VERSION (commit=<pin>), which
# wmtm.semparse_catalog checks before importing anything (wrong pin / missing licence -> refuse).
#   usage: fetch_semparse_hitl.sh [DEST] [PIN]   (SEMPARSE_SRC=<existing clone> skips the network fetch)
# PIN (or env SEMPARSE_PIN; short or full): f44d7b74 (default; catalog mode) or 24e37182 (Man Hin 2026-11-12, the
# sentence-by-sentence mode: semparse_mode sentence and the master-parser path; also checks
# seeded_rules.pettachainer-master.metta).  t-2026-11-15-wmtm-sentence-feed: before, the pin and its checksums were
# hard-coded to f44d7b74, so a 24e37182 fetch failed its sha checks.  An unknown pin is refused before any fetch.
set -euo pipefail
W="$(cd "$(dirname "$0")/.." && pwd)"; D="${1:-$W/.semparse-hitl}"
REPO=https://github.com/leungmanhin/semantic-parsing-hitl
WANT="${2:-${SEMPARSE_PIN:-f44d7b74}}"
SHA_LICENSE=586023696f36ad863849d2b96648022c589acdd12b27c7b15e51356343077d4c  # MIT, (c) 2026 leungmanhin
SHA_MASTER=""                                                                  # seeded_rules.pettachainer-master.metta (24e37182 only)
case "$WANT" in
  f44d7b74|f44d7b740aed240c834165672b6a862998ee4a12)
    PIN=f44d7b740aed240c834165672b6a862998ee4a12
    SHA_PROMPT=645bff3f5c3a0670d98a463d60d18e178d899c08c58f17ea4b3ff5a53b1d25b6   # templates/generated/PROMPT_CATALOG.txt
    SHA_SEEDED=c2ef51866d157e19245622ba0dcc2a357061134a8a6477001665aa9adb3f5e86   # templates/generated/seeded_rules.metta
    SHA_PARSER=f976114bc735f507ce7cd334fec2188c93f79e0681aa2dc809c52e2b5b4f899b   # semantic-parse.py (providers)
    ;;
  24e37182|24e37182e64a20981d423ed1d851da6de5e3b3e8)
    PIN=24e37182e64a20981d423ed1d851da6de5e3b3e8
    SHA_PROMPT=257425b2c1593569789317f0f007f57f21f856df868b382adc0880c1c3414809   # = semparse_catalog ALLOWED_PINS[24e37182]
    SHA_SEEDED=2ade9354bbf5ec2da2847cb114efc26a25d2ffe95f3d6a6d6ea0bf4d10fedb03
    SHA_PARSER=cb5e15c17d92f4ab889e5b9409a7c4e2c8d672e49d388ae7e740a613a59e8e5e   # has chat-completions + the sentence context
    SHA_MASTER=9c58f2e01f8db9a67553e3b5985de107d1bd5941b2ecb65337d45b4d0c2b0454   # 280 rules (master_loader.seeded_rules)
    ;;
  *) echo "fetch_semparse_hitl.sh: unknown pin '$WANT' (known: f44d7b74, 24e37182)" >&2; exit 2 ;;
esac
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
if [ -n "$SHA_MASTER" ]; then
  echo "$SHA_MASTER  $TMP/out/templates/generated/seeded_rules.pettachainer-master.metta" | sha256sum -c --quiet; fi
cp "$TMP/out/templates/generated/seeded_rules.metta" "$TMP/out/seeded_rules.metta"   # pc_fullkb / pc_timeout default path
printf 'source=%s\ncommit=%s\nPROMPT_CATALOG.txt=%s\nseeded_rules.metta=%s\nsemantic-parse.py=%s\nlicence=MIT LICENSE=%s\n' \
  "$REPO" "$PIN" "$SHA_PROMPT" "$SHA_SEEDED" "$SHA_PARSER" "$SHA_LICENSE" > "$TMP/out/VERSION"
if [ -n "$SHA_MASTER" ]; then
  printf 'seeded_rules.pettachainer-master.metta=%s\n' "$SHA_MASTER" >> "$TMP/out/VERSION"; fi
printf '*\n' > "$TMP/out/.gitignore"          # self-ignoring: never lands in the enclosing repo
mkdir -p "$D"; cp -r "$TMP/out/." "$D/"
echo "semantic-parsing-hitl ${PIN:0:8} -> $D (licence: MIT)"
