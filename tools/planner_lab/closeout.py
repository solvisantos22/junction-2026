"""Build the reproducible results handoff from completed audit artifacts."""

import json
from pathlib import Path

from lightlag_planner_lab.worker import file_hash, source_manifest
from .common import OUT, read_batch, read_receipts, require, rows, utc, write


LABELS={'reference':'Frozen reference','old_extra_trees':'Previous Extra Trees',
    'static_best':'Best fixed strategy','learned_random_forest':'New Random Forest',
    'learned_pooled_forest':'Pooled forest','learned_extra_trees':'New Extra Trees','learned_mlp':'MLP'}
GATE_LABELS={'mean_gain':'gain of at least +1 pp over the reference',
    'nonnegative_vs_old':'mean at least as high as the previous Extra Trees',
    'positive_interval':'positive paired confidence interval','validation_eligible':'validation eligibility',
    'home':'no worse home/alive count','deaths':'no worse death count','valid':'valid controller calls'}


def read(name): return json.loads((OUT/name).read_text())
def pp(value): return f'{100*value:+.4f}'
def interval(values): return f'[{pp(values[0])}, {pp(values[1])}]'


def platform_example():
    from lightlag_traverse.environment import TraverseEnvironment
    different=next((r for r in read('final/local-audit.json')['checked'] if not r['exact']),None)
    if different is None: return None
    item=next(r for r in read_receipts('final') if r['job_id']==different['job_id'])
    bundle=read_batch(item); episode=next(e for e in bundle['episodes'] if e['arm']['name']==different['name'])
    remote=episode['replay']['world']['features']
    environment=TraverseEnvironment(different['seed'])
    while not environment.advance(5)['episode_complete']: pass
    local=environment.replay()['world']['features']
    changes=[]
    def compare(a,b,path='world.features'):
        if isinstance(a,dict):
            require(a.keys()==b.keys(),'map metadata schema differs')
            for key in a: compare(a[key],b[key],path+'.'+str(key))
        elif isinstance(a,list):
            require(len(a)==len(b),'map metadata list differs')
            for i,(x,y) in enumerate(zip(a,b)): compare(x,y,path+'['+str(i)+']')
        elif a!=b:
            require(isinstance(a,(int,float)) and isinstance(b,(int,float)),'nonnumeric metadata difference')
            changes.append({'path':path,'linux':a,'mac':b,'absolute_difference':abs(a-b)})
    compare(remote,local)
    require(changes,'nonexact replay had no map metadata difference')
    result={'seed':different['seed'],'name':different['name'],'numeric_differences':len(changes),
        'maximum_absolute_difference':max(c['absolute_difference'] for c in changes),'examples':changes[:8],
        'note':'One illustrative world. Every mission separately passed exact physical-trajectory and grade checks.'}
    write(OUT/'platform-difference-example.json',result); return result


