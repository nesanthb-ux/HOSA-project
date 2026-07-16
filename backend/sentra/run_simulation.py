import time
from datetime import datetime, timezone

from . import database
from .pipeline import SentraPipeline
from .simulator import NodeSimulator


def main():
    database.init_db()
    pipeline = SentraPipeline()

    nodes = [
        NodeSimulator("P-A", "node-A", scenario="stable", true_hr=62, true_temp=36.6),
        NodeSimulator("P-B", "node-B", scenario="deteriorating", true_hr=88, true_temp=37.0),
        NodeSimulator("P-C", "node-C", scenario="intermittent", true_hr=75, true_temp=36.8),
        NodeSimulator("P-D", "node-D", scenario="fall_event", true_hr=70, true_temp=36.7),
    ]

    # Simulated nurse intake (Doc 07 §17): calibrate each patient's starting
    # baseline from a national-standard age band instead of a cold start.
    calibrations = [
        ("P-A", "Patient A", "adult_18_64yr"),
        ("P-B", "Patient B", "older_adult_65plus"),
        ("P-C", "Patient C", "adult_18_64yr"),
        ("P-D", "Patient D", "adolescent_12_17yr"),
    ]
    for patient_id, name, age_band in calibrations:
        database.set_patient_calibration(patient_id, name, age_band)
        pipeline.calibrate_patient(patient_id, age_band)

    print("SENTRA pipeline simulator running. Ctrl+C to stop.")
    print("In another terminal run: streamlit run dashboard/app.py")

    ts = datetime.now(timezone.utc)
    try:
        while True:
            for node in nodes:
                for packet in node.tick(ts):
                    dashboard_object = pipeline.on_packet(packet)
                    if dashboard_object is not None:
                        database.record_snapshot(dashboard_object)
            ts = datetime.fromtimestamp(ts.timestamp() + 1, tz=timezone.utc)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
