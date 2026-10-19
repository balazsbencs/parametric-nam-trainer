"""Portable ConcatWaveNet playback calibration and qualification.

All supported concat protection is represented by ordinary NAM weights and a Hardtanh head.
No custom metadata handling or modified pedal runtime is required.
"""
import copy
import hashlib
import itertools
import random
from .checks import read_json
from nam.capture.project import atomic_write_json
import json
import math
from pathlib import Path

import numpy as np
import torch
from nam.models.parametric import ConcatWaveNet

POLICY = {
    "version": 2, "input_pad_db": 0.0, "raw_output_ceiling": 0.8,
    "normalized_output_ceiling": 10 ** (-1 / 20),
    "max_mean_validation_esr": 0.10, "max_capture_validation_esr": 0.25,
}


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def load(document):
    if document.get("architecture") != "ConcatWaveNet" or document.get("sample_rate") != 48000:
        raise ValueError("Protected playback export requires a 48 kHz concat model. FiLM raw outputs remain in the run folder; select concat for a protected export.")
    net = ConcatWaveNet.init_from_config(copy.deepcopy(document["config"]))
    if net.import_weights(document["weights"]) != len(document["weights"]):
        raise ValueError("Weight count mismatch")
    if not all(torch.isfinite(p).all() for p in net.parameters()):
        raise ValueError("Nonfinite model weights")
    return net.eval()


def calibrated(document, policy=POLICY):
    if document.get("metadata", {}).get("ardor_playback"):
        raise ValueError("Already calibrated; input attenuation must not be applied twice")
    if document.get("metadata", {}).get("input_level_dbu") is not None:
        raise ValueError("Analog-calibrated captures need an explicit level mapping; this exporter requires an explicit digital input mapping")
    if not 0 <= policy["input_pad_db"] <= 30 or not 0 < policy["raw_output_ceiling"] <= 1:
        raise ValueError("Invalid playback calibration policy")
    net = load(document)
    config = document["config"]
    if config.get("head") or len(config["layers"]) != 1:
        raise ValueError("Conversion currently supports the single-array A2 recipe without an existing post-stack head")
    layer = config["layers"][0]
    if any(layer.get(name, {}).get("active", False) for name in (
        "conv_pre_film", "conv_post_film", "input_mixin_pre_film", "input_mixin_post_film",
        "activation_pre_film", "activation_post_film", "layer1x1_post_film", "head1x1_post_film")):
        raise ValueError("FiLM input routes are not supported by this conversion")
    if layer.get("groups_input_mixin", 1) != 1 or layer.get("slimmable"):
        raise ValueError("Grouped/slimmable input routes are not supported")
    gain = 10 ** (-policy["input_pad_db"] / 20)
    ceiling = policy["raw_output_ceiling"]
    array = net._wavenet._layer_arrays[0]
    with torch.no_grad():
        # Raw audio is channel zero both in the initial projection and every
        # conditioned input mixer. Controls must retain their original scaling.
        array._rechannel.weight[:, 0, :].mul_(gain)
        for block in array._layers:
            block._input_mixer.weight[:, 0, :].mul_(gain)
        # WaveNet applies head_scale before its optional post-stack head.
        # Feed y/ceiling into Hardtanh, then multiply by ceiling: exact clipping,
        # with an identity transfer inside the original useful output range.
        array._head_rechannel.weight.div_(ceiling)
        if array._head_rechannel.bias is not None:
            array._head_rechannel.bias.div_(ceiling)
    result = copy.deepcopy(document)
    result["config"]["head"] = {"channels": 1, "activation": "Hardtanh",
                                 "out_channels": 1, "kernel_sizes": [1]}
    weights = net._export_weights().tolist()
    result["weights"] = weights[:-1] + [ceiling, 0.0] + weights[-1:]
    final = load(result)
    with torch.inference_mode():
        x = final._metadata_loudness_x()
        y = final(x[None], params=final.nominal_params).double()
        measured = float(20 * torch.log10(y.square().mean().sqrt()))
    if not math.isfinite(measured):
        raise ValueError("Calibrated loudness is not finite")
    # This floor prevents normalization from amplifying the mathematically
    # bounded head above -1 dBFS, even for an unusually quiet trained model.
    loudness_floor = -18 + 20 * math.log10(ceiling / policy["normalized_output_ceiling"])
    loudness = max(measured, loudness_floor)
    metadata = result.setdefault("metadata", {})
    metadata.pop("gain", None)  # Old nonlinear gain estimate no longer describes this transfer.
    metadata["loudness"] = loudness
    # This export defines its own digital input domain; do not also apply an old
    # device/capture calibration gain before its baked-in input pad.
    metadata.pop("input_level_dbu", None)
    metadata["name"] = metadata.get("name", "Parametric amp") + " / Calibrated playback"
    metadata["ardor_playback"] = dict(policy, measured_loudness_db=measured,
        normalization_loudness_db=loudness,
        normalized_peak_bound=ceiling * 10 ** ((-18-loudness)/20),
        input_mapping="playback input x -> original trained input x * 10^(-input_pad_db/20)")
    return result


