"""Plot retained development validations; never run policies or open worlds.

Use the separate plotting environment (matplotlib3.10.7/numpy2.3.4):
  python -m tools.learning_final.plot_results --runs RUNS --output FIGURES
"""

import argparse
from importlib.metadata import version
import json
from pathlib import Path
import platform

from . import decide

CHECKPOINTS = (0, 512, 2048, 8192)


def common_means(runs):
    """No averaging across different budgets, missing seeds, or last observations."""
    output = {}
    for algorithm in decide.ALGORITHMS:
        members = [run for run in runs if run['algorithm'] == algorithm]
        if (len(members) != 3 or {run['training_seed'] for run in members} != set(decide.SEEDS)):
            raise ValueError('every method requires all three initialization seeds')
        shared = set.intersection(*(set(run['checkpoints']) for run in members))
        output[algorithm] = [
            {'episodes': count,
             'mean_reward': sum(run['checkpoints'][str(count)]['mean_reward'] for run in members)/3,
             'home': sum(run['checkpoints'][str(count)]['home'] for run in members),
             'alive': sum(run['checkpoints'][str(count)]['alive'] for run in members),
             'invalid_calls': sum(run['checkpoints'][str(count)]['invalid_calls'] for run in members),
             'validation_cases': 96}
            for count in sorted(map(int, shared))]
    return output


def collect(directory):
    directory = Path(directory).resolve()
    rows, pins, config = [], None, None
    for algorithm in decide.ALGORITHMS:
        for seed in decide.SEEDS:
            run = directory/f'{algorithm}-{seed}'
            report = decide.read(run/'report.json')
            if (report['schema'] != 'learning-training-report-v1'
                    or report.get('experiment') != decide.EXPERIMENT
                    or report['smoke'] is not False or report['algorithm'] != algorithm
                    or report['seed'] != seed or report['episodes_target'] != 8192
                    or report['status'] not in ('complete', 'deadline', 'failed')
                    or not 0 <= report['episodes_completed'] <= 8192
                    or (report['status'] == 'complete' and report['episodes_completed'] != 8192)
                    or not set(report['validations']).issubset(map(str, CHECKPOINTS))):
                raise ValueError('only terminal final-version fit reports are accepted')
            if pins is not None and report['source_sha256'] != pins:
                raise ValueError('source versions differ across runs')
            pins = report['source_sha256']
            checkpoints = {}
            for count in sorted(map(int, report['validations'])):
                if count > report['episodes_completed']:
                    raise ValueError('validation exceeds completed training')
                summary, current_config = decide.validation(
                    run, count, algorithm, seed, report['validations'][str(count)])
                if config is not None and config != current_config:
                    raise ValueError('learner configuration differs')
                config = current_config
                checkpoints[str(count)] = summary
            rows.append({'algorithm': algorithm, 'training_seed': seed,
                         'status': report['status'], 'episodes_completed': report['episodes_completed'],
                         'episodes_target': report['episodes_target'], 'directory': str(run),
                         'report_sha256': decide.digest(run/'report.json'), 'checkpoints': checkpoints})
    return {'schema': 'learning-final-development-curve-v1', 'experiment': decide.EXPERIMENT,
            'validation_maps': decide.MAPS, 'runs': rows, 'method_means': common_means(rows),
            'source_sha256': pins, 'learner_config': config,
            'plot_code_sha256': decide.digest(__file__),
            'validation_checker_sha256': decide.digest(decide.__file__),
            'python': platform.python_version(),
            'plot_packages': {name: version(name) for name in
                              ('matplotlib', 'numpy', 'contourpy', 'cycler', 'fonttools',
                               'kiwisolver', 'packaging', 'pillow', 'pyparsing', 'python-dateutil', 'tzdata')},
            'limit': 'Reused development validation only. Thin lines retain every seed; means use only '
                     'checkpoints shared by all three seeds. Missing checkpoints are not interpolated '
                     'or treated as completed. No fresh-test reference scores are overlaid.'}


