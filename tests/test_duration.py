import json
from pathlib import Path
import hashlib
import importlib.util
from zipfile import ZipFile
import numpy as np
import pytest
import soundfile as sf
from parametric_mac.duration import workload,estimate,benchmark_duration
from parametric_mac.training import prepare_run
from test_workflow import project


def test_workload_counts_real_windows_and_partial_capture_batches(project):
    run=prepare_run(project,'cpu',1,4)
    data=json.loads((run/'data.json').read_text())
    learning=json.loads((run/'learning.json').read_text())
    counts=workload(data,learning,3)
    assert counts['train']['windows']==3*7
    assert counts['train']['batches']==6
    assert counts['train']['scored_frames']==21*512
    assert {row['batch'] for row in counts['train']['groups']}=={3,4}


def test_estimate_adds_validation_and_scales_epochs():
    work={split:{'groups':[{'batch':4,'ny':8192,'batches':n}]} for split,n in [('train',100),('validation',10)]}
    train=[{'seconds':2.,'batch':4,'ny':8192}]*4
    validation=[{'seconds':1.,'batch':4,'ny':8192}]*4
    result=estimate(work,train,validation,[50,200])
    assert result['epoch']['seconds']==210
    assert result['targets']['200']['seconds']==42000
    assert result['targets']['50']['planning_low_seconds']<10500
    with pytest.raises(ValueError):estimate(work,[],validation,[200])


def test_both_architectures_use_fresh_models_and_export_only_timing(project):
    for path in project.glob('*.wav'):
        data,rate=sf.read(path)
        sf.write(path,np.tile(data,8),rate,subtype='PCM_24')
    # An incompatible Standard-only warm start must never be used for timing Nano.
    (project/'fine_tune.json').write_text(json.dumps({'source':'missing-standard.nam'}))
    out=benchmark_duration(project,'cpu',batch=2,steps=2,val_steps=2,warmup=1,epochs=[2],timeout=120)
    result=json.loads((out/'results.json').read_text())
    assert set(result['models'])=={'Standard','Nano'}
    assert result['status']=='complete'
    assert all(row['passed'] for row in result['models'].values())
    assert all(row['measurement']['validation_samples'] for row in result['models'].values())
    assert all(row['estimates']['validation']['seconds']>0 for row in result['models'].values())
    assert (out/'RESULTS.txt').is_file() and (out/'results.csv').is_file()
    assert 'Standard + Nano sequentially, 2 epochs' in (out/'RESULTS.txt').read_text()
    assert not list(out.rglob('*.nam')) and not list(out.rglob('*.ckpt'))


def test_portable_packages_are_complete_and_start_fresh(project, tmp_path):
    import nam
    trainer = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('build_duration_packages', trainer/'cloud/benchmark/build_packages.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    (project/'fine_tune.json').write_text('{"source":"standard.nam"}')
    (project/'standard.nam').write_text('must not ship')
    (project/'workflow.json').write_text(json.dumps({'warm_start_path':'standard.nam', 'gear_kind':'amp'}))
    sf.write(project/'reserved.wav', np.zeros(100), 48000)
    (project/'transient_validation.json').write_text('{"validation":[]}')
    for platform, device in [('mac','mps'), ('runpod','cuda')]:
        archive = builder.build(trainer, Path(nam.__file__).resolve().parents[1], project, tmp_path/'archives', platform)
        with ZipFile(archive) as zipped:
            assert zipped.testzip() is None
            prefix = zipped.namelist()[0].split('/')[0]+'/'
            manifest = json.loads(zipped.read(prefix+'SHA256.json'))
            for name, sha in manifest.items():
                assert hashlib.sha256(zipped.read(prefix+name)).hexdigest() == sha
            assert json.loads(zipped.read(prefix+'BENCHMARK.json'))['device'] == device
            assert 'vendor/parametric_mac/duration.py' in manifest
            assert all('fine_tune' not in name and not name.endswith('.nam') and 'reserved.wav' not in name for name in manifest)
            assert 'warm_start_path' not in json.loads(zipped.read(prefix+'project/workflow.json'))
            assert 'import tkinter as _tk\n' not in zipped.read(prefix+'vendor/nam/train/core.py').decode().split('def _nasty_checks_modal():')[0]
            launcher = 'Benchmark Both.command' if platform == 'mac' else 'setup.sh'
            assert (zipped.getinfo(prefix+launcher).external_attr >> 16) & 0o111
        assert archive.with_suffix('.zip.sha256').read_text().split()[0] == hashlib.sha256(archive.read_bytes()).hexdigest()
