"""Build Ardor regression fixtures from real .nam exports and Python inference.

Run with this project's installed environment. Input weights/configs/metadata are
preserved; only the enclosing test fixture and its audio cases are generated.
"""
import argparse
import copy
import json
import sys
from pathlib import Path
import numpy as np
import torch
from nam.models.parametric import ConcatWaveNet
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parametric_mac.film import from_export

parser = argparse.ArgumentParser()
parser.add_argument("models", type=Path, nargs="+")
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
torch.set_num_threads(2)
signal = (np.sin(np.arange(512) * .173) * .08 + np.sin(np.arange(512) * .791) * .03).astype(np.float32)
fixtures = []
for path in args.models:
    document = json.loads(path.read_text())
    cases = []
    tiers = [(1, document)]
    if document["architecture"] == "SlimmableContainer":
        tiers = [(0 if i == 0 else 1, tier["model"])
                 for i, tier in enumerate(document["config"]["submodels"])]
    for size, child in tiers:
        if child["architecture"] == "ParametricWaveNet":
            net = from_export(child)
            definitions = child["config"]["parametric"]["parameters"]
        else:
            if child["architecture"] != "ConcatWaveNet" or child["version"] != "1.0.0":
                raise ValueError(f"{path}: expected concat or FiLM export")
            config = copy.deepcopy(child["config"])
            config["sample_rate"] = child["sample_rate"]
            net = ConcatWaveNet.init_from_config(config)
            if net.import_weights(child["weights"]) != len(child["weights"]):
                raise ValueError("Weight layout did not roundtrip")
            definitions = child["config"]["params"]
        net.eval()
        defaults = {p["name"]: p["default"] for p in definitions}
        settings = [defaults, {**defaults, definitions[0]["name"]: definitions[0]["min"]},
                    {**defaults, definitions[0]["name"]: definitions[0]["max"]}]
        if len(definitions) > 1:
            settings.extend([{p["name"]: p[bound] for p in definitions} for bound in ("min", "max")])
            settings.append({**defaults, definitions[-1]["name"]: definitions[-1]["max"]})
        for spec in definitions:
            if spec.get("type") == "switch":
                settings.append({**defaults, spec["name"]: spec["max"]})
        # Ardor's NamProcessor applies the existing NAM plugin loudness convention.
        loudness = child.get("metadata", {}).get("loudness")
        gain = 1 if loudness is None else 10 ** ((-18 - loudness) / 20)
        with torch.no_grad():
            for values in settings:
                params = torch.tensor([values[p["name"]] for p in definitions], dtype=torch.float32)
                output = net(torch.from_numpy(signal), params, pad_start=True).cpu().numpy() * gain
                if not np.isfinite(output).all():
                    raise ValueError(f"{path}: nonfinite reference output")
                cases.append({"parameters": values, "output": output.tolist(), "slimmable_size": size})
    fixtures.append({"label": document.get("metadata", {}).get("training_architecture", path.stem),
                     "model": document, "cases": cases})
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps({"input": signal.tolist(), "models": fixtures}, separators=(",", ":")) + "\n")
print(f"Wrote {len(fixtures)} models with {sum(len(f['cases']) for f in fixtures)} audio cases: {args.output}")
