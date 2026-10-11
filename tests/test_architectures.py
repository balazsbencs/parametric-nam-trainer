import json
import copy
import numpy as np
import pytest
import soundfile as sf
from test_workflow import project
from parametric_mac.architectures import apply_architecture, A2_KERNEL_SIZES, A2_DILATIONS
from parametric_mac.checks import read_json, check_project
from parametric_mac.cli import project_configs
from parametric_mac.training import prepare_run, run_training, finish_exports
from parametric_mac.bundle import bundle_a2


def longer_audio(project):
    for file in project.glob("*.wav"):
        signal, rate = sf.read(file)
        sf.write(file, np.tile(signal, 2), rate, subtype="PCM_24")


def test_combined_training_exports_both_tiers_and_switches(project):
    import torch
    torch.set_num_threads(2)
    torch.manual_seed(1457)
    longer_audio(project)
    model = read_json(project / "model_concat.json")
    model["net"]["config"]["params"].append({"name": "Mode", "min": 0, "max": 1, "default": 0,
                                             "type": "switch", "enum_names": ["Soft", "Hard"]})
    (project / "model_concat.json").write_text(json.dumps(model))
    data = read_json(project / "data.json")
    for split in ("train", "validation"):
        for i, entry in enumerate(data[split]):
            entry["params"]["Mode"] = i % 2
    (project / "data.json").write_text(json.dumps(data))
    out = run_training(project, "cpu", 1, 4, architecture="a2-dual")
    artifact = read_json(out / "model_parametric.nam")
    assert artifact["architecture"] == "SlimmableContainer"
    assert artifact["version"] == "1.0.0" and artifact["sample_rate"] == 48000
    assert artifact["metadata"]["training_architecture"] == "a2-dual"
    assert "loudness" not in artifact["metadata"]
    assert read_json(out / "status.json")["status"] == "exported"
    assert set(read_json(out / "metrics.json")["tiers"]) == {"standard", "nano"}
    tiers = artifact["config"]["submodels"]
    assert [(tier["name"], tier["max_value"]) for tier in tiers] == [("Nano", .5), ("Standard", 1)]
    for tier, name, channels in zip(tiers, ("nano", "standard"), (3, 8)):
        standalone = read_json(out / "tiers" / name / "model_parametric.nam")
        assert tier["model"] == standalone
        assert standalone["config"]["layers"][0]["channels"] == channels
        assert standalone["config"]["params"][-1]["enum_names"] == ["Soft", "Hard"]
        assert read_json(out / "tiers" / name / "metrics.json")["epoch"] == 1
    assert "Standard" in (out / "training.log").read_text() and "Nano" in (out / "training.log").read_text()
    # A failed packaging attempt must not publish an incompatible combined file.
    nano = copy.deepcopy(tiers[0]["model"])
    for field, value in (("controls", "Other"), ("gear_type", "amp"), ("input_level_dbu", 6.4)):
        bad = copy.deepcopy(nano)
        if field == "controls":
            bad["config"]["params"][0]["name"] = value
        else:
            bad["metadata"][field] = value
        path = out / "invalid.nam"
        path.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            bundle_a2(out / "tiers/standard/model_parametric.nam", path, out / "invalid-combined.nam")
        assert not (out / "invalid-combined.nam").exists()


