import copy
import json
import numpy as np
import pytest
import torch
from test_workflow import project
from test_architectures import longer_audio
from parametric_mac.architectures import apply_architecture
from parametric_mac.checks import read_json, check_project
from parametric_mac.training import run_training
from parametric_mac.film import FiLMA2, dc_block, from_export, export_film, init_film
from parametric_mac.bundle import bundle_a2


def test_dc_block_matches_recurrence_and_backprop():
    x = torch.randn(2, 3077, requires_grad=True)
    alpha = np.float32(1 - 2*np.pi*20/48000)
    reference = np.zeros(x.shape, dtype=np.float32)
    signal = x.detach().numpy()
    for i in range(signal.shape[1]):
        reference[:, i] = signal[:, i] - (signal[:, i-1] if i else 0) + alpha*(reference[:, i-1] if i else 0)
    output = dc_block(x)
    np.testing.assert_allclose(output.detach(), reference, atol=5e-6, rtol=5e-5)
    output.square().mean().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all() and x.grad.abs().max() > 0


def test_film_raw_controls_gradients_and_export_roundtrip(tmp_path):
    torch.set_num_threads(2)
    torch.manual_seed(132)
    specs = [{"name": "Drive", "min": 0, "max": 10, "default": 5},
             {"name": "Tone", "min": -5, "max": 5, "default": 0}]
    net = FiLMA2(specs, 3)
    x = torch.randn(2, net.receptive_field+64) * .05
    params = torch.tensor([[2., -3.], [8., 4.]])
    output = net(x, params)
    assert output.shape == (2, 65)
    output.square().mean().backward()
    for layer in net.films:
        assert layer.weight.grad is not None and torch.isfinite(layer.weight.grad).all()
        assert layer.weight.grad.abs().max() > 0
    net.eval()
    export_film(net, tmp_path, output_scale=2, basename="scaled")
    document = read_json(tmp_path / "scaled.nam")
    assert (document["architecture"], document["version"], document["sample_rate"]) == ("ParametricWaveNet", "0.7.0", 48000)
    assert document["config"]["parametric"]["parameters"] == specs
    restored = from_export(document).eval()
    torch.testing.assert_close(restored(x, params), net(x, params)/2, atol=2e-6, rtol=2e-4)
    assert net.export_model_dict_post_hooks == []
    assert not torch.allclose(net(x[:1], params[0]), net(x[:1], params[1]))
    with pytest.raises(ValueError, match="physical ranges"):
        restored(x, torch.tensor([11., 0.]))
    with pytest.raises(ValueError, match="Truncated"):
        restored.import_weights(document["weights"][:-1])


def test_film_preflight_limits_without_changing_project(project):
    original = read_json(project / "model_concat.json")
    switch = copy.deepcopy(original)
    switch["net"]["config"]["params"].append({"name": "Mode", "type": "switch", "min": 0, "max": 1,
                                              "default": 0, "enum_names": ["Soft", "Hard"]})
    with pytest.raises(ValueError, match="switches"):
        apply_architecture(switch, "film-dual")
    too_many = copy.deepcopy(original)
    too_many["net"]["config"]["params"] = [{"name": f"Knob {i}", "min": 0, "max": 1, "default": .5} for i in range(17)]
    with pytest.raises(ValueError, match="1–16"):
        apply_architecture(too_many, "film-nano")
    maximum = copy.deepcopy(too_many)
    maximum["net"]["config"]["params"].pop()
    net = init_film(apply_architecture(maximum, "film-nano")["net"]["config"])
    assert net.param_dim == 16
    assert (project / "model_concat.json").read_text() == json.dumps(original)
    report = check_project(project, model=apply_architecture(original, "film-nano"))
    assert any("model context" in e for e in report.errors)  # Checks the full A2 receptive field.


def test_actual_film_dual_training_and_individual_export(project):
    torch.set_num_threads(2)
    torch.manual_seed(2971)
    longer_audio(project)
    model = read_json(project / "model_concat.json")
    model["net"]["config"]["params"].append({"name": "Tone", "min": -5, "max": 5, "default": 0})
    (project / "model_concat.json").write_text(json.dumps(model))
    data = read_json(project / "data.json")
    for split in ("train", "validation"):
        for index, entry in enumerate(data[split]):
            entry["params"]["Tone"] = [-5, 0, 5][index]
    data["joint"] = [{"name": "nam.data.normalize_joint_dataset_output", "kwargs": {"level_rms_dbfs": -10}}]
    (project / "data.json").write_text(json.dumps(data))
    out = run_training(project, "cpu", 1, 4, architecture="film-dual")
    combined = read_json(out / "model_parametric.nam")
    assert combined["version"] == "0.7.0" and combined["architecture"] == "SlimmableContainer"
    assert combined["metadata"]["tier_training"] == "independent"
    assert combined["metadata"]["loudness"] == -18
    assert read_json(out / "status.json")["status"] == "exported"
    assert set(read_json(out / "metrics.json")["tiers"]) == {"standard", "nano"}
    x = torch.sin(torch.arange(512) * .173) * .08
    values = torch.tensor([7., -2.])
    for tier, name, channels in zip(combined["config"]["submodels"], ("nano", "standard"), (3, 8)):
        standalone = read_json(out / "tiers" / name / "model_parametric.nam")
        assert standalone["config"]["layers"] == channels
        assert standalone["config"]["parametric"]["parameters"] == model["net"]["config"]["params"]
        assert read_json(out / "tiers" / name / "metrics.json")["epoch"] == 1
        gain = 10**((-18-standalone["metadata"]["loudness"])/20)
        with torch.no_grad():
            expected = from_export(standalone)(x, values, pad_start=True) * gain
            actual = from_export(tier["model"])(x, values, pad_start=True)
        torch.testing.assert_close(actual, expected, atol=5e-6, rtol=2e-4)
        assert list((out / "tiers" / name).rglob("*.ckpt"))
    invalid = copy.deepcopy(combined["config"]["submodels"][0]["model"])
    invalid["config"]["parametric"]["parameters"][0]["default"] = 3
    bad = out / "bad.nam"
    bad.write_text(json.dumps(invalid))
    with pytest.raises(ValueError, match="identical controls"):
        bundle_a2(out / "tiers/standard/model_parametric.nam", bad, out / "bad-combined.nam")
    assert not (out / "bad-combined.nam").exists()
    (project / "workflow.json").write_text('{"gear_kind":"amp","model_architecture":"film-nano"}')
    single = run_training(project, "cpu", 1, 4)
    document = read_json(single / "model_parametric.nam")
    assert document["architecture"] == "ParametricWaveNet" and document["metadata"]["gear_type"] == "amp"
    assert document["metadata"]["training_architecture"] == "film-nano"
