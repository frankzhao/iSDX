#!/usr/bin/env bash

# Add MongoDB repository
cat << EOF > /etc/yum.repos.d/mongodb-org-3.2.repo
[mongodb-org-3.2]
name=MongoDB Repository
baseurl=https://repo.mongodb.org/yum/redhat/$releasever/mongodb-org/3.2/x86_64/
gpgcheck=0
enabled=1
EOF

# Install dependencies
yum -y install epel-release
yum -y update
yum -y install autoconf automake openssl-devel graphviz \
	python python-devel python-qt4 python-twisted-conch \
	libtool python-pip git tmux vim python-paramiko \
	python-sphinx sshfs perl-String-CRC32 mongodb-org \
	mongodb-org-server

pip install twisted alabaster pymongo

mkdir ~/bin/
echo "sudo mn -c; sudo mn --topo single,3 --mac --switch ovsk --controller remote" > ~/bin/mininet.sh
chmod 755 ~/bin/mininet.sh

systemctl start mongod
