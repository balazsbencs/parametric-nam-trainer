"""Count full recording workloads and estimate Standard/Nano training duration."""
import csv
from datetime import datetime, timezone
import math
from pathlib import Path
import statistics
import subprocess
import sys
import os
import uuid
from .checks import read_json, absolute_data


def workload(data, learning, receptive_field):
    """Use the pinned dataset's actual trimming/delay/context rules, one capture at a time."""
    from nam.data import Dataset
    result = {}
    for split, loader_key in (('train','train_dataloader'), ('validation','val_dataloader')):
        loader = learning[loader_key]
        batch = loader.get('batch_size',1)
        drop = loader.get('drop_last',False)
        grouped = loader.get('capture_grouped_batches',True)
        counts = []
        for row in data[split]:
            config = {**data.get('common',{}), **row}
            config.pop('params',None)
            config.pop('type',None)
            config.update(nx=receptive_field)
            dataset = Dataset.init_from_config(config)
            try:
                counts.append((len(dataset),dataset.ny))
            finally:
                dataset.teardown()
        if len({ny for _,ny in counts}) != 1:
            raise ValueError('The trainer needs a consistent window size within each split')
        if not grouped:
            counts=[(sum(n for n,_ in counts),counts[0][1])]
        groups={}
        for count,ny in counts:
            full,tail=divmod(count,batch)
            if full: groups[(batch,ny)]=groups.get((batch,ny),0)+full
            if tail and not drop: groups[(tail,ny)]=groups.get((tail,ny),0)+1
        result[split]={'windows':sum(n for n,_ in counts),'batches':sum(groups.values()),
                       'groups':[{'batch':b,'ny':ny,'batches':n} for (b,ny),n in sorted(groups.items())],
                       'scored_frames':sum(b*ny*n for (b,ny),n in groups.items())}
    return result


def phase_estimate(groups, samples):
    if not samples or any(not math.isfinite(s['seconds']) or s['seconds']<=0 for s in samples):
        raise ValueError('No finite timing samples for this phase')
    per_frame=[s['seconds']/(s['batch']*s['ny']) for s in samples]
    fallback=statistics.median(per_frame)
    seconds,unobserved=0.,0
    for group in groups:
        exact=[s['seconds'] for s in samples if (s['batch'],s['ny'])==(group['batch'],group['ny'])]
        if exact:
            per_batch=statistics.median(exact)
        else:
            per_batch=fallback*group['batch']*group['ny']
            unobserved+=group['batches']
        seconds+=per_batch*group['batches']
    spread=statistics.pstdev(per_frame)/statistics.mean(per_frame) if len(per_frame)>1 else 0.
    margin=max(.3 if unobserved else .2,min(spread,1.))
    return {'seconds':seconds,'planning_low_seconds':seconds*max(0,1-margin),
            'planning_high_seconds':seconds*(1+margin),
            'measured_batches':len(samples),'extrapolated_batch_shapes':unobserved}


def estimate(work,train_samples,val_samples,epochs):
    training=phase_estimate(work['train']['groups'],train_samples)
    validation=phase_estimate(work['validation']['groups'],val_samples)
    epoch={k:training[k]+validation[k] for k in ('seconds','planning_low_seconds','planning_high_seconds')}
    return {'training':training,'validation':validation,'epoch':epoch,
            'targets':{str(n):{k:value*n for k,value in epoch.items()} for n in epochs}}


def snapshot(project, destination):
    """Create a fresh-start benchmark project; never inherit a Standard-only warm start."""
    from .cli import project_configs
    from .transients import project_data
    from .input_reference import resolve_reference
    from .workflow import read_state
    project=Path(project).resolve()
    data,model=project_configs(project,'auto')
    data=project_data(project,data or read_json(project/'data.json'))
    resolve_reference(project,data)  # Verify recorded references before using their WAVs.
    if (project/'capture_project.json').exists():
        from .controls import load_project
        from nam.capture.export import build_concat_learning_config
        learning=build_concat_learning_config(load_project(project))
    else:
        learning=read_json(project/'learning_concat.json')
    model=model or read_json(project/'model_concat.json')
    destination.mkdir(parents=True)
    from nam.capture.project import atomic_write_json
    for name,value in (('data',absolute_data(data,project)),('model_concat',model),('learning_concat',learning),
                       ('workflow',{'gear_kind':read_state(project).get('gear_kind','amp')})):
        atomic_write_json(destination/f'{name}.json',value)
    return destination


