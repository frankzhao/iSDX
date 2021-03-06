#!/usr/bin/env python
#  Author:
#  Rudiger Birkner (Networked Systems Group ETH Zurich)
#  Arpit Gupta (Princeton)


import argparse
import json
from multiprocessing.connection import Listener, Client
from netaddr import IPNetwork, IPAddress
import os
import socket
import struct
from threading import Thread

import sys
np = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
if np not in sys.path:
    sys.path.append(np)
import util.log

from utils import parse_packet, craft_arp_packet, craft_eth_frame, craft_garp_response


logger = util.log.getLogger('arp')

ETH_BROADCAST = 'ff:ff:ff:ff:ff:ff'
ETH_TYPE_ARP = 0x0806


class ArpProxy(object):

    def __init__(self, config_file):
        self.run = True
        self.host = None
        self.raw_socket = None
        self.listener_garp = None
        self.garp_socket = None
        self.interface = None

        self.participants = {}
        self.portmac_2_participant = {}

        self.vnhs = None

        # info about non-sdn participants
        # TODO: Create a mapping between actual interface IP addresses
        # and the corresponding MAC addresses for all the non-SDN participants
        # In case of MDS, it is actual mac adresses of these interfaces, in case
        # of the superset scheme it is : 1XXXX-nexthop_id
        self.nonSDN_nhip_2_nhmac = {}

        self.parse_arpconfig(config_file)

        # Set various listeners
        self.set_arp_listener()
        self.set_garp_listener()


    def parse_arpconfig(self, config_file):
        "Parse the config file to extract eh_sockets and portmac_2_participant"
        with open(config_file, 'r') as f:
            config = json.load(f)

            self.vnhs = IPNetwork(config["VNHs"])

            tmp = config["ARP Proxy"]["GARP_SOCKET"]
            self.garp_socket = tuple([tmp[0], int(tmp[1])])

            self.interface = config["ARP Proxy"]["Interface"]

            for participant_id in config["Participants"]:
                participant = config["Participants"][participant_id]

                participant_id = int(participant_id)

                self.participants[participant_id] = {}
                # Create Persistent Client Object
                addr, port = participant["EH_SOCKET"]
                self.participants[participant_id]["eh_socket"] = (addr, int(port))
                for port in participant["Ports"]:
                    self.portmac_2_participant[port['MAC']] = participant_id


    def set_arp_listener(self):
        # Set listener for ARP requests from IXP Fabric
        self.host = socket.gethostbyname(socket.gethostname())

        try:
            self.raw_socket = socket.socket( socket.AF_PACKET , socket.SOCK_RAW , socket.ntohs(ETH_TYPE_ARP))
            self.raw_socket.bind((self.interface, 0))
            self.raw_socket.settimeout(1.0)
        except socket.error as msg:
            logger.exception('Failed to create socket. Error Code : ' + str(msg[0]) + ' Message ' + msg[1])
            raise


    def start_arp_listener(self):

        while self.run:
            # receive arp requests
            try:
                packet, addr = self.raw_socket.recvfrom(65565)
                eth_frame, arp_packet = parse_packet(packet)

                arp_type = struct.unpack("!h", arp_packet["oper"])[0]
                logger.debug("Received ARP-" + ("REQUEST" if (arp_type == 1) else "REPLY") +" SRC: "+eth_frame["src_mac"]+" / "+arp_packet["src_ip"]+" "+"DST: "+eth_frame["dst_mac"]+" / "+arp_packet["dst_ip"])

                if arp_type == 1:
                    # check if the arp request stems from one of the participants
                    requester_srcmac = eth_frame["src_mac"]
                    requested_ip = arp_packet["dst_ip"]
                    # Send the ARP request message to respective controller and forget about it
                    if IPAddress(requested_ip) in self.vnhs:
                        self.send_arp_request(requester_srcmac, requested_ip)
    
                        # TODO: If the requested IP address belongs to a non-SDN participant
                        # then refer the structure `self.nonSDN_nhip_2_nhmac` and
                        # send an immediate ARP response.
                        """
                        response_vmac = self.get_vmac_default(requester_srcmac, requested_ip)
                        if response_vmac != "":
                            logger.debug("ARP-PROXY: reply with VMAC "+response_vmac)

                            data = self.craft_arp_packet(arp_packet, response_vmac)
                            eth_packet = self.craft_eth_frame(eth_frame, response_vmac, data)
                            self.raw_socket.send(''.join(eth_packet))
                        """

            except socket.timeout:
                # prints about once per second
                #logger.debug('Socket Timeout Occured')
                pass


    def set_garp_listener(self):
        "Set listener for ARP replies from the participants' controller"
        logger.info("Starting the ARP  listener")
        self.listener_garp = Listener(self.garp_socket, authkey=None)
        ps_thread = Thread(target=self.start_garp_handler)
        ps_thread.daemon = True
        ps_thread.start()


    def start_garp_handler(self):
        logger.info("ARP Response Handler started")
        while True:
            conn_ah = self.listener_garp.accept()
            logger.info("Connection from a pctrl accepted.")
            tmp = conn_ah.recv()
            self.process_garp(json.loads(tmp))
            reply = "Gratuitous ARP response processed"
            conn_ah.send(reply)
            conn_ah.close()


    def process_garp(self, data):
        """
        Process the incoming ARP data from the Participant Controller:
        -Format ARP Reply:
            eth_src = VMAC, eth_dst = requester_mac, 
            SHA = VMAC, SPA = vnhip, 
            THA = requester_mac, TPA = requester_ip

        -Format Gratuitous ARP:
            eth_src = VMAC, eth_dst = 00..00<part_id>, 
            SHA = VMAC, SPA = vnhip, 
            THA = VMAC, TPA = vnhip
        """
        if data["THA"] == data["eth_dst"]:
            logger.debug("ARP Reply relayed: "+str(data))
        else:
            logger.debug("Gratuitous ARP relayed: "+str(data))

        garp_message = craft_garp_response(**data)
        self.raw_socket.send(garp_message)


    def send_arp_request(self, requester_srcmac, requested_ip):
        "Get the VMAC for the arp request message"
        if requester_srcmac in self.portmac_2_participant:
            requester_id = self.portmac_2_participant[requester_srcmac]
            if requester_id in self.participants:
                # ARP request is sent by participant with its own SDN controller
                logger.debug("relay ARP-REQUEST to participant "+str(requester_id))
                eh_socket = Client(self.participants[requester_id]["eh_socket"])
                data = {}
                data['arp'] = [requester_srcmac, requested_ip]
                eh_socket.send(json.dumps(data))
                recv = eh_socket.recv()
                eh_socket.close()
                return recv


    def get_vmac_default(self, requester_id):
        " Keep track of VMACs to be returned for non SDN participants"
        # TODO: Complete the logic for this function
        # TODO: We can create these mappings during init itself
        return ''


    def stop(self):
        self.run = False
        self.raw_socket.close()
        self.listener_garp.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', help='the directory of the example')
    args = parser.parse_args()

    # locate config file
    base_path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)),"..","examples",args.dir,"config"))
    config_file = os.path.join(base_path, "sdx_global.cfg")

    logger.info("Launching ARP Proxy with config file "+str(config_file))

    # start arp proxy
    sdx_ap = ArpProxy(config_file)
    ap_thread = Thread(target=sdx_ap.start_arp_listener)
    ap_thread.daemon = True
    ap_thread.start()


    while ap_thread.is_alive():
        try:
            ap_thread.join(1)
        except KeyboardInterrupt:
            sdx_ap.stop()


if __name__ == '__main__':
    main()
