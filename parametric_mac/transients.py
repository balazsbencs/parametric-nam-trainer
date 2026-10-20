"""Reserved teacher attacks: fidelity, excess clipping and recovery are export gates."""
from pathlib import Path
import copy
import numpy as np
import torch
from .checks import absolute_data, read_json


def project_data(directory, data):
    """Merge separately generated teacher examples without rewriting capture history."""
    path = Path(directory) / 'augmentation.json'
    result = copy.deepcopy(data)
    if path.exists():
        extra = read_json(path)
        if extra.get('version') != 1:
            raise ValueError('Unsupported augmentation version')
        for split in ('train', 'validation'):
            # The pinned ConcatDataset requires one ny per split. Validation
            # capture recipes commonly use 48000, while training uses 8192.
            exemplar = {**data.get('common', {}), **data[split][0]}
            for row in extra.get(split, []):
                result[split].append({**row, 'ny': exemplar.get('ny')})
    return result


def reserved_data(directory):
    path = Path(directory) / 'transient_validation.json'
    if not path.exists():
        return None
    data = read_json(path)
    if data.get('version') != 1 or not data.get('validation'):
        raise ValueError('Transient validation needs version 1 and reserved teacher recordings')
    return absolute_data(data, Path(directory))


def metrics(prediction, target, ceiling=.8):
    """Score the whole attack and tail, including silence; do not discard the attack."""
    prediction, target = prediction.double(), target.double()
    if not torch.isfinite(prediction).all() or not torch.isfinite(target).all():
        return {'passed': False, 'error': 'Nonfinite transient response'}
    energy = float(target.square().sum())
    if energy <= 1e-12:
        return {'passed': False, 'error': 'Transient reference is silent'}
    error = prediction-target
    esr = float(error.square().sum())/energy
    # A ceiling can hide an unstable learned response. Compare its sustained
    # plateau to the correct teacher response, rather than trusting boundedness.
    excess = ((prediction.abs() >= ceiling*.999) & (target.abs() < ceiling*.95)).numpy()
    edges = np.flatnonzero(np.diff(np.r_[False, excess, False].astype(int)))
    longest = int(max(edges[1::2]-edges[::2], default=0))
    peak_error = float(error.abs().max())
    # ESR scores the complete recovery tail. A separate worst-20ms score keeps
    # a long sequence of good events from masking one bad hard-pick response.
    frame = 960
    squared = error.square()
    padded = torch.nn.functional.pad(squared, (0, (-len(squared)) % frame))
    local_rms = float(padded.reshape(-1, frame).mean(1).sqrt().max())
    passed = esr <= .25 and longest <= 48 and local_rms <= .10 and peak_error <= .35
    return {'passed': bool(passed), 'esr': esr, 'max_error': peak_error,
            'max_20ms_error_rms': local_rms, 'longest_excess_clip_samples': longest}


def predict(net, x, params, chunk=32768):
    """Bound memory while retaining the complete causal receptive-field history."""
    result = []
    for start in range(0, len(x), chunk):
        left = max(0, start-net.receptive_field+1)
        stop = min(len(x), start+chunk)
        y = net(x[left:stop][None], params=params)[0]
        result.append(y[start-left:stop-left])
    return torch.cat(result)


def qualify(net, data, input_pad_db, ceiling=.8):
    if data is None:
        return {'passed': False, 'error': 'Reserved transient recordings are missing. Add teacher or physical attack captures in transient_validation.json before saving a playback model.'}
    from nam.data import Dataset
    specs = net._export_config()['params']
    rows = []
    with torch.inference_mode():
        for row in data['validation']:
            config = {**data.get('common', {}), **row}
            params = config.pop('params')
            config.pop('type', None)
            config.update(y_scale=1., nx=net.receptive_field, ny=None)
            dataset = Dataset.init_from_config(config)
            try:
                x, target = dataset.x, dataset.y
                if len(x) <= net.receptive_field or not torch.any(x.abs() > 0):
                    raise ValueError('Transient recording is too short or silent')
                prediction = predict(net, x*10**(input_pad_db/20),
                                     torch.tensor([[params[s['name']] for s in specs]]))
                rows.append({'params': params, **metrics(prediction, target, ceiling)})
            finally:
                dataset.teardown()
    return {'passed': bool(rows) and all(r['passed'] for r in rows), 'captures': rows,
            'limits': {'esr': .25, 'excess_clip_samples': 48, 'max_20ms_error_rms': .10, 'max_error': .35}}
