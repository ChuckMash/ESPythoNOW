from ESPythoNOW import *
import struct
import time
import random




class wizmote_sender:

  def __init__(self, interface):
    self.button_lookup = {"ON":1, "OFF":2, "SLEEP":3, "1":16, "2":17, "3":18, "4":19, "-":8, "+":9}
    self.espnow = ESPythoNow(interface=interface)
    self.espnow.start()
    self.sequence = 1



  def send_button(self, button):
    msg = b""
    msg += struct.pack('<B',  0x91 if button == "ON" else 0x81) # Type
    msg += struct.pack('<I',  self.sequence)                    # Sequence
    msg += struct.pack('<B',  32)                               # Data type
    msg += struct.pack('<B',  self.button_lookup[button])       # Button
    msg += struct.pack('<B',  1)                                # Data type
    msg += struct.pack('<B',  100)                              # Battery level
    msg += struct.pack('<4B', *random.randbytes(4))             # CCM not implimented, may not work with actual WiZ lights
    self.espnow.send("FF:FF:FF:FF:FF:FF", msg)
    self.sequence+=1





if __name__ == "__main__":
  wm = wizmote_sender(interface="wlp1s0")

  while True:
    print("Sending ON Button")
    wm.send_button("ON")
    time.sleep(3)

    print("Sending OFF Button")
    wm.send_button("OFF")
    time.sleep(3)

    print("Sending SLEEP Button")
    wm.send_button("SLEEP")
    time.sleep(3)

    print("Sending 1 Button")
    wm.send_button("1")
    time.sleep(3)

    print("Sending 2 Button")
    wm.send_button("2")
    time.sleep(3)

    print("Sending 3 Button")
    wm.send_button("3")
    time.sleep(3)

    print("Sending 4 Button")
    wm.send_button("4")
    time.sleep(3)

    print("Sending - Button")
    wm.send_button("-")
    time.sleep(3)

    print("Sending + Button")
    wm.send_button("+")
    time.sleep(3)
