# Hardware

Bill of materials and wiring notes for the SENTRA Patient Node and Hub.

## Patient Node (per patient)

| Part | Purpose | Notes |
|---|---|---|
| ESP32 Dev Module | MCU + BLE | Runs `firmware/patient_node/patient_node.ino` |
| MAX30102 | PPG (HR + SpO2) | I2C |
| MAX30205 | Skin temperature | I2C |
| MPU6050 | Motion / fall detection | I2C |
| RGB LED | Local visual alert | GPIO 25/26/27, see firmware README |
| LiPo battery + charge circuit | Power | Voltage divider to GPIO 34 for battery monitoring |

No ECG hardware is included in this BOM — see `docs/HARDWARE_SCOPE.md` for
what that means for the software and how to add it later.

## Hub

Raspberry Pi (or equivalent) running `backend/`, receiving BLE
notifications from every Patient Node in range.

## What's next

This directory is a placeholder for wiring diagrams, enclosure files, and
a finalized BOM with part numbers/suppliers once hardware is ordered and
assembled — none of that exists yet.
