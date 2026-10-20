#!/usr/bin/env python3
"""Freeze matching Mac M2 and Runpod duration packages, including fitting WAVs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile,ZIP_DEFLATED,ZipInfo


def git(root,*args):
    return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()


def build(trainer,upstream,dataset,output,platform):
    scripts=Path(__file__).resolve().parent
    folder='NAM-Benchmark-Mac-M2' if platform=='mac' else 'NAM-Benchmark-Runpod'
    target=output/(folder+'.zip')
    hashes={}
    provenance={'trainer_commit':git(trainer,'rev-parse','HEAD'),
                'trainer_local_changes':git(trainer,'status','--short'),
                'upstream_commit':git(upstream,'rev-parse','HEAD'),
                'upstream_local_changes':git(upstream,'status','--short'),
                'purpose':'Standard/Nano training + validation duration estimation; no playable exports',
                'headless_patch':'Defer tkinter import in NAM train/core.py until its modal is used.'}
    if provenance['upstream_local_changes']:raise ValueError('Pinned upstream must be clean')
    data=json.loads((dataset/'data.json').read_text())
    extra=json.loads((dataset/'augmentation.json').read_text()) if (dataset/'augmentation.json').exists() else {}
    audio=set()
    for split in ('train','validation'):
        for row in data[split]+extra.get(split,[]):
            config={**data.get('common',{}),**row}
            for key in ('x_path','y_path'):
                path=(dataset/config[key]).resolve()
                audio.add(path.relative_to(dataset.resolve()))
    output.mkdir(parents=True,exist_ok=True)
    with ZipFile(target,'x',ZIP_DEFLATED,compresslevel=1) as archive:
        def write(name,content,executable=False):
            hashes[name]=hashlib.sha256(content).hexdigest()
            info=ZipInfo(folder+'/'+name)
            info.compress_type=ZIP_DEFLATED
            info.external_attr=(0o100755 if executable else 0o100644)<<16
            archive.writestr(info,content,compresslevel=1)
        for name in ('benchmark.py','README.md'):
            write(name,(scripts/name).read_bytes(),name.endswith('.py'))
        requirements=(trainer/'cloud/runpod/requirements.txt').read_bytes()
        write('requirements.txt',requirements)
        write('BENCHMARK.json',(json.dumps({'device':'mps' if platform=='mac' else 'cuda','models':['standard','nano']},indent=2)+'\n').encode())
        if platform=='mac':
            write('Install.command',(scripts/'Install.command').read_bytes(),True)
            for label,models in (('Both','standard nano'),('Standard','standard'),('Nano','nano')):
                text='#!/bin/bash\nset -euo pipefail\ncd -- "$(dirname -- "$0")"\n'
                text+='if [[ ! -x .venv/bin/python ]]; then echo "Run Install.command first."; exit 1; fi\n'
                text+=f'exec .venv/bin/python benchmark.py --models {models} "$@"\n'
                write('Benchmark '+label+'.command',text.encode(),True)
        else:
            write('setup.sh',(scripts/'setup.sh').read_bytes(),True)
        for source,prefix in ((trainer/'parametric_mac','vendor/parametric_mac'),(upstream/'nam','vendor/nam')):
            for path in sorted(source.rglob('*')):
                if (not path.is_file() or '__pycache__' in path.parts or
                    (path.suffix not in ('.py','.json','.wav') and path.name.upper() not in ('LICENSE','NOTICE','COPYING'))):continue
                content=path.read_bytes()
                if prefix=='vendor/nam' and path.relative_to(source).as_posix()=='train/core.py':
                    text=content.decode()
                    assert text.count('import tkinter as _tk\n')==1
                    text=text.replace('import tkinter as _tk\n','').replace('def _nasty_checks_modal():\n','def _nasty_checks_modal():\n    import tkinter as _tk\n')
                    content=text.encode()
                write(prefix+'/'+path.relative_to(source).as_posix(),content)
        write('vendor/NAM-LICENSE',(upstream/'LICENSE').read_bytes())
        metadata=('data.json','model_concat.json','learning_concat.json','capture_project.json',
                  'workflow.json','input_reference.json','augmentation.json','teacher-sources.json','attack-provenance.json')
        for name in metadata:
            path=dataset/name
            if not path.exists():continue
            content=path.read_bytes()
            if name=='workflow.json':
                state=json.loads(content)
                for key in ('warm_start_path','performance_profile'):state.pop(key,None)
                content=(json.dumps(state,indent=2)+'\n').encode()
            write('project/'+name,content)
        for name in sorted(audio):write('project/'+name.as_posix(),(dataset/name).read_bytes())
        provenance.update(fitting_audio_files=len(audio),platform=platform)
        write('PROVENANCE.json',(json.dumps(provenance,indent=2)+'\n').encode())
        archive.writestr(folder+'/SHA256.json',json.dumps(hashes,indent=2)+'\n')
    with target.open('rb') as stream:sha=hashlib.file_digest(stream,'sha256').hexdigest()
    target.with_suffix('.zip.sha256').write_text(f'{sha}  {target.name}\n')
    print(f'Created {target}: {target.stat().st_size:,} bytes; SHA256 {sha}',flush=True)
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trainer',type=Path,required=True)
    parser.add_argument('--upstream',type=Path,required=True)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--platform',choices=('mac','runpod','both'),default='both')
    args=parser.parse_args()
    for platform in (('mac','runpod') if args.platform=='both' else (args.platform,)):
        build(args.trainer.resolve(),args.upstream.resolve(),args.dataset.resolve(),args.output.resolve(),platform)


if __name__=='__main__':main()
