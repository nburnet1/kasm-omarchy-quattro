#!/bin/bash
set -e
python3 - <<'PYTHON'
from pathlib import Path
p = Path('/home/nburnet1/kasm-omarchy-quattro/Dockerfile')
s = p.read_text()
old = '''      python python-pip cpanminus \\
    && /usr/bin/vendor_perl/cpanm --notest Hash::Merge::Simple \\
    && cp -a /usr/local/share/perl5/site_perl/Hash /usr/share/perl5/vendor_perl/ 2>/dev/null || true \\
    && pacman -Scc --noconfirm'''
new = '''      python python-pip perl-clone \\
    && mkdir -p /tmp/hms && cd /tmp/hms \\
    && curl -fsSL https://cpan.metacpan.org/authors/id/R/RO/ROKR/Hash-Merge-Simple-0.051.tar.gz -o hms.tar.gz \\
    && tar xzf hms.tar.gz && cd Hash-Merge-Simple-* \\
    && mkdir -p /usr/share/perl5/vendor_perl/Hash/Merge /usr/share/perl5/site_perl/Hash/Merge \\
    && cp lib/Hash/Merge/Simple.pm /usr/share/perl5/vendor_perl/Hash/Merge/Simple.pm \\
    && cp lib/Hash/Merge/Simple.pm /usr/share/perl5/site_perl/Hash/Merge/Simple.pm \\
    && cd / && rm -rf /tmp/hms \\
    && pacman -Scc --noconfirm'''
if old not in s:
    print('block not found')
    exit(1)
s = s.replace(old,new)
p.write_text(s)
print('patched')
PYTHON
