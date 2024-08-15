# ESPythoNOW
Linux based Python ESP-NOW library

---

* Send and receive ESP-NOW messages to and from a Linux machine and ESP8266/ESP32 devices
* Monitor all ESP-NOW messages
* Work In Progress

---
Prep the interface and set channel
---
```
sudo bash prep.sh wlp1s0 8
```
---
Send and Recieve ESP-NOW messages
---
```
from ESPythoNOW import *

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlp1s0", mac="48:55:19:00:00:55", callback=callback)
espnow.start()

while True:
  msg=b'\x01'
  espnow.send("48:55:19:00:00:33", msg)
  time.sleep(3)


```
---
Monitor/Sniff all ESP-NOW Traffic
---
```
from ESPythoNOW import *

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlp1s0", mac="48:55:19:00:00:55", accept_all=True, callback=callback)
espnow.start()
input() # Run until enter is pressed
```

---
Example Data Structures
---

ESP Struct
```
typedef struct python_message{
  int a = 0;
  bool b = false;
  uint8_t c[10];
} python_message;
python_message pm;
```

Python Send Struct
```
import struct

msg = b""
msg += struct.pack('i', 5)
msg += struct.pack('?', False)
msg += struct.pack('11s', b"abcdefghij")
```

Python Receive Struct
```
import struct

def callback(from_mac, to_mac, msg):
  a, b, c = struct.unpack("i?10s", msg[2:-3])
  print(a, b, c)
```

---
NOTE about current state, subject to change or improvments
---
* Interface must support monitor mode
* Any "local" MAC address is supported
  * Only actual local MAC will provide delivery confirmation
* Does not retry transmission, or detect delivery confirmation
* Does not support ESP-NOW encryption
