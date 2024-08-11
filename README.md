# ESPythoNOW
Linux based Python ESP-NOW library

---

* Send and receive ESP-NOW messages to and from a Linux machine and ESP8266/ESP32 devices
* Monitor all ESP-NOW messages
* Work In Progress

---

Prep the interface and set channel
```
sudo bash prep.sh wlp1s0 8
```
---
Send and Recieve ESP-NOW messages
```
from ESPythoNOW import *

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlp1s0", mac="48:55:19:00:00:55", callback=callback)
espnow.start()

i=0
while True:
  msg=b'\x01\x00'+i.to_bytes(1,"big")
  espnow.send("FF:FF:FF:FF:FF:FF", msg)
  i+=1
  time.sleep(1)


```
---
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
