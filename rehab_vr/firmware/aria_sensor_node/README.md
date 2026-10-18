# ARIA Sensor Node Firmware

ESP32 firmware for the arm-worn node. Once a second it sends the laptop
whatever it can trust from three channels: heart rate (PPG), skin
temperature, and skin conductance (EDA). Placement and reasoning are in
[docs/HARDWARE_DESIGN.md](../../../docs/HARDWARE_DESIGN.md).

**Status, stated plainly.** The signal code (PPG heart rate, motion gate, EDA
math, JSON payload, ECG reference) is unit tested on a PC against synthetic
signals. The sketch itself has only been type-checked against stub headers.
Nothing here has run on real hardware yet, and the PPG thresholds in
`makePpgConfig()` are starting points to tune from a real recording.

---

## 1. Parts

Pick what you actually have. The switches are at the top of
[aria_sensor_node.ino](aria_sensor_node.ino).

| Part | Role | Notes |
|---|---|---|
| ESP32 DevKit | Brain, WiFi | |
| PPG sensor | Heart rate, upper-arm band | `PPG_SOURCE_MAX3010X 1` for a MAX30102/MAX30101 breakout (I2C). `0` for a simple analog pulse sensor on GPIO35 |
| MPU6050 | Motion gate | Same band as the PPG. Without it the firmware cannot tell a real pulse from arm motion (`ENABLE_IMU 0` still builds, but expect worse HR) |
| MAX30205 | Skin temperature, contact | Forearm, just proximal to the radial artery |
| Grove GSR | EDA | Palm / fingers |
| AD8232 | ECG **reference only** | `ENABLE_ECG_REFERENCE 1`. Used to check the PPG on the bench, not worn as a sensor |
| LiPo + charger | Power | Required whenever AD8232 electrodes are on skin |

**AD8232 safety.** Run the node from a battery, not from a laptop USB cable
plugged into mains, whenever electrodes touch skin. Battery power keeps the
person electrically isolated from the wall. Ask a teacher or mentor to look at
your setup before putting electrodes on anyone.

## 2. Wiring

I2C bus (SDA GPIO21, SCL GPIO22) is shared. Addresses do not clash:
MAX30102 `0x57`, MAX30205 `0x48`, MPU6050 `0x68`. Every I2C part gets 3.3 V.

| Signal | ESP32 pin | Notes |
|---|---|---|
| GSR signal | GPIO34 | ADC1 pin, input only |
| Analog PPG signal | GPIO35 | Only if `PPG_SOURCE_MAX3010X 0` |
| AD8232 OUTPUT | GPIO36 | Reference mode only |
| AD8232 LO+ / LO- | GPIO32 / GPIO33 | Leads-off detection |

Only ADC1 pins are used because ADC2 stops working while WiFi is on. I did not
verify a "3.3 V switch" on the Grove GSR board from documentation, so check
your own board's supply range before wiring it to 3.3 V.

## 3. Arduino IDE setup

1. Install ESP32 board support (Boards Manager, search "esp32").
2. Libraries: **SparkFun MAX3010x Pulse and Proximity Sensor Library** (only if
   using the MAX3010x). Everything else in this folder is self-contained.
3. Board: `ESP32 Dev Module`.
4. Copy `wifi_config.example.h` to `wifi_config.h`, fill in your WiFi and your
   laptop's IPv4 address (`ipconfig`). `wifi_config.h` is gitignored.
5. Upload, then open the Serial Monitor at 115200.

## 4. Bring-up, in this order

1. **Each sensor alone.** Confirm the Serial Monitor names each part that
   initializes. A part that fails is skipped and its channel is simply omitted.
2. **Look at the raw PPG.** Build with `-DSTREAM_RAW_PPG=1` (or set it to 1),
   open Tools > Serial Plotter, and hold still. You should see a clean
   repeating pulse. If it is flat, the sensor has no contact. If it is
   clipped, lower the LED current. This is the step that tells you whether the
   upper arm gives a usable signal at all.
3. **Tune `makePpgConfig()`.** `contactMinRaw` and `minRms` depend on your
   sensor and your arm. Set them from the raw recording, not from guesses.
4. **Compare against the reference.** With `ENABLE_ECG_REFERENCE 1` on
   battery power, log PPG and ECG heart rate together, then score them with
   `tools/compare_hr.py` (see section 6).
5. **Run the whole chain.** On the laptop:

```bash
python -m rehab_vr.sensor_service.server --hardware
```

Then `python rehab_vr/web/serve.py 5500` and open the page. Press
**Calibrate (30 s)** while the athlete sits still. If the node stops
reporting, the status line says so within about 5 seconds instead of showing a
frozen number.

## 5. What the firmware refuses to do

- No made-up values. A channel that is not trustworthy is omitted from the
  message, and the service treats it as "no reading."
- Heart rate is omitted while the arm is moving (motion gate, 1.5 s holdoff),
  when the sensor has no contact, or when the pulse is not clearly periodic.
  That means **no heart rate mid-throw, by design.** It comes back a moment
  after the arm settles.
- EDA is omitted when the ADC is at a rail (open or shorted electrode).
- The service also drops any value outside a wide sanity range, and never
  escalates the VR exposure level on partial data.

## 6. Tests you can run without hardware

From the repo root (needs a C++ compiler; I used `zig c++`):

```bash
python rehab_vr/firmware/aria_sensor_node/test/compile_check.py
python -m pytest tests/test_compare_hr.py -q
```

`test/test_firmware.cpp` builds and runs the signal-code checks on a PC.
`compile_check.py` type-checks the `.ino` across 8 option combinations against
stub Arduino headers. These prove the logic and the syntax. They do not prove
the sensors work on a person.

## 7. This is a prototype, not a medical device

The EDA conversion is Seeed's published reference formula, not a clinical
calibration. The score is compared against a per-athlete baseline that you
measure with the Calibrate button. Nothing here is clinically validated.
