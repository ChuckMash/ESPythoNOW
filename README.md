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
import time

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
Example: Python <-> ESP32 using channel 8 with BROADCAST
---

Python
```
# First run: sudo bash prep.sh wlp1s0 8
# Then replace interface and MAC address in code

from ESPythoNOW import *
import struct
import time

def callback(from_mac, to_mac, msg):
  a, b, c = struct.unpack("i?11s", msg)
  print(a, b, c)

espnow = ESPythoNow(interface="wlp1s0", mac="DD:DD:DD:DD:DD:DD", callback=callback)
espnow.start()

while True:
  msg = b""
  msg += struct.pack('i', 5)
  msg += struct.pack('?', False)
  msg += struct.pack('12s', b"Hello World")

  espnow.send("FF:FF:FF:FF:FF:FF", msg)

  time.sleep(1)

```

ESP32
```
#include <esp_now.h>
#include <WiFi.h>
#include "esp_private/wifi.h"

typedef struct python_message {
  int a = 1;
  bool b = false;
  uint8_t c[11];
} python_message;

python_message pm;

esp_now_peer_info_t peerInfo;

uint8_t python_peer[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

 void esp_now_rx_callback(const esp_now_recv_info_t * info, const uint8_t *data, int len) {
  memcpy(&pm, data, sizeof(pm));
  Serial.println(pm.a);
  Serial.println(pm.b);
  for(int i=0; i<11; i++){
    Serial.write(pm.c[i]);
  }
  Serial.println();
 }
 
void setup() {
  Serial.begin(115200);
 
  WiFi.mode(WIFI_STA);

  esp_wifi_set_channel(8, WIFI_SECOND_CHAN_NONE);

  esp_now_init();
  
  memcpy(peerInfo.peer_addr, python_peer, 6);
  peerInfo.channel = 8;  
  peerInfo.encrypt = false;
  
  esp_now_add_peer(&peerInfo);
  esp_now_register_recv_cb(esp_now_recv_cb_t(esp_now_rx_callback));
}

void loop() {
  pm.a = 567;
  pm.b = true;
  memcpy(pm.c, "hello world", 11);

  esp_now_send(python_peer, (uint8_t *) &pm, sizeof(pm));
   
  delay(3000);
}
```





---
NOTE about current state, subject to change or improvments
---
* Interface must support monitor mode
* Any "local" MAC address is supported
  * Only actual local MAC will provide delivery confirmation
* Does not retry transmission, or detect delivery confirmation
* Does not support ESP-NOW encryption
