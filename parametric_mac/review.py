"""Lightweight verification at the desktop's final save boundary."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def verified_model_bytes(run):
    run = Path(run)
    try:
        report = json.loads((run / "playback/qualification.json").read_text())
        content = (run / "playback/model_playback.nam").read_bytes()
        tiers = report.get('tiers')
        checks = list(tiers.values()) if isinstance(tiers, dict) else [report]
        if (report.get('policy', {}).get('version') != 3 or not checks or
                not all(row.get('transients', {}).get('passed') is True for row in checks)):
            raise ValueError('This model needs the current reserved-attack qualification before saving.')
        if report.get("passed") is not True or hashlib.sha256(content).hexdigest() != report.get("model_sha256"):
            raise ValueError("Playback model has not passed qualification or changed after qualification. Qualify this run again.")
        return content
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("No qualified playback model. Confirm input mapping and qualify this run first.") from exc


def qualified_model(run):
    try:
        verified_model_bytes(run)
        return Path(run) / "playback/model_playback.nam"
    except ValueError:
        return None


def save_model(run, destination):
    # Validate the bytes actually written, including after an open Save dialog.
    content = verified_model_bytes(run)
    destination = Path(destination)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
