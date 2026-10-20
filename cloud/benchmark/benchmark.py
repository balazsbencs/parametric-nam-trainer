#!/usr/bin/env python3
"""Portable Standard/Nano duration benchmark, with explicit MPS/CUDA selection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile,ZIP_DEFLATED

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'vendor'))
os.environ.setdefault('MPLBACKEND','Agg')
os.environ.setdefault('TOKENIZERS_PARALLELISM','false')


def verify():
    hashes=json.loads((ROOT/'SHA256.json').read_text())
    for name,expected in hashes.items():
        with (ROOT/name).open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=expected:
                raise ValueError('Package file changed: '+name)
    print(f'Verified {len(hashes)} package files.',flush=True)


def doctor(device):
    from parametric_mac.training import select_device
    from parametric_mac.performance import hardware
    import torch
    select_device(device)
    model=torch.nn.Conv1d(2,8,6).to(device)
    model(torch.randn(1,2,8192,device=device)).square().mean().backward()
    if device=='mps':torch.mps.synchronize()
    elif device=='cuda':torch.cuda.synchronize()
    print(json.dumps(hardware(device),indent=2),flush=True)
    print('Device convolution/backpropagation passed.',flush=True)


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith('-'):argv.insert(0,'run')
    config=json.loads((ROOT/'BENCHMARK.json').read_text())
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('verify')
    command=sub.add_parser('doctor')
    command.add_argument('--device',choices=('mps','cuda','cpu'),default=config['device'])
    command=sub.add_parser('run')
    command.add_argument('--device',choices=('mps','cuda','cpu'),default=config['device'])
    command.add_argument('--models',nargs='+',choices=('standard','nano'),default=['standard','nano'])
    command.add_argument('--batch',type=int,default=4)
    command.add_argument('--steps',type=int,default=20)
    command.add_argument('--val-steps',type=int,default=8)
    command.add_argument('--warmup',type=int,default=3)
    command.add_argument('--epochs',nargs='+',type=int,default=[50,100,200])
    command.add_argument('--timeout',type=int,default=1200,help='Maximum seconds per architecture, including preparation in its measurement worker')
    command.add_argument('--precision',choices=('32-true','bf16-mixed'),default='32-true')
    command.add_argument('--compile',dest='compiled',action='store_true')
    command.add_argument('--ny',type=int)
    command.add_argument('--workers',type=int,default=0)
    command.add_argument('--hourly-rate',type=float,help='Optional actual pod compute rate; never guessed by the benchmark')
    args=parser.parse_args(argv)
    verify()
    if args.command=='verify':return 0
    doctor(args.device)
    if args.command=='doctor':return 0
    from parametric_mac.duration import benchmark_duration
    destination=benchmark_duration(ROOT/'project',args.device,args.models,args.batch,args.steps,args.val_steps,args.warmup,
        args.epochs,{'precision':args.precision,'compile':args.compiled,'ny':args.ny,'workers':args.workers},
        ROOT/'results',args.timeout,args.hourly_rate)
    archive=destination/'benchmark-results.zip'
    with ZipFile(archive,'x',ZIP_DEFLATED) as zipped:
        for path in destination.iterdir():
            if path.is_file() and path.suffix in ('.json','.csv','.txt','.log'):
                zipped.write(path,path.name)
        zipped.write(ROOT/'PROVENANCE.json','PACKAGE-PROVENANCE.json')
    print(f'Share this report: {archive}',flush=True)
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except (OSError,ValueError,RuntimeError,ImportError) as exc:
        print('Benchmark error: '+str(exc),file=sys.stderr);sys.exit(1)
    except KeyboardInterrupt:
        print('Stopped. Partial results are retained under results/.',file=sys.stderr);sys.exit(130)
