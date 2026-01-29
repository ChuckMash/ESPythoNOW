# python3 ESPaudioNOW.py wlan1 audio.mp3 128 FF:FF:FF:FF:FF:FF

from ESPythoNOW import *
import sys, datetime
from time import sleep, perf_counter





class ESPaudioNOW:

  def __init__(self, interface="wlan1", chunk_size=1427, DEBUG=False):
    self.espnow     = ESPythoNow(interface=interface)
    self.chunk_size = chunk_size
    self.DEBUG      = DEBUG
    self.espnow.start()

  # Chunks up MP3 file for sending over ESP-NOW, also can shuttle data through ID3 tag overwrites
  def chunk_file(self, file_path, data=b""):
    with open(file_path, 'rb') as f:
      if data:
        h = f.read(10)

        if h[:3] == b'ID3':
          sz = int.from_bytes(h[6:10], 'big')
          f.seek(((sz>>3)&0x1FFFFF)|((sz>>2)&0x1FFF)|((sz>>1)&0x7F)|(sz&0x7F) + 10)
        else:
          f.seek(0)

        frames = b'TALB' + (len(str(len(data)))+1).to_bytes(4,'big') + b'\x00\x00\x00' + str(len(data)).encode() + \
                 b'TIT2' + (len(data)+1).to_bytes(4,'big') + b'\x00\x00\x00' + data

        sz = len(frames)
        synch = (((sz>>21)&0x7F)<<24)|(((sz>>14)&0x7F)<<16)|(((sz>>7)&0x7F)<<8)|(sz&0x7F)

        yield b'ID3\x03\x00\x00' + synch.to_bytes(4,'big') + frames

      while chunk := f.read(self.chunk_size):
        yield chunk



  def send(self, f, mac="FF:FF:FF:FF:FF:FF", bitrate=128, loop=False, block=True, burst=0, data=b""):
    delay = self.chunk_size / ((int(bitrate) * 1000) / 8)
    next_send = perf_counter()
    cnt = 0

    while True:
      for chunk in self.chunk_file(f, data):

        # Rate limit send based on calculated MP3 playback speed. Initial burst to fill buffer
        if burst > 0:
          burst -= 1
        else:
          sleep_time = next_send - perf_counter()
          if sleep_time > 0:
            sleep(sleep_time)
          next_send += delay

        # Send
        cnt += 1
        self.espnow.send(mac, chunk, block=block)
        if self.DEBUG:
          print(f"{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-4] } ESPythoNOW sent {len(chunk)} Byte ESP-NOW message ({cnt})")

        if not loop:
          break





if __name__ == "__main__":
  mp3send = ESPaudioNOW(interface=sys.argv[1], chunk_size=1427, DEBUG=True)
  mp3send.send(sys.argv[2], bitrate=sys.argv[3], mac=sys.argv[4], loop=True, block=True, burst=5, data=b"Hello. this is a test. Limit of 63 bytes. E S P y t h o N O W !")
