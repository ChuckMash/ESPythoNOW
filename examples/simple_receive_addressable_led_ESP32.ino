#include <esp_now.h>
#include "esp_private/wifi.h"
#include <WiFi.h>
#include <FastLED.h>

#define LED_NUM    82                    // Number of LEDs
#define LED_PIN    16                    // LED pin
unsigned long      fps_last_time;        // Time of last FPS calculation
unsigned long      fps_frame_count;      // Number of frames since last FPS calculation
bool               final_packet = false; // Flag for last multipart
uint16_t           start_pos;            // Start LED of incoming LED data 
CRGBArray<LED_NUM> leds;                 // FastLED 



// Calculate FPS
void do_fps(){
  fps_frame_count++;
  if (millis() - fps_last_time >= 1000) {
    Serial.print("FPS: "); Serial.println(fps_frame_count);
    fps_frame_count = 0;
    fps_last_time = millis();
  }
}



// ESP-NOW receive message callback
void esp_now_rx_callback(const esp_now_recv_info_t * info, const uint8_t *data, int len) {

  // Set start LED for new data
  memcpy(&start_pos, data, 2);

  // Check inbound data for size
  if( (len-2) > (LED_NUM*3 - start_pos*3) ){
    //Serial.println("size mismatch");
    return;
  }

  // Check if inbound data is final multipart for LEDs greater than 82
  else if((len-2) == (LED_NUM*3 - start_pos*3)){
    final_packet = true;
  }

  // Set LED data
  memcpy(&leds[start_pos], data+2, len-2);
 }



void setup() {
  Serial.begin(115200);
  FastLED.addLeds<NEOPIXEL, LED_PIN>(leds, LED_NUM);
  WiFi.mode(WIFI_STA);
  esp_wifi_set_channel(8, WIFI_SECOND_CHAN_NONE);
  esp_now_init();
  esp_now_register_recv_cb(esp_now_recv_cb_t(esp_now_rx_callback));
}



void loop() {
  if(final_packet){
    FastLED.show();
    do_fps();
    final_packet = false;
  }
}
