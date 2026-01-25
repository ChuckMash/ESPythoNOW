import scapy.all as scapy
import collections
import random
import time
import struct
import sys
import json
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
    self.message_signatures  = []                                        # Hold message signatures




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
          # Message may never reach here due to scapy filtering rules
          data = b"%sEncrypted Message" % random.randbytes(15)

      # ESP-NOW message is plaintext
      else:
        data = packet["Raw"].load

      # Check if vendor category code has been stripped. Due to cooked mode host network mode passthrough removing this byte?
      if data[0] != 0x7f:
        data = b"\x7f" + data

      # Check packets random values to filter resent messages
      if data[4:8] in self.recent_rand_values:
        return
      else:
        self.recent_rand_values.append(data[4:8])

      # Parse messages from packet, v1.0 and v2.0
      msg = b''.join([data[15:][i:i + 250] for i in range(0, len(data[15:]), 257)])

      # Check if there is a signature based callback
      sig = self.identify_signatures(msg)

      if sig:
        # Filter duplicate messsages, different than filtering resent messages
        if "recent" in sig:
          if msg in sig["recent"]:
            return
          sig["recent"].append(msg)

        # Execute the specific callback tied to the message signature
        if "callback" in sig and callable(sig["callback"]):

          # Send the hex message data to the signature callback
          if sig["data"]=="hex":
            sig["callback"](from_mac, to_mac, msg.hex(" "))

          # Send the dict parsed data to the signature callback
          elif sig["data"]=="dict":
            sig["callback"](from_mac, to_mac, self.parse_signature_data(sig, msg))

          # Send the dict parsed data to the signature callback as a json string
          elif sig["data"]=="json":
            sig["callback"](from_mac, to_mac, json.dumps(self.parse_signature_data(sig, msg)))

          # Send the raw message data to the signature callback
          else:
            sig["callback"](from_mac, to_mac, msg)

      # Execute RX generic callback for message
      elif callable(self.esp_now_rx_callback):
        self.esp_now_rx_callback(from_mac, to_mac, msg)



  # Identify the message signature
  def identify_signatures(self, data):

    # Loop through each stored signature
    for dev in self.message_signatures:
      sig = dev["signature"]

      # Check messsage length if it exists
      if "length" in sig and len(data) != sig["length"]:
        continue

      # Check known byte locations and values
      if "bytes" in sig:
        reject = False
        for k,v in sig["bytes"].items():
          if data[k] != v:
            reject = True
        if reject:
          continue
      return dev



  # Takes the signature data and creates a dictionary of the parsed data to send to callback
  def parse_signature_data(self, sig, msg):
    data = dict(zip(sig["vars"], struct.unpack(sig["struct"], msg)))
    out  = {}

    for k,v in sig["dict"].items():
      if k not in sig["vars"]:
        continue

      if isinstance(v, bool) and v:
        out[k] = data[k]

      elif isinstance(v, dict):
        for kk,vv in v.items():
          if data[k] == kk:
            out[k] = vv

    return out



  # Send ESP-NOW message(s) to MAC
  def send(self, mac, msg, block=None, delay=0):
    self.prepare()

    # Block argument overrides global delivery_block setting
    if not isinstance(block, bool):
      block = self.delivery_block

    if not isinstance(msg, list):
      msg = [msg]

    returns = []

    for msg_ in msg:
      # Prepare for delivery confirmation
      self.delivery_confirmed = False
      self.delivery_event.clear()

      # Send as v1.0 if message 250 bytes or less
      if len(msg_) <= 250:
        data = b"\x7f\x18\xfe\x34%s\xDD%s\x18\xfe\x34\x04\x01%s" % (random.randbytes(4), (5+len(msg_)).to_bytes(1, 'big'), msg_)

      # Send as v2.0 packet, up to 1427 bytes. This is less than the perported ESP-NOW v2.0 limit of 1470, potentially due to MTU size?
      else:
        data = b"\x7f\x18\xfe\x34" + random.randbytes(4) + b''.join([b"\xDD" + (5+len(msg_[i:i+250])).to_bytes(1, 'big') + b"\x18\xfe\x34\x04\x02" + msg_[i:i+250] for i in range(0, len(msg_), 250)])

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



  # Add message signature and signature callback
  def add_signature(self, sig, callback, data=None, dedupe=False):
    sig["callback"] = callback
    sig["data"] = data

    if dedupe:
      sig["recent"] = collections.deque(maxlen=10)

    self.message_signatures.append(sig)



  # Provided MAC matches ESP-NOW BROADCAST address
  def is_broadcast(self, mac):
    return mac == "FF:FF:FF:FF:FF:FF"



  # Return interface's HW MAC. "XX:XX:XX:XX:XX:XX"
  def hw_mac_as_str(self, interface):
    if hasattr(scapy, "get_if_raw_hwaddr"):
      return ("%02X:" * 6)[:-1] % tuple(scapy.orb(x) for x in scapy.get_if_raw_hwaddr(self.l2_socket.iface)[1])
    else:
      return scapy.get_if_hwaddr(interface).upper() # Potentially better suited for containers





# QOL structures
known_profiles = {
  "wizmote":{
    "name":      "Wizmote",
    "struct":    "<BIBBBB4s",
    "vars":      ["type", "sequence", "dt1", "button", "dt2", "battery", "ccm"],
    "dict":      {"battery": True, "sequence": True, "button": {1: "on", 2: "off", 3: "sleep", 16: "1", 17: "2", 18: "3", 19: "4", 8: "-", 9: "+"}},
    "signature": {"length": 13, "bytes": {5: 0x20, 7: 0x01}}
    },

  "wiz_motion":{
    "name": "wiz motion sensor",
    "struct": "<BIBBBBBBBB4s",
    "vars": ["type", "sequence", "dt1", "_0", "_1", "_2", "motion", "_3", "_4", "_5", "ccm"],
    "dict": {"motion": {0x0b: True, 0x19: True, 0x0a: False, 0x18: False}}, # 0x0b RT Motion | 0x19 LT Motion | 0x0a RT Clear | 0x18 LT Clear
    "signature": {"length": 17, "bytes": {0: 0x81, 5: 0x42}}
    }
}




if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Test/example usage: python3 ESPythoNOW.py wlan1")
    quit()

  def generic_callback(from_mac, to_mac, data):
    print(from_mac, to_mac, "Generic callback handler. (%s)" % len(data), data.hex(" "))

  def wizmote_callback(from_mac, to_mac, data):
    print(from_mac, to_mac, "Wizmote callback handler", data)

  def wiz_motion_callback(from_mac, to_mac, data):
    print(from_mac, to_mac, "Wiz Motion callback handler", data)





  espnow = ESPythoNow(interface=sys.argv[1], callback=generic_callback, accept_all=True)

  espnow.add_signature(known_profiles["wizmote"], wizmote_callback, data="dict", dedupe=True)

  espnow.add_signature(known_profiles["wiz_motion"], wiz_motion_callback, data="dict", dedupe=True)

  espnow.start()

  input()
