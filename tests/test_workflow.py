import json
from pathlib import Path
import numpy as np
import pytest
import soundfile as sf
from parametric_mac.checks import check_project, read_json
from parametric_mac.training import mac_learning_config, prepare_run, run_training


@pytest.fixture
def project(tmp_path):
    rng = np.random.default_rng(8)
    x = rng.normal(0, 0.06, 4096).astype(np.float32)
    sf.write(tmp_path / 'input.wav', x, 48000, subtype='PCM_24')
    config = {'type': 'parametric', 'common': {'x_path': 'input.wav', 'delay': 0, 'ny': 512},
              'train': [], 'validation': []}
    for split, values in [('train', [0, 5, 10]), ('validation', [2, 4, 8])]:
        for index, value in enumerate(values):
            name = f'{split}-{index}.wav'
            sf.write(tmp_path / name, np.tanh(x * (1 + value / 10)), 48000, subtype='PCM_24')
            config[split].append({'y_path': name, 'params': {'Drive': value}})
    model = {'net': {'name': 'ConcatWaveNet', 'config': {
        'layers': [{'channels': 2, 'kernel_sizes': [3], 'dilations': [1],
                    'activation': 'LeakyReLU', 'gated': False,
                    'head': {'out_channels': 1, 'kernel_size': 1, 'bias': True}}],
        'head_scale': 0.01,
        'params': [{'name': 'Drive', 'min': 0, 'max': 10, 'default': 5}], 'sample_rate': 48000}},
        'loss': {'val_loss': 'esr'}, 'optimizer': {'lr': 0.003},
        'lr_scheduler': {'class': 'ExponentialLR', 'kwargs': {'gamma': 0.99}}}
    learning = {'trainer': {'max_epochs': 200, 'gradient_clip_val': 0.5},
                'train_dataloader': {'shuffle': True}, 'val_dataloader': {}}
    for name, value in [('data', config), ('model_concat', model), ('learning_concat', learning)]:
        (tmp_path / f'{name}.json').write_text(json.dumps(value))
    return tmp_path


def edit(directory, name, change):
    path = directory / f'{name}.json'
    data = read_json(path)
    change(data)
    path.write_text(json.dumps(data))


def test_valid_dataset_with_unseen_settings(project):
    report = check_project(project)
    assert report.ok, report.text()
    assert report.sample_rate == 48000
    assert report.captures == {'train': 3, 'validation': 3}


def test_cropped_window_checks_upstream_preceding_silence(project):
    edit(project, 'data', lambda d: d['common'].update(start_seconds=.025))
    assert any('input must be silent' in error for error in check_project(project).errors)
    x, rate = sf.read(project / 'input.wav')
    x[:1200] = 0
    sf.write(project / 'input.wav', x, rate, subtype='PCM_24')
    assert check_project(project).ok


def test_config_only_project_can_explicitly_disable_pre_silence(project):
    edit(project, 'data', lambda d: d['common'].update(start_seconds=.025, require_input_pre_silence=None))
    assert check_project(project).ok


@pytest.mark.parametrize('required_silence', [None, 0, .005, .4])
def test_cropped_preflight_agrees_with_pinned_loader(project, required_silence):
    from nam.data import Dataset, XYError
    from parametric_mac.checks import absolute_data

    edit(project, 'data', lambda d: d['common'].update(
        start_seconds=.025, require_input_pre_silence=required_silence))
    data = absolute_data(read_json(project / 'data.json'), project)
    config = {**data['common'], **data['train'][0], 'nx': 3}
    config.pop('params')
    if required_silence:
        with pytest.raises(XYError, match="isn't silent"):
            Dataset.init_from_config(config)
        assert not check_project(project).ok
        x, rate = sf.read(project / 'input.wav')
        start = int(.025 * rate)
        x[max(0, start - int(required_silence * rate)):start] = 0
        sf.write(project / 'input.wav', x, rate, subtype='PCM_24')
    dataset = Dataset.init_from_config(config)
    try:
        assert len(dataset) > 0
        report = check_project(project)
        assert report.ok, report.text()
    finally:
        dataset.teardown()


def test_rejects_settings_leakage(project):
    edit(project, 'data', lambda d: d['validation'][0]['params'].update(Drive=5))
    assert any('share knob settings' in x for x in check_project(project).errors)


@pytest.mark.parametrize('fault', ['clipping', 'silence', 'stereo', 'wrong_rate', 'nonfinite', 'short'])
def test_rejects_bad_audio(project, fault):
    data, rate = sf.read(project / 'train-0.wav')
    subtype = 'PCM_24'
    if fault == 'clipping': data[10] = 1
    elif fault == 'silence': data[:] = 0
    elif fault == 'stereo': data = np.stack([data, data], axis=1)
    elif fault == 'wrong_rate': rate = 44100
    elif fault == 'nonfinite':
        data[10] = np.nan
        subtype = 'FLOAT'
    elif fault == 'short': data = data[:100]
    sf.write(project / 'train-0.wav', data, rate, subtype=subtype)
    assert not check_project(project).ok