def write_summary(destination,report):
    from nam.capture.project import atomic_write_json
    atomic_write_json(destination/'results.json',report)
    lines=['Training duration benchmark','',f"Device: {report['device']}; batch {report['batch']}",
           'Estimates cover training + epoch validation on all packaged fitting recordings.',
           'They exclude setup, checkpoint/NAM export, final qualification and idle/storage costs.',
           'Ranges are planning margins, not statistical confidence intervals.','',
           'Model        Epoch       '+'  '.join(f'{n} epochs' for n in report['epochs'])]
    records=[]
    successful=[]
    for name,row in report['models'].items():
        if not row.get('passed'):
            lines.append(f"{name}: FAILED — {row.get('error','see model log')}")
            continue
        estimates=row['estimates']
        epoch=estimates['epoch']['seconds']
        targets=estimates['targets']
        formatted=[f'{targets[str(n)]["seconds"]/3600:.2f} h' if str(n) in targets else '—' for n in report['epochs']]
        lines.append(f'{name:<12} {epoch/60:>6.1f} min  '+ '  '.join(f'{v:>10}' for v in formatted))
        largest=str(max(report['epochs']))
        low,high=(targets[largest][k]/3600 for k in ('planning_low_seconds','planning_high_seconds'))
        lines.append(f'  {largest}-epoch planning range: {low:.2f}–{high:.2f} h')
        successful.append(row)
        for n,target in targets.items():
            record={'model':name,'epochs':n,'training_seconds_per_epoch':estimates['training']['seconds'],
                    'validation_seconds_per_epoch':estimates['validation']['seconds'],**target}
            if report.get('hourly_rate') is not None:record['estimated_compute_cost']=target['seconds']/3600*report['hourly_rate']
            records.append(record)
    if len(successful)==2:
        for n in report['epochs']:
            seconds=sum(row['estimates']['targets'][str(n)]['seconds'] for row in successful)
            lines.append(f'Standard + Nano sequentially, {n} epochs each: {seconds/3600:.2f} h')
            records.append({'model':'Standard + Nano','epochs':n,'seconds':seconds,
                'planning_low_seconds':sum(row['estimates']['targets'][str(n)]['planning_low_seconds'] for row in successful),
                'planning_high_seconds':sum(row['estimates']['targets'][str(n)]['planning_high_seconds'] for row in successful)})
    lines+=['','See results.csv for planning ranges and results.json for hardware, settings and measured batches.',
            'These are timing estimates, not a promise of convergence or a qualified playable model.']
    (destination/'RESULTS.txt').write_text('\n'.join(lines)+'\n')
    if records:
        keys=list(dict.fromkeys(k for row in records for k in row))
        with (destination/'results.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=keys);writer.writeheader();writer.writerows(records)
    return '\n'.join(lines)


def benchmark_duration(project,device,models=('standard','nano'),batch=4,steps=20,val_steps=8,warmup=3,
                       epochs=(50,100,200),performance=None,output=None,timeout=1200,hourly_rate=None):
    from .training import prepare_run,select_device
    from .performance import hardware,options
    from .benchmark import _terminate
    from nam.capture.project import atomic_write_json
    if (not models or any(m not in ('standard','nano') for m in models) or len(set(models))!=len(models)
        or type(batch) is not int or not 1<=batch<=64 or type(steps) is not int or not 2<=steps<=200
        or type(val_steps) is not int or not 2<=val_steps<=100 or type(warmup) is not int or not 1<=warmup<=20
        or not epochs or any(type(n) is not int or not 1<=n<=10000 for n in epochs)
        or not 10<=timeout<=7200 or (hourly_rate is not None and (not math.isfinite(hourly_rate) or hourly_rate<0))):
        raise ValueError('Invalid bounded duration benchmark settings')
    device=select_device(device)
    settings=options(performance,device)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:6]
    destination=(Path(output) if output else Path(project)/'duration-results')/stamp
    destination.mkdir(parents=True,exist_ok=False)
    fresh=snapshot(project,destination/'fresh-project')
    report={'version':1,'device':device,'hardware':hardware(device),'batch':batch,'epochs':list(epochs),
            'settings':settings,'hourly_rate':hourly_rate,'models':{},'status':'running',
            'method':'Full dataset window/batch counts; sampled real training/backprop and separate validation after warmup. Fresh initialization for each architecture.',
            'excludes':['setup','checkpoint and NAM exports','final qualification','time to convergence','idle and storage costs']}
    write_summary(destination,report)
    print(f'Results folder: {destination}',flush=True)
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parent.parent)+os.pathsep+os.environ.get('PYTHONPATH','')}
    for name in models:
        print(f'Duration benchmark: {name.capitalize()} on {device}',flush=True)
        try:
            run=prepare_run(fresh,device,1,batch,'a2-'+name,performance=settings)
            result_path=destination/f'{name}-measurement.json'
            job={'run':str(run),'device':device,'batch':batch,'settings':settings,'steps':steps,
                 'warmup':warmup,'result':str(result_path),'duration':True,'val_steps':val_steps}
            job_path=destination/f'{name}-job.json';atomic_write_json(job_path,job)
            with (destination/f'{name}.log').open('w') as log:
                process=subprocess.Popen([sys.executable,'-m','parametric_mac.benchmark_worker',str(job_path)],
                    env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=os.name=='posix')
                try:process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:pass
                finally:_terminate(process)
            if not result_path.exists():raise ValueError(f'Measurement failed or exceeded {timeout}s; see {name}.log')
            measured=read_json(result_path)
            if process.returncode!=0 or not measured.get('passed'):
                raise ValueError(measured.get('error',f'Exit status {process.returncode}'))
            row={'passed':True,'measurement':measured,
                 'estimates':estimate(measured['workload'],measured['train_samples'],measured['validation_samples'],epochs)}
            row['recording_sha256']=read_json(run/'manifest.json')['audio_sha256']
            report['models'][name.capitalize()]=row
        except (OSError,ValueError,RuntimeError) as exc:
            report['models'][name.capitalize()]={'passed':False,'error':str(exc)}
        except KeyboardInterrupt:
            report['status']='interrupted';write_summary(destination,report);raise
        write_summary(destination,report)
        print(f"{name.capitalize()}: "+('timing completed' if report['models'][name.capitalize()]['passed'] else report['models'][name.capitalize()]['error']),flush=True)
    report['status']='complete' if all(row['passed'] for row in report['models'].values()) else 'partial_failure'
    print(write_summary(destination,report),flush=True)
    print(f'Duration results: {destination}',flush=True)
    if report['status']!='complete':raise ValueError(f'One or more models failed; successful measurements are retained in {destination}')
    return destination
