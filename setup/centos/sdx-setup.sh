yum -y install quagga help2man python-setuptools

# Quagga config
setsebool -P zebra_write_config 1
systemctl start zebra
systemctl enable zebra
systemctl start bgpd
systemctl enable bgpd
systemctl enable zebra.service
systemctl enable ripd.service

echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf
sysctl -p /etc/sysctl.conf

cat << EOF > /etc/quagga/zebra.conf
hostname localhost.localdomain
password zebra
enable password zebra
EOF

git clone https://github.com/USC-NSL/miniNExT.git miniNExT/
cd miniNExT
git checkout 1.4.0
make install

pip install requests

sudo chmod 755 xrs/client.py xrs/route_server.py
mkdir xrs/ribs
pip install -U exabgp