def plot(data, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter, StrMethodFormatter

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    names = ('learning-curve.png', 'learning-curve.svg', 'learning-curve-data.json',
             'learning-curve-manifest.json', 'plot-requirements.txt')
    if any((output/name).exists() for name in names):
        raise FileExistsError('plot output already exists')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 12,
                         'svg.hashsalt': 'junction-learning-final-development-v1',
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(16, 9), sharey=True)
    fig.subplots_adjust(left=.075, right=.965, bottom=.25, top=.76, wspace=.18)
    fig.text(.075, .92, 'Learning on the final frozen Traverse', fontsize=25, weight='bold', color='#152532')
    fig.text(.075, .865, 'Development validation — not the fresh final check', fontsize=17, color='#455664')
    fig.text(.075, .825, '32 reused maps per checkpoint · initialization seeds 17, 29 and 43', fontsize=13, color='#61717c')
    markers, styles = ('o', 's', '^'), ('-', '--', ':')
    colors = {'ppo': '#006b8f', 'replay': '#bf5900'}
    titles = {'ppo': 'PPO', 'replay': 'Replay (Double-DQN + PER)'}
    for axis, algorithm in zip(axes, decide.ALGORITHMS):
        members = sorted((r for r in data['runs'] if r['algorithm'] == algorithm), key=lambda r:r['training_seed'])
        for run, marker, style in zip(members, markers, styles):
            xs = sorted(map(int, run['checkpoints']))
            ys = [run['checkpoints'][str(x)]['mean_reward'] for x in xs]
            axis.plot(xs, ys, color='#8d989f', alpha=.8, linewidth=1.5, marker=marker,
                      markersize=5, linestyle=style, label=f"Seed {run['training_seed']}")
        means = data['method_means'][algorithm]
        axis.plot([r['episodes'] for r in means], [r['mean_reward'] for r in means],
                  color=colors[algorithm], linewidth=3.3, marker='o', markersize=7,
                  label='Mean of all 3 seeds', zorder=5)
        axis.set_title(titles[algorithm], loc='left', fontsize=18, weight='bold', pad=13)
        axis.set_xlim(-180, 8500)
        axis.set_ylim(0, .45)
        axis.set_xticks((0, 2048, 4096, 6144, 8192))
        axis.xaxis.set_major_formatter(StrMethodFormatter('{x:,.0f}'))
        axis.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
        axis.set_yticks((0, .1, .2, .3, .4))
        axis.set_xlabel('Training missions per initialization', labelpad=12)
        axis.grid(axis='y', color='#dfe5e8', linewidth=.8)
        axis.set_axisbelow(True)
        axis.tick_params(length=0, pad=8)
        axis.legend(loc='lower right', frameon=False, fontsize=11)
        last = means[-1]
        axis.annotate(f"{last['mean_reward']:.1%}",
                      xy=(last['episodes'], last['mean_reward']), xytext=(-8, 15),
                      textcoords='offset points', color=colors[algorithm], weight='bold',
                      fontsize=13, ha='right')
    axes[0].set_ylabel('Official normalized reward', labelpad=12)
    fig.text(.075, .15, 'Thin lines: individual seeds. Bold lines: means only at checkpoints available for all three seeds.',
             fontsize=12, color='#455664')
    incomplete = [r for r in data['runs'] if r['status'] != 'complete']
    note = ('All declared fit runs completed.' if not incomplete else
            '; '.join(f"{r['algorithm'].capitalize()} seed {r['training_seed']} stopped at {r['episodes_completed']:,} missions; "
                      f"last validated checkpoint {max(map(int,r['checkpoints'])):,}" for r in incomplete)+'.')
    fig.text(.075, .105, note, fontsize=12, color='#455664')
    partial = [algorithm.capitalize() for algorithm in decide.ALGORITHMS
               if 8192 not in {row['episodes'] for row in data['method_means'][algorithm]}]
    footer = 'No missing checkpoint is filled in.'
    if partial:
        footer += ' '+', '.join(partial)+' has no three-seed mean at 8,192 missions.'
    fig.text(.075, .06, footer, fontsize=12, color='#455664')
    fig.savefig(output/names[0], dpi=120, facecolor='white', metadata={'Software':'Matplotlib 3.10.7'})
    fig.savefig(output/names[1], facecolor='white', metadata={'Date':None, 'Creator':'Junction learning-final plot_results.py'})
    plt.close(fig)
    (output/names[2]).write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False)+'\n')
    (output/names[4]).write_text(''.join(f'{name}=={value}\n' for name,value in sorted(data['plot_packages'].items())))
    manifest = {'schema':'learning-final-development-figure-manifest-v1',
                'artifacts':{name:decide.digest(output/name) for name in (names[0],names[1],names[2],names[4])},
                'render_pixels':[1920,1080], 'plot_code_sha256':decide.digest(__file__),
                'reproduce':'python -m tools.learning_final.plot_results --runs RUNS --output NEW_FIGURES_DIRECTORY'}
    (output/names[3]).write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=plot(collect(args.runs),args.output)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
