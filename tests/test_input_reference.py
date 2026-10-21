import json
import pytest
from parametric_mac.input_reference import record_reference, resolve_reference
from parametric_mac.training import prepare_run
from test_workflow import project


def test_recorded_digital_reference_is_automatic_and_bound_to_inputs(project):
    data = json.loads((project/'data.json').read_text())
    record_reference(project, data, capture=-12, playback=0)
    run = prepare_run(project, 'cpu', 1, 1)
    calibration = json.loads((run/'manifest.json').read_text())['playback_calibration']
    assert calibration['input_pad_db'] == 12 and calibration['confirmed']
    with pytest.raises(ValueError, match='conflicts'):
        prepare_run(project, 'cpu', 1, 1, input_pad_db=6)
    path = project/'input.wav'
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError, match='does not match'):
        prepare_run(project, 'cpu', 1, 1)


def test_analog_mapping_uses_full_scale_references_without_double_counting(project):
    data = json.loads((project/'data.json').read_text())
    record_reference(project, data, kind='analog', capture=18, playback=12)
    assert resolve_reference(project, data)['input_pad_db'] == 6
    with pytest.raises(ValueError):
        record_reference(project, data, capture=0, playback=-12)
    assert resolve_reference(project, data)['input_pad_db'] == 6


def test_recorded_mapping_includes_pinned_loader_input_gain(project):
    data=json.loads((project/'data.json').read_text())
    data['common']['input_gain']=3.
    record_reference(project,data,capture=-12,playback=0)
    assert resolve_reference(project,data)['input_pad_db']==9
    data['train'][0]['input_gain']=6
    with pytest.raises(ValueError,match='different dataset'):
        resolve_reference(project,data)


def test_invalid_effective_mapping_preserves_previous_reference(project):
    data = json.loads((project / 'data.json').read_text())
    data['common']['input_gain'] = 6.
    record_reference(project, data, capture=-12, playback=0)
    before = (project / 'input_reference.json').read_bytes()
    with pytest.raises(ValueError, match='unsupported boost'):
        record_reference(project, data, capture=0, playback=0)
    assert (project / 'input_reference.json').read_bytes() == before
    assert resolve_reference(project, data)['input_pad_db'] == 6
