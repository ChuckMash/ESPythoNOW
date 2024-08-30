from ESPythoNOW import *
import struct
import collections





class wizmote_receive:

  def __init__(self, interface, callback):
    self.callback      = callback
    self.button_lookup = {1:"ON", 2:"OFF", 3:"SLEEP", 16:"1", 17:"2", 18:"3", 19:"4", 8:"-", 9:"+"}
    self.recent        = collections.deque(maxlen=10)
    self.espnow        = ESPythoNow(interface=interface, callback=self.espnow_callback, accept_all=True)
    self.espnow.start()



  def espnow_callback(self, from_mac, to_mac, msg):
    try:
      type, sequence, d1, button, d2, battery, ccm = struct.unpack("<BIBBBB4s", msg)
    except:
      #print("Error processing ESP-NOW packet, not WiZmote")
      return

    # Discard duplicate messages
    if from_mac.encode()+ccm in self.recent:
      return

    # Button code not found, should not happen
    if button not in self.button_lookup.keys():
      return

    self.recent.append(from_mac.encode()+ccm)

    if callable(self.callback):
      self.callback(from_mac, self.button_lookup[button])





if __name__ == "__main__":

  def wizmote_callback(from_mac, button):
    print(from_mac, button)

  wm = wizmote_receive(interface="wlp1s0", callback=wizmote_callback)

  input() # Run until enter is pressed
