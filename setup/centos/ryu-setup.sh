#!/usr/bin/env bash
yum -y install python-routes python-devel
pip install oslo.config==3.0.0 msgpack-python eventlet webob

git clone git://github.com/osrg/ryu.git
cp ./ryu-flags.py ryu/ryu/flags.py
cd ryu
python ./setup.py install