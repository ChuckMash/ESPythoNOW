#include <espnow.h>
#include <ESP8266WiFi.h>
#include <FastLED.h>

#define LED_NUM    82                    // Number of LEDs
#define LED_PIN    D4                    // LED pin
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
void esp_now_rx_callback(uint8_t *mac, uint8_t *data, uint8_t len) {

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
  wifi_set_channel(8);
  esp_now_init();
  esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);
  esp_now_register_recv_cb(esp_now_recv_cb_t(esp_now_rx_callback));
}



void loop() {
  if(final_packet){
    FastLED.show();
    do_fps();
    final_packet = false;
  }
}
