"""Fixed validation controls; no final maps, training, cloud or model APIs."""
import importlib.util
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import platform
import sys
import time

FROZEN = Path('/tmp/junction-learning-frozen')
OUTPUT = Path('/tmp/junction-learning-validation-controls')
sys.path.insert(0, str(FROZEN))
import numpy as np
import torch
from lightlag_learning import environment
from lightlag_learning import train
from lightlag_traverse import pilot

spec = importlib.util.spec_from_file_location('validation_control_evaluator', OUTPUT/'evaluator.py')
evaluator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = evaluator
spec.loader.exec_module(evaluator)


def work(job):
    bundle = evaluator.evaluate_job(job)
    audit = evaluator.audit_case(bundle, job['arm'])
    return bundle, audit


def main():
    torch.set_num_threads(1)
    if (OUTPUT/'freeze.json').exists() or (OUTPUT/'report.json').exists():
        raise FileExistsError('controls already frozen; do not rerun or overwrite')
    source = train.source_pins()
    campaign = train.read_json(FROZEN/'docs/learning-campaign-results/freeze.json')
    assert all(campaign['source_sha256'].get(name)==hashed for name,hashed in source.items())
    assert set(campaign['source_sha256'])-set(source)=={'tools/learning_campaign/__init__.py','tools/learning_campaign/modal_job.py'}
    assert all(train.digest(FROZEN/name)==hashed for name,hashed in campaign['source_sha256'].items())
    modules = {'train':train.__file__, 'environment':environment.__file__, 'pilot':pilot.__file__}
    assert all(Path(p).resolve().is_relative_to(FROZEN.resolve()) for p in modules.values())
    maps = list(train.VALIDATION_MAPS)
    assert maps == list(range(81000,81032)) and not set(maps).intersection(train.FINAL_MAPS)
    config = {'schema':'learning-validation-controls-freeze-v1',
              'purpose':'New diagnostic evaluations on already-declared validation maps; not fresh final confirmation and not staging-gate changes.',
              'source_commit':campaign['source_commit'], 'source_sha256':campaign['source_sha256'],
              'training_source_sha256':source,
              'campaign_freeze_sha256':train.digest(FROZEN/'docs/learning-campaign-results/freeze.json'),
              'evaluator_sha256':train.digest(OUTPUT/'evaluator.py'),
              'driver_sha256':train.digest(OUTPUT/'driver.py'), 'module_paths':modules,
              'maps':maps, 'arms':['greedy','beam'], 'episodes':64, 'workers':4,
              'numpy':np.__version__, 'torch':torch.__version__, 'python':platform.python_version(),
              'model_api_calls':0, 'cloud_jobs':0, 'training_updates':0}
    train.atomic_json(OUTPUT/'freeze.json',config)
    report={'schema':'learning-validation-controls-v1','complete':False,'status':'running',
            'freeze_sha256':train.digest(OUTPUT/'freeze.json'),'cases':[]}
    train.atomic_json(OUTPUT/'report.json',report)
    jobs=[{'arm':{'id':arm,'kind':arm},'seed':seed,'action_seed':seed}
          for arm in config['arms'] for seed in maps]
    started=time.monotonic()
    try:
        with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn'),
                                 initializer=train.worker_init) as pool:
            pending={pool.submit(work,job):job for job in jobs}
            for future in as_completed(pending):
                job=pending[future]
                bundle,audit=future.result()
                assert (bundle['arm'],bundle['seed']) == (job['arm']['id'],job['seed'])
                name=f"cases/{bundle['arm']}-{bundle['seed']}.json.gz"
                assert not (OUTPUT/name).exists()
                train.atomic_json(OUTPUT/name,bundle)
                row=evaluator.row_for(bundle,name,train.digest(OUTPUT/name))
                row['audit']=audit
                report['cases'].append(row)
                report['cases'].sort(key=lambda r:(r['arm'],r['seed']))
                train.atomic_json(OUTPUT/'report.json',report)
                if len(report['cases'])%8==0:
                    print(json.dumps({'cases_completed_and_audited':len(report['cases']),
                                      'elapsed_seconds':round(time.monotonic()-started,2)}),flush=True)
        assert train.source_pins()==source
        assert train.digest(OUTPUT/'evaluator.py')==config['evaluator_sha256']
        assert train.digest(OUTPUT/'driver.py')==config['driver_sha256']
        assert train.digest(OUTPUT/'freeze.json')==report['freeze_sha256']
        assert {(r['arm'],r['seed']) for r in report['cases']} == {(j['arm']['id'],j['seed']) for j in jobs}
        assert len(report['cases'])==64
        summary={}
        for arm in config['arms']:
            rows=[r for r in report['cases'] if r['arm']==arm]
            summary[arm]={'n':len(rows),'mean_reward':float(np.mean([r['reward'] for r in rows])),
                          'home':sum(r['home'] for r in rows),'alive':sum(r['alive'] for r in rows),
                          'invalid_calls':sum(r['invalid_calls'] for r in rows),
                          'cases_audited':sum(r['audit']['physics_verified'] for r in rows)}
        report.update(complete=True,status='complete',summary=summary,
                      elapsed_seconds=time.monotonic()-started,
                      limit='Full physics/grades and greedy choices audited; public observation extraction and choice-to-command linkage are source-pinned. Original beam logic is source-pinned. Validation context only; final maps remain unopened.')
        train.atomic_json(OUTPUT/'report.json',report)
        print(json.dumps({'complete':True,'summary':summary,'elapsed_seconds':report['elapsed_seconds']}),flush=True)
    except BaseException as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error))
        train.atomic_json(OUTPUT/'report.json',report)
        raise


if __name__=='__main__':main()
