#!/bin/bash
# copy every pc_shadow spec_c*.json of every arm into /tmp/gfr/specs/<arm>/ before the 1 h cleanup removes it
while ! grep -q "CHAIN_UNSEEDED_DONE" /tmp/gfr/NOTES.txt; do
  for f in /tmp/gfr/loop/*/state/runtime/pc_shadow/spec_c*.json; do
    [ -f "$f" ] || continue; arm=$(echo $f | sed 's#/tmp/gfr/loop/\([^/]*\)/.*#\1#'); mkdir -p /tmp/gfr/specs/$arm
    [ -f /tmp/gfr/specs/$arm/$(basename $f) ] || cp "$f" /tmp/gfr/specs/$arm/ 2>/dev/null
  done; sleep 1
done
echo "$(date -Is) KEEP_SPECS_DONE" >> /tmp/gfr/NOTES.txt
