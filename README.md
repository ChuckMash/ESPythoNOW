# ESPythoNOW
Python ESP-NOW library

---

* Send and receive ESP-NOW messages to and from ESP8266 and ESP32 devices
* Monitor all ESP-NOW messages
* Work In Progress

---

Send and Recieve ESP-NOW messages
```
from ESPythoNOW import *

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlp1s0", mac="48:55:19:00:00:55", callback=callback)
espnow.start()

while True:
  msg=b'0x01'
  espnow.send("48:55:19:00:00:33", msg)
  time.sleep(3)

```

Monitor all ESP-NOW Traffic
```
from ESPythoNOW import *

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlp1s0", mac="48:55:19:00:00:55", accept_all=True, callback=callback)
espnow.start()
```



---
NOTE
---
* Any "local" MAC address is supported, does not need to match actual local MAC
* ESPythoNOW not send ESP-NOW delivery confirmation, so an ESP based device sending messages to ESPythoNOW will not have a confirmed delivery
