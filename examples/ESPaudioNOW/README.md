# ESPaudioNOW

Stream MP3 audio wirelessly from Linux to ESP32 devices using ESP-NOW protocol.

## Overview

- ESPaudioNOW enables real-time wireless MP3 streaming from a Python sender to an ESP32 receiver.
- Tested up to 320 KBps audio


[![Watch the video](https://i.sstatic.net/qIFETh_wlEA.png)](https://youtu.be/qIFETh_wlEA)
[![Watch the video](https://img.youtube.com/vi/qIFETh_wlEA/maxresdefault.jpg)](https://youtu.be/qIFETh_wlEA)


### Receiver (ESP32)
- ESP32 development board
- I2S DAC/Amplifier (e.g., MAX98357A)
- Connections:
  - GPIO 22: I2S DOUT
  - GPIO 26: I2S BCLK
  - GPIO 25: I2S LRC

### Sender
- Linux machine with WiFi adapter supporting monitor mode
- ESPythoNOW library

```
python3 ESPaudioNOW.py wlan1 audio.mp3 128 FF:FF:FF:FF:FF:FF
```

## Configuration

### Receiver (`receiver.ino`)
```cpp
#define BUFFER_SIZE             8192   // Ring buffer size
#define AUDIO_BUFFER_SIZE       4096   // Audio buffer size
#define MIN_BUFFER_BEFORE_START 0.8    // Start at 80% full
#define CLEAR_BUFFER_AFTER      5000   // Clear after 5s timeout
#define WIFI_CHANNEL            8      // ESP-NOW channel
#define DEFAULT_GAIN            0.5    // Volume (0.0-4.0)
```

### Sender (`sender.py`)
```python
mp3send.send(
    file_path,
    mac="FF:FF:FF:FF:FF:FF",  # Broadcast or specific MAC
    bitrate=128,              # Match MP3 file bitrate
    loop=True,                # Loop playback
    block=True,               # Wait for ACK
    burst=5,                  # Send first 5 packets fast
    data=b"Custom data"       # Optional data shuttle
)
```

