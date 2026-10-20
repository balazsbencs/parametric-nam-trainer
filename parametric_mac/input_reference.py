"""Recorded, fixed input-domain mapping. Never infer calibration from audio peaks."""
import hashlib
import json
import math
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def input_paths(data, directory):
    return {str((Path(directory) / {**data.get('common', {}), **row}['x_path']).resolve())
            for split in ('train', 'validation') for row in data.get(split, [])}


def resolve_reference(directory, data):
    path = Path(directory) / 'input_reference.json'
    if not path.exists():
        return None
    reference = json.loads(path.read_text())
    if reference.get('version') != 1:
        raise ValueError('Unsupported input reference version')
    mode = reference.get('kind')
    fields = {'digital': ('capture_signal_gain_db', 'playback_signal_gain_db'),
              'analog': ('capture_full_scale_dbu', 'playback_full_scale_dbu')}
    if mode not in fields:
        raise ValueError('Input reference must describe digital gains or measured analog full-scale levels')
    first, second = (reference.get(k) for k in fields[mode])
    if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in (first, second)):
        raise ValueError('Input reference levels must be finite numbers')
    # Digital: recorded signal = source * capture_gain; live source = source * playback_gain.
    # Analog: input NAM full-scale C dBu, live ADC full-scale P dBu -> gain = P-C dB.
    pad = second-first if mode == 'digital' else first-second
    gains = [{**data.get('common', {}), **row}.get('input_gain', 0.)
             for split in ('train', 'validation') for row in data.get(split, [])]
    if any(isinstance(g, bool) or not isinstance(g, (int, float)) or not math.isfinite(g) for g in gains):
        raise ValueError('Dataset input gains must be finite numbers')
    if len(set(gains)) > 1:
        raise ValueError('One playback mapping cannot represent different dataset input gains')
    input_gain = gains[0] if gains else 0.
    pad -= input_gain
    if not 0 <= pad <= 30:
        raise ValueError('Recorded mapping requires an unsupported boost or more than 30 dB attenuation')
    hashes = reference.get('input_sha256', {})
    for name in input_paths(data, directory):
        relative = Path(name).relative_to(Path(directory).resolve()).as_posix()
        if hashes.get(relative) != digest(name):
            raise ValueError(f'Input reference does not match recording: {relative}; record its actual levels again')
    return {'confirmed': True, 'input_pad_db': float(pad), 'source': 'recorded_input_reference',
            'reference': reference, 'dataset_input_gain_db': input_gain}


def record_reference(directory, data, *, kind='digital', capture=0., playback=0.):
    directory = Path(directory).resolve()
    fields = {'digital': ('capture_signal_gain_db', 'playback_signal_gain_db'),
              'analog': ('capture_full_scale_dbu', 'playback_full_scale_dbu')}
    if kind not in fields:
        raise ValueError('Unknown input reference kind')
    if not input_paths(data, directory):
        raise ValueError('Record captures before binding an input reference')
    reference = {'version': 1, 'kind': kind, **dict(zip(fields[kind], (capture, playback))),
                 'input_sha256': {Path(p).relative_to(directory).as_posix(): digest(p)
                                  for p in sorted(input_paths(data, directory))}}
    # Validate before replacing a previously recorded reference.
    first, second = capture, playback
    pad = second-first if kind == 'digital' else first-second
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (first, second)) or not 0 <= pad <= 30:
        raise ValueError('Reference must give a finite attenuation between 0 and 30 dB')
    from nam.capture.project import atomic_write_json
    atomic_write_json(directory / 'input_reference.json', reference)
    return reference
