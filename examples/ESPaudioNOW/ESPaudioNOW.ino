#include <esp_now.h>
#include "esp_wifi.h" 
#include <WiFi.h>
#include "AudioFileSourceBuffer.h"
#include "AudioFileSourceID3.h"
#include "AudioGeneratorMP3.h"
#include "AudioOutputI2S.h"

#define DEBUG                   1000                // Print debug information over serial every x ms. Comment out to disable.
#define CHUNK_SIZE              1427                // Max ESP-NOW message size that ESPythoNOW supports
#define BUFFER_SIZE             8192                // Byte size of the ring buffer to fit data from ESP-NOW
#define AUDIO_BUFFER_SIZE       4096                // Byte size of the audio buffer that feeds audio playback.
#define MIN_BUFFER_BEFORE_START (BUFFER_SIZE * 0.8) // How full the ring buffer needs to be before starting playback
#define CLEAR_BUFFER_AFTER      5000                // ms since last message receive to clear ring buffer
#define I2S_DOUT                22
#define I2S_BCLK                26
#define I2S_LRC                 25
#define DEFAULT_RATE            44100
#define DEFAULT_GAIN            0.5
#define ID3_SIZE_LIMIT          63                  // Limit imposed by ESP8266Audio ID3 tag size limit
#define WIFI_CHANNEL            8                   // Channel to receive ESP-NOW messages

volatile unsigned long last_packet_time = 0;        // Timestamp of last received ESP-NOW message
volatile uint32_t      packets_received = 0;        // How many ESP-NOW messages have been received
volatile bool          playing          = false;    // Audio is currently playing
volatile uint16_t      write_index      = 0;        // Tracks where in the ring buffer to write
volatile uint16_t      read_index       = 0;        // Tracks where in the ring buffer to read
volatile uint16_t      data_available   = 0;        // Tracks how many bytes of unprocessed data are in the ring buffer
uint8_t                audio_buffer[BUFFER_SIZE];   // Ring buffer that contains MP3 data
SemaphoreHandle_t      buffer_lock;                 // Mutex for ring buffer access
AudioGeneratorMP3      *mp3;
AudioOutputI2S         *out;
AudioFileSourceID3     *id3;
AudioFileSourceBuffer  *buff; // Second buffer. Maybe should be audiooutputbuffer instead



// Hold data shuttled in through ID3 tag
struct data_shuttle {
  uint8_t data[ID3_SIZE_LIMIT];
  uint16_t len;
} data_shuttle;

// ID3 tag to data shuttler.
void id3_to_data(void*, const char *type, bool, const char *data) {
  if (strcmp(type, "eof") == 0) return;
  else if (strcmp(type, "Album") == 0)
    data_shuttle.len = atoi(data);
  else if (strcmp(type, "Title") == 0) { 
    uint16_t copyLen = min(data_shuttle.len, (uint16_t)sizeof(data_shuttle.data));
    memcpy(data_shuttle.data, data, copyLen);
    Serial.printf("Data Shuttle: %.*s\n", copyLen, (char*)data_shuttle.data);
  }
}



// Callback for receiving data from ESP-NOW
void on_data_receive(const esp_now_recv_info_t *inf, const uint8_t *data, int len){
  last_packet_time = millis();
  packets_received++;
  write_to_buffer((uint8_t*)data, len);
}



// Write data to ring buffer
void write_to_buffer(uint8_t* data, uint16_t length) {
  if (xSemaphoreTake(buffer_lock, portMAX_DELAY)) {
    uint16_t available_space = BUFFER_SIZE - data_available;
    
    if (length > available_space) {
      Serial.println("Warning: Buffer overflow!");
      length = available_space;
    }
    
    if (length == 0) {
      xSemaphoreGive(buffer_lock);
      return;
    }
    
    uint16_t space_to_end = BUFFER_SIZE - write_index;
    
    if (length <= space_to_end) {
      memcpy(&audio_buffer[write_index], data, length);
      write_index = (write_index + length) % BUFFER_SIZE;
    } else {
      memcpy(&audio_buffer[write_index], data, space_to_end);
      memcpy(&audio_buffer[0], data + space_to_end, length - space_to_end);
      write_index = length - space_to_end;
    }
    
    data_available += length;
    xSemaphoreGive(buffer_lock);
  }
}



