/*
  ESP32 PIR -> MQTT (Olhar Vivo)
  - Lê sensor PIR no GPIO 13
  - Publica eventos em 'olharvivo/sensor/pir'
  - Debounce simples + retenção

  Bibliotecas:
    - WiFi.h (nativa ESP32)
    - PubSubClient (Gerenciador de Bibliotecas)
*/

#include <WiFi.h>
#include <PubSubClient.h>

// ======== CONFIG ========
const char* WIFI_SSID     = "SEU_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA";

const char* MQTT_BROKER   = "192.168.1.10";
const uint16_t MQTT_PORT  = 1883;
const char* MQTT_CLIENTID = "olharvivo-pir-01";
const char* MQTT_TOPIC    = "olharvivo/sensor/pir";

const int PIR_PIN = 13;
const unsigned long DEBOUNCE_MS = 1500;
// =========================

WiFiClient espClient;
PubSubClient mqtt(espClient);
unsigned long lastPub = 0;
int lastState = LOW;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Conectando WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi conectado. IP: " + WiFi.localIP().toString());
}

void connectMQTT() {
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  while (!mqtt.connected()) {
    Serial.print("Conectando MQTT...");
    if (mqtt.connect(MQTT_CLIENTID)) {
      Serial.println("OK");
      mqtt.publish(MQTT_TOPIC, "online", true);
    } else {
      Serial.print("falhou rc="); Serial.print(mqtt.state());
      Serial.println(" tente novamente em 2s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIR_PIN, INPUT);
  connectWiFi();
  connectMQTT();
}

void loop() {
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  int state = digitalRead(PIR_PIN);
  unsigned long now = millis();

  if (state == HIGH && (now - lastPub) > DEBOUNCE_MS) {
    mqtt.publish(MQTT_TOPIC, "motion", true);
    lastPub = now;
  }
  lastState = state;
}