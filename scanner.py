#UDP Sniffer

import socket
import os
import struct
from ctypes import *
import threading
import time
from netaddr import IPNetwork,IPAddress

#host to listen on
host = "10.1.10.103"

#subnet to target
subnet = "10.1.10.0/24"

#magic string to check ICMP responses for
magic_message = "xyzzy"

def udp_sender(subnet,magic_message):
    time.sleep(5)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for ip in IPNetwork(subnet):
        try:
            sender.sendto(magic_message,("%s" % ip,65212))
        except:
            pass
#IP header
class IP(Structure):
    _fields_ = [
        ("ihl",c_ubyte, 4),
        ("version",c_ubyte, 4),
        ("tos",c_ubyte),
        ("len",c_ushort),
        ("id",c_ushort),
        ("offset",c_ushort),
        ("ttl",c_ubyte),
        ("protocol_num",c_ubyte),
        ("sum",c_ushort),
        ("src",c_ulong),
        ("dst",c_ulong)
        ]
    
    def __new__(self,socket_buffer=None):
        return self.from_buffer_copy(socket_buffer)
    
    def __init__(self, socket_buffer=None):
        
        #map protocol constants to names
        self.protocol_map = {1:"ICMP",6:"TCP",17:"UDP"}
        
        #human readable IP addresses
        self.src_address = socket.inet_ntoa(struct.pack("<L",self.src))
        self.dst_address = socket.inet_ntoa(struct.pack("<L",self.dst))
        
        #human readable protocol
        try:
            self.protocol = self.protocol_map[self.protocol_num]
        except:
            self.protocol = str(self.protocol_num)
            
class ICMP(Structure):
    _fields_ = [
        ("type", c_ubyte),
        ("code", c_ubyte),
        ("checksum", c_ushort),
        ("unused", c_ushort),
        ("next_hop_mtu", c_ushort)
        ]
    
    def __new__(self,socket_buffer):
        return self.from_buffer_copy(socket_buffer)
    def __init__(self, socket_buffer):
        pass

#create raw socket and bind to public interface
if os.name == "nt":
    socket_protocol = socket.IPPROTO_IP
else:
    socket_protocol = socket.IPPROTO_ICMP
    
sniffer = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket_protocol)
sniffer.bind((host,0))

#include IP headers
sniffer.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)

#if windows, set up promiscuous mode
if os.name == "nt":
    sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
    
#start sending packets
t = threading.Thread(target=udp_sender,args=(subnet,magic_message))
t.start()
try:
    while True:
        #read in packet
        raw_buffer = sniffer.recvfrom(65565)[0]
        #create IP header from first 20 bytes
        ip_header = IP(raw_buffer[0:20])
        #print out detected protocol and hosts
        print "Protocol: %s %s -> %s" % (ip_header.protocol, ip_header.src_address, ip_header.dst_address)
        
        #if it's ICMP, get it
        if ip_header.protocol == "ICMP":
            #calc where ICMP packet starts
            offset = ip_header.ihl*4
            buf = raw_buffer[offset:offset+sizeof(ICMP)]
            #create ICMP struct
            icmp_header = ICMP(buf)
            print "ICMP -> Type %d Code: %d" % (icmp_header.type, icmp_header.code)
            #check for Type 3 and CODE
            if icmp_header.code == 3 and icmp_header.type == 3:
                #check in target subnet
                if IPAddress(ip_header.src_address) in IPNetwork(subnet):
                    #check for magic message
                    if raw_buffer[len(raw_buffer)-len(magic_message):]==magic_message:
                        print "Host Up: %s" % ip_header.src_address
    #handle CTRL-C
except KeyboardInterrupt:
#if windows, turn off promiscuous mode
    if os.name == "nt":
        sniffer.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
