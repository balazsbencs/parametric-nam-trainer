"""Run Qt GUI checks in an isolated, offscreen subprocess."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Offscreen checks never inspect the machine's CoreAudio devices, including on a Mac.
NO_COREAUDIO = "from parametric_mac import device_rates\ndevice_rates._live_halves = lambda: []\n"

ROOT = Path(__file__).resolve().parents[1]


def run_gui(script: str, timeout: int = 180) -> str:
    """Run `script` with offscreen Qt and throwaway settings and project folders.

    The script must print "OK" when all its checks pass. Returns stdout.
    """
    with tempfile.TemporaryDirectory(prefix="parametric-settings-") as settings, \
            tempfile.TemporaryDirectory(prefix="parametric-projects-") as projects:
        env = {**os.environ, "QT_QPA_PLATFORM": "offscreen",
               "PARAMETRIC_SETTINGS_DIR": settings, "PARAMETRIC_PROJECTS_ROOT": projects}
        result = subprocess.run([sys.executable, "-c", NO_COREAUDIO + script], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 or "OK" not in result.stdout.split():
        raise AssertionError(f"GUI script failed ({result.returncode}).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}")
    return result.stdout
