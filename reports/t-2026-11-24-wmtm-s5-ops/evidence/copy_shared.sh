#!/bin/bash
set -u
S=/srv/hive-evidence/shared
mkdir -p $S
: > /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
mkdir -p $S/npl-store && cp -r --preserve=timestamps /tmp/npl/store/. $S/npl-store/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/frozen_parses-store && cp -r --preserve=timestamps /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/store/. $S/frozen_parses-store/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/frozen_parses-raw && cp -r --preserve=timestamps /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/raw/. $S/frozen_parses-raw/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/frozen_parses-inputs && cp -r --preserve=timestamps /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs/. $S/frozen_parses-inputs/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/frozen_parses-notes && cp -r --preserve=timestamps /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/notes/. $S/frozen_parses-notes/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/sp2 && cp -r --preserve=timestamps /home/openclaw/scratch/sp2/. $S/sp2/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/p3_out-ab && cp -r --preserve=timestamps /tmp/p3_out/ab/. $S/p3_out-ab/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/p3_out-bparse && cp -r --preserve=timestamps /tmp/p3_out/bparse/. $S/p3_out-bparse/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/mav2-sent-s1 && cp -r --preserve=timestamps /tmp/mav2/sent/s1/. $S/mav2-sent-s1/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
mkdir -p $S/clerk-ab-scratch && cp -r --preserve=timestamps /home/openclaw/work/t-2026-11-18-wmtm-clerk-ab/scratch/. $S/clerk-ab-scratch/ 2>>/srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.err
chmod -R g+rX,o-rwx $S
cd $S && find . -type f ! -name SHA256SUMS | sort | xargs -d '\n' sha256sum > SHA256SUMS && sha256sum -c --quiet SHA256SUMS && echo COPY_VERIFY_OK $(wc -l < SHA256SUMS) > /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.out
(cd /tmp/npl/store && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./npl-store/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/store && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./frozen_parses-store/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/raw && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./frozen_parses-raw/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/inputs && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./frozen_parses-inputs/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /home/openclaw/research-agent/projects/omegaclaw/frozen_parses/notes && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./frozen_parses-notes/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /home/openclaw/scratch/sp2 && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./sp2/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /tmp/p3_out/ab && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./p3_out-ab/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /tmp/p3_out/bparse && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./p3_out-bparse/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /tmp/mav2/sent/s1 && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./mav2-sent-s1/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
(cd /home/openclaw/work/t-2026-11-18-wmtm-clerk-ab/scratch && find . -type f | sort | xargs -d '\n' sha256sum | sed 's#  \./#  ./clerk-ab-scratch/#') >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums
cd $S && diff <(sort -k2 /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig.sums) <(sort -k2 SHA256SUMS) > /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/orig_vs_copy.diff && echo ORIG_EQ_COPY >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.out || echo ORIG_DIFFERS >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.out
echo DONE >> /srv/hive-evidence/t-2026-11-24-wmtm-s5-ops/copy.out
