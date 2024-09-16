# Sending encrypted messages is not currently supported.
# https://github.com/ChuckMash/ESPythoNOW/issues/1

from ESPythoNOW import *
import struct
import time

def callback(from_mac, to_mac, msg):
  a, b, c = struct.unpack("<I?22s", msg)
  rssi = espnow.packet.dBm_AntSignal

  if scapy.Dot11CCMP in espnow.packet:
    print("Encrypted: %s (%s) %s %s %s" % (from_mac, rssi, a, b, c))
  else:
    print("Plaintext: %s (%s) %s %s %s" % (from_mac, rssi, a, b, c))

espnow = ESPythoNow(
  interface="wlp1s0",
  mac="E0:5A:1B:11:22:33", # Override HW MAC
  callback=callback,
  pmk="0u4hgz7pgct3gnv8", # Do not leave. Example PMK
  lmk="a3o4csuv2bpvr0wu" # Do not leave. Example LMK
)
espnow.start()

while True:
  msg = b""
  msg += struct.pack('<I', 123)
  msg += struct.pack('<?', True)
  msg += struct.pack('<22s', b"Hello from ESPythoNOW!")
  espnow.send("E0:5A:1B:33:22:11", msg)
  time.sleep(30)
