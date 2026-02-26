import scapy.all as scapy
import collections
import random
import time
import struct
import sys
import json
import re
import subprocess

try:
  from Crypto.Cipher import AES
  HAVE_PYCRYPTODOME = True
except:
  HAVE_PYCRYPTODOME = False

try:
  import paho.mqtt.client as mqtt
  HAVE_PAHO = True
except:
  HAVE_PAHO = False



class ESPythoNow:

  def __init__(self, interface, set_interface=True, mtu=1500, rate=0, channel=0, mac="", callback=None, send_raw=False, no_wait=False, retry_limit=0, repeat=0, accept_broadcast=True, accept_all=False, accept_ack=False, block_on_send=False, pmk="", lmk="", decoders={}, mqtt_config={}):

    if set_interface:
      self.prep_interface(interface, channel, mtu=mtu, retry_limit=retry_limit)

    self.interface           = interface                                 # Wireless interface to use
    self.set_interface       = set_interface                             # Set the interface to monitor mode and channel
    self.mtu                 = mtu                                       # MTU for the interface
    self.rate                = float(rate)                               # PHY rate 1, 2, 5.5, 11, 6, 9, 12, 18, 24, 36, 48, 54 Mbps
    self.wifi_channel        = channel                                   # Wifi Channel to use, if set_interface
    self.local_mac           = mac.upper() if mac else None              # Local ESP-NOW peer MAC, does not need to match actual hw MAC
    self.esp_now_rx_callback = callback                                  # Callback function to execute on packet RX
    self.send_raw            = send_raw                                  # Send packets with raw socket instead of scapy, can be faster and unstable
    self.no_wait             = no_wait                                   # Don't wait for receiver to confirm sent messages. faster unicast messages. no automatic retransmit.
    self.retry_limit         = retry_limit                               # The limit of how many times a packet will automatically be resent if delivery not confirmed
    self.repeat              = repeat                                    # The number of times to force packet resend
    self.accept_broadcast    = accept_broadcast                          # Allow incoming ESP-NOW broadcast packets
    self.accept_all          = accept_all                                # Accept ESP-NOW packets, no matter the destination MAC
    self.accept_ack          = accept_ack                                # Pass delivery confirmation to callback
    self.delivery_block      = block_on_send                             # Block on send, wait for delivery or timeout
    self.pmk                 = pmk                                       # Primary Master Key, used to encrypt Local Master Key
    self.lmk                 = lmk                                       # Local Master Key, used to encrypt ESP-NOW messages
    self.decoders            = decoders                                  # Known message decoders
    self.mqtt_config         = mqtt_config                               # Configuration dict for MQTT connection
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
    self.use_mqtt            = False                                     # MQTT will be used





  # Set the retry limit for the interface
  def set_retry_limit(self, interface, limit=5):
    if not limit:
      return
    try:
      subprocess.run(['iwconfig', interface, 'retry', str(limit)], check=True)
      return True
    except Exception as e:
      print(f"Failed to set retry limit: {e}")
      return False



  # Set the MTU for the interface
  def set_mtu(self, interface, mtu=1500):
    print(f"Setting {interface} MTU to {mtu}")
    try:
      with open(f"/sys/class/net/{interface}/mtu", 'r+') as f:
        if int(f.read()) == mtu:                               # Check existing MTU
          return True                                          # Do nothing if already matches
        f.write(str(mtu))                                      # Set new MTU
        f.seek(0)
        success = int(f.read()) == mtu                         # validation of new MTU
        if success:
          self.mtu = mtu
        return success
    except Exception as e:
      print("Failed to set MTU:", e)
    return False



  # Get monitor mode status and channel of interface
  def get_interface_info(self, interface):
    for check_cmd, mode_str, channel_pattern in [
      (['iw', 'dev', interface, 'info'], 'type monitor', 'channel '),
      (['iwconfig', interface], 'Mode:Monitor', 'Frequency:')]:
      try:
        result = subprocess.run(check_cmd, capture_output=True, text=True, check=True).stdout
        if mode_str in result:
          try:
            freq = float(result.split(channel_pattern)[1].split()[0])
            channel = int(freq) if channel_pattern == 'channel ' else int((freq * 1000 - 2407) / 5)
            return (True, channel)
          except:
            return (True, None)
      except:
        pass
    return (False, None)



  # Prepare the interface with monitor mode and channel (replaces prep.sh)
  def prep_interface(self, interface, channel=0, mtu=0, retry_limit=0, force=False):
    monitor, current_channel = self.get_interface_info(interface) if not force else (False, None)
    need_monitor = not monitor
    need_channel = channel and current_channel != channel

    if not need_monitor and not need_channel and mtu==0 and retry_limit==0:
      print(f"{interface} already configured")
      return

    print(f"Setting {interface} for monitor mode and channel {channel}")

    methods = [[], []]

    if need_monitor:
      methods[0].extend([['ip', 'link', 'set', interface, 'down'],
                         ['iw', 'dev', interface, 'set', 'type', 'monitor'],
                         ['ip', 'link', 'set', interface, 'up']])

      methods[1].extend([['ifconfig', interface, 'down'],
                         ['iwconfig', interface, 'mode', 'monitor'],
                         ['ifconfig', interface, 'up']])

    if need_channel:
      methods[0].append(['iw', 'dev', interface, 'set', 'channel', str(channel)])
      methods[1].append(['iwconfig', interface, 'channel', str(channel)])

    for method in methods:
      try:
        for cmd in method:
          subprocess.run(cmd, check=True)
        if mtu:                                              # If MTU is set
          self.set_mtu(interface, mtu=mtu)                   # Set interface MTU
        if retry_limit:                                      # If retry limit is set
          self.set_retry_limit(interface, limit=retry_limit) # Set retry limit for interface
        return
      except:
        pass

    print("Failed. Install (iproute2 and iw) and/or (net-tools and wireless-tools)")



  # Required tasks prior to sending or receiving
  def prepare(self):
    if self.prepared:
      return False;

    # Local MAC is not set, default to interface MAC
    if not self.local_mac:
      self.local_mac = self.local_hw_mac

    # If PMK and LMK are valid length, create CCMP key
    if self.pmk and self.lmk and len(self.pmk)==16 and len(self.lmk)==16:

      # Check for library required for encrypted ESP-NOW
      if HAVE_PYCRYPTODOME:
        try:
          # Convert PMK and LMK to bytes if needed
          self.pmk = str.encode(self.pmk) if isinstance(self.pmk, str) else self.pmk
          self.lmk = str.encode(self.lmk) if isinstance(self.lmk, str) else self.lmk

          # Create CCM KEY by encrypting LMK with PMK
          self.key       = AES.new(self.pmk, AES.MODE_ECB).encrypt(self.lmk)
          self.encrypted = True

        except Exception as e:
          print("Encryption error: %s" % e)
          self.encrypted = False

      else:
        print("Error! PyCryptoDome missing, encryption can not be enabled.")
        self.encrypted = False

    # Prepare the send packet ahead of time. Reuses packet for better performance
    VALID_RATES = [1, 2, 5.5, 11, 6, 9, 12, 18, 24, 36, 48, 54]
    kwargs = {}
    present = []
    txflags = []

    if self.rate in VALID_RATES:
      present.append("Rate")
      present.append("Flags")
      kwargs["Rate"]  = self.rate
    elif self.rate != 0:
      print("Invalid rate", VALID_RATES)

    if self.no_wait:
      present.append("TXFlags")
      txflags.append("NOACK")

    if txflags:
      kwargs["TXFlags"] = "+".join(txflags)

    if present:
      kwargs["present"] = "+".join(present)

    self.esp_now_send_packet           = scapy.RadioTap(**kwargs) / scapy.Dot11FCS(type=0, subtype=13,                      addr1=self.local_mac, addr2=self.local_mac, addr3="FF:FF:FF:FF:FF:FF") / scapy.Raw(load=None)
    self.esp_now_send_packet_encrypted = scapy.RadioTap(**kwargs) / scapy.Dot11FCS(type=0, subtype=13, FCfield='protected', addr1=self.local_mac, addr2=self.local_mac, addr3="FF:FF:FF:FF:FF:FF") / scapy.Raw(load=None)

    self.esp_now_send_packet_raw       = bytearray(scapy.raw(self.esp_now_send_packet))                        # Store a raw version of the unencrypted packet
    self.raw_packet_index              = self.esp_now_send_packet_raw.index(self.mac_as_bytes(self.local_mac)) # The raw packet index of start of addr1
    self.raw_packet_fc_index           = int.from_bytes(self.esp_now_send_packet_raw[2:4], 'little')           # The raw packet index of FC flags

    # Create filter part for local mac
    self_mac_filter = "" if self.accept_all else " and (wlan addr1 %s or wlan addr1 FF:FF:FF:FF:FF:FF)" % self.local_mac

    # Create packet filter
    if self.encrypted:
      # Filter for all managment/action frames. Adds detection of encrypted ESP-NOW messages at the cost of downstream filtering
      self.filter = "((type 0 subtype 0xd0%s) or (type 4 subtype 0xd0 and wlan addr1 %s)) and wlan src ! %s" % (self_mac_filter, self.local_mac, self.local_mac)
    else:
      # Filter for all unencrypted ESP-NOW messages and ESP-NOW ACK
      self.filter = "((type 0 subtype 0xd0 and wlan[24:4]=0x7f18fe34%s) or (type 4 subtype 0xd0 and wlan addr1 %s)) and wlan src ! %s" % (self_mac_filter, self.local_mac, self.local_mac)

    # Add history deque to decoders as needed
    for k,dec in self.decoders.items():
      if "dedupe" in dec:
        dec["recent"] = collections.deque(maxlen=dec["dedupe"])

    # MQTT
    if self.mqtt_config:
      if not HAVE_PAHO:
        print("Error! paho-mqtt missing, MQTT can not be enabled.")
        self.use_mqtt = False
      else:
        self.mqtt_client_id     = f"ESPythoNOW-{self.local_mac}"
        self.mqtt_topic_base    = f"ESPythoNOW-{self.local_mac}"
        self.mqtt_topic_send    = self.mqtt_topic_base+"/send"
        self.mqtt_broker_ip     = self.mqtt_config.get("ip",        None)  # MQTT broker IP, hostname not supported?
        self.mqtt_broker_port   = self.mqtt_config.get("port",      1883)  # MQTT broker port, default to 1883
        self.mqtt_username      = self.mqtt_config.get("username",  None)  # MQTT broker username
        self.mqtt_password      = self.mqtt_config.get("password",  None)  # MQTT broker password
        self.mqtt_keepalive     = self.mqtt_config.get("keepalive", 60)    # Keepalive for MQTT connection
        self.mqtt_publish_raw   = self.mqtt_config.get("raw",       False) # Publish raw bytes
        self.mqtt_publish_hex   = self.mqtt_config.get("hex",       False) # Publish hex bytes
        self.mqtt_publish_json  = self.mqtt_config.get("json",      False) # Publish JSON of message, if decoder exists
        self.mqtt_publish_ack   = self.mqtt_config.get("ack",       False) # Publish any received ACK messages, can loosely be used to check if message has been delivered
        self.mqtt_discard_empty = True                                     # Discard messages with no data

        # Ensure that at least hex is published to MQTT
        if not any([self.mqtt_publish_raw, self.mqtt_publish_hex, self.mqtt_publish_json]):
          self.mqtt_publish_hex = True

        if not self.mqtt_broker_ip:
          print("No broker address, not using MQTT")
          self.use_mqtt = False
        else:
          self.use_mqtt = True

          self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

          if self.mqtt_username and self.mqtt_password:
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)

          # Set MQTT callbacks
          self.mqtt_client.on_message = self.mqtt_on_message
          self.mqtt_client.on_connect = self.mqtt_on_connect

          # Set LWT for offline
          self.mqtt_client.will_set(self.mqtt_topic_base, payload="offline", qos=1, retain=True)

          # Connect to the broker
          try:
            self.mqtt_client.connect(self.mqtt_broker_ip, self.mqtt_broker_port, keepalive=self.mqtt_keepalive)
          except Exception as e:
            print(f"Connection failed: {e}")

          self.mqtt_client.loop_start()

    self.prepared = True



  # Send ESP-NOW message(s) to MAC
  def send(self, mac, msg, block=None, delay=0, raw=None):
    self.prepare()

    # Block argument overrides global delivery_block setting
    if not isinstance(block, bool):
      block = self.delivery_block

    # Send raw argument overrides global send_raw setting
    if not isinstance(raw, bool):
      raw = self.send_raw

    if not isinstance(msg, list):
      msg = [msg]

    returns = []

    for msg_ in msg:
      # Prepare for delivery confirmation
      self.delivery_confirmed = False
      self.delivery_event.clear()

      # Send as v1.0 if message 250 bytes or less
      if len(msg_) <= 250:
        plaintext_data = b"\x7f\x18\xfe\x34%s\xDD%s\x18\xfe\x34\x04\x01%s" % (random.randbytes(4), (5+len(msg_)).to_bytes(1, 'big'), msg_)

      # Send as v2.0 packet, messages up to 1427 bytes (1500 MTU), or up to 2089 bytes (2304 MTU)
      else:
        plaintext_data = b"\x7f\x18\xfe\x34" + random.randbytes(4) + b''.join([b"\xDD" + (5+len(msg_[i:i+250])).to_bytes(1, 'big') + b"\x18\xfe\x34\x04" + (b"\x12" if i+250 < len(msg_) else b"\x02") + msg_[i:i+250] for i in range(0, len(msg_), 250)])

      # Send encrypted ESP-NOW message
      if self.encrypted:
        counter       = self.esp_now_send_packet_encrypted.SC >> 4
        src_mac_bytes = bytes.fromhex(self.local_mac.replace(':', ''))
        dst_mac_bytes = bytes.fromhex(mac.replace(':', ''))
        pn_low        = counter & 0xff
        pn_high       = (counter >> 8) & 0xff
        ccmp_hdr      = bytes([pn_low, pn_high, 0x00, 0xE0, 0x00, 0x00, 0x00, 0x00])
        nonce         = b'\x00' + src_mac_bytes + b'\x00\x00\x00\x00' + bytes([pn_high, pn_low])
        sc            = counter << 4
        aad           = struct.pack('<H', 0x4080) + dst_mac_bytes + src_mac_bytes + b'\xff\xff\xff\xff\xff\xff' + struct.pack('<H', sc & 0x000f)
        cipher        = AES.new(self.key, AES.MODE_CCM, nonce=nonce, mac_len=8)
        cipher.update(aad)
        enc_text, mic = cipher.encrypt_and_digest(plaintext_data)
        packet        = self.esp_now_send_packet_encrypted
        packet.SC     = sc
        packet.load   = ccmp_hdr + enc_text + mic

      # Send plaintext ESP-NOW message
      else:
        packet        = self.esp_now_send_packet
        packet.load   = plaintext_data

      packet.addr1    = self.format_mac(mac)
      packet.addr2    = self.local_mac
      packet.SC       = (((packet.SC >> 4) + 1) & 0xFFF) << 4

      # Time how long the send process takes
      send_time = time.time()

      # Send ESP-NOW packet
      try:

        # Send the packet directly to the socket, can be much faster and unstable
        if raw and not self.encrypted: # Send the packet directly to the socket, can be much faster

          #self.raw_packet_index is the index to start messing with the packet
          self.esp_now_send_packet_raw[self.raw_packet_index      : self.raw_packet_index + 6]  = bytes.fromhex(packet.addr1.replace(':', '')) # mac
          #self.esp_now_send_packet_raw[self.raw_packet_index + 6  : self.raw_packet_index + 12] = bytes.fromhex(packet.addr2.replace(':', '')) # local mac # should never change
          #self.esp_now_send_packet_raw[self.raw_packet_index + 12 : self.raw_packet_index + 18] = bytes.fromhex(packet.addr3.replace(':', '')) # broadcast # should never change
          self.esp_now_send_packet_raw[self.raw_packet_index + 18 : self.raw_packet_index + 20] = packet.SC.to_bytes(2, 'little')              # count # driver overwrites this?
          self.esp_now_send_packet_raw[self.raw_packet_index + 20 : -4] = plaintext_data                                                       # data

          # Send the raw packet
          self.l2_socket.ins.send(self.esp_now_send_packet_raw) #, 64)     # Send the packet
          self.esp_now_send_packet_raw[self.raw_packet_fc_index+1] ^= 0x08 # Set the resend flag in the raw packet
          for i in range(self.repeat):
            self.l2_socket.ins.send(self.esp_now_send_packet_raw) #, 64)   # Send any forced resends
          self.esp_now_send_packet_raw[self.raw_packet_fc_index+1] ^= 0x08 # Unset the resend flag

        # Send the packet with scapy
        else:
          self.l2_socket.send(packet)                              # Send the packet
          self.esp_now_send_packet[scapy.Dot11FCS].FCfield ^= 0x08 # Set the resend flag in the scapy packet
          for i in range(self.repeat):
            self.l2_socket.send(packet)                            # Send any forced resends
          self.esp_now_send_packet[scapy.Dot11FCS].FCfield ^= 0x08 # Unset the resend flag

      except Exception as e:
        print("Error sending:",e)

      # Roughly detects when the send takes longer than it should
      if (time.time() - send_time) > 0.1:
        print("Outbound kernel buffer / driver / interface may be overwhelmed")

      # Wait for delivery confirmation from remote peer or timeout
      if (block and not self.is_broadcast(mac)) or (block and self.block_on_broadcast and self.is_broadcast(mac)):
        returns.append(self.delivery_event.wait(timeout=self.delivery_timeout))

      # Additional delay after sending each ESP-NOW packet
      if delay:
        time.sleep(delay)

    return all(returns)



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



  # Callback for connection to broker
  def mqtt_on_connect(self, client, userdata, flags, reason_code, properties):

    # Set LWT Online
    self.mqtt_client.publish(self.mqtt_topic_base, "online", qos=1, retain=True)

    if reason_code == 0:
      print("Connected to broker")
      client.subscribe(self.mqtt_topic_send+"/#")
    else:
      print(f"Failed to connect to broker, return code {reason_code}")



  # Experimental support for sending ESP-NOW messages on MQTT receive
  # work in progress
  def mqtt_on_message(self, client, userdata, msg):

    # Discard empty message
    if self.mqtt_discard_empty and not msg:
      return

    if msg.topic.startswith(self.mqtt_topic_send):

      macs = msg.topic.split(self.mqtt_topic_send)[1].split("/")[1:]
      # Validates that topic ESPythoNOW/send/AA:AA:AA:AA:AA:AA(/BB:BB:BB:BB:BB:BB) contains valid MAC addresses
      if not all(self.is_valid_mac(mac) for mac in macs):
        print("Invalid macs")
        return

      if len(macs) == 1:
        print(f"MQTT->ESP-NOW: {macs[0]} - {msg.payload}")
        self.send(macs[0], msg.payload)

      #elif len(macs) == 2:
      #  print(f"Dual MAC: {macs[0]} -> {macs[1]}, Data: {msg.payload}")



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
      if self.accept_ack:

        if callable(self.esp_now_rx_callback):
          self.esp_now_rx_callback(False, to_mac, "ack")

        if self.use_mqtt and self.mqtt_publish_ack:
          self.mqtt_client.publish(f"{self.mqtt_topic_base}/ack/{to_mac}", "ack", qos=1)

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

      # Parse message from ESP-NOW packet, v1.0 and v2.0
      msg_raw = b''.join([data[15:][i:i + 250] for i in range(0, len(data[15:]), 257)])

      # Check if there is a decoder that matches this message
      dec = self.check_decoders(msg_raw)

      # If a decoder exists for this message, and is set to filter duplicate messages, different from filtering resent messages.
      if dec and "recent" in dec:
        if msg_raw in dec["recent"]:
          return
        dec["recent"].append(msg_raw)

      # Prepare default callback values
      callback = self.esp_now_rx_callback
      output   = msg_raw

      # Check if decoder has a callback associated with it
      if dec and "callback" in dec and callable(dec["callback"]):
        callback = dec["callback"]
        if   dec["data"] == "hex":  output = msg_raw.hex(" ")
        elif dec["data"] == "dict": output = self.decode(dec, msg_raw)
        elif dec["data"] == "json": output = json.dumps(self.decode(dec, msg_raw))

      # Execute the callback if one was found
      if callback and callable(callback):
        callback(from_mac, to_mac, output)

      # Check to see if using MQTT and publish incoming messages
      if self.use_mqtt and self.mqtt_client.is_connected():

        if self.mqtt_discard_empty and not msg_raw:
          return

        if self.mqtt_publish_raw:
          self.mqtt_client.publish(f"{self.mqtt_topic_base}/{from_mac}/{to_mac}/raw", msg_raw, qos=1)

        if self.mqtt_publish_hex:
          self.mqtt_client.publish(f"{self.mqtt_topic_base}/{from_mac}/{to_mac}/hex", msg_raw.hex(" "), qos=1)

        if dec and self.mqtt_publish_json:
          self.mqtt_client.publish(f"{self.mqtt_topic_base}/{from_mac}/{to_mac}/json", json.dumps(self.decode(dec, msg_raw)), qos=1)



  # Identify the message signature
  def check_decoders(self, data):
    # Loop through each stored signature
    for name, dev in self.decoders.items():
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
  def decode(self, sig, msg):
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



  # Add message signature and signature callback
  def add_signature(self, name, callback, data=None, dedupe=10): # dedupe should be more like recent history filter
    if name not in self.decoders:
      print("Unknown decoder")
      return False
    self.decoders[name]["callback"] = callback
    self.decoders[name]["data"]     = data # actually should be "return data type"



  # Provided MAC matches ESP-NOW BROADCAST address
  def is_broadcast(self, mac):
    return mac.replace(":", "").upper() == "FFFFFFFFFFFF"



  # Matches formated AA:BB:CC:DD:EE:FF or unformated AABBCCDDEEFF
  def is_valid_mac(self, mac):
    return re.match(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$|^[0-9A-Fa-f]{12}$', mac)



  # Ensure MAC is formatted like FF:FF:FF:FF:FF:FF
  def format_mac(self, mac):
    return ":".join(mac.replace(":", "").upper()[i:i+2] for i in range(0, 12, 2))



  # Return interface's HW MAC. "XX:XX:XX:XX:XX:XX"
  def hw_mac_as_str(self, interface):
    if hasattr(scapy, "get_if_raw_hwaddr"):
      return ("%02X:" * 6)[:-1] % tuple(scapy.orb(x) for x in scapy.get_if_raw_hwaddr(self.l2_socket.iface)[1])
    else:
      return scapy.get_if_hwaddr(interface).upper() # Potentially better suited for containers



  # Return mac as raw bytes
  def mac_as_bytes(self, mac):
    if isinstance(mac, bytes):
        return mac
    return bytes.fromhex(mac.replace(':', ''))





def speed_test(espnow, duration, size, mac):
  data, start = b'\x00' * int(size), time.time()
  byte_count, packet_count, total, last_report = 0, 0, 0, start
  mbps_history = []
  while (now := time.time()) - start < int(duration):
    espnow.send(mac, data, block=False)
    byte_count += len(data)
    packet_count += 1
    total += 1
    if now - last_report >= 1.0:
      if packet_count == 0:
        byte_count, packet_count, last_report = 0, 0, now
        continue
      mbps_history.append((byte_count * 8) / (now - last_report) / 1000000)
      print(f"pkts/s: {packet_count / (now - last_report):.0f}  B/s: {byte_count / (now - last_report):.0f}  kbps: {byte_count * 8 / (now - last_report) / 1000:.1f}  Mbps: {mbps_history[-1]:.3f}  [min: {min(mbps_history):.3f}  avg: {sum(mbps_history) / len(mbps_history):.3f}  max: {max(mbps_history):.3f}]")
      byte_count, packet_count, last_report = 0, 0, now
  espnow._speed_test_packets_sent = total
  print(f"\n\t\t\t {total} packets sent")





# QOL structures
decoders = {
  "wizmote":{
    "name":      "Wizmote",
    "struct":    "<BIBBBB4s",
    "vars":      ["type", "sequence", "dt1", "button", "dt2", "battery", "ccm"],
    "dict":      {"battery": True, "sequence": True, "button": {1: "on", 2: "off", 3: "sleep", 16: "1", 17: "2", 18: "3", 19: "4", 8: "-", 9: "+"}},
    "signature": {"length": 13, "bytes": {5: 0x20, 7: 0x01}},
    "dedupe":    10
    },

  "wiz_motion":{
    "name":      "wiz motion sensor",
    "struct":    "<BIBBBBBBBB4s",
    "vars":      ["type", "sequence", "dt1", "_0", "_1", "_2", "motion", "_3", "_4", "_5", "ccm"],
    "dict":      {"motion": {0x0b: True, 0x19: True, 0x0a: False, 0x18: False}}, # 0x0b RT Motion | 0x19 LT Motion | 0x0a RT Clear | 0x18 LT Clear
    "signature": {"length": 17, "bytes": {0: 0x81, 5: 0x42}},
    "dedupe":    10
    }
}





def main():
  import argparse
  import signal

  def s2b(v): return True if v.lower() in ('yes', 'true', 't', 'y', '1') else False

  def generic_callback   (from_mac, to_mac, data): print(from_mac, to_mac, "Generic callback handler. (%s)" % len(data), data)
  def wizmote_callback   (from_mac, to_mac, data): print(from_mac, to_mac, "Wizmote callback handler", data)
  def wiz_motion_callback(from_mac, to_mac, data): print(from_mac, to_mac, "Wiz Motion callback handler", data)

  parser = argparse.ArgumentParser(description='ESPythoNOW: ESP-NOW for Linux!')

  parser.add_argument('-i',      '--interface',        required=True,  default="wlan1",           help='Dedicated wireless interface (e.g., wlan1)')
  parser.add_argument('-c',      '--channel',          required=False, default=0,     type=int,   help='Wireless channel to use')
  parser.add_argument('-s',      '--set_interface',    required=False, default=False, type=s2b,   help='ESPythoNOW will try and set monitor mode and channel')
  parser.add_argument('-M',      '--mtu',              required=False, default=0,     type=int,   help='ESPythoNOW will try and set the MTU for the interface')
  parser.add_argument('-r',      '--rate',             required=False, default=0,     type=float, help='ESPythoNOW will try and set the PHY rate for the interface')
  parser.add_argument('-m',      '--mac',              required=False, default=None,              help='Override local MAC address (default: interfaces MAC)')
  parser.add_argument('-S',      '--send_raw',         required=False, default=False, type=s2b,   help='Send with raw socket, can be faster and unstable')
  parser.add_argument('-n',      '--no_wait',          required=False, default=False, type=s2b,   help='Don\'t wait for confirmation from receiver when sending. Speeds up UNICAST sending at cost of no retransmit')
  parser.add_argument('-R',      '--retry_limit',      required=False, default=0,     type=int,   help='Try and set the retry limit')
  parser.add_argument('-d',      '--repeat',           required=False, default=0,     type=int,   help='Force packet repeat in send n times')
  parser.add_argument('-b',      '--accept_broadcast', required=False, default=True,  type=s2b,   help='Accept broadcast ESP-NOW messages (default: True)')
  parser.add_argument('-a',      '--accept_all',       required=False, default=False, type=s2b,   help='Accept all ESP-NOW messages regardless of destination (default: False)')
  parser.add_argument('-ack',    '--accept_ack',       required=False, default=False, type=s2b,   help='Execute callback on ACK confirmation (default: False)')
  parser.add_argument('-blk',    '--block_on_send',    required=False, default=False, type=s2b,   help='Block on sending data, wait for ACK from receiving device')
  parser.add_argument('-pmk',    '--primary_key',      required=False, default=None,              help='Primary master key for encrypted ESP-NOW (16 chars)')
  parser.add_argument('-lmk',    '--local_key',        required=False, default=None,              help='Local master key for encrypted ESP-NOW (16 chars)')
  parser.add_argument('-mqh',    '--mqtt_host',        required=False, default=None,              help='MQTT broker IP address')
  parser.add_argument('-mqp',    '--mqtt_port',        required=False, default=1883,  type=int,   help='MQTT broker port (default: 1883)')
  parser.add_argument('-mqu',    '--mqtt_username',    required=False, default=None,              help='MQTT username for authentication')
  parser.add_argument('-mqP',    '--mqtt_password',    required=False, default=None,              help='MQTT password for authentication')
  parser.add_argument('-mqk',    '--mqtt_keepalive',   required=False, default=60,    type=int,   help='MQTT keepalive')
  parser.add_argument('-mqraw',  '--mqtt_raw',         required=False, default=False, type=s2b,   help='Publish raw bytes to MQTT (default: True)')
  parser.add_argument('-mqhex',  '--mqtt_hex',         required=False, default=True,  type=s2b,   help='Publish hex-encoded data to MQTT (default: True)')
  parser.add_argument('-mqjson', '--mqtt_json',        required=False, default=True,  type=s2b,   help='Publish JSON-formatted data to MQTT, if decoder exists. (default: True)')
  parser.add_argument('-mqack',  '--mqtt_ack',         required=False, default=False, type=s2b,   help='Publish ACK (messsage received) to confirm message delivery on send (default: False)')
  parser.add_argument('-z',      '--speed_test',       required=False, default="",                help='Execute 30 second sending speed test, set packet size: --speed_test 30,250,FF:FF:FF:FF:FF:FF (seconds, message size, address)')

  #args = parser.parse_args()





  
  
  #HA testing
  import json
  import os
  from types import SimpleNamespace

  class Options(SimpleNamespace):
    def __getattr__(self, name):
        return None
      
  OPTIONS_PATH = "/data/options.json"

  if os.path.exists(OPTIONS_PATH):
    print("[ESPythoNOW] Loading config from /data/options.json", flush=True)
    with open(OPTIONS_PATH) as f:
      options = json.load(f)
    args = Options(**{
      k: v
      for k, v in options.items()
      if v is not None and v != ""
    })


    import urllib.request
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    req = urllib.request.Request(
      "http://supervisor/services/mqtt",
      headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as r:
      data = json.loads(r.read()).get("data", {})

    print(data)






  
  else:
    args = parser.parse_args()
  
  if args.mqtt_host:
    mqtt_config = {
      "ip":        args.mqtt_host,
      "port":      args.mqtt_port,
      "username":  args.mqtt_username,
      "password":  args.mqtt_password,
      "keepalive": args.mqtt_keepalive,
      "raw":       args.mqtt_raw,
      "hex":       args.mqtt_hex,
      "json":      args.mqtt_json,
      "ack":      args.mqtt_ack}
  else:
    mqtt_config = {}

  espnow = ESPythoNow(
    interface        = args.interface,
    channel          = args.channel,
    set_interface    = args.set_interface,
    mtu              = args.mtu,
    rate             = args.rate,
    mac              = args.mac,
    send_raw         = args.send_raw,
    no_wait          = args.no_wait,
    retry_limit      = args.retry_limit,
    repeat           = args.repeat,
    accept_broadcast = args.accept_broadcast,
    accept_all       = args.accept_all,
    accept_ack       = args.accept_ack,
    block_on_send    = args.block_on_send,
    pmk              = args.primary_key,
    lmk              = args.local_key,
    callback         = generic_callback,
    decoders         = decoders,
    mqtt_config      = mqtt_config)

  espnow.add_signature("wizmote", wizmote_callback, data="dict")
  espnow.add_signature("wiz_motion", wiz_motion_callback, data="dict")

  if args.speed_test and len(st := args.speed_test.split(",")) == 3:
    results=[]
    def speed_test_cb(from_mac, to_mac, data):
      if from_mac in results:
        return
      results.append(from_mac)
      decoded = data.decode()
      packets_received = int(decoded.split(" ")[0])
      packet_loss = 100 - (packets_received / espnow._speed_test_packets_sent * 100)
      print(from_mac, "\t", decoded, "%.1f%% packet loss" % packet_loss)
      print()

    speed_test(espnow, *st)                    # Run the test
    espnow.esp_now_rx_callback = speed_test_cb # Callback to get results from remote device after the test
    espnow.start()                             # Listen for a response
    time.sleep(15)                             # Wait for a response



  espnow.start()


  
  signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
  try:
    signal.pause()
  except:
    pass
  print()








if __name__ == "__main__":
  main()
