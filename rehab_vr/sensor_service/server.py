"""WebSocket server broadcasting fused sensor readings to the browser app.

Reads from the simulator by default. Pass --hardware to read from the real
ESP32 node instead (see hardware_reader.py and
rehab_vr/firmware/aria_sensor_node/). Both readers expose the same read()
contract, {eda_us, heart_rate_bpm, skin_temp_c}, except that the hardware
reader returns None for any channel that is not currently trustworthy.

One ticker reads the sensor once per tick and sends the same message to every
connected browser, so the number of open pages never changes how often the
sensor is read or how a calibration is sampled.

A browser can send the text "calibrate" to start a resting-baseline
calibration (see calibration.py). While it runs, the message carries no
arousal score, so nothing downstream can act on a half-measured baseline.

Run from the repo root:
  python -m rehab_vr.sensor_service.server              # simulator
  python -m rehab_vr.sensor_service.server --hardware    # real ESP32 node
"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Optional

import websockets

from . import hardware_reader, sensor_config, simulator
from .calibration import BaselineCalibrator, CalibrationResult
from .fusion import READING_TO_CHANNEL, Baseline, fuse
from .sensor_config import SensorConfig

HOST = "0.0.0.0"
PORT = 8765
TICK_SECONDS = 1.0
CALIBRATION_SECONDS = 30.0


class SensorSession:
    """The state shared by every connected browser: the active baseline and
    the calibration in progress. Kept separate from the socket handling so it
    can be tested without any network."""

    def __init__(
        self,
        tick_seconds: float = TICK_SECONDS,
        calibration_seconds: float = CALIBRATION_SECONDS,
        config: SensorConfig = sensor_config.DEFAULT,
    ):
        self.tick_seconds = tick_seconds
        self.calibration_ticks = max(1, round(calibration_seconds / tick_seconds))
        self.config = config
        self.baseline = Baseline()
        self.baseline_is_personal = False
        self._calibrator: Optional[BaselineCalibrator] = None
        self._last_result: Optional[CalibrationResult] = None

    def start_calibration(self) -> None:
        # Only the channels this build actually has, or a build without a
        # temperature sensor could never finish a calibration.
        self._calibrator = BaselineCalibrator(self.calibration_ticks, channels=self.config.expected)
        self._last_result = None

    @property
    def calibrating(self) -> bool:
        return self._calibrator is not None

    def process(self, reading: dict) -> dict:
        """One tick: fuse the reading against the current baseline and report
        calibration state. During calibration the reading is collected and the
        arousal score is withheld (None)."""
        # Ignore any channel this build does not have fitted, so the simulator
        # behaves exactly like the real hardware it is standing in for. Without
        # this, a simulator run would quietly score a channel the actual node
        # can never send, and would look better than the build ever will.
        reading = {
            name: (reading.get(name) if self.config.expects(name) else None)
            for name in sensor_config.SCORED_CHANNELS
        }
        fused = fuse(reading["eda_us"], reading["heart_rate_bpm"], reading["skin_temp_c"], self.baseline)

        if self._calibrator is not None:
            self._calibrator.add(reading)
            fused["arousal_score"] = None  # never score against a half-measured baseline
            seconds_left = round(self._calibrator.ticks_left * self.tick_seconds, 1)
            if self._calibrator.done:
                result = self._calibrator.result()
                self._calibrator = None
                self._last_result = result
                if result.ok:
                    self.baseline = result.baseline
                    self.baseline_is_personal = True
                    calibration = self._status("done", 0.0)
                else:
                    calibration = self._status("failed", 0.0)
            else:
                calibration = self._status("running", seconds_left)
        else:
            calibration = self._status("done" if self._last_result and self._last_result.ok else
                                       "failed" if self._last_result else "idle", None)

        # A channel this build never had is not a dropout. Only a channel the
        # build was expected to deliver, and did not, blocks stepping up.
        missing = [
            name
            for name in self.config.expected
            if fused["channels"][READING_TO_CHANNEL[name]]["available"] is False
        ]
        return {
            **reading,  # the filtered values, so the UI never shows an unfitted channel
            **fused,
            "calibration": calibration,
            "sensor_config": self.config.name,
            "channels_expected": list(self.config.expected),
            "channels_missing": missing,
            "complete": not missing,
        }

    def _status(self, state: str, seconds_left: Optional[float]) -> dict:
        result = self._last_result
        return {
            "state": state,
            "seconds_left": seconds_left,
            "personal_baseline": self.baseline_is_personal,
            "reason": result.reason if result and not result.ok else None,
        }


async def run_server(reader, host: str = HOST, port: int = PORT, tick_seconds: float = TICK_SECONDS,
                     calibration_seconds: float = CALIBRATION_SECONDS, ready: Optional[asyncio.Future] = None,
                     config: SensorConfig = sensor_config.DEFAULT) -> None:
    session = SensorSession(tick_seconds, calibration_seconds, config)
    clients: set = set()

    async def handler(websocket):
        clients.add(websocket)
        try:
            async for message in websocket:
                if message == "calibrate" and not session.calibrating:
                    session.start_calibration()
        except websockets.exceptions.ConnectionClosed:
            pass  # a closed/reloaded browser tab, not a server error
        finally:
            clients.discard(websocket)

    async def ticker():
        while True:
            reading = reader.read()
            payload = {"timestamp": time.time(), **reading, **session.process(reading)}
            if reader is hardware_reader:
                payload["hardware_stale"] = hardware_reader.is_stale()
            message = json.dumps(payload)
            for websocket in list(clients):
                try:
                    await websocket.send(message)
                except websockets.exceptions.ConnectionClosed:
                    clients.discard(websocket)
            await asyncio.sleep(tick_seconds)

    async with websockets.serve(handler, host, port) as server:
        bound = server.sockets[0].getsockname()[1]
        if ready is not None and not ready.done():
            ready.set_result(bound)
        ticker_task = asyncio.create_task(ticker())
        try:
            await asyncio.Future()
        finally:
            ticker_task.cancel()


async def main(use_hardware: bool, config_name: str = sensor_config.DEFAULT.name) -> None:
    reader = hardware_reader if use_hardware else simulator
    mode = "REAL ESP32 HARDWARE" if use_hardware else "simulator"
    config = sensor_config.get(config_name)
    print(f"Sensor fusion service on ws://{HOST}:{PORT}, reading from: {mode}")
    print(f"Sensor config '{config.name}': expects {', '.join(config.expected)}. {config.description}")
    if use_hardware:
        hardware_reader.ensure_ingest_server_started()  # start ingest immediately, don't wait for the first client
    await run_server(reader, config=config)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hardware", action="store_true", help="read from the real ESP32 sensor node instead of the simulator"
    )
    parser.add_argument(
        "--config",
        default=sensor_config.DEFAULT.name,
        choices=sorted(sensor_config.CONFIGS),
        help="which sensors this build has fitted (default: %(default)s)",
    )
    args = parser.parse_args()
    asyncio.run(main(args.hardware, args.config))
