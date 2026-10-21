"""One disposable benchmark trial using the real NAM loss and optimizer."""
import json
import math
import time
from pathlib import Path
import sys
import copy


def subset(data):
    # Sample both ordinary audio and augmentation, with a spread of controls.
    result = copy.deepcopy(data)
    for split in ('train', 'validation'):
        groups = {}
        for row in data[split]:
            merged = {**data.get('common', {}), **row}
            groups.setdefault(merged['x_path'], []).append(row)
        result[split] = []
        for rows in groups.values():
            result[split].extend(rows[i] for i in sorted({0, len(rows)//2, len(rows)-1}))
    return result


def run(job):
    import torch
    import pytorch_lightning as pl
    from nam.train import parametric as upstream
    from nam.data import apply_joint_dataset_hooks, get_joint_dataset_hooks
    from .performance import configure, runtime
    from .checks import read_json
    from .warm_start import initialize
    pl.seed_everything(42, workers=True)
    root = Path(job['run'])
    device = job['device']
    model_config = read_json(root/'model.json')
    full_data, model_config, learning = configure(read_json(root/'data.json'), model_config,
                                            read_json(root/'learning.json'), job['settings'], device)
    data = upstream._data_config_from_model(subset(full_data), model_config)
    module = upstream._ParametricLightningModule.init_from_config(model_config)
    net = upstream._get_parametric_net(module)
    manifest = read_json(root/'manifest.json')
    if manifest.get('warm_start'):
        initialize(net, root/'warm_start.nam', manifest['warm_start']['source_sha256'])
    data.setdefault('common', {})['nx'] = net.receptive_field
    full_workload = None
    if job.get('duration'):
        from .duration import workload
        full_workload = workload(full_data, learning, net.receptive_field)
    datasets = []
    loader = None
    val_loader = None
    try:
        for split in (upstream._Split.TRAIN, upstream._Split.VALIDATION):
            datasets.append(upstream._init_dataset(data, split))
        apply_joint_dataset_hooks(dataset_train=upstream._ConcatDataset(upstream._iter_inner_datasets(datasets[0])),
            dataset_validation=upstream._ConcatDataset(upstream._iter_inner_datasets(datasets[1])),
            hooks=get_joint_dataset_hooks(data.get('joint', [])))
        net.sample_rate = getattr(datasets[0], 'sample_rate', None)
        upstream._handshake_datasets(module, *datasets)
        config = learning['train_dataloader']
        config['batch_size'] = job['batch']
        loader = upstream._make_parametric_dataloader(datasets[0], config)
        if len(loader) == 0:
            raise ValueError('No training windows fit this candidate')
        module.set_capture_batch_samplers(train_sampler=loader.batch_sampler)
        upstream._enable_training_fast_paths(net, [loader], learning['torch_compile'])
        durations, frames, train_samples, validation_samples = [], [], [], []
        validation_seen = [0]
        first_seconds = []
        def sync():
            if device == 'cuda': torch.cuda.synchronize()
            elif device == 'mps': torch.mps.synchronize()
        class Measure(pl.Callback):
            def on_train_start(self, trainer, model):
                sync()
                self.last = time.perf_counter()
            def on_train_batch_end(self, trainer, model, outputs, batch, batch_idx):
                sync()
                now = time.perf_counter()
                elapsed = now-self.last
                if not torch.isfinite(outputs['loss']):
                    raise ValueError('Nonfinite training loss')
                index = trainer.global_step-1
                if index == 0: first_seconds.append(elapsed)
                if index >= job['warmup']:
                    durations.append(elapsed)
                    frames.append(int(batch[-1].numel()))
                    train_samples.append({'seconds': elapsed, 'batch': int(batch[-1].shape[0]), 'ny': int(batch[-1].shape[-1])})
                self.last = time.perf_counter()
            def on_validation_start(self, trainer, model):
                sync()
                self.last_validation = time.perf_counter()
            def on_validation_batch_end(self, trainer, model, outputs, batch, batch_idx, dataloader_idx=0):
                sync()
                now = time.perf_counter()
                if validation_seen[0] >= job['warmup']:
                    validation_samples.append({'seconds':now-self.last_validation,
                                               'batch':int(batch[-1].shape[0]),'ny':int(batch[-1].shape[-1])})
                validation_seen[0] += 1
                self.last_validation = time.perf_counter()
            def on_train_end(self, trainer, model):
                values = [p.detach() for p in model.parameters()]
                values += [p.grad for p in model.parameters() if p.grad is not None]
                if not all(bool(torch.isfinite(value).all()) for value in values):
                    raise ValueError('Nonfinite model weights or gradients')
        with runtime(device):
            trainer = pl.Trainer(accelerator='gpu' if device == 'cuda' else device, devices=1,
                precision=job['settings']['precision'], benchmark=device == 'cuda',
                max_steps=job['warmup']+job['steps'], max_epochs=-1,
                limit_val_batches=0, num_sanity_val_steps=0,
                enable_checkpointing=False, enable_progress_bar=False, enable_model_summary=False,
                logger=False, callbacks=[Measure()], gradient_clip_val=learning['trainer'].get('gradient_clip_val',.5))
            trainer.fit(module, loader)
            if job.get('duration'):
                val_config = dict(learning['val_dataloader'], batch_size=job['batch'])
                val_loader = upstream._make_parametric_dataloader(datasets[1], val_config)
                if not len(val_loader):
                    raise ValueError('No validation batches fit the selected settings')
                module.set_capture_batch_samplers(train_sampler=loader.batch_sampler,val_sampler=val_loader.batch_sampler)
                required = job['warmup']+job['val_steps']
                while validation_seen[0] < required:
                    trainer.limit_val_batches = min(len(val_loader), required-validation_seen[0])
                    measured = trainer.validate(module, dataloaders=val_loader, verbose=False)
                    if any(not math.isfinite(float(value)) for row in measured for value in row.values()):
                        raise ValueError('Nonfinite validation loss')
                if len(validation_samples) != job['val_steps']:
                    raise ValueError('Incomplete validation timing')
        if len(durations) != job['steps'] or not all(math.isfinite(t) and t > 0 for t in durations):
            raise ValueError('Benchmark did not complete the requested measured steps')
        result = {'passed': True, 'audio_seconds_per_second': sum(frames)/48000/sum(durations),
                'seconds_per_step': sum(durations)/len(durations), 'first_step_seconds': first_seconds[0],
                'measured_steps': len(durations), 'batch': job['batch'],
                'settings': job['settings'], 'frames_scored': sum(frames),
                'peak_cuda_memory_bytes': torch.cuda.max_memory_allocated() if device == 'cuda' else None}
        if job.get('duration'):
            result.update(workload=full_workload,train_samples=train_samples,validation_samples=validation_samples,
                          receptive_field=net.receptive_field)
        return result
    finally:
        upstream._release_training_fast_paths(net)
        for used_loader in (loader,val_loader):
            iterator = getattr(used_loader, '_iterator', None)
            if iterator is not None:
                iterator._shutdown_workers()
        for dataset in datasets:
            dataset.teardown()


def main():
    from nam.capture.project import atomic_write_json
    path = Path(sys.argv[1])
    job = json.loads(path.read_text())
    started = time.perf_counter()
    try:
        result = run(job)
    except Exception as exc:
        result = {'passed': False, 'error': f'{type(exc).__name__}: {exc}',
                  'batch': job['batch'], 'settings': job['settings']}
    result['trial_wall_seconds'] = time.perf_counter()-started
    atomic_write_json(Path(job['result']), result)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
