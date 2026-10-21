"""Explicit training controls and hardware-bound benchmark recommendations."""
import copy
import hashlib
import json
import platform
from contextlib import contextmanager
from pathlib import Path

DEFAULTS = {'precision': '32-true', 'workers': 0, 'ny': None,
            'compile': False, 'scheduler': 'original', 'early_stopping_patience': 0}


def options(value=None, device='cpu'):
    value = {} if value is None else value
    if not isinstance(value, dict) or set(value)-set(DEFAULTS):
        raise ValueError('Unknown training performance settings')
    result = {**DEFAULTS, **value}
    if result['precision'] not in ('32-true', 'bf16-mixed'):
        raise ValueError('Choose 32-true or bf16-mixed precision')
    if type(result['compile']) is not bool:
        raise ValueError('Compilation must be a boolean')
    for key, lo, hi in (('workers', 0, 8), ('early_stopping_patience', 0, 1000)):
        if type(result[key]) is not int or not lo <= result[key] <= hi:
            raise ValueError(f'{key} must be an integer between {lo} and {hi}')
    if result['ny'] is not None and (type(result['ny']) is not int or not 64 <= result['ny'] <= 131072):
        raise ValueError('Training window must be 64–131072 samples')
    if result['scheduler'] not in ('original', 'plateau'):
        raise ValueError('Choose original or plateau learning-rate schedule')
    if device != 'cuda' and (result['compile'] or result['precision'] != '32-true'):
        raise ValueError('Compilation and BF16 profiles currently require CUDA; CPU/MPS keep FP32 eager execution')
    if device == 'cuda' and result['precision'] == 'bf16-mixed':
        import torch
        if not torch.cuda.is_bf16_supported():
            raise ValueError('This CUDA device does not support BF16')
    return result


def configure(data, model, learning, settings, device):
    settings = options(settings, device)
    data, model, learning = copy.deepcopy((data, model, learning))
    if settings['compile'] and model['net']['name'] != 'ConcatWaveNet':
        raise ValueError('Compilation currently supports concat training only')
    if settings['ny'] is not None:
        for row in data['train']:
            row['ny'] = settings['ny']
    if settings['scheduler'] == 'plateau':
        model['lr_scheduler'] = {'class': 'ReduceLROnPlateau',
            'kwargs': {'mode': 'min', 'factor': .5, 'patience': 5, 'min_lr': 1e-6}, 'monitor': 'val_loss'}
    learning['torch_compile'] = {'enabled': settings['compile']}
    learning['trainer']['precision'] = settings['precision']
    learning['trainer']['benchmark'] = device == 'cuda'
    for key in ('train_dataloader', 'val_dataloader'):
        loader = learning[key]
        loader.update(num_workers=settings['workers'], pin_memory=device == 'cuda')
        if settings['workers']:
            loader.update(persistent_workers=True, prefetch_factor=2, multiprocessing_context='spawn')
        else:
            for name in ('persistent_workers', 'prefetch_factor', 'multiprocessing_context'):
                loader.pop(name, None)
    return data, model, learning


def hardware(device):
    import torch
    result = {'device': device, 'machine': platform.machine(), 'system': platform.system(),
              'torch': torch.__version__, 'threads': torch.get_num_threads()}
    if device == 'cuda':
        props = torch.cuda.get_device_properties(torch.cuda.current_device())
        result.update(name=props.name, memory=props.total_memory, capability=[props.major, props.minor], cuda=torch.version.cuda)
    else:
        result.update(processor=platform.processor(), platform=platform.platform())
    return result


def context(model, data, manifest):
    """Bind recommendations to content, controls/losses, initialization and hardware."""
    root = Path(manifest['project'])
    def portable(path):
        try:
            return Path(path).resolve().relative_to(root).as_posix()
        except ValueError:
            return str(Path(path).resolve())
    data = copy.deepcopy(data)
    for row in [data.get('common', {})]+[r for split in ('train','validation') for r in data[split]]:
        for key in ('x_path', 'y_path'):
            if key in row:
                row[key] = portable(root/row[key])
    payload = {'engine_version': 1, 'model': model, 'data': data, 'architecture': manifest['model_architecture'], 'upstream': manifest['upstream_revision'],
               'initialization': manifest.get('warm_start'),
               'audio': {portable(p): sha for p, sha in manifest['audio_sha256'].items()}}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def recommended(path, device):
    from .checks import read_json
    report = read_json(path)
    if report.get('version') != 1 or report.get('hardware') != hardware(device):
        raise ValueError('Benchmark recommendation belongs to different hardware or a different PyTorch runtime; benchmark this device again')
    selected = report.get('recommended')
    batch = report.get('recommended_batch')
    if report.get('status') != 'complete' or type(batch) is not int or not 1 <= batch <= 64:
        raise ValueError('Benchmark must finish with a valid recommended batch size')
    if not selected or not any(row.get('passed') is True and row.get('settings') == selected and row.get('batch') == report.get('recommended_batch')
                              for row in report.get('trials', [])):
        raise ValueError('Benchmark contains no successful recommendation')
    return options(selected, device), report


@contextmanager
def runtime(device):
    import torch
    previous, benchmark = torch.get_float32_matmul_precision(), torch.backends.cudnn.benchmark
    try:
        torch.set_float32_matmul_precision('highest')
        torch.backends.cudnn.benchmark = device == 'cuda'
        yield
    finally:
        torch.set_float32_matmul_precision(previous)
        torch.backends.cudnn.benchmark = benchmark
