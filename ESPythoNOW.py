import scapy.all as scapy
import collections
import random
import time





class ESPythoNow:



  def __init__(self, interface, mac, accept_broadcast=True, accept_all=False, callback=None):
    self.interface           = interface
    self.mac                 = mac
    self.accept_broadcast    = accept_broadcast
    self.accept_all          = accept_all
    self.esp_now_rx_callback = callback
    self.recent_rand_values  = collections.deque(maxlen=10)
    self.listener            = None

  def start(self):
    self.listener = scapy.AsyncSniffer(iface=self.interface, prn=self.parse_rx_packet, filter="type 0 subtype 0xd0 and wlan[24:4]=0x7f18fe34 and wlan src ! %s" % self.mac)
    self.listener.start()



  # Process incoming ESP-NOW messages
  def parse_rx_packet(self, packet):

    from_mac = packet.addr2.upper()
    to_mac   = packet.addr1.upper()

    allow = False

    if self.accept_all:
      allow = True

    elif self.accept_broadcast and to_mac == "FF:FF:FF:FF:FF:FF":
      allow = True

    elif to_mac == self.mac:
      allow = True

    else:
      allow = False

    if not allow:
      return


    # Get raw ESP-NOW packet
    data = packet["Raw"].load

    # Check packets random values to weed out resent messages
    if data[4:8] in self.recent_rand_values:
      return
    else:
      self.recent_rand_values.append(data[4:8])

    # Execute RX callback
    if callable(self.esp_now_rx_callback):
      self.esp_now_rx_callback(from_mac, to_mac, data[15:])



  # Send ESP-NOW message to MAC
  def send(self, mac, msg):
    dot11 = scapy.Dot11FCS(type=0, subtype=13, addr1=mac, addr2=self.mac, addr3=mac);
    load = b"\x7f\x18\xfe\x34%s\xDD%s\x18\xfe\x34\x04\x01%s" % (random.randbytes(4), (5+len(msg)).to_bytes(1,'big'), msg)
    frame = scapy.RadioTap() / dot11 / scapy.Raw(load=load) / scapy.Dot11Elt(ID='Rates', info='\x82\x84\x8b\x96\x0c\x12\x18')
    scapy.sendp(frame, iface=self.interface, verbose=False)



  # Send ESP-NOW message confirmation packet. Does not work
  #def send_ack(self, mac):
  #  dot11 = scapy.Dot11FCS(type=1, subtype=13, addr1=mac, addr2=self.mac, addr3=mac);
  #  frame = scapy.RadioTap() / dot11 / scapy.Dot11Elt(ID='Rates', info='\x82\x84\x8b\x96\x0c\x12\x18')
  #  scapy.sendp(frame, iface=self.interface, verbose=False)
