import copy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
import torch
from nam.capture.project import atomic_write_json
from nam.models.parametric import ConcatWaveNet
from parametric_mac.playback import calibrated, load, qualify_run, control_grid, POLICY
from parametric_mac.review import qualified_model, save_model
from parametric_mac.training import prepare_run, run_training
from test_workflow import project


@pytest.fixture
def trained_run(project):
    torch.set_num_threads(2)
    torch.manual_seed(21)
    recipe = json.loads((project / "model_concat.json").read_text())
    net = ConcatWaveNet.init_from_config(recipe["net"]["config"])
    document = net._get_export_dict()
    data = json.loads((project / "data.json").read_text())
    x, rate = sf.read(project / "input.wav", dtype="float32")
    # A known exact teacher gives an independent, non-training-based fidelity oracle.
    with torch.inference_mode():
        for entry in data["validation"]:
            y = net(torch.from_numpy(x)[None], params=torch.tensor([[entry["params"]["Drive"]]])).numpy()[0]
            sf.write(project / entry["y_path"], y, rate, subtype="FLOAT")
    import shutil
    shutil.copyfile(project/'input.wav', project/'reserved-input.wav')
    reserved = {'version':1, 'common': {'x_path':'reserved-input.wav', 'delay':0}, 'validation': []}
    for i, entry in enumerate(data['validation']):
        name = f'reserved-{i}.wav'
        shutil.copyfile(project/entry['y_path'], project/name)
        reserved['validation'].append({'y_path':name, 'params':entry['params']})
    atomic_write_json(project/'transient_validation.json', reserved)
    out = prepare_run(project, "cpu", 1, 1, input_pad_db=6)
    atomic_write_json(out / "model_parametric.nam", document)
    return out


def test_qualified_save_uses_playback_bytes_and_rejects_tampering(trained_run, tmp_path):
    run = trained_run
    assert qualified_model(run) is None
    report = qualify_run(run)
    assert report["passed"], report
    assert report["mean_validation_esr"] < 1e-6
    dest = tmp_path / "saved.nam"
    save_model(run, dest)
    assert dest.read_bytes() == (run / "playback/model_playback.nam").read_bytes()
    assert dest.read_bytes() != (run / "model_parametric.nam").read_bytes()
    assert json.loads(dest.read_text())["metadata"]["ardor_playback"]["input_pad_db"] == 6
    (run / "playback/model_playback.nam").write_text("{}")
    assert qualified_model(run) is None
    with pytest.raises(ValueError):
        save_model(run, dest)
    # A failed save must not replace the user's previous file.
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == report["model_sha256"]


def test_unknown_mapping_changed_audio_and_bad_fit_block_save(trained_run):
    run = trained_run
    manifest = json.loads((run / "manifest.json").read_text())
    manifest.pop("playback_calibration")
    atomic_write_json(run / "manifest.json", manifest)
    report = qualify_run(run)
    assert not report["passed"] and "Confirm" in report["error"]
    assert qualified_model(run) is None
    assert not qualify_run(run, float("nan"))["passed"]
    assert not qualify_run(run, True)["passed"]
    assert qualify_run(run, 6)["passed"]
    path = Path(next(iter(manifest["audio_sha256"])))
    content = path.read_bytes()
    path.write_bytes(content + b"changed")
    report = qualify_run(run, 6)
    assert not report["passed"] and "Recording changed" in report["error"]
    assert qualified_model(run) is None


def test_poor_fit_is_not_published(trained_run):
    document = json.loads((trained_run / "model_parametric.nam").read_text())
    document["weights"][-1] *= 10
    document["config"]["head_scale"] *= 10
    atomic_write_json(trained_run / "model_parametric.nam", document)
    report = qualify_run(trained_run)
    assert not report["passed"], report
    assert report["mean_validation_esr"] > .1
    assert not (trained_run / "playback/model_playback.nam").exists()


def test_non_bassman_controls_and_grid_budget():
    specs = [{"name": "Mix", "min": 0., "max": 1., "default": .5, "step": .25},
             {"name": "Channel", "min": 0, "max": 2, "default": 0, "type": "switch"}]
    grid, complete = control_grid(specs, [{"Mix": .3, "Channel": 1}])
    assert complete and len(grid) == 16 and (.3, 1) in grid
    many = [{"name": f"K{i}", "min": 0, "max": 10, "default": 5} for i in range(24)]
    grid, complete = control_grid(many, [])
    assert not complete and len(grid) <= 256


