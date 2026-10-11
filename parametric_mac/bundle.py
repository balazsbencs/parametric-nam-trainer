"""Package separately trained A2 models using Ardor's parametric container contract."""
import copy
import math
from pathlib import Path

from .architectures import A2_KERNEL_SIZES, A2_DILATIONS
from .checks import read_json


def bundle_a2(standard_path, nano_path, output_path):
    standard, nano = (read_json(Path(path)) for path in (standard_path, nano_path))
    film = standard.get("architecture") == "ParametricWaveNet"
    family, version = ("ParametricWaveNet", "0.7.0") if film else ("ConcatWaveNet", "1.0.0")
    for model, channels in ((standard, 8), (nano, 3)):
        if (model.get("architecture"), model.get("version"), model.get("sample_rate")) != (family, version, 48000):
            raise ValueError("A2 bundles require matching 48 kHz concat or FiLM exports.")
        layers = model["config"]["layers"]
        if film:
            from .film import from_export
            from_export(model)  # Validate the full schema and weight layout before packaging.
            if layers != channels:
                raise ValueError("FiLM bundle requires an 8-channel Standard and a 3-channel Nano.")
        elif (len(layers) != 1 or layers[0]["channels"] != channels
                or layers[0]["kernel_sizes"] != list(A2_KERNEL_SIZES)
                or layers[0]["dilations"] != list(A2_DILATIONS)):
            raise ValueError("A2 bundle requires an 8-channel Standard and a 3-channel Nano.")
        weights = model.get("weights")
        if not weights or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in weights):
            raise ValueError("A2 bundle requires finite exported weights.")
        for field in ("loudness", "input_level_dbu"):
            value = model.get("metadata", {}).get(field)
            if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value)):
                raise ValueError(f"Invalid {field} calibration.")
    def controls(model):
        return model["config"]["parametric"]["parameters"] if film else model["config"]["params"]
    if controls(standard) != controls(nano):
        raise ValueError("Standard and Nano must have identical controls, ranges and defaults.")
    for field in ("gear_type", "input_level_dbu"):
        if standard.get("metadata", {}).get(field) != nano.get("metadata", {}).get(field):
            raise ValueError(f"Standard and Nano must share {field}.")
    metadata = copy.deepcopy(standard.get("metadata", {}))
    # Each tier keeps its own loudness; Ardor normalizes the selected child.
    metadata.pop("loudness", None)
    metadata.pop("output_level_dbu", None)
    metadata["training_architecture"] = "film-dual" if film else "a2-dual"
    metadata["tier_training"] = "independent"
    if film:
        # Gene Ko containers apply the parent gain, not per-child gains. Normalize
        # copies to -18 dB so each tier matches its standalone normalized playback
        # in Ardor and Gene Ko's player. Original per-tier files stay untouched.
        standard, nano = copy.deepcopy(standard), copy.deepcopy(nano)
        for model in (standard, nano):
            loudness = model.get("metadata", {}).get("loudness")
            if loudness is None:
                raise ValueError("FiLM tiers require measured loudness for combined export.")
            gain = 10 ** ((-18 - loudness) / 20)
            model["config"]["head_scale"] *= gain
            model["weights"][-1] *= gain
            if not math.isfinite(model["weights"][-1]):
                raise ValueError("FiLM tier normalization must be finite.")
            model["metadata"]["loudness"] = -18.0
            model["metadata"].pop("output_level_dbu", None)
        metadata["loudness"] = -18.0
        metadata["tier_normalization_db"] = -18.0
    document = {"architecture": "SlimmableContainer", "version": version,
                "sample_rate": 48000, "metadata": metadata,
                "config": {"submodels": [
                    {"name": "Nano", "max_value": 0.5, "model": nano},
                    {"name": "Standard", "max_value": 1.0, "model": standard},
                ]}}
    from nam.capture.project import atomic_write_json
    atomic_write_json(Path(output_path), document)
    return document
