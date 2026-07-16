# Patient Node Firmware

ESP32 sketch for the wearable Patient Node: `patient_node/patient_node.ino`.
Until a board is on the bench, `backend/sentra/simulator.py` plays this same
role in software so the rest of the pipeline (docs 03-12) can be built and
demoed against it.

## Files

- `patient_node/patient_node.ino` — setup/loop, BLE server, local RGB alert
  logic, battery read, and the disconnect buffer (graceful degradation).
- `patient_node/hr_spo2_max30102.h` — MAX30102: FIFO access via the SparkFun
  MAX3010x library, plus our own beat-detection (DC-tracking + rising-edge
  timing) and a rough ratio-of-ratios SpO2 estimate.
- `patient_node/temp_max30205.h` — MAX30205 skin temperature via direct I2C
  register reads (no vendor library needed).
- `patient_node/motion_mpu6050.h` — MPU6050 accelerometer via direct I2C
  register reads, with a rolling window used to tell a brief fall/impact
  apart from sustained seizure-like oscillation.

## Dependencies

- Arduino IDE or PlatformIO, board = "ESP32 Dev Module".
- Library: **SparkFun MAX3010x Pulse and Proximity Sensor Library** (for
  `hr_spo2_max30102.h`'s FIFO access).
- Everything else (`Wire.h`, `BLEDevice.h` and friends) ships with the
  ESP32 Arduino core.

## Wiring assumptions (edit the `#define`/`constexpr` pins in the .ino to match your board)

- I2C: MAX30102, MAX30205, and MPU6050 all share the bus (default ESP32
  SDA/SCL pins). Give the MPU6050 a distinct address if it collides with
  another I2C device on the same board.
- RGB LED on GPIO 25/26/27 (common-cathode assumed).
- Battery voltage on GPIO 34 through a 2:1 resistor divider (LiPo range
  ~3.3-4.2V doesn't fit the ESP32's 3.3V ADC directly).

## Packet contract

The node notifies one JSON object per sensor type per second over the BLE
characteristic, with field names matching `backend/sentra/models.py`'s
`SensorPacket` directly:

```json
{"patient_id":"P-A","device_id":"node-A","sensor_type":"PPG",
 "sampling_rate":1,"values":[72.00,97.00],"battery_level":98.5,
 "firmware_version":"1.0.0","metadata":{"seq":1042,"is_buffered":false}}
```

`sensor_type` is one of `PPG` (`values=[hr_bpm, spo2_pct]`), `IMU`
(`values=[motion_magnitude]`), or `TEMPERATURE` (`values=[skin_temp_c]`) —
matching the `column()` convention `backend/sentra/sensor_layer/window_builder.py`
expects (see `docs/HARDWARE_SCOPE.md` §4).

**`packet_id`, `timestamp`, and `connection_strength` are deliberately not
sent by the node.** They're properties the *receiver* measures (RSSI of
this specific link, arrival time) or a housekeeping ID the Hub is equally
able to assign from `metadata.seq` — the Hub's BLE central should fill
these in before constructing a full `SensorPacket` and calling
`SentraPipeline.on_packet()`.

## Graceful degradation

While disconnected, the node keeps sampling and pushes each `Sample` into a
fixed-size ring buffer (`BUFFER_CAPACITY = 300`, ~5 minutes at 1 Hz) instead
of dropping it. On reconnect, `flushBufferIfConnected()` notifies the whole
backlog (each one flagged `metadata.is_buffered=true`) before resuming live
sends, so the Hub can backfill history rather than showing a gap.

## What's next

- A real `backend/sentra/ble_manager.py` BLE central on the Raspberry Pi to
  replace `simulator.py` — it needs to parse these JSON notifications,
  measure the link's actual RSSI, assign `packet_id`/`timestamp`, and call
  `SentraPipeline.on_packet()`. Nothing else in `backend/sentra/` needs to
  change to support this — `on_packet()` already accepts a `SensorPacket`
  regardless of where it came from.
- Replace the ratio-of-ratios SpO2 estimate with a calibrated lookup table
  per the MAX30102/MAX30105 datasheet before trusting SpO2 numbers.
- Tune `Mpu6050::motionMetric()`'s scale factor and the fall/seizure
  thresholds against real accelerometer data — the current values are
  starting guesses, not validated ones (see `docs/HARDWARE_SCOPE.md`).
- Multi-node BLE range/interference testing per `docs/14_MVP_Deployment_Roadmap.md`.
