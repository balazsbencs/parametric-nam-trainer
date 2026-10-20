import copy
import json
from pathlib import Path
import pytest
import torch
from parametric_mac.performance import options, configure, runtime
from parametric_mac.training import prepare_run, run_training
from parametric_mac.benchmark import best, tune
from test_workflow import project


def test_settings_reject_unsupported_or_invalid_acceleration():
    for values in ({'precision':'bf16-mixed'}, {'compile':True}, {'workers':True}, {'ny':2},
                   {'workers':-1}, {'early_stopping_patience':-1}, {'unknown':1}):
        with pytest.raises(ValueError):options(values,'cpu')
    assert options({},'mps')['precision']=='32-true'
    assert best([{'passed':False,'audio_seconds_per_second':999}]) is None


def test_profiles_preserve_architecture_and_validation_windows(project):
    original=json.loads((project/'model_concat.json').read_text())
    out=prepare_run(project,'cpu',1,2,performance={'ny':1024,'workers':2,'scheduler':'plateau','early_stopping_patience':3})
    data=json.loads((out/'data.json').read_text())
    model=json.loads((out/'model.json').read_text())
    learning=json.loads((out/'learning.json').read_text())
    assert all(row['ny']==1024 for row in data['train'])
    assert data['common']['ny']==512
    assert all('ny' not in row for row in data['validation'])
    assert model['net']==original['net']
    assert model['lr_scheduler']['class']=='ReduceLROnPlateau'
    assert learning['train_dataloader']['multiprocessing_context']=='spawn'
    assert learning['train_dataloader']['persistent_workers']
    assert json.loads((project/'model_concat.json').read_text())==original


def test_runtime_restores_process_settings_on_error():
    precision=torch.get_float32_matmul_precision()
    benchmark=torch.backends.cudnn.benchmark
    with pytest.raises(RuntimeError):
        with runtime('cpu'):
            assert torch.get_float32_matmul_precision()=='highest'
            raise RuntimeError('stop')
    assert torch.get_float32_matmul_precision()==precision
    assert torch.backends.cudnn.benchmark==benchmark


def test_real_tuning_binds_recommendation_and_never_exports_model(project):
    torch.set_num_threads(2)
    report_path=tune(project,'cpu','auto',batches=(1,2),steps=2,warmup=1,max_trials=2,timeout=60)
    report=json.loads(report_path.read_text())
    assert report['status']=='complete'
    assert len(report['trials'])==2
    assert all(row['passed'] for row in report['trials']),report
    assert all(row['measured_steps']==2 for row in report['trials'])
    assert not list(Path(report['prepared_run']).glob('*.nam'))
    assert 'provisional' in report['quality_status']
    out=prepare_run(project,'cpu',1,1,performance_profile=report_path)
    assert json.loads((out/'manifest.json').read_text())['batch_size']==report['recommended_batch']
    original=copy.deepcopy(report)
    report['hardware']['torch']='different'
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='hardware'):
        prepare_run(project,'cpu',1,1,performance_profile=report_path)
    report_path.write_text(json.dumps(original))
    recipe=json.loads((project/'model_concat.json').read_text())
    recipe['loss']['dc_weight']=.1
    (project/'model_concat.json').write_text(json.dumps(recipe))
    with pytest.raises(ValueError,match='does not match'):
        prepare_run(project,'cpu',1,1,performance_profile=report_path)


def test_plateau_and_early_stopping_use_real_trainer(project):
    torch.set_num_threads(2)
    out=run_training(project,'cpu',1,2,performance={'scheduler':'plateau','early_stopping_patience':2})
    assert (out/'model_parametric.nam').is_file()


def test_failed_or_nonfinite_trial_never_becomes_recommendation():
    rows=[{'passed':False,'audio_seconds_per_second':999},
          {'passed':True,'audio_seconds_per_second':float('nan')},
          {'passed':True,'audio_seconds_per_second':float('inf')},
          {'passed':True,'audio_seconds_per_second':.5}]
    assert best(rows)==rows[-1]


def test_benchmark_stop_terminates_its_process_group():
    import os,subprocess,sys
    from parametric_mac.benchmark import _terminate
    process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=os.name=='posix')
    _terminate(process)
    assert process.poll() is not None


def test_profile_loader_settings_are_removed_when_workers_disabled(project):
    out=prepare_run(project,'cpu',1,2)
    data=json.loads((out/'data.json').read_text())
    model=json.loads((out/'model.json').read_text())
    learning=json.loads((out/'learning.json').read_text())
    _,_,enabled=configure(data,model,learning,{'workers':2},'cpu')
    _,_,disabled=configure(data,model,enabled,{'workers':0},'cpu')
    assert 'prefetch_factor' not in disabled['train_dataloader']
    assert 'persistent_workers' not in disabled['val_dataloader']
    assert 'multiprocessing_context' not in disabled['train_dataloader']


def test_recommendation_rejects_changed_recording(project):
    import soundfile as sf
    from parametric_mac.performance import DEFAULTS
    out=prepare_run(project,'cpu',1,2)
    manifest=json.loads((out/'manifest.json').read_text())
    report={'version':1,'status':'complete','hardware':manifest['hardware'],
            'context':manifest['performance_context'],'recommended':DEFAULTS,'recommended_batch':2,
            'trials':[{'passed':True,'settings':DEFAULTS,'batch':2,'audio_seconds_per_second':1.}]}
    path=project/'benchmark.json'
    path.write_text(json.dumps(report))
    x,sr=sf.read(project/'input.wav')
    sf.write(project/'input.wav',x*.9,sr,subtype='PCM_24')
    with pytest.raises(ValueError,match='does not match'):
        prepare_run(project,'cpu',1,2,performance_profile=path)


def test_unsupported_architecture_cannot_claim_compiled_training():
    with pytest.raises(ValueError,match='concat'):
        configure({'train':[]},{'net':{'name':'parametric_mac.film.init_film'}},{},
                  {'compile':True},'cuda')