def stress_probe():
    n = 8192
    t = np.arange(n) / 48000
    rng = np.random.default_rng(20261019)
    impulse = np.zeros(n); impulse[n//2] = 1
    # Include steps, DC, full-scale/high-frequency audio, random transients,
    # silence, and +12 dB overload. This is a boundedness test, not a fidelity test.
    probe = np.concatenate([np.zeros(n), .1*np.sin(2*np.pi*220*t),
        np.sin(2*np.pi*220*t), np.sin(2*np.pi*8000*t),
        np.sign(np.sin(2*np.pi*110*t)), rng.uniform(-1, 1, n),
        impulse, 4*np.sin(2*np.pi*220*t), np.full(n, -4.), np.full(n, 4.), np.zeros(n)])
    return probe.astype("float32")


def control_grid(specs, validation_params, limit=256):
    values, exhaustive = [], True
    for spec in specs:
        lo, hi = float(spec["min"]), float(spec["max"])
        default = float(spec.get("default", (lo+hi)/2))
        if spec.get("type") == "switch":
            choices = list(range(int(lo), int(hi)+1))
        elif spec.get("step") and 0 < spec["step"] and (hi-lo)/spec["step"] <= 200:
            choices = np.arange(lo, hi+spec["step"]*.01, spec["step"]).tolist()
        else:
            choices = [lo, default, hi]
            exhaustive = False
        values.append(sorted(set(choices + [default])))
    total = math.prod(len(v) for v in values)
    if total <= limit:
        grid = list(itertools.product(*values))
    else:
        exhaustive = False
        default = tuple(float(s.get("default", (s["min"]+s["max"])/2)) for s in specs)
        grid = [default]
        # Include every individual endpoint/position before deterministic joint samples.
        for i, options in enumerate(values):
            for value in options:
                row = list(default); row[i] = value
                grid.append(tuple(row))
                if len(set(grid)) >= limit:
                    break
            if len(set(grid)) >= limit:
                break
        rng = random.Random(20261019)
        for _ in range(limit*10):
            if len(set(grid)) >= limit:
                break
            grid.append(tuple(rng.choice(v) for v in values))
    grid = list(dict.fromkeys(grid))[:limit]
    # Held-out points need not be quantized; test them too, without dropping the grid.
    grid = list(dict.fromkeys(grid + [tuple(p[s["name"]] for s in specs) for p in validation_params]))
    return grid, exhaustive


def _qualify_document(document, data, policy):
    from nam.data import Dataset
    net = load(document)
    specs = document["config"]["params"]
    normalization = 10 ** ((-18-document["metadata"]["loudness"])/20)
    boost = 10 ** (policy["input_pad_db"]/20)
    rows = []
    with torch.inference_mode():
        for entry in data["validation"]:
            config = {**data.get("common", {}), **entry}
            params = config.pop("params")
            config.pop("type", None)
            # Reuse the pinned loader's delay, window, input gain and y_scale rules.
            # The exported weights undo y_scale, so compare to the unscaled target.
            config["y_scale"] = 1.0
            config.update(nx=net.receptive_field, ny=None)
            dataset = Dataset.init_from_config(config)
            try:
                x, target = dataset.x, dataset.y
                prediction = net((x*boost)[None], params=torch.tensor([[params[s["name"]] for s in specs]])).double()[0]
                skip = min(max(net.receptive_field-1, min(24000, len(x)//4)), len(x)-1)
                target = target.double()[skip:]
                error = prediction[skip:] - target
                denominator = float(target.square().sum())
                esr = float(error.square().sum())/denominator if denominator > 0 else math.inf
                rows.append({"params": params, "esr": esr if math.isfinite(esr) else None,
                             "frames_scored": len(target)})
            finally:
                dataset.teardown()
        if not rows:
            raise ValueError("No held-out recordings available for playback qualification")
        finite = all(row["esr"] is not None for row in rows)
        mean = float(np.mean([r["esr"] for r in rows])) if finite else None
        worst = max(r["esr"] for r in rows) if finite else None
        grid, exhaustive = control_grid(specs, [r["params"] for r in rows])
        probe = torch.from_numpy(np.concatenate([stress_probe(), net._metadata_loudness_x().numpy()]))[None]
        stress = []
        for index, setting in enumerate(grid):
            y = net(probe, params=torch.tensor([setting])).double()*normalization
            valid = bool(torch.isfinite(y).all())
            peak = float(y.abs().max()) if valid else None
            stress.append({"params": dict(zip([s["name"] for s in specs], setting)),
                           "finite": valid, "normalized_peak": peak})
            if (index+1) % 32 == 0:
                print(f"Playback checks: {index+1}/{len(grid)} control settings", flush=True)
    passed = (finite and mean <= policy["max_mean_validation_esr"]
              and worst <= policy["max_capture_validation_esr"]
              and all(s["finite"] and s["normalized_peak"] <= policy["normalized_output_ceiling"]*1.00001 for s in stress))
    return {"passed": bool(passed), "mean_validation_esr": mean, "max_validation_esr": worst,
            "validation": rows, "stress": stress, "grid_exhaustive": exhaustive,
            "policy": policy, "limitations": "Recorded-level fidelity and sampled overload tests; listening and hardware deadlines remain separate."}


def _qualify_run(run, input_pad_db=None):
    from .bundle import bundle_a2
    run = Path(run).resolve()
    destination = run / "playback"
    destination.mkdir(exist_ok=True)
    final = destination / "model_playback.nam"
    if final.exists():
        final.replace(destination / "previous-qualified.json")
    manifest = read_json(run / "manifest.json")
    try:
        calibration = manifest.get("playback_calibration", {})
        if not isinstance(calibration, dict):
            raise ValueError("Saved input mapping is invalid. Confirm it again before qualifying this run.")
        if input_pad_db is None:
            if calibration.get("confirmed") is not True:
                raise ValueError("Confirm this project's playback input mapping, then qualify the saved run. No attenuation is inferred.")
            input_pad_db = calibration.get("input_pad_db")
        if isinstance(input_pad_db, bool) or not isinstance(input_pad_db, (int, float)) or not math.isfinite(input_pad_db) or not 0 <= input_pad_db <= 30:
            raise ValueError("Playback input pad must be a finite number between 0 and 30 dB")
        policy = dict(POLICY, input_pad_db=float(input_pad_db))
        data = read_json(run / "data.json")
        hashes = manifest.get("audio_sha256", {})
        if not hashes:
            raise ValueError("Run has no audio hashes; check and train the project with this app first")
        for path, expected in hashes.items():
            if digest(path) != expected:
                raise ValueError(f"Recording changed since training: {path}")
        source = run / "model_parametric.nam"
        original = read_json(source)
        reports = {}
        if original.get("architecture") == "SlimmableContainer":
            for tier in original["config"]["submodels"]:
                model = calibrated(tier["model"], policy)
                reports[tier["name"]] = _qualify_document(model, data, policy)
                atomic_write_json(destination / f"{tier['name'].lower()}-candidate.json", model)
            if not all(report["passed"] for report in reports.values()):
                report = {"passed": False, "tiers": reports, "error": "One or more tiers failed playback checks. Keep the checkpoints; inspect fidelity and input mapping."}
                atomic_write_json(destination / "qualification.json", report)
                return report
            bundle_a2(destination / "standard-candidate.json", destination / "nano-candidate.json", destination / "combined-candidate.json")
            document = read_json(destination / "combined-candidate.json")
            report = {"passed": True, "tiers": reports}
        else:
            document = calibrated(original, policy)
            report = _qualify_document(document, data, policy)
            atomic_write_json(destination / "candidate.json", document)
        report.update(source_sha256=digest(source), policy=policy)
        if report["passed"]:
            atomic_write_json(final, document)
            report["model_sha256"] = digest(final)
        else:
            report["error"] = "Playback checks failed. Inspect validation error and input mapping; checkpoints are retained."
        atomic_write_json(destination / "qualification.json", report)
        return report
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        report = {"passed": False, "error": str(exc)}
        atomic_write_json(destination / "qualification.json", report)
        return report


def qualify_run(run, input_pad_db=None):
    previous = torch.get_num_threads()
    try:
        torch.set_num_threads(min(previous, 2))
        report = _qualify_run(run, input_pad_db)
        print("Playback qualification passed." if report["passed"] else "Playback export blocked: " + report.get("error", "See qualification.json"), flush=True)
        return report
    finally:
        torch.set_num_threads(previous)
