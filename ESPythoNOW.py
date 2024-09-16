import scapy.all as scapy
import collections
import random
import time
import struct

try:
  from Crypto.Cipher import AES
except:
  pass





class ESPythoNow:

  def __init__(self, interface, mac="", callback=None, accept_broadcast=True, accept_all=False, accept_ack=False, block_on_send=False, pmk="", lmk=""):
    self.interface           = interface                                 # Wireless interface to use
    self.local_mac           = mac.upper()                               # Local ESP-NOW peer MAC, does not need to match actual hw MAC
    self.esp_now_rx_callback = callback                                  # Callback function to execute on packet RX
    self.accept_broadcast    = accept_broadcast                          # Allow incoming ESP-NOW broadcast packets
    self.accept_all          = accept_all                                # Accept ESP-NOW packets, no matter the destination MAC
    self.accept_ack          = accept_ack                                # Pass delivery confirmation to callback
    self.delivery_block      = block_on_send                             # Block on send, wait for delivery or timeout
    self.pmk                 = pmk                                       # Primary Master Key, used to encrypt Local Master Key
    self.lmk                 = lmk                                       # Local Master Key, used to encrypt ESP-NOW messages
    self.key                 = None                                      # The PMK encrypted LMK
    self.encrypted           = False                                     # ESP-NOW messages will be encrypted
    self.delivery_confirmed  = False                                     # Have received a delivery confirmation since the last send
    self.delivery_event      = scapy.threading.Event()                   # Used with block on send
    self.delivery_timeout    = .025                                      # How long to wait for delivery confirmation when blocking
    self.startup_event       = scapy.threading.Event()                   # Used with starting Scapy listener
    self.recent_rand_values  = collections.deque(maxlen=10)              # Ring buffer of recent packet randvalues used to filter packets
    self.listener            = None                                      # Scapy sniffer
    self.l2_socket           = scapy.conf.L2socket(iface=self.interface) # L2 socket, for reuse
    self.packet              = None                                      # Scapy packet of the most recent received valid ESP-NOW message
    self.local_hw_mac        = self.hw_mac_as_str(self.interface)        # Interface's actual HW MAC
    self.block_on_broadcast  = False                                     # Enable block on BROADCAST send, disabled by default. Some ESP-NOW versions will send ACK when receiving BROADCAST
    self.prepared            = False                                     # Required tasks have been completed, or not



  # Required tasks prior to sending or receiving
  def prepare(self):
    if self.prepared:
      return False;

    # Local MAC is not set, default to interface MAC
    if not self.local_mac:
      self.local_mac = self.local_hw_mac

    # If PMK and LMK are valid length, create CCMP key
    if len(self.pmk) == 16 and len(self.lmk) == 16:

      # Check for library required for encrypted ESP-NOW
      try:
        AES
      except:
        print("Error! PyCryptoDome missing, encryption can not be enabled.")
        quit()

      try:
        # Convert PMK and LMK to bytes if needed
        self.pmk = str.encode(self.pmk) if isinstance(self.pmk, str) else self.pmk
        self.lmk = str.encode(self.lmk) if isinstance(self.lmk, str) else self.lmk

        # Create CCM KEY by encrypting LMK with PMK
        self.key = AES.new(self.pmk, AES.MODE_ECB).encrypt(self.lmk)

        self.encrypted = True

      except Exception as e:
        print("Encryption error: %s" % e)
        self.encrypted = False

    # Prepare ahead of time the send packet. Reuses packet for better performance
    self.esp_now_send_packet = scapy.RadioTap() / scapy.Dot11FCS(type=0, subtype=13, addr1=self.local_mac, addr2=self.local_mac, addr3="FF:FF:FF:FF:FF:FF") / scapy.Raw(load=None)

    # Create filter part for local mac
    self_mac_filter = "" if self.accept_all else " and (wlan addr1 %s or wlan addr1 FF:FF:FF:FF:FF:FF)" % self.local_mac

    # Create packet filter
    if self.encrypted:
      # Filter for all managment/action frames. Adds detection of encrypted ESP-NOW messages at the cost of downstream filtering
      self.filter = "((type 0 subtype 0xd0%s) or (type 4 subtype 0xd0 and wlan addr1 %s)) and wlan src ! %s" % (self_mac_filter, self.local_mac, self.local_mac)
    else:
      # Filter for all unencrypted ESP-NOW messages and ESP-NOW ACK
      self.filter = "((type 0 subtype 0xd0 and wlan[24:4]=0x7f18fe34%s) or (type 4 subtype 0xd0 and wlan addr1 %s)) and wlan src ! %s" % (self_mac_filter, self.local_mac, self.local_mac)

    self.prepared = True



  # Start listening for ESP-NOW packets
  def start(self):
    self.prepare()

    self.startup_event.clear()

    self.listener = scapy.AsyncSniffer(iface=self.interface, prn=self.parse_rx_packet, filter=self.filter, started_callback=lambda: self.startup_event.set())
    self.listener.start()

    if self.startup_event.wait(timeout=1):
      return True
    else:
      print("Error starting listener")
      return False



  # Process incoming ESP-NOW packets
  def parse_rx_packet(self, packet):
    is_ack   = (packet.type==1 and packet.subtype==13) # Packet is a delivery confirmation
    from_mac = "" if is_ack else packet.addr2.upper()  # Source MAC
    to_mac   = packet.addr1.upper()                    # Destination MAC
    allow    = False                                   # Deny packet flag

    # Allow all ESP-NOW UNICAST packets
    if self.accept_all and not is_ack:
      allow = True

    # Allow ESP-NOW BROADCAST packets
    elif self.accept_broadcast and self.is_broadcast(to_mac):
      allow = True

    # Allow ESP-NOW packet sent to local_mac
    elif to_mac == self.local_mac:
      allow = True

    # Deny if not accepting packets sent to non local_mac
    if (not self.accept_all and to_mac != self.local_mac) and (not self.accept_broadcast and self.is_broadcast(to_mac)):
      allow = False

    # Deny if not accepting BROADCAST and packet is BROADCAST
    if not self.accept_broadcast and self.is_broadcast(to_mac):
      allow = False

    # Ignore packet
    if not allow:
      return

    # Store most recent packet
    self.packet = packet

    # Packet is ACK, delivery confirmation from remote peer
    if is_ack:
      self.delivery_confirmed = True

      # Execute RX callback for ACK
      if self.accept_ack and callable(self.esp_now_rx_callback):
        self.esp_now_rx_callback(False, to_mac, "ack")

      # Clear delivery confirmation flag
      self.delivery_event.set()

    # Packet is ESP-NOW message
    else:

      # ESP-NOW message is encrypted
      if scapy.Dot11CCMP in packet:

        # If decryption keys present
        if self.encrypted:
          nonce = b'\x00'+bytes.fromhex(from_mac.replace(':',''))+struct.pack("BBBBBB",packet.PN5,packet.PN4,packet.PN3,packet.PN2,packet.PN1,packet.PN0)
          data = AES.new(self.key, AES.MODE_CCM, nonce, mac_len=8).decrypt(packet.data[:-8])

          # Check if decryption succeded
          if not data.startswith(b"\x7f\x18\xfe\x34"):
            print("Decryption Failed")
            data = b"%sEncrypted Message" % random.randbytes(15)

        # No decryption keys present
        else:
          data = b"%sEncrypted Message" % random.randbytes(15)

      # ESP-NOW message is plaintext
      else:
        data = packet["Raw"].load

      # Check packets random values to filter resent messages
      if data[4:8] in self.recent_rand_values:
        return
      else:
        self.recent_rand_values.append(data[4:8])

      # Execute RX callback for message
      if callable(self.esp_now_rx_callback):
        self.esp_now_rx_callback(from_mac, to_mac, data[15:])



  # Send ESP-NOW message(s) to MAC
  def send(self, mac, msg, block=None, delay=0):
    self.prepare()

    # block argument overrides global delivery_block setting
    if not isinstance(block, bool):
      block = self.delivery_block

    if not isinstance(msg, list):
      msg = [msg]

    returns = []

    for msg_ in msg:
      # Prepare for delivery confirmation
      self.delivery_confirmed = False
      self.delivery_event.clear()

      # Construct packet
      data = b"\x7f\x18\xfe\x34%s\xDD%s\x18\xfe\x34\x04\x01%s" % (random.randbytes(4), (5+len(msg_)).to_bytes(1, 'big'), msg_)

      # ESP-NOW message will be sent encrypted
      if self.encrypted:
        print("Sending encrypted ESP-NOW messages is not supported at this time.")
        print("See https://github.com/ChuckMash/ESPythoNOW/issues/1")
        return False

      # ESP-NOW message will be sent in plaintext
      else:
        self.esp_now_send_packet.addr1 = mac
        self.esp_now_send_packet.load = data

      # Send ESP-NOW packet
      self.l2_socket.send(self.esp_now_send_packet)

      # Wait for delivery confirmation from remote peer or timeout
      if (block and not self.is_broadcast(mac)) or (block and self.block_on_broadcast and self.is_broadcast(mac)):
        returns.append(self.delivery_event.wait(timeout=self.delivery_timeout))

      # Additional delay after sending each ESP-NOW packet
      if delay:
        time.sleep(delay)

    return all(returns)



  # Provided MAC matches ESP-NOW BROADCAST address
  def is_broadcast(self, mac):
    return mac == "FF:FF:FF:FF:FF:FF"



  # Return interface's HW MAC. "XX:XX:XX:XX:XX:XX"
  def hw_mac_as_str(self, interface):
    return ("%02X:" * 6)[:-1] % tuple(scapy.orb(x) for x in scapy.get_if_raw_hwaddr(self.l2_socket.iface)[1])