// Read data from ring buffer
uint16_t read_from_buffer(uint8_t* data, uint16_t maxLength) {
  if (xSemaphoreTake(buffer_lock, portMAX_DELAY)) {
    uint16_t bytesToRead = (maxLength < data_available) ? maxLength : data_available;
    
    if (bytesToRead == 0) {
      xSemaphoreGive(buffer_lock);
      return 0;
    }
    
    uint16_t bytes_to_end = BUFFER_SIZE - read_index;
    
    if (bytesToRead <= bytes_to_end) {
      memcpy(data, &audio_buffer[read_index], bytesToRead);
      read_index = (read_index + bytesToRead) % BUFFER_SIZE;
    } else {
      memcpy(data, &audio_buffer[read_index], bytes_to_end);
      memcpy(data + bytes_to_end, &audio_buffer[0], bytesToRead - bytes_to_end);
      read_index = bytesToRead - bytes_to_end;
    }
    
    data_available -= bytesToRead;
    xSemaphoreGive(buffer_lock);
    return bytesToRead;
  }
  
  return 0;
}



// Custom audio source for ESP-NOW data
class AudioFileSourceESPNOW : public AudioFileSource {
  public:
    AudioFileSourceESPNOW() {bufferSize = BUFFER_SIZE;}
    virtual          ~AudioFileSourceESPNOW() override {}
    virtual uint32_t read(void *data, uint32_t len) override {return read_from_buffer((uint8_t*)data, len);}
    virtual bool     isOpen() override { return true; }
    void             writeData(uint8_t* data, uint16_t length) {write_to_buffer(data, length);}
  private:
    uint32_t bufferSize;
}; AudioFileSourceESPNOW *espnowSource;





void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  esp_wifi_set_channel(WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
  esp_now_init();
  esp_now_register_recv_cb(on_data_receive);
  delay(1000);
  Serial.printf("MAC Address: %s\n", WiFi.macAddress().c_str());

  buffer_lock  = xSemaphoreCreateMutex();
  espnowSource = new AudioFileSourceESPNOW(); 
  buff         = new AudioFileSourceBuffer(espnowSource, AUDIO_BUFFER_SIZE);
  id3          = new AudioFileSourceID3(buff);
  mp3          = new AudioGeneratorMP3();
  out          = new AudioOutputI2S();
  out->SetPinout(I2S_BCLK, I2S_LRC, I2S_DOUT);
  out->SetOutputModeMono(true);
  out->SetGain(DEFAULT_GAIN);
  out->SetRate(DEFAULT_RATE);
  id3->RegisterMetadataCB(id3_to_data, NULL);
    
  Serial.println("Waiting for MP3 data...");
}



void loop() {
  unsigned long cur_millis = millis();
  
  if (data_available > 0 && !playing && (cur_millis - last_packet_time) > CLEAR_BUFFER_AFTER ) {    
    if (xSemaphoreTake(buffer_lock, portMAX_DELAY)) {
      data_available = 0;
      write_index    = 0;
      read_index     = 0;
      xSemaphoreGive(buffer_lock);
    }
  }

  if (!playing && data_available >= MIN_BUFFER_BEFORE_START) {
    if (id3) delete id3;
    if(buff) delete buff;

    buff = new AudioFileSourceBuffer(espnowSource, AUDIO_BUFFER_SIZE);
    id3 = new AudioFileSourceID3(buff);
    id3->RegisterMetadataCB(id3_to_data, NULL);

    mp3->begin(id3, out);
    playing = true;
    Serial.println("Started playback");
  }

  if (playing && mp3->isRunning()) {
    if (!mp3->loop()) {
      mp3->stop();
      playing = false;
      Serial.println("Stopped playback");
    }
  }

  #ifdef DEBUG
    static unsigned long lastStats = 0;
    if (cur_millis - lastStats > DEBUG) {
      lastStats = cur_millis;
      Serial.printf("Packets: %5u\tBuffers: %4u/%4u\t%4u/%4u\tFree Mem: %6u\tPlaying: %s\n",packets_received, data_available, BUFFER_SIZE, buff->getFillLevel(),AUDIO_BUFFER_SIZE, ESP.getFreeHeap(), playing ? "Yes" : "No");
    }
  #endif
  taskYIELD();
}
