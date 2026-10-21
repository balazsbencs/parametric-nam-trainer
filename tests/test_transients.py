import copy
import json
import numpy as np
import pytest
import soundfile as sf
import torch
from parametric_mac.transients import metrics
from parametric_mac.warm_start import prepare, initialize
from parametric_mac.playback import load, qualify_run
from parametric_mac.training import prepare_run, run_training
from test_workflow import project


def test_long_clipped_attack_fails_even_when_averaged_into_long_good_audio():
    teacher = torch.zeros(48000)
    teacher[1024:1040] = .3
    prediction = teacher.clone()
    prediction[1040:4911] = .8
    result = metrics(prediction, teacher)
    assert not result['passed']
    assert result['longest_excess_clip_samples'] == 3871
    assert metrics(teacher, teacher)['passed']


def test_fine_tuning_matches_raw_predictions_and_does_not_reapply_calibration(project):
    from nam.models.parametric import ConcatWaveNet
    recipe = json.loads((project/'model_concat.json').read_text())
    data = json.loads((project/'data.json').read_text())
    net = ConcatWaveNet.init_from_config(recipe['net']['config'])
    document = net._get_export_dict()
    path = project/'raw.nam'
    path.write_text(json.dumps(document))
    data['joint'] = [{'name': 'normalize'}]
    data['common']['y_scale'] = 42
    model, fixed_data, provenance = prepare(path, recipe, data)
    initialized = ConcatWaveNet.init_from_config(model['net']['config'])
    initialize(initialized, path, provenance['source_sha256'])
    x = torch.randn(1,4096)*.1
    params = torch.tensor([[5.]])
    torch.testing.assert_close(initialized(x, params=params), net(x,params=params))
    assert fixed_data['joint'] == [] and 'y_scale' not in fixed_data['common']
    bad = copy.deepcopy(recipe)
    bad['net']['config']['params'][0]['max'] = 11
    with pytest.raises(ValueError, match='match'):
        prepare(path, bad, data)
    document.setdefault('metadata', {})['ardor_playback'] = {'input_pad_db':12}
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='raw training export'):
        prepare(path, recipe, data)


def test_missing_reserved_transients_blocks_export(project):
    from nam.models.parametric import ConcatWaveNet
    recipe = json.loads((project/'model_concat.json').read_text())
    net = ConcatWaveNet.init_from_config(recipe['net']['config'])
    run = prepare_run(project, 'cpu', 1,1,input_pad_db=0)
    (run/'model_parametric.nam').write_text(json.dumps(net._get_export_dict()))
    result = qualify_run(run)
    assert not result['passed'] and not result['transients']['passed']
    assert 'missing' in result['transients']['error']


def test_chunked_inference_retains_exact_history(project):
    from nam.models.parametric import ConcatWaveNet
    from parametric_mac.transients import predict
    recipe = json.loads((project/'model_concat.json').read_text())
    net = ConcatWaveNet.init_from_config(recipe['net']['config']).eval()
    x = torch.randn(8192)*.1
    params = torch.tensor([[5.]])
    with torch.inference_mode():
        torch.testing.assert_close(predict(net,x,params,chunk=1024),net(x[None],params=params)[0])


def test_real_training_warm_start_survives_export_in_raw_units(project):
    from nam.models.parametric import ConcatWaveNet
    torch.set_num_threads(2)
    recipe = json.loads((project/'model_concat.json').read_text())
    recipe['optimizer']['lr'] = 0
    (project/'model_concat.json').write_text(json.dumps(recipe))
    net = ConcatWaveNet.init_from_config(recipe['net']['config']).eval()
    path = project/'raw-start.nam'
    path.write_text(json.dumps(net._get_export_dict()))
    out = run_training(project,'cpu',1,4,input_pad_db=0,warm_start=path)
    restored = load(json.loads((out/'model_parametric.nam').read_text()))
    x = torch.randn(1,4096)*.1
    params=torch.tensor([[5.]])
    with torch.inference_mode():
        torch.testing.assert_close(restored(x,params=params),net(x,params=params),atol=1e-6,rtol=1e-5)
    assert 'Initialized fine-tuning' in (out/'training.log').read_text()


def test_augmentation_keeps_each_splits_required_window_size():
    import tempfile
    from pathlib import Path
    from parametric_mac.transients import project_data
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)
        (p/'augmentation.json').write_text(json.dumps({'version':1,
            'train':[{'ny':8192}], 'validation':[{'ny':8192}]}))
        data={'train':[{'ny':8192}], 'validation':[{'ny':48000}]}
        merged=project_data(p,data)
        assert [r['ny'] for r in merged['train']] == [8192,8192]
        assert [r['ny'] for r in merged['validation']] == [48000,48000]
