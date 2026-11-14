"""Read-only audit of retained sample-chain artifacts; writes only requested output."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
from statistics import mean
import sys
import time

p = argparse.ArgumentParser()
p.add_argument('--repo', type=Path, default=Path.cwd())
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
sys.path.insert(0, str(a.repo.resolve()))
from tools.certified_challenge_probe.model import generate, verify
from tools.certified_challenge_probe.search import beam, compile_choices
from tools.certified_challenge_probe.study import run_case, summarize

package = a.repo / 'tools/certified_challenge_probe'
report = {'python': platform.python_version(), 'model_calls': 0, 'artifacts': []}
started = time.perf_counter()
for split in ('development', 'check'):
    path = package / 'results' / (split + '.json')
    frozen = json.loads(path.read_text())
    item = {'split': split, 'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_hashes_match': True, 'mission_regenerations': 0, 'valid_policy_replays': 0,
            'identical_policy_reproductions': 0, 'certified_references': 0, 'metrics': {}}
    for name, value in frozen['source_sha256'].items():
        assert hashlib.sha256((package / name).read_bytes()).hexdigest() == value, name
    assert summarize(frozen['cases']) == frozen['summary']
    for case in frozen['cases']:
        assert generate(case['seed'], case['jobs']) == case['mission']
        item['mission_regenerations'] += 1
        reproduced = run_case(case['seed'], case['jobs'], frozen['configuration']['max_nodes'])
        assert reproduced['mission'] == case['mission']
        assert reproduced['candidate_count'] == case['candidate_count']
        for name, saved in case['runs'].items():
            checked = verify(case['mission'], saved['plan'])
            assert checked['valid'] and checked['value'] == saved['value']
            item['valid_policy_replays'] += 1
            # Different hardware/Python versions may change elapsed time only.
            expected = {k: v for k, v in saved.items() if k != 'seconds'}
            actual = {k: v for k, v in reproduced['runs'][name].items() if k != 'seconds'}
            assert actual == expected, (split, case['seed'], case['jobs'], name)
            item['identical_policy_reproductions'] += 1
        item['certified_references'] += reproduced['runs']['reference']['proven_optimal']
    for size in sorted({c['jobs'] for c in frozen['cases']}):
        cases = [c for c in frozen['cases'] if c['jobs'] == size]
        metrics = {'cases': len(cases), 'maximum_reference_nodes': max(c['runs']['reference']['nodes'] for c in cases)}
        for name in ('portfolio', 'beam64'):
            metrics[name] = {
                'mean_fraction_optimum': mean(c['runs'][name]['value']/c['runs']['reference']['value'] for c in cases),
                'optimal_cases': sum(c['runs'][name]['value'] == c['runs']['reference']['value'] for c in cases),
                'mean_raw_value': mean(c['runs'][name]['value'] for c in cases),
            }
        item['metrics'][str(size)] = metrics
    report['artifacts'].append(item)
report['elapsed_seconds'] = time.perf_counter() - started
a.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
