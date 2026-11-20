#!/bin/bash
set -e
# Fallback pure-perl install if cpanm unavailable
mkdir -p /tmp/hms && cd /tmp/hms
curl -fsSL https://cpan.metacpan.org/authors/id/R/RO/ROKR/Hash-Merge-Simple-0.051.tar.gz -o hms.tar.gz
tar xzf hms.tar.gz
cd Hash-Merge-Simple-*
mkdir -p /usr/share/perl5/vendor_perl/Hash/Merge
cp lib/Hash/Merge/Simple.pm /usr/share/perl5/vendor_perl/Hash/Merge/Simple.pm
mkdir -p /usr/local/share/perl5/site_perl/Hash/Merge
cp lib/Hash/Merge/Simple.pm /usr/local/share/perl5/site_perl/Hash/Merge/Simple.pm || true