def test_training_automatically_runs_playback_checks(project):
    torch.set_num_threads(2)
    out = run_training(project, "cpu", 1, 4, input_pad_db=0)
    report = json.loads((out / "playback/qualification.json").read_text())
    assert len(report["validation"]) == 3
    assert report["policy"]["input_pad_db"] == 0
    assert report["stress"]
    assert (out / "model_parametric.nam").is_file()
    assert bool(qualified_model(out)) == report["passed"]


def test_conversion_preserves_audio_and_bounds_overload(trained_run):
    document = json.loads((trained_run / "model_parametric.nam").read_text())
    raw = load(document)
    final = calibrated(document, dict(POLICY, input_pad_db=6))
    transformed = load(final)
    x = torch.randn(1, 8192)*.1
    with torch.inference_mode():
        expected = raw(x*10**(-6/20), params=torch.tensor([[4.]]))
        actual = transformed(x, params=torch.tensor([[4.]]))
        torch.testing.assert_close(actual, expected.clamp(-.8, .8), atol=1e-5, rtol=1e-4)
        output = transformed(x*100, params=torch.tensor([[4.]]))
        gain = 10**((-18-final["metadata"]["loudness"])/20)
        assert float((output*gain).abs().max()) <= 10**(-1/20)+1e-5
    with pytest.raises(ValueError):
        calibrated(final)


def test_dual_requires_both_tiers_to_pass(project):
    from parametric_mac.architectures import apply_architecture
    from parametric_mac.bundle import bundle_a2
    torch.set_num_threads(2)
    for path in project.glob("*.wav"):
        x, sr = sf.read(path)
        sf.write(path, np.tile(x, 4), sr, subtype="FLOAT")
    data = json.loads((project / "data.json").read_text())
    for entry in data["validation"]:
        sf.write(project / entry["y_path"], np.full(16384, .1), 48000, subtype="FLOAT")
    import shutil
    shutil.copyfile(project/'input.wav', project/'reserved-input.wav')
    sf.write(project/'reserved-target.wav', np.full(16384,.1),48000,subtype='FLOAT')
    atomic_write_json(project/'transient_validation.json', {'version':1, 'validation':[
        {'x_path':'reserved-input.wav', 'y_path':'reserved-target.wav', 'params':{'Drive':4}}]})
    out = prepare_run(project, "cpu", 1, 1, "a2-dual", input_pad_db=0)
    recipe = json.loads((project / "model_concat.json").read_text())
    for tier in ("standard", "nano"):
        net = ConcatWaveNet.init_from_config(apply_architecture(recipe, "a2-"+tier)["net"]["config"])
        with torch.no_grad():
            for parameter in net.parameters():
                parameter.zero_()
            net._wavenet._layer_arrays[0]._head_rechannel.bias.fill_(10.)
        doc = {"architecture": "ConcatWaveNet", "version": "1.0.0", "sample_rate": 48000,
               "metadata": {"gear_type": "pedal", "loudness": -20.},
               "config": net._export_config(), "weights": net._export_weights().tolist()}
        atomic_write_json(out / f"{tier}.nam", doc)
    bundle_a2(out / "standard.nam", out / "nano.nam", out / "model_parametric.nam")
    report = qualify_run(out)
    assert report["passed"], report
    assert set(report["tiers"]) == {"Standard", "Nano"}
    final = json.loads(qualified_model(out).read_text())
    assert final["architecture"] == "SlimmableContainer"
    assert all(tier["model"]["config"]["head"]["activation"] == "Hardtanh" for tier in final["config"]["submodels"])
    bad = json.loads((out / "nano.nam").read_text())
    bad["weights"][-2] = 60.  # Final layer-array head bias before head_scale.
    atomic_write_json(out / "nano.nam", bad)
    bundle_a2(out / "standard.nam", out / "nano.nam", out / "model_parametric.nam")
    report = qualify_run(out)
    assert not report["passed"] and not report["tiers"]["Nano"]["passed"]
    assert qualified_model(out) is None


def test_old_boundedness_only_report_cannot_enable_save(trained_run):
    assert qualify_run(trained_run)['passed']
    path = trained_run/'playback/qualification.json'
    report=json.loads(path.read_text())
    report['policy']['version']=2
    report.pop('transients')
    atomic_write_json(path,report)
    assert qualified_model(trained_run) is None
