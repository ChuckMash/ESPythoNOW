from ESPythoNOW import *



def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))



espnow = ESPythoNow(interface="wlp1s0", mac="48:55:19:00:00:55", accept_broadcast=True, accept_all=True, callback=callback)
espnow.start()



while True:
  msg=b'0x01'
  espnow.send("FF:FF:FF:FF:FF:FF", msg)
  time.sleep(3)