def test_rejects_bad_control_and_delay(project):
    edit(project, 'data', lambda d: d['train'][0].update(params={'Drive': 11}, delay=0.4))
    report = check_project(project)
    assert any('finite range' in x for x in report.errors)
    assert any('integer' in x for x in report.errors)


def test_mac_profile_keeps_model_learning_choices():
    original = {'trainer': {'strategy': 'ddp', 'gradient_clip_val': 0.5},
                'trainer_fit_kwargs': {'ckpt_path': '/another-machine/old.ckpt'},
                'train_dataloader': {'persistent_workers': True, 'prefetch_factor': 4}}
    result = mac_learning_config(original, 'mps', 1, 4)
    assert result['trainer']['gradient_clip_val'] == 0.5
    assert result['trainer']['precision'] == '32-true'
    assert result['torch_compile']['enabled'] is False
    assert result['train_dataloader']['drop_last'] is False
    assert 'strategy' not in result['trainer']
    assert 'ckpt_path' not in result['trainer_fit_kwargs']
    assert 'prefetch_factor' not in result['train_dataloader']
    assert 'strategy' in original['trainer']


def test_run_inputs_are_absolute_and_isolated(project):
    before = (project / 'learning_concat.json').read_bytes()
    first = prepare_run(project, 'cpu', 1, 2)
    second = prepare_run(project, 'cpu', 1, 2)
    assert first != second
    assert Path(read_json(first / 'data.json')['common']['x_path']).is_absolute()
    assert (project / 'learning_concat.json').read_bytes() == before
    assert read_json(first / 'manifest.json')['device'] == 'cpu'


def test_actual_one_epoch_export(project):
    # The real fork, real Torch optimizer, dataset, checkpoint and .nam exporter.
    import torch
    torch.set_num_threads(2)
    out = run_training(project, 'cpu', 1, 4)
    artifact = read_json(out / 'model_parametric.nam')
    assert artifact['architecture'] == 'ConcatWaveNet'
    assert artifact['config']['params'][0]['name'] == 'Drive'
    assert len(artifact['weights']) > 0
    assert np.isfinite(artifact['weights']).all()
    assert read_json(out / 'status.json')['status'] == 'exported'
    metrics = read_json(out / 'metrics.json')
    assert metrics['epoch'] == 1
    assert metrics['ESR'] >= 0


def test_delay_is_applied_after_the_window(project):
    edit(project, 'data', lambda d: d['train'][0].update(delay=12, start_seconds=0,
         stop_seconds=4096 / 48000))
    assert check_project(project).ok
    edit(project, 'data', lambda d: d['train'][0].update(ny=4090))
    assert any('model context' in e for e in check_project(project).errors)


def test_latest_capture_project_overrides_stale_exports(project):
    from nam.capture.params import KnobSpec
    from nam.capture.project import CaptureProject, KnobModel, CaptureEntryModel, WindowModel, save_project
    data = read_json(project / 'data.json')
    capture = CaptureProject(name='Fixture', knobs=[KnobModel.from_knob_spec(KnobSpec('Drive', 0, 10))],
        train_input='input.wav', validation_input='input.wav', sample_rate=48000,
        train_window=WindowModel(ny=8192), validation_window=WindowModel(ny=8192))
    for split in ('train', 'validation'):
        for i, entry in enumerate(data[split]):
            capture.entries.append(CaptureEntryModel(index=i, split=split, params=entry['params'],
                y_path=entry['y_path'], delay=0, status='captured'))
    # The normal recipe has a larger receptive field. Use sufficiently long audio.
    x = np.random.default_rng(5).normal(0, .04, 30000)
    for path in project.glob('*.wav'):
        sf.write(path, x, 48000, subtype='PCM_24')
    save_project(capture, project)
    edit(project, 'data', lambda d: d.update(train=[], validation=[]))
    out = prepare_run(project, 'cpu', 1, 1)
    assert len(read_json(out / 'data.json')['train']) == 3
    assert read_json(out / 'model.json')['net']['config']['layers'][0]['channels'] == 8
    # Also exercise the generated architecture, spectral loss and silence anchors.
    import torch
    torch.set_num_threads(2)
    trained = run_training(project, 'cpu', 1, 1)
    assert (trained / 'model_parametric.nam').is_file()
    assert 'Epoch 1 finished.' in (trained / 'training.log').read_text()
