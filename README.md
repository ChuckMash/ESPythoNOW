# ESPythoNOW
Linux/Python ESP-NOW library.

* Send and receive ESP-NOW messages to and from a Linux machine and ESP8266/ESP32 devices
* Monitor all ESP-NOW messages
* [Stream high quality audio to ESP device](https://github.com/ChuckMash/ESPythoNOW/tree/main/examples/ESPaudioNOW)
* Supports ESP-NOW v1.0 and v2.0
  * ESP-NOW on ESP32 supports messages up to 1,470 bytes.
  * ESPythoNOW supports messages up to 2,089 bytes!
    
* Supports sending and receiving encrypted ESP-NOW messages!
* MQTT Subscribe and publish, send and receive ESP-NOW  
*  **This is a work in progress**





---
Prep the interface and set channel (depreciated)
---
```
sudo bash prep.sh wlan1 8
```


---
Try it out, listen for known message types and other ESP-NOW traffic
---
```
python3 ESPythoNOW.py wlan1
```


---
Send and Recieve ESP-NOW messages
---
```python
from ESPythoNOW import *
import time

def callback(from_mac, to_mac, msg):
  print("ESP-NOW message from %s to %s: %s" % (from_mac, to_mac, msg))

espnow = ESPythoNow(interface="wlan1", callback=callback)
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

espnow = ESPythoNow(interface="wlan1", accept_all=True, callback=callback)
espnow.start()
input() # Run until enter is pressed
```





---
Receive/Send encrypted ESP-NOW messages
---
```python
espnow = ESPythoNow(interface="wlan1", callback=callback, pmk="0u4hgz7pgct3gnv8", lmk="a3o4csuv2bpvr0wu")
```

---
MQTT. Work in progress
---
```
python3 ESPythoNOW.py --interface=wlan1 --mqtt_host=192.168.0.10 --mqtt_port=1883 --mqtt_username=test_user --mqtt_password=test_password --mqtt_keepalive=60 --mqtt_raw=false --mqtt_hex=True --mqtt_json=true
```

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
Message Signatures/Decoders / callback data types
---
```python
# Get Wizmote data as a dict

def wizmote_callback(from_mac, to_mac, data):
  print(from_mac, to_mac, "Wizmote callback handler", data)

espnow = ESPythoNow(interface="wlan1", accept_all=True)
espnow.add_signature(known_profiles["wizmote"], wizmote_callback, data="dict", dedupe=True)
#espnow.add_signature(known_profiles["wizmote"], wizmote_callback, data="json", dedupe=True) # or as json
#espnow.add_signature(known_profiles["wizmote"], wizmote_callback, data="raw", dedupe=False) # or raw bytes
#espnow.add_signature(known_profiles["wizmote"], wizmote_callback, data="hex", dedupe=False) # or hex

espnow.start()

```

```python
# Get Wiz PIR motion sensor data
# Provide a custom profile that can detect/fingerprint ESP-NOW messsages as well as decode them
custom_profile = {
  "wiz_motion":{
    "name": "wiz motion sensor",
    "struct": "<BIBBBBBBBB4s",
    "vars": ["type", "sequence", "dt1", "_0", "_1", "_2", "motion", "_3", "_4", "_5", "ccm"],
    "dict": {"motion": {0x0b: True, 0x19: True, 0x0a: False, 0x18: False}}, # 0x0b RT Motion | 0x19 LT Motion | 0x0a RT Clear | 0x18 LT Clear
    "signature": {"length": 17, "bytes": {0: 0x81, 5: 0x42}}}}

def wiz_motion_callback(from_mac, to_mac, data):
  print(from_mac, to_mac, "Wiz Motion callback handler", data)

espnow = ESPythoNow(interface="wlan1", accept_all=True)
espnow.add_signature(custom_profile["wiz_motion"], wiz_motion_callback, data="dict", dedupe=True)
espnow.start()

```




---
How to install with pip and use with sudo (not recommended)
---
```
sudo pip install git+https://github.com/ChuckMash/ESPythoNOW.git@main
sudo espythonow -i wlan1
```

---
How to install with venv and setcap
---
```
# Create virtual environment
python3 -m venv --copies venv

# Add capabilities so can be run without root
sudo setcap cap_net_raw,cap_net_admin=eip venv/bin/python3

# Activate it
source venv/bin/activate

# Upgrade pip
pip3 install --upgrade pip

# Now install from GitHub
pip3 install git+https://github.com/ChuckMash/ESPythoNOW.git@main

espythonow -i wlan1
```

---
How to use with Docker Container
---
```

# Download the docker files from GitHub
wget -O Dockerfile "https://raw.githubusercontent.com/ChuckMash/ESPythoNOW/refs/heads/main/addon-espythonow/Dockerfile"
wget -O docker-compose.yml "https://raw.githubusercontent.com/ChuckMash/ESPythoNOW/refs/heads/main/docker-compose.yml"

# Edit docker-compose.yml to customize interface, send/receive settings, MQTT information, etc.

# Build the Docker images from the Dockerfile
docker-compose build #--no-cache

# Start containers in detached mode (background)
docker-compose up -d

# Follow the logs from the espythonow container
docker-compose logs -f espythonow
```


---
How to Install as Home Assistant Addon/App
---
* Select Setttings, Apps, Install App
* Select the 3 dot menu in the upper right corner and select Repositories
* Add https://github.com/ChuckMash/ESPythoNOW
* Wait a moment and refresh the page
* Install ESPythoNOW - ESP-NOW to MQTT Bridge
---



---
NOTE about current state, subject to change or improvements
---
* Interface must support monitor mode
* Any "local" MAC address is supported
  * Only actual local hardware MAC will provide delivery confirmation
*  **This is a work in progress**
