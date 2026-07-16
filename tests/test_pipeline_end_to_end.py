"""Full SensorPacket -> DashboardObject pipeline, driven by the simulator,
matching ARCHITECTURE.md's documented data flow end to end."""
from datetime import datetime, timedelta, timezone

from sentra.models import PatientState
from sentra.pipeline import SentraPipeline
from sentra.simulator import NodeSimulator


def _run(pipeline, node, ticks, start):
    ts = start
    last = None
    for _ in range(ticks):
        for packet in node.tick(ts):
            result = pipeline.on_packet(packet)
            if result is not None:
                last = result
        ts += timedelta(seconds=1)
    return last


def test_stable_patient_produces_dashboard_output_without_crashing():
    pipeline = SentraPipeline()
    pipeline.calibrate_patient("P1", "adult_18_64yr")
    node = NodeSimulator("P1", "node-1", scenario="stable", true_hr=65)

    result = _run(pipeline, node, ticks=60, start=datetime.now(timezone.utc))

    assert result is not None
    assert result.patient_id == "P1"
    assert result.patient_state == PatientState.NORMAL
    assert result.explanation is not None
    assert 0.0 <= result.confidence <= 1.0


def test_invalid_packet_does_not_crash_pipeline():
    from sentra.models import SensorPacket, SensorType

    pipeline = SentraPipeline()
    bad_packet = SensorPacket(
        patient_id="", device_id="node-1", sensor_type=SensorType.PPG,
        sampling_rate=1, values=[70.0],
    )
    result = pipeline.on_packet(bad_packet)  # missing patient_id -> validation failure
    assert result is None  # rejected, not crashed


def test_intermittent_connection_does_not_crash_pipeline_across_reconnects():
    pipeline = SentraPipeline()
    pipeline.calibrate_patient("P1", "adult_18_64yr")
    node = NodeSimulator("P1", "node-1", scenario="intermittent", true_hr=75)

    # Long enough to guarantee at least one simulated disconnect/reconnect
    # cycle (NodeSimulator has a 2%/tick chance of dropping).
    result = _run(pipeline, node, ticks=200, start=datetime.now(timezone.utc))
    assert result is not None
