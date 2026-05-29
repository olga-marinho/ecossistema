#include <WiFi.h>
#include <PubSubClient.h>
#include <Adafruit_NeoPixel.h>

#define NUM_LEDS 139
#define LERP_SPEED 0.06
#define LDR_PIN 34
#define LDR_PIN2 35
#define LDR_PIN3 32
#define LED_PIN 27

const char* WIFI_SSID = "IoT-test";
const char* WIFI_PASSWORD = "Denohd0dkooz8Oir";
const char* MQTT_BROKER = "broker.emqx.io";
const int MQTT_PORT = 1883;
const char* MQTT_USER = "";
const char* MQTT_PASSWORD = "";
const char* MQTT_TOPIC_LDR = "ecossistema/sensor/ldr";
const char* MQTT_TOPIC_LED = "ecossistema/led/rgb";

Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);
WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);

float curR = 0, curG = 0, curB = 0;
float tgtR = 0, tgtG = 0, tgtB = 0;
unsigned long lastLdrSend = 0;

void aplicarCor() {
	for (int i = 0; i < NUM_LEDS; i++) {
		strip.setPixelColor(i, strip.Color((int)curR, (int)curG, (int)curB));
	}
	strip.show();
}

void atualizarCorAlvo(String mensagem) {
	int i1 = mensagem.indexOf(',');
	int i2 = mensagem.indexOf(',', i1 + 1);
	if (i1 > 0 && i2 > i1) {
		tgtR = mensagem.substring(0, i1).toInt();
		tgtG = mensagem.substring(i1 + 1, i2).toInt();
		tgtB = mensagem.substring(i2 + 1).toInt();
	}
}

void callbackMQTT(char* topic, byte* payload, unsigned int length) {
	String mensagem;
	for (unsigned int i = 0; i < length; i++) {
		mensagem += (char)payload[i];
	}

	if (String(topic) == MQTT_TOPIC_LED) {
		atualizarCorAlvo(mensagem);
	}
}

void reconnectWiFi() {
	if (WiFi.status() == WL_CONNECTED) {
		return;
	}

	WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
	while (WiFi.status() != WL_CONNECTED) {
		delay(250);
	}
}

void reconnectMQTT() {
	while (!mqttClient.connected()) {
		String clientId = "ecossistema_esp32_" + String(random(0xffff), HEX);

		bool conectado = false;
		if (strlen(MQTT_USER) > 0) {
			conectado = mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD);
		} else {
			conectado = mqttClient.connect(clientId.c_str());
		}

		if (conectado) {
			mqttClient.subscribe(MQTT_TOPIC_LED);
		} else {
			delay(1000);
		}
	}
}

void setup() {
	Serial.begin(115200);
	pinMode(LDR_PIN, INPUT);
	pinMode(LDR_PIN2, INPUT);
	pinMode(LDR_PIN3, INPUT);
	strip.begin();
	strip.show();

	randomSeed(micros());

	mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
	mqttClient.setCallback(callbackMQTT);
}

void loop() {
	reconnectWiFi();
	reconnectMQTT();
	mqttClient.loop();

	if (millis() - lastLdrSend >= 500) {
		lastLdrSend = millis();
		int ldr = (analogRead(LDR_PIN) + analogRead(LDR_PIN2) + analogRead(LDR_PIN3)) / 3;
		mqttClient.publish(MQTT_TOPIC_LDR, String(ldr).c_str());
	}

	curR += (tgtR - curR) * LERP_SPEED;
	curG += (tgtG - curG) * LERP_SPEED;
	curB += (tgtB - curB) * LERP_SPEED;
	aplicarCor();

	delay(20);
}
