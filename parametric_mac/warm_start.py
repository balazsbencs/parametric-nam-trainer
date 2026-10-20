"""Initialize fine-tuning from a raw NAM, with original labels in their raw units."""
import copy
from .checks import read_json
from .input_reference import digest


def prepare(source, model, data):
    from .playback import load
    from nam.models.parametric import ConcatWaveNet
    document = read_json(source)
    if document.get('metadata', {}).get('ardor_playback') or document['config'].get('head'):
        raise ValueError('Fine-tuning needs the raw training export, before playback calibration')
    source_net = load(document)
    if model['net']['name'] != 'ConcatWaveNet':
        raise ValueError('Raw NAM fine-tuning currently supports concat only')
    expected = ConcatWaveNet.init_from_config(copy.deepcopy(model['net']['config']))._export_config()
    actual = source_net._export_config()
    for value in (expected, actual):
        value.pop('head_scale', None)
    if expected != actual:
        raise ValueError('Fine-tune model architecture and controls must match the raw NAM')
    model = copy.deepcopy(model)
    model['net']['config'] = copy.deepcopy(document['config'])
    # A raw NAM already predicts physical recording units. Disabling joint output
    # normalization avoids loading raw weights into a differently scaled target.
    data = copy.deepcopy(data)
    data['joint'] = []
    data.get('common', {}).pop('y_scale', None)
    for split in ('train', 'validation'):
        for row in data[split]:
            row.pop('y_scale', None)
    model.setdefault('optimizer', {})['lr'] = min(model.get('optimizer', {}).get('lr', 1e-4), 1e-4)
    return model, data, {'source_sha256': digest(source), 'output_units': 'raw recording',
                         'learning_rate': model['optimizer']['lr']}


def initialize(net, path, expected_hash):
    if digest(path) != expected_hash:
        raise ValueError('Fine-tune source changed since preparing this run')
    document = read_json(path)
    if net.import_weights(document['weights']) != len(document['weights']):
        raise ValueError('Fine-tune weight count mismatch')
