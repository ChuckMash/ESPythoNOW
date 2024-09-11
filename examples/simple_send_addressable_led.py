from ESPythoNOW import *
import struct
import time





class espnow_led_sender:

  def __init__(self, interface, pixel_num, fps=30, peer="FF:FF:FF:FF:FF:FF"):
    self.espnow    = ESPythoNow(interface=interface)
    self.pixel_num = pixel_num
    self.fps       = fps
    self.peer      = peer



  def wheel(self, pos):
    if pos < 85: return pos * 3, 255 - pos * 3, 0
    elif pos < 170: return 255 - (pos-85) * 3, 0, (pos-85) * 3
    else: return 0, (pos-170) * 3, 255 - (pos-170) * 3



  def construct_messages(self):
    msgs=[]
    msg = struct.pack('H', 0)
    while True:
      for j in range(255):
        for i in range(self.pixel_num):
          led = struct.pack('BBB', *self.wheel(((i*256//self.pixel_num)+j)&255))
          if len(msg)+len(led) > 250:
            msgs.append(msg)
            msg = struct.pack('H', i)
          msg+=led
        msgs.append(msg)
        yield msgs
        msgs=[]
        msg = struct.pack('H', 0)



  def start(self):
    for msgs in self.construct_messages():
      start = time.time()
      self.espnow.send(self.peer, msgs)
      time.sleep(max(1.0/self.fps -(time.time() -start),0))
      print("FPS:", 1.0 / (time.time() - start))





if __name__ == "__main__":
  sender = espnow_led_sender(interface="wlp1s0", pixel_num=82, fps=30)
  sender.start()



"""

Benchmarks


* USB WIFI: driver=ath9k_htc driverversion=6.5.0-35-generic firmware=1.4
* USB WIFI: driver=rt2800usb driverversion=6.5.0-35-generic firmware=0.36

* ESP8266 D1 Mini & ESP32 D1 Mini 32
  * 82  LEDS @ ~300 FPS
  * 200 LEDS @ ~120 FPS
  * 484 LEDS @ ~50  FPS

"""





