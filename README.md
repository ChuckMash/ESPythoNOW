# ESPythoNOW
Linux/Python ESP-NOW library.

* Send and receive ESP-NOW messages to and from a Linux machine and ESP8266/ESP32 devices
* Monitor all ESP-NOW messages





---
Prep the interface and set channel
---
```
sudo bash prep.sh wlp1s0 8
```





---
Send and Recieve ESP-NOW messages
---
```python
from ESPythoNOW import *
import time

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlp1s0", callback=callback)
espnow.start()

while True:
  msg=b'\x01'
  espnow.send("FF:FF:FF:FF:FF:FF", msg)
  time.sleep(3)
```





---
Monitor/Sniff all ESP-NOW Traffic
---
```python
from ESPythoNOW import *

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlp1s0", accept_all=True, callback=callback)
espnow.start()
input() # Run until enter is pressed
```





---
Receive encrypted ESP-NOW messages
---
```python
espnow = ESPythoNow(interface="wlp1s0", callback=callback, pmk="0u4hgz7pgct3gnv8", lmk="a3o4csuv2bpvr0wu")
```
Note: [Sending encrypted ESP-NOW messages is not currently supported.](https://github.com/ChuckMash/ESPythoNOW/issues/1) 




---
Assorted Details
---
* espnow = ESPythoNow() - Initialize ESPythoNOW 
  * Arguments
    * **interface** - The only required argument, the wireless interface to use. Must support monitor mode.
    * **mac** - The MAC address to use. Defaults to **interface's MAC**.
    * **callback** - Function will execute in thread on ESP-NOW message receive.
    * **accept_broadcast** - Accept/Reject ESP-NOW BROADCAST messages. Defaults to **True**.
    * **accept_all** - Accept/Reject ESP-NOW messages no matter the destination MAC. Defaults to **False**.
    * **accept_ack** - If enabled, will execute the callback function when remote peer confirms delivery of sent message. Defaults to **False**.
    * **block_on_send** - If enabled, will block on send() until remote peer confirms delivery or timeout. Defaults to **False**
  * Returns
    * ESPythoNow object.

* espnow.start() - Begin listening for ESP-NOW messages
  * Returns
    * True/False on listener starting

* espnow.send() - Send ESP-NOW messages to remote peer
  * Arguments
    * **mac** - The MAC address of remote ESP-NOW peer.
    * **msg** - The message contents.
      * Also supports list of messages
    * **block** - If enabled, will block until remote peer confirms delivery or timeout. Overrides global block_on_send. Defaults to **block_on_send**.
  * Returns
    * If not blocking, will always return **True**.
    * If blocking, will return **True** if message(s) have delivery confirmed by remote peer.





---
NOTE about current state, subject to change or improvements
---
* Interface must support monitor mode
* Any "local" MAC address is supported
  * Only actual local MAC will provide delivery confirmation
* Supports receiving encrypted messages, does not support sending [yet](https://github.com/ChuckMash/ESPythoNOW/issues/1) 
* This is a work in progress
