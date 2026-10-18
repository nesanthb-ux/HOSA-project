"""Type-checks aria_sensor_node.ino against stub Arduino headers, in every
build-option combination, using whatever C++ compiler is available.

    python test/compile_check.py                 # uses g++/clang++ on PATH
    python test/compile_check.py "python -m ziglang c++"

This catches typos, type errors, and scope mistakes in the sketch. It CANNOT
catch a wrong assumption about the real Arduino/ESP32/SparkFun libraries,
because the stubs encode my understanding of them. Real compile + upload is
still the test that matters.
"""
import itertools
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKETCH_DIR = HERE.parent
STUBS = HERE / "arduino_stubs"


def find_compiler() -> list[str]:
    if len(sys.argv) > 1:
        return shlex.split(sys.argv[1])
    for name in ("g++", "clang++"):
        if shutil.which(name):
            return [name]
    sys.exit("No C++ compiler found. Pass one, e.g.: python test/compile_check.py \"python -m ziglang c++\"")


def main() -> int:
    cc = find_compiler()
    failures = 0
    combos = list(itertools.product((1, 0), (1, 0), (0, 1)))  # MAX3010x?, IMU?, ECG reference?
    for max3010x, imu, ecg in combos:
        flags = [
            f"-DPPG_SOURCE_MAX3010X={max3010x}",
            f"-DENABLE_IMU={imu}",
            f"-DENABLE_ECG_REFERENCE={ecg}",
            "-DARDUINO=10800",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            # A throwaway object file: some drivers (zig c++) report a bogus
            # FileNotFound with -fsyntax-only because no object is produced.
            cmd = cc + [
                "-x", "c++", "-std=c++17", "-c", "-o", str(Path(tmp) / "sketch.o"),
                "-Wall", "-Wextra", "-Wno-nullability-completeness",
                # Pins/periods for features a given combination switches off are legitimately unused.
                "-Wno-unused-const-variable",
                "-include", str(STUBS / "freertos_stub.h"),
                "-I", str(STUBS), "-I", str(SKETCH_DIR),
                *flags,
                str(SKETCH_DIR / "aria_sensor_node.ino"),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
        label = f"MAX3010x={max3010x} IMU={imu} ECG_REF={ecg}"
        diagnostics = [
            l for l in (proc.stderr or "").splitlines()
            if ("error" in l or "warning" in l) and not l.startswith("zig:")
        ]
        if proc.returncode == 0 and not diagnostics:
            print(f"ok    {label}")
        else:
            failures += 1
            print(f"FAIL  {label}")
            for line in diagnostics[:12]:
                print("      " + line)
    print(f"\n{len(combos) - failures}/{len(combos)} configurations compile cleanly")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
