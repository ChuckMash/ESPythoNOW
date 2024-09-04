from ESPythoNOW import *
import struct
import time

def callback(from_mac, to_mac, msg):
  a, b, c = struct.unpack("<I?22s", msg)
  rssi = espnow.packet.dBm_AntSignal
  print("%s (%s) %s %s %s" % (from_mac, rssi, a, b, c))

espnow = ESPythoNow(interface="wlp1s0", callback=callback)
espnow.start()

while True:
  msg = b""
  msg += struct.pack('<I', 123)
  msg += struct.pack('<?', True)
  msg += struct.pack('<22s', b"Hello from ESPythoNOW!")

  espnow.send("FF:FF:FF:FF:FF:FF", msg)

  time.sleep(1)
