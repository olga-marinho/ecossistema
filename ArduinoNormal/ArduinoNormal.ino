#include <ModbusMaster.h>
#include <SoftwareSerial.h>

#define MAX485_DE 3
#define MAX485_RE_NEG 2

SoftwareSerial rs485Serial(10, 11);
ModbusMaster node;

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

	rs485Serial.begin(4800);

	node.begin(1, rs485Serial);
	node.preTransmission(preTransmission);
	node.postTransmission(postTransmission);
}

void loop() {
	if (millis() - lastModbus >= 500) {
		lastModbus = millis();

		if (node.readHoldingRegisters(0, 1) == node.ku8MBSuccess) {
			windSpeed = node.getResponseBuffer(0) * 0.1;
		}

		Serial.print("WIND,");
		Serial.println(windSpeed, 2);
	}
}
