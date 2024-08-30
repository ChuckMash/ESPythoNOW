#include <espnow.h>
#include <ESP8266WiFi.h>

typedef struct __attribute__ ((packed)) python_message {
  int a = 567;
  bool b = false;
  uint8_t c[22];
} python_message;
python_message pm;

uint8_t python_peer[] = {0xFF,0xFF,0xFF,0xFF,0xFF,0xFF};

void esp_now_rx_callback(uint8_t *mac, uint8_t *data, uint8_t len) {
  memcpy(&pm, data, sizeof(pm));
  Serial.println(pm.a);
  Serial.println(pm.b);
  Serial.write(pm.c, 22);
  Serial.println();
 }

void setup() {
  Serial.begin(115200);
  WiFi.mode(WIFI_STA);
  wifi_set_channel(8);
  esp_now_init();
  esp_now_set_self_role(ESP_NOW_ROLE_CONTROLLER);
  esp_now_register_recv_cb(esp_now_recv_cb_t(esp_now_rx_callback));
}

void loop() {
  pm.a = 567;
  pm.b = false;
  memcpy(pm.c, "Hello from ESP device!", 22);
  esp_now_send(python_peer, (uint8_t *) &pm, sizeof(pm));
  delay(3000);
}
