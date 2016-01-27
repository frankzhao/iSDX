#!/usr/bin/env bash
# Install newer kernel for mininet
rpm --import https://www.elrepo.org/RPM-GPG-KEY-elrepo.org
rpm -Uvh http://www.elrepo.org/elrepo-release-7.0-2.el7.elrepo.noarch.rpm

--- REBOOT ---

git clone https://github.com/frankzhao/mininet
cd mininet
util/install.sh
