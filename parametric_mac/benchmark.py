"""Bounded, disposable tuning runs. Results recommend throughput, never audio quality."""
import copy
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from .checks import read_json
from .performance import options, hardware


def best(trials):
    valid = [row for row in trials if row.get('passed') is True and
             isinstance(row.get('audio_seconds_per_second'), (int, float)) and
             0 < row['audio_seconds_per_second'] < float('inf')]
    return max(valid, key=lambda row: row['audio_seconds_per_second']) if valid else None


def _terminate(process):
    # The parent may have crashed while loader children remain in its group.
    if os.name == 'posix':
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.terminate()
    if process.poll() is None:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == 'posix': os.killpg(process.pid, signal.SIGKILL)
            else: process.kill()
            process.wait()


def tune(project, device='auto', architecture=None, batches=(4, 8, 16, 32),
         steps=4, warmup=2, timeout=180, max_trials=8):
    from .training import prepare_run
    from .architectures import is_dual
    from nam.capture.project import atomic_write_json
    if (not batches or any(type(v) is not int or not 1 <= v <= 64 for v in batches)
            or type(steps) is not int or not 2 <= steps <= 100 or type(warmup) is not int or not 1 <= warmup <= 20
            or not 10 <= timeout <= 600 or type(max_trials) is not int or not 1 <= max_trials <= 16):
        raise ValueError('Invalid bounded benchmark settings')
    root = prepare_run(project, device, 1, batches[0], architecture)
    manifest = read_json(root/'manifest.json')
    if is_dual(manifest['model_architecture']):
        raise ValueError('Benchmark one size at a time: choose A2 Standard or Nano instead of a combined model')
    device = manifest['device']
    destination = Path(project).resolve()/'performance'/root.name
    destination.mkdir(parents=True)
    report_path = destination/'benchmark.json'
    report = {'version': 1, 'hardware': hardware(device), 'context': manifest['performance_context'],
              'prepared_run': str(root), 'trials': [], 'recommended': None,
              'status': 'running', 'quality_status': 'provisional throughput recommendation; full audio/transient qualification remains required',
              'method': 'Same initial model and seeded sampled captures; real losses/optimizer/loader; warmup excluded from throughput, included in trial wall time.'}
    atomic_write_json(report_path, report)
    tried = set()
    def trial(batch, settings):
        settings = options(settings, device)
        identity = (batch, str(sorted(settings.items())))
        if identity in tried or len(report['trials']) >= max_trials:
            return
        tried.add(identity)
        index = len(report['trials'])+1
        job_path = destination/f'trial-{index}.json'
        result_path = destination/f'result-{index}.json'
        log_path = destination/f'trial-{index}.log'
        job = {'run': str(root), 'device': device, 'batch': batch, 'settings': settings,
               'steps': steps, 'warmup': warmup, 'result': str(result_path)}
        atomic_write_json(job_path, job)
        print(f'Benchmark trial {index}/{max_trials}: batch {batch}, {settings}', flush=True)
        env = dict(os.environ)
        env['PYTHONPATH'] = str(Path(__file__).resolve().parent.parent)+os.pathsep+env.get('PYTHONPATH', '')
        started = time.perf_counter()
        with log_path.open('w') as log:
            process = subprocess.Popen([sys.executable, '-m', 'parametric_mac.benchmark_worker', str(job_path)],
                stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=os.name == 'posix')
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                _terminate(process)
            except BaseException:
                _terminate(process)
                report['status'] = 'interrupted'
                atomic_write_json(report_path, report)
                raise
            finally:
                _terminate(process)
        if result_path.exists():
            result = read_json(result_path)
            if process.returncode != 0:
                result['passed'] = False
                result.setdefault('error', f'Trial exited with status {process.returncode}; see {log_path.name}')
        else:
            result = {'passed': False, 'settings': settings, 'batch': batch,
                      'error': f'Trial failed or exceeded {timeout}s; see {log_path.name}'}
        result['process_wall_seconds'] = time.perf_counter()-started
        report['trials'].append(result)
        winner = best(report['trials'])
        if winner:
            report.update(recommended=winner['settings'], recommended_batch=winner['batch'])
        atomic_write_json(report_path, report)
        print(f"Benchmark result: {result.get('audio_seconds_per_second', 0):.3f} audio seconds/s" if result['passed']
              else 'Benchmark result: '+result['error'], flush=True)
    try:
        for batch in batches:
            trial(batch, {})
        winner = best(report['trials'])
        if winner:
            data = read_json(root/'data.json')
            base_ny = {**data.get('common', {}), **data['train'][0]}.get('ny')
            if base_ny and base_ny*2 <= 131072:
                trial(winner['batch'], {**winner['settings'], 'ny': base_ny*2})
            winner = best(report['trials'])
            trial(winner['batch'], {**winner['settings'], 'workers': 2})
            if device == 'cuda':
                winner = best(report['trials'])
                trial(winner['batch'], {**winner['settings'], 'compile': True})
                import torch
                if torch.cuda.is_bf16_supported():
                    winner = best(report['trials'])
                    trial(winner['batch'], {**winner['settings'], 'precision': 'bf16-mixed'})
        report['status'] = 'complete'
        atomic_write_json(report_path, report)
    except KeyboardInterrupt:
        report['status'] = 'interrupted'
        atomic_write_json(report_path, report)
        raise
    print(f'Performance report: {report_path}', flush=True)
    if not report['recommended']:
        raise ValueError('No benchmark trial completed; inspect the per-trial logs')
    print(f"Recommended batch {report['recommended_batch']}: {report['recommended']}. Audio quality has not been qualified.", flush=True)
    return report_path