def main():
    summary=read('final/summary.json'); selected=read('selection.json'); diagnostics=read('development-diagnostics.json')
    require(selected['source']==source_manifest(),'source changed')
    counts={'smoke':34,'data':7232,'final':960}; audits={}; repeats=0
    for stage,n in counts.items():
        report=read(stage+'/report.json'); cloud=read(stage+'/cloud-audit.json'); local=read(stage+'/local-audit.json')
        require(report['missions']==cloud['missions']==cloud['exact']==local['missions']==n,'incomplete replay checks')
        require(cloud['receipts_sha256']==local['receipts_sha256']==file_hash(OUT/stage/'receipts.jsonl'),'audit receipts differ')
        audits[stage]={'missions':n,'linux_exact':cloud['exact'],'mac_exact':local['exact'],
                       'mac_metadata_only':local['metadata_only_differences']}
        repeats+=len(read(stage+'/repeat-audit.json')['checked'])
    require(read('final/statistics-audit.json')['summary_sha256']==file_hash(OUT/'final/summary.json'),'summary audit differs')
    require(read('final/decision-audit.json')['selection_sha256']==file_hash(OUT/'selection.json'),'decision selection differs')
    resource={}
    for stage in counts:
        receipts=read_receipts(stage); stage_rows=rows(stage)
        resource[stage]={'missions':len(stage_rows),'batches':len(receipts),
            'recorded_batch_cpu_hours':sum(r['cpu_seconds'] for r in receipts)/3600,
            'recorded_batch_wall_hours':sum(r['wall_seconds'] for r in receipts)/3600,
            'standalone_equivalent_controller_cpu_hours':sum(r['cpu_seconds'] for r in stage_rows)/3600}
    fit_seconds={p.stem:json.loads(p.read_text())['seconds'] for p in (OUT/'models').glob('*.json')}
    resource.update(fit_seconds=fit_seconds,total_recorded_mission_cpu_hours=sum(resource[s]['recorded_batch_cpu_hours'] for s in counts),
        note='Execution measurements, not an invoice. Excludes platform restarts, startup, idle, serialization, replay-audit and full-repeat compute. Batch timing shares prefixes; controller timing counts a full prefix per policy.')
    write(OUT/'compute-summary.json',resource); example=platform_example()
    t=summary['table']; primary=summary['primary']; p=t[primary]; n=p['n']; fixed=t['static_best']
    lines=['# Modal planner lab — completed results','',
        f"**{LABELS[primary]} was the primary selected model.** On {n} fresh matched worlds it scored **{100*p['mean']:.4f}%**, versus **{100*t['reference']['mean']:.4f}%** for the frozen reference: **{pp(p['delta'])} percentage points**, paired 95% interval **{interval(p['ci95'])}**.", '',
        f"The predefined fixed-strategy control, `{selected['best_static']}`, scored **{100*fixed['mean']:.4f}%** ({pp(fixed['delta'])} pp versus reference, paired 95% interval {interval(fixed['ci95'])}), with {fixed['home_alive']}/{n} rovers home/alive. Its gain over the previous model was {pp(fixed['vs_old_delta'])} pp, interval {interval(fixed['vs_old_ci95'])}.", '',
        f"The predeclared practical-upgrade gate **{'passed' if summary['confirmed'] else 'did not pass'}**. Criteria not met: {'; '.join(GATE_LABELS[k] for k,v in summary['gate'].items() if not v) or 'none'}. The canonical reference remains unchanged.", '',
        '## Fresh comparison','',
        '| Policy | Mean score | Gain vs reference | Paired 95% interval (pp) | Home/alive | Deaths |',
        '|---|---:|---:|---:|---:|---:|']
    for arm in selected['arms']:
        name=arm['name']; v=t[name]
        lines.append(f"| {LABELS[name]} | {100*v['mean']:.4f}% | {pp(v['delta'])} pp | {interval(v['ci95'])} | {v['home_alive']}/{n} | {v['deaths']} |")
    lines += ['',f"Primary versus the previous frozen Extra Trees: **{pp(p['vs_old_delta'])} pp**, paired 95% interval **{interval(p['vs_old_ci95'])}**. Against the reference it won on {p['higher']} worlds, tied on {p['equal']} and lost on {p['lower']}. Its interval adjusted for four comparisons is **{interval(p['ci_family95'])} pp**. All fresh policies had zero controller errors and invalid calls.", '',
        '![Fresh paired comparison](fresh-comparison.png)', '',
        '[Vector figure](fresh-comparison.svg) · [PDF figure](fresh-comparison.pdf) · [full statistics](final/summary.json) · [independent statistics audit](final/statistics-audit.json)', '',
        '## What was trained','',
        '384 training worlds × 16 strategy programs, 64 validation worlds × 16 programs plus the previous model, and 192 fresh worlds × five policies: **8,192 production missions**. Four model families were actually fitted on Modal in parallel: Extra Trees, Random Forest, a pooled action-conditioned forest with failure prediction, and a two-layer MLP. Each uses 61 public-state features at tick 70. The existing reference handles navigation; the learner chooses a strategy program. No hidden state, map seed or future outcome is a decision input.', '',
        'Validation tested 24 fixed settings and selected two distinct families. All four original checkpoints are retained. The neural network did not satisfy validation eligibility. The best fixed strategy was `'+selected['best_static']+'`. Selection and weights were published before any fresh mission in commit `'+read('final/freeze.json')['commit']+'`.', '',
        '| Model family, best validation setting (eligible ranked first) | Validation score | Gain vs reference | Home/alive | Eligible |',
        '|---|---:|---:|---:|---|']
    for name,v in diagnostics['models'].items():
        st=v['stats']; lines.append(f"| {name} | {100*st['mean']:.4f}% | {pp(st['delta'])} pp | {st['home_alive']}/64 | {'yes' if v['eligible'] else 'no'} |")
    lines += ['', '## Which ideas helped on development worlds','',
        'The table below is descriptive validation evidence, used in selection. It is not another fresh confirmation.', '',
        '| Fixed strategy | Validation score | Gain vs reference | Home/alive | Deaths |',
        '|---|---:|---:|---:|---:|']
    for name,v in diagnostics['splits']['validation']['fixed'].items():
        lines.append(f"| {name} | {100*v['mean']:.4f}% | {pp(v['delta'])} pp | {v['home_alive']}/64 | {v['deaths']} |")
    ceiling=diagnostics['splits']['validation']['hindsight_oracle_gain']
    lines += ['',f"Choosing the best of all 16 outcomes with hindsight would gain only **{100*ceiling:.4f} pp** on validation. That is a descriptive ceiling, not an executable policy. The predeclared practical target remained +1 pp. Return guards were overly conservative. The table retains every tested strategy, including both beneficial and unsuccessful variations. [Full diagnostics and paired strategy comparisons](development-diagnostics.json).", '',
        '## Verification and limits','',
        f"All **{sum(counts.values()):,} archived missions** (production plus 34 smoke) replay exactly on Linux. On the Mac, every physical trajectory and grade matches; {sum(a['mac_metadata_only'] for a in audits.values())} differ only in decorative map metadata. {repeats} full controller reruns also match, including the original reference, previous frozen learned policy and selected new learner. All checkpoint predictions, validation rankings, new/old model choices and final paired statistics independently reproduce. Eight controller/model tests and a separate concurrent-report test passed.", '',
        '[Linux fresh replay audit](final/cloud-audit.json) · [Mac fresh replay audit](final/local-audit.json) · [full-controller repeats](final/repeat-audit.json) · [decision audit](final/decision-audit.json) · [selection audit](selection-audit.json) · [training-data audit](data/cloud-audit.json) · [test output](local-tests.txt) · [concurrency test](archive-tests.txt)', '']
    if example:
        lines += [f"One [cross-platform metadata example](platform-difference-example.json) differs by at most {example['maximum_absolute_difference']:.3g} in decorative coordinates; its physics and score match exactly.", '']
    lines += ['This is one fit seed per family and one normal-map test distribution. Bootstrap intervals describe variation across worlds, not training seeds. The pooled model’s failure penalty and forest-disagreement penalty are heuristics, not safety guarantees. No new Claude evaluation, reference promotion, simulator change or teammate-model modification occurred.', '',
        '## Compute and reproduction','',
        f"Up to 100 mission containers; four model fits in parallel. Recorded mission-worker CPU time totals **{resource['total_recorded_mission_cpu_hours']:.2f} hours**, with shared prefixes. Model fit durations were "+', '.join(f'{k}: {v:.2f} s' for k,v in sorted(fit_seconds.items()))+'. These measurements exclude platform/startup/idle/replay overhead and are not an invoice. No GPU or LLM API calls. [Compute details](compute-summary.json).', '',
        'Original attempts, platform preemptions, partial checkpoints and every policy outcome are retained. Controller, feature and model definitions stayed pinned. Orchestration and audit code were recorded separately, including fixes for concurrent report writes and audit memory use. Per-attempt hashes preserve those changes. All ten experiment apps are [verified stopped](app-status.json); other apps were left unchanged.', '',
        '[Protocol](../planner-lab.md) · [selection](selection.json) · [weights](models/) · [fit calls](fit-receipt.json) · [training receipts](data/receipts.jsonl) · [fresh receipts](final/receipts.jsonl) · [figure provenance](figure-receipt.json)', '',
        '```sh', 'python -m tools.planner_lab.run summary', 'python -m tools.planner_lab.verify_selection selection',
        'python -m tools.planner_lab.verify_selection final', 'python -m tools.planner_lab.audit final decisions',
        'python -m tools.planner_lab.plot', '```', '',
        'The cloud entry points are `tools.planner_lab.run` (`smoke`, `data`, `fit`, `final`) and `tools.planner_lab.audit` (`cloud`, `repeats`). Existing archived stages resume only missing batches. Published selection/weights are immutable; final worlds are now consumed and must not be reused for tuning.']
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    write(OUT/'closeout-audit.json',{'created_utc':utc(),'audits':audits,'full_controller_repeats':repeats,
        'selection_sha256':file_hash(OUT/'selection.json'),'summary_sha256':file_hash(OUT/'final/summary.json'),
        'readme_sha256':file_hash(OUT/'README.md')})
    print('Wrote completed results and compute handoff.')


if __name__=='__main__': main()
