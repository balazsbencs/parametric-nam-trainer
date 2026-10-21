"""Render repeatable attack datasets with a native NAM teacher renderer.

The renderer accepts a JSON job list (model/input/output/raw/block_size) and
reads/writes mono float32. Teachers stay local; packages contain only WAV targets.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import numpy as np
import soundfile as sf


def excitation(seed, levels):
    rng = np.random.default_rng(seed)
    events = [np.zeros(16384, dtype=np.float32)]
    for level in levels:
        for duration in (1, 4, 16, 64, 256, 1024):
            event = np.zeros(16384, dtype=np.float32)
            burst = rng.uniform(-1, 1, duration)
            event[1024:1024+duration] = burst * level / max(abs(burst))
            events.append(event)
        t = np.arange(16384)/48000
        pluck = (np.sin(2*np.pi*110*t)+.5*np.sin(2*np.pi*330*t)+.25*np.sin(2*np.pi*990*t))*np.exp(-t*12)
        events.append((pluck*level/max(abs(pluck))).astype('float32'))
    return np.concatenate(events)


def generate(project, sources, renderer, pad_db):
    project = Path(project).resolve()
    destination = project / 'attacks'
    destination.mkdir(exist_ok=False)
    definitions = {'train': (7301, [.1, .25, .5, .75, .95]),
                   'validation': (8301, [.25, .75, .95]),
                   'qualification': (44, [.5, .95])}
    jobs = []
    extra = {'version': 1, 'train': [], 'validation': []}
    reserved = {'version': 1, 'common': {'delay': 0}, 'validation': [],
                'description': 'Reserved attacks, including complete silent recovery tails; never used for gradient updates or epoch selection.'}
    for role, (seed, levels) in definitions.items():
        x = excitation(seed, levels)*10**(-pad_db/20)
        sf.write(destination / f'{role}-input.wav', x, 48000, subtype='FLOAT')
        x.tofile(destination / f'{role}-input.f32')
    for source in json.loads(Path(sources).read_text()):
        split = source['split']
        for role in (split, 'qualification'):
            stem = f'{role}-{source["id"]}'
            jobs.append({'model': source['path'], 'input': str(destination / f'{role}-input.f32'),
                         'output': str(destination / (stem+'.f32')), 'raw': True, 'block_size': 128})
            row = {'x_path': f'attacks/{role}-input.wav', 'y_path': f'attacks/{stem}.wav',
                   'delay': 0, 'params': source['params'], 'ny': 8192}
            if role == 'qualification':
                reserved['validation'].append(row)
            else:
                extra[split].append(row)
    def render(index):
        group = jobs[index::3]
        path = destination / f'jobs-{index}.json'
        path.write_text(json.dumps(group, indent=2)+'\n')
        subprocess.run([str(renderer), str(path)], check=True, stdout=(destination / f'render-{index}.log').open('w'), stderr=subprocess.STDOUT)
        for job in group:
            y = np.fromfile(job['output'], dtype=np.float32)
            expected = Path(job['input']).stat().st_size//4
            if len(y) != expected or not np.isfinite(y).all() or max(abs(y)) >= 1:
                raise ValueError(f'Teacher produced invalid or clipped attack recording: {job["output"]}')
            sf.write(Path(job['output']).with_suffix('.wav'), y, 48000, subtype='FLOAT')
    with ThreadPoolExecutor(max_workers=3) as executor:
        list(executor.map(render, range(3)))
    from nam.capture.project import atomic_write_json
    atomic_write_json(project / 'augmentation.json', extra)
    atomic_write_json(project / 'transient_validation.json', reserved)
    from .cli import project_configs
    from .checks import read_json
    from .transients import project_data
    from .input_reference import record_reference
    data, _ = project_configs(project)
    data = project_data(project, data or read_json(project / 'data.json'))
    record_reference(project, data, capture=-pad_db, playback=0.)
    for path in destination.glob('*.f32'):
        path.unlink()
    print(f'Rendered {len(jobs)} attack captures; {len(reserved["validation"])} reserved for final qualification.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--renderer', type=Path, required=True)
    parser.add_argument('--input-pad-db', type=float, required=True)
    args = parser.parse_args()
    if not np.isfinite(args.input_pad_db) or not 0 <= args.input_pad_db <= 30:
        parser.error('Input mapping must be between 0 and 30 dB')
    generate(args.project, args.sources, args.renderer, args.input_pad_db)


if __name__ == '__main__':
    main()
