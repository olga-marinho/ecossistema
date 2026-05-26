#include <Adafruit_NeoPixel.h>

#define PIN 10
#define NUM_LEDS 30

Adafruit_NeoPixel strip(NUM_LEDS, PIN, NEO_GRB + NEO_KHZ800);

void setAllColor(uint8_t r, uint8_t g, uint8_t b) {
  for (int i = 0; i < NUM_LEDS; i++) {
    strip.setPixelColor(i, strip.Color(r, g, b));
  }
  strip.show();
}

void setup() {
  Serial.begin(9600);
  strip.begin();
  strip.show();
  Serial.println("Cores: vermelho, verde, azul, amarelo, branco, laranja, roxo, apagar");
}

void loop() {
  if (Serial.available() > 0) {
    String cor = Serial.readStringUntil('\n');
    cor.trim();
    cor.toLowerCase();

    if (cor == "vermelho") {
      setAllColor(255, 0, 0);
    } else if (cor == "verde") {
      setAllColor(0, 255, 0);
    } else if (cor == "azul") {
      setAllColor(0, 0, 255);
    } else if (cor == "amarelo") {
      setAllColor(255, 255, 0);
    } else if (cor == "branco") {
      setAllColor(255, 255, 255);
    } else if (cor == "laranja") {
      setAllColor(255, 80, 0);
    } else if (cor == "roxo") {
      setAllColor(128, 0, 255);
    } else if (cor == "apagar") {
      setAllColor(0, 0, 0);
    }

    Serial.println(cor);
  }
}
