// MAX30102 connection test for ESP32. Needs no libraries.
//
// Every 3 seconds it:
//   1. scans the I2C bus and lists every device that answers
//   2. asks the device at 0x57 for its part ID 10 times (a MAX30102 answers 0x15)
//      and reports how many of the 10 worked, so a loose wire shows up as
//      "some worked, some didn't" instead of a single confusing error
//
// Wiring (power it from 3.3 V if you can, see HARDWARE_DESIGN.md):
//   MAX30102 VIN -> ESP32 3V3      MAX30102 GND -> ESP32 GND
//   MAX30102 SDA -> SDA_PIN        MAX30102 SCL -> SCL_PIN
//   INT is not needed. Leave it unconnected.
//
// Open the Serial Monitor at 115200 baud.
//
// Error 263 printed by the ESP32 itself ("i2cWriteReadNonStop returned Error 263")
// means TIMEOUT: it waited for the sensor and nothing came back. This sketch
// still prints its own summary after those lines. To hide the ESP32's own error
// lines, set Tools > Core Debug Level > None.
#include <Wire.h>

// Set these to the pins you actually wired.
//   Classic ESP32 DevKit (ESP32-WROOM-32): SDA 21, SCL 22
//   ESP32-S3 or ESP32-C3 DevKit:           SDA 8,  SCL 9
const int SDA_PIN = 8;
const int SCL_PIN = 9;

const uint8_t MAX30102_ADDRESS = 0x57;
const uint8_t PART_ID_REGISTER = 0xFF;  // a MAX30102 / MAX30105 answers 0x15
const int EXPECTED_PART_ID = 0x15;
const int ATTEMPTS = 10;

enum PartIdResult { PART_ID_OK, PART_ID_WRONG, PART_ID_NO_REPLY };

PartIdResult readPartIdOnce(int* idOut) {
  Wire.beginTransmission(MAX30102_ADDRESS);
  Wire.write(PART_ID_REGISTER);
  if (Wire.endTransmission(false) != 0) return PART_ID_NO_REPLY;
  if (Wire.requestFrom(MAX30102_ADDRESS, static_cast<uint8_t>(1)) != 1) return PART_ID_NO_REPLY;
  *idOut = Wire.read();
  return *idOut == EXPECTED_PART_ID ? PART_ID_OK : PART_ID_WRONG;
}

void checkPartId() {
  int good = 0, noReply = 0, wrong = 0, lastWrongId = -1;
  for (int i = 0; i < ATTEMPTS; i++) {
    int id = -1;
    switch (readPartIdOnce(&id)) {
      case PART_ID_OK: good++; break;
      case PART_ID_WRONG: wrong++; lastWrongId = id; break;
      case PART_ID_NO_REPLY: noReply++; break;
    }
    delay(50);
  }
  Serial.printf("part ID reads out of %d: %d good, %d no reply, %d wrong ID\n", ATTEMPTS, good, noReply, wrong);

  if (good == ATTEMPTS) {
    Serial.println("GOOD: every read returned 0x15. The sensor is connected and talking. Wiring is fine.");
  } else if (good > 0) {
    Serial.println("INTERMITTENT: it works sometimes. That is almost always a loose or badly-touching wire.");
    Serial.println("  Wiggle each of the 4 wires (VIN, GND, SDA, SCL) gently while watching the counts above.");
    Serial.println("  Whichever one changes the result is the bad contact. Soldering fixes this for good.");
  } else if (wrong > 0) {
    Serial.printf("Something answers at 0x57 but its part ID is 0x%02X, not 0x15. Not a MAX30102.\n", lastWrongId);
  } else {
    Serial.println("It answers its address but never sends data back (that is the error 263 timeout).");
    Serial.println("  Most likely a poor contact on SDA or SCL, or a weak power connection.");
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500);  // give the Serial Monitor time to connect

  Serial.println();
  Serial.println("MAX30102 connection test");
  Serial.printf("Board: %s (revision %d)\n", ESP.getChipModel(), ESP.getChipRevision());
  Serial.printf("This board's default I2C pins: SDA=%d SCL=%d\n", SDA, SCL);
  Serial.printf("This test is using:           SDA=%d SCL=%d\n", SDA_PIN, SCL_PIN);

#if CONFIG_IDF_TARGET_ESP32
  // On a classic ESP32, GPIO 6 to 11 are wired to the board's own flash chip.
  // Driving them as I2C can crash or hang the board, so refuse to start.
  if ((SDA_PIN >= 6 && SDA_PIN <= 11) || (SCL_PIN >= 6 && SCL_PIN <= 11)) {
    Serial.println();
    Serial.println("STOP: this is a classic ESP32, and GPIO 6 to 11 are the flash chip.");
    Serial.println("Move the SDA wire to GPIO 21 and the SCL wire to GPIO 22,");
    Serial.println("then set SDA_PIN = 21 and SCL_PIN = 22 at the top of this sketch.");
    while (true) delay(1000);
  }
#endif

  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);  // slow and forgiving for a first test
}

void loop() {
  Serial.println();
  Serial.println("--- scanning ---");
  int found = 0;
  bool sensorSeen = false;
  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      Serial.printf("device found at 0x%02X\n", address);
      found++;
      if (address == MAX30102_ADDRESS) sensorSeen = true;
    }
  }

  if (found == 0) {
    Serial.println("NOTHING answered. Check, in this order:");
    Serial.println("  1. VIN goes to a power pin and GND goes to GND (the sensor's LED may glow red when powered)");
    Serial.println("  2. SDA and SCL are not swapped");
    Serial.println("  3. SDA_PIN and SCL_PIN above match the pins you wired");
    Serial.println("  4. Every connection actually touches. Wrapped or looped wires often don't hold.");
  } else if (!sensorSeen) {
    Serial.println("Something answered, but nothing at 0x57, which is where a MAX30102 lives.");
  } else {
    checkPartId();
  }

  delay(3000);
}
