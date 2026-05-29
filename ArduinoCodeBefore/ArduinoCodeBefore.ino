#include <Adafruit_NeoPixel.h>
#include <ModbusMaster.h>

#if !defined(ESP32)
#include <SoftwareSerial.h>
#endif

#define NUM_LEDS 30
#define LERP_SPEED 0.06

#if defined(ESP32)

#define LDR_PIN 34
// WROVER-B safe mapping (avoid boot strapping pins and PSRAM pins 16/17).
#define LED_PIN 27
#define RS485_RX_PIN 26
#define RS485_TX_PIN 25

#define MAX485_DIR_PIN 14
#define MAX485_DE MAX485_DIR_PIN
#define MAX485_RE_NEG MAX485_DIR_PIN

HardwareSerial rs485Serial(2);
#else
#define LDR_PIN A0
#define LED_PIN 10
#define MAX485_DE 3
#define MAX485_RE_NEG 2

SoftwareSerial rs485Serial(7, 8);
#endif

ModbusMaster node;
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

String inputBuffer = "";
float curR = 0, curG = 0, curB = 0;
float tgtR = 0, tgtG = 0, tgtB = 0;

float windSpeed = 0;
unsigned long lastModbus = 0;

void preTransmission() {
  digitalWrite(MAX485_RE_NEG, 1);
  digitalWrite(MAX485_DE, 1);
}

void postTransmission() {
  digitalWrite(MAX485_RE_NEG, 0);
  digitalWrite(MAX485_DE, 0);
}

void setup() {
  Serial.begin(9600);

  pinMode(MAX485_DE, OUTPUT);
  pinMode(MAX485_RE_NEG, OUTPUT);
  digitalWrite(MAX485_RE_NEG, 0);
  digitalWrite(MAX485_DE, 0);

  #if defined(ESP32)
  rs485Serial.begin(4800, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);
  #else
  rs485Serial.begin(4800);
  #endif

  node.begin(1, rs485Serial);
  node.preTransmission(preTransmission);
  node.postTransmission(postTransmission);

  strip.begin();
  strip.show();
}

void loop() {
  if (millis() - lastModbus >= 500) {
    lastModbus = millis();

    if (node.readHoldingRegisters(0, 1) == node.ku8MBSuccess) {
      windSpeed = node.getResponseBuffer(0) * 0.1;
    }

    int ldr = analogRead(LDR_PIN);
    Serial.print(ldr);
    Serial.print(",");
    Serial.println(windSpeed, 2);
  }

  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      int i1 = inputBuffer.indexOf(',');
      int i2 = inputBuffer.indexOf(',', i1 + 1);
      if (i1 > 0 && i2 > i1) {
        tgtR = inputBuffer.substring(0, i1).toInt();
        tgtG = inputBuffer.substring(i1 + 1, i2).toInt();
        tgtB = inputBuffer.substring(i2 + 1).toInt();
      }
      inputBuffer = "";
    } else {
      inputBuffer += c;
    }
  }

  curR += (tgtR - curR) * LERP_SPEED;
  curG += (tgtG - curG) * LERP_SPEED;
  curB += (tgtB - curB) * LERP_SPEED;

  for (int i = 0; i < NUM_LEDS; i++) {
    strip.setPixelColor(i, strip.Color((int)curR, (int)curG, (int)curB));
  }
  strip.show();

  delay(20);
}