@pytest.mark.parametrize("architecture", ["a2-dual", "film-dual"])
def test_combined_interruption_retains_first_tier_without_final_export(project, monkeypatch, architecture):
    import parametric_mac.training as training
    longer_audio(project)
    def interrupted(out, tier, *args):
        if tier == "Nano":
            raise KeyboardInterrupt("test interruption")
        (out / "model_parametric.nam").write_text("{}")
        (out / "metrics.json").write_text('{"epoch":1,"ESR":0.2}')
        (out / "training.log").write_text("first tier log")
    monkeypatch.setattr(training, "_train_prepared", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_training(project, "cpu", 1, 4, architecture=architecture)
    out = next((project / "outputs").iterdir())
    assert not (out / "model_parametric.nam").exists()
    assert (out / "tiers/standard/model_parametric.nam").is_file()
    assert "first tier log" in (out / "training.log").read_text()
    assert read_json(out / "status.json")["status"] == "failed_or_interrupted"


@pytest.mark.parametrize("profile,channels", [("a2-standard", 8), ("a2-nano", 3)])
def test_a2_training_and_export(project, profile, channels):
    import torch
    torch.set_num_threads(2)
    torch.manual_seed(1839)
    x = np.random.default_rng(9).normal(0, 0.04, 7000).astype(np.float32)
    sf.write(project / "input.wav", x, 48000, subtype="PCM_24")
    data = read_json(project / "data.json")
    for split in ("train", "validation"):
        for entry in data[split]:
            sf.write(project / entry["y_path"], np.tanh(x * (1 + entry["params"]["Drive"] / 10)), 48000, subtype="PCM_24")
    (project / "workflow.json").write_text(json.dumps({"model_architecture": profile, "gear_kind": "amp"}))
    _, checked_model = project_configs(project)
    layer = checked_model["net"]["config"]["layers"][0]
    assert layer["channels"] == channels
    assert layer["kernel_sizes"] == list(A2_KERNEL_SIZES)
    assert layer["dilations"] == list(A2_DILATIONS)
    assert layer["head"]["kernel_size"] == 16
    assert check_project(project, model=checked_model).ok
    out = run_training(project, "cpu", 1, 4)
    manifest = read_json(out / "manifest.json")
    assert manifest["model_architecture"] == profile
    artifact = read_json(out / "model_parametric.nam")
    assert artifact["version"] == "1.0.0" and artifact["sample_rate"] == 48000
    assert artifact["architecture"] == "ConcatWaveNet"
    exported_layer = artifact["config"]["layers"][0]
    assert exported_layer["channels"] == channels
    assert exported_layer["kernel_sizes"] == list(A2_KERNEL_SIZES)
    assert len(artifact["weights"]) > 1000 and np.isfinite(artifact["weights"]).all()
    assert artifact["metadata"]["gear_type"] == "amp"
    assert artifact["metadata"]["training_architecture"] == profile


def test_profiles_preserve_controls_and_original_config(project):
    model = read_json(project / "model_concat.json")
    before = copy.deepcopy(model)
    model["net"]["config"]["params"].append({"name": "Mode", "min": 0, "max": 1, "default": 0,
                                           "type": "switch", "enum_names": ["Off", "On"]})
    params = copy.deepcopy(model["net"]["config"]["params"])
    a2 = apply_architecture(model, "a2-nano")
    assert a2["net"]["config"]["params"] == params
    assert model["net"]["config"]["layers"] == before["net"]["config"]["layers"]
    assert apply_architecture(model) == model
    with pytest.raises(ValueError):
        apply_architecture(model, "unknown")


def test_finish_exports_preserves_weights_and_calibration(tmp_path):
    metadata = {"loudness": -17.2, "input_level_dbu": 6.4, "date": {"year": 2026}}
    model = {"architecture": "ConcatWaveNet", "version": "1.0.0", "sample_rate": 48000,
             "metadata": metadata, "weights": [0.125, -0.5], "config": {"params": []}}
    (tmp_path / "manifest.json").write_text(json.dumps({"model_name": "My pedal", "gear_type": "pedal", "model_architecture": "a2-nano"}))
    (tmp_path / "model_parametric.nam").write_text(json.dumps(model))
    finish_exports(tmp_path)
    artifact = read_json(tmp_path / "model_parametric.nam")
    assert artifact["weights"] == model["weights"] and artifact["config"] == model["config"]
    assert artifact["metadata"] == {**metadata, "name": "My pedal", "gear_type": "pedal", "training_architecture": "a2-nano"}


def test_explicit_profile_overrides_saved_without_rewriting_source(project):
    (project / "workflow.json").write_text(json.dumps({"model_architecture": "a2-standard"}))
    for file in project.glob("*.wav"):
        signal, rate = sf.read(file)
        sf.write(file, np.tile(signal, 2), rate, subtype="PCM_24")
    before = (project / "model_concat.json").read_bytes()
    out = prepare_run(project, "cpu", 1, 4, "a2-nano")
    assert read_json(out / "model.json")["net"]["config"]["layers"][0]["channels"] == 3
    assert (project / "model_concat.json").read_bytes() == before


def test_rejects_uniform_non_ardor_rate(project):
    for file in project.glob("*.wav"):
        signal, _ = sf.read(file)
        sf.write(file, signal, 44100, subtype="PCM_24")
    report = check_project(project)
    assert not report.ok
    assert any("48000 Hz recordings" in error for error in report.errors)


def test_rejects_more_than_24_controls(project):
    model = read_json(project / "model_concat.json")
    model["net"]["config"]["params"] = [
        {"name": f"Control {i}", "min": 0, "max": 10, "default": 5} for i in range(25)
    ]
    report = check_project(project, model=model)
    assert not report.ok
    assert any("1–24 controls" in error for error in report.errors)
