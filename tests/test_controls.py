import itertools
import json
import numpy as np
import pytest
import soundfile as sf
from nam.capture.params import KnobSpec
from nam.capture.project import save_project, WindowModel
from parametric_mac.controls import SwitchSpec, load_project, model_config
from parametric_mac.workflow import quality_settings, make_plan
from parametric_mac.training import prepare_run, run_training


def controls():
    return (KnobSpec('Gain', 0, 10, .5, avoid_zero=True, is_gain=True),
            KnobSpec('Tone', 0, 10, .5),
            SwitchSpec('Bright', 0, 1, 1, 0),
            SwitchSpec('Mode', 0, 2, 1, 0, enum_names=('Clean', 'Crunch', 'Lead')))


def test_all_switch_combinations_have_unseen_tests_and_safe_filenames(tmp_path):
    specs, train, tests = quality_settings(controls(), 2)
    plan = make_plan(specs, train, tests)
    states = set(itertools.product(range(2), range(3)))
    for split in ('train', 'validation'):
        entries = plan.entries_for_split(split)
        assert {(e.params['Bright'], e.params['Mode']) for e in entries} == states
    train_keys = {tuple(e.params.values()) for e in plan.entries_for_split('train')}
    test_keys = {tuple(e.params.values()) for e in plan.entries_for_split('validation')}
    assert not train_keys & test_keys
    assert all(len(e.y_path.split('/')) == 2 for e in plan.entries)
    save_project(plan, tmp_path)
    loaded = load_project(tmp_path)
    assert loaded.model_dump() == plan.model_dump()
    params = model_config(loaded)['net']['config']['params']
    assert params[-1]['enum_names'] == ['Clean', 'Crunch', 'Lead']
    assert params[-1]['type'] == 'switch'


def test_twenty_four_knobs_plan_is_bounded_and_held_out():
    controls = tuple(KnobSpec(f'Knob {i}', 0, 10, .5) for i in range(24))
    specs, train, tests = quality_settings(controls, 2)
    plan = make_plan(specs, train, tests)
    assert train + tests <= len(plan.entries) <= train + tests + 50
    assert not {tuple(e.params.values()) for e in plan.entries_for_split('train')} & {tuple(e.params.values()) for e in plan.entries_for_split('validation')}


def test_switch_combination_limit_is_actionable():
    knobs = [KnobSpec('Gain', 0, 10, .5)]
    knobs += [SwitchSpec(f'Switch {i}', 0, 1, 1, 0) for i in range(6)]
    with pytest.raises(ValueError, match='64 combinations.*keep some switches fixed'):
        quality_settings(knobs, 2)


def test_corrupt_switch_metadata_is_rejected(tmp_path):
    plan = make_plan(*quality_settings(controls(), 0))
    save_project(plan, tmp_path)
    file = tmp_path / 'capture_project.json'
    payload = json.loads(file.read_text())
    payload['knobs'][-1]['enum_names'] = ['Only one']
    file.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        load_project(tmp_path)


def test_switch_conditioned_manifest_trains_and_exports(tmp_path):
    import torch
    torch.set_num_threads(2)
    specs = (KnobSpec('Gain', 0, 10, 1), SwitchSpec('Bright', 0, 1, 1, 0))
    plan = make_plan(specs, 4, 2, corners=False)
    plan.sample_rate = 48000
    plan.train_window = WindowModel(ny=8192)
    plan.validation_window = WindowModel(ny=8192)
    signal = np.random.default_rng(11).normal(0, .04, 30000)
    for name in (plan.train_input, plan.validation_input):
        sf.write(tmp_path / name, signal, 48000, subtype='PCM_24')
    for entry in plan.entries:
        output = np.tanh(signal * (1 + entry.params['Gain']/10 + entry.params['Bright']*.1))
        file = tmp_path / entry.y_path
        file.parent.mkdir(exist_ok=True)
        sf.write(file, output, 48000, subtype='PCM_24')
        entry.status = 'captured'
        entry.delay = 0
    save_project(plan, tmp_path)
    snapshot = prepare_run(tmp_path, 'cpu', 1, 1)
    assert json.loads((snapshot/'model.json').read_text())['net']['config']['params'][1]['type'] == 'switch'
    out = run_training(tmp_path, 'cpu', 1, 1)
    exported = json.loads((out/'model_parametric.nam').read_text())
    assert exported['config']['params'][1]['enum_names'] == ['Off', 'On']
    assert exported['config']['params'][1]['type'] == 'switch'


def test_display_names_do_not_become_directories_or_oversized_filenames():
    names = [('Shared prefix ' * 25) + str(i) + ' / é' for i in range(24)]
    controls = tuple(KnobSpec(n, 0, 10, 2) for n in names)
    plan = make_plan(controls, 4, 2)
    paths = [e.y_path for e in plan.entries]
    assert len(paths) == len(set(paths))
    assert all(len(path.split('/')) == 2 and len(path.split('/')[1].encode()) <= 220 for path in paths)
    assert list(plan.entries[0].params) == names


def test_swap_starter_only_replaces_an_untouched_starter():
    from dataclasses import replace
    from parametric_mac.control_editor import is_untouched_starter, starter, swap_starter
    pedal, amp = starter(False), starter(True)
    assert is_untouched_starter(pedal) and is_untouched_starter(amp)
    assert swap_starter(pedal, True) == amp
    assert swap_starter(amp, False) == pedal
    changed = pedal + (replace(pedal[1], name="Level"),)
    assert not is_untouched_starter(changed)
    assert swap_starter(changed, True) is changed
    renamed = (replace(pedal[0], name="Gain"), pedal[1])
    assert swap_starter(renamed, True) is renamed
