"""Render the frozen final comparison from its audited complete analysis only."""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(analysis_path, output):
    analysis_path, output = Path(analysis_path), Path(output)
    data = json.loads(analysis_path.read_text())
    primary = 'ensemble-all-rho090'
    assert data['stage'] == 'final' and set(data['primary_success']) == {primary}
    assert len(data['artifacts']) == 2560
    groups = data['summary']
    assert all(x['maps'] == 256 for x in groups.values())
    output.mkdir(parents=True, exist_ok=False)
    ids = ['greedy', 'ensemble-all-rho000', primary, 'beam']
    labels = ['Greedy', 'Six-policy rank ensemble', 'Ensemble + greedy filter', 'Frozen reference']
    values = [100 * groups[g]['mean_reward'] for g in ids]
    selected = groups[primary]
    gain = 100 * selected['vs_greedy']['mean']
    low, high = [100 * x for x in selected['vs_greedy']['bootstrap_95_percentile']]
    passed = data['primary_success'][primary]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 15,
                         'svg.hashsalt': 'junction-hybrid-final-20261115'})
    fig, (left, right) = plt.subplots(1, 2, figsize=(16, 9), gridspec_kw={'width_ratios': [1.4, 1]})
    fig.subplots_adjust(left=.22, right=.96, top=.76, bottom=.27, wspace=.42)
    fig.patch.set_facecolor('#fafaf7')
    for ax in (left, right):
        ax.set_facecolor('#fafaf7')
        ax.spines[['top', 'right', 'left']].set_visible(False)
        ax.set_axisbelow(True)
    colors = ['#94a3b8', '#b8c2cf', '#2563eb', '#334155']
    left.barh(range(4), values, color=colors, height=.58)
    left.set_yticks(range(4), labels)
    left.invert_yaxis()
    left.set_xlim(0, max(values) + 9)
    left.set_xlabel('Mean mission reward (%)', labelpad=15)
    left.grid(axis='x', color='#dfe3e6', linewidth=.8)
    left.tick_params(axis='y', length=0, pad=12)
    for i, value in enumerate(values):
        left.text(value + .9, i, f'{value:.2f}%', va='center', fontsize=15, fontweight='bold')
    right.axvline(0, color='#64748b', linewidth=1.2)
    right.axvline(1, color='#b45309', linestyle='--', linewidth=1.3)
    right.errorbar(gain, 0, xerr=[[gain-low], [high-gain]], fmt='o', color='#2563eb',
                   capsize=9, markersize=10, linewidth=2.5)
    right.set_xlim(min(low-.35, -.35), max(high+.35, 1.35))
    right.set_ylim(-1, 1)
    right.set_yticks([])
    right.grid(axis='x', color='#dfe3e6', linewidth=.8)
    right.set_title('Paired gain over greedy', fontsize=17, pad=28)
    right.set_xlabel('Percentage points', labelpad=15)
    right.text(.5, .24, f'{gain:+.2f} pp\n95% interval [{low:+.2f}, {high:+.2f}]',
               transform=right.transAxes, ha='center', va='center', fontsize=16)
    right.text(1, .73, 'Required gain: +1 pp', ha='center', fontsize=12, color='#92400e')
    fig.text(.08, .92, 'Frozen hybrid comparison', fontsize=28, fontweight='bold', color='#172033')
    fig.text(.08, .865, '256 untouched worlds · same missions and scoring for every controller',
             fontsize=17, color='#475569')
    outcome = ('Predeclared improvement target met' if passed else
               'Small measured gain; below the +1-point target' if low > 0 and gain > 0 else
               'Predeclared improvement target not met')
    fig.text(.08, .15, outcome, fontsize=19, fontweight='bold', color='#172033')
    home_alive = round(selected['home_rate'] * selected['episodes'])
    fig.text(.08, .105,
             f'Selected hybrid: {home_alive}/{selected["episodes"]} home and alive · '
             f'{selected["deaths"]} deaths · {selected["invalid_calls"]} invalid calls',
             fontsize=14, color='#475569')
    fig.text(.08, .055, 'Existing trained weights; no new training. Paired 95% bootstrap interval uses 20,000 map resamples.',
             fontsize=12, color='#64748b')
    fig.savefig(output/'comparison.png', dpi=120, facecolor=fig.get_facecolor(), metadata={'Software': 'Matplotlib'})
    fig.savefig(output/'comparison.svg', facecolor=fig.get_facecolor(), metadata={'Date': None})
    svg = output/'comparison.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    plt.close(fig)
    provenance = {'analysis_sha256': hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
                  'stage': 'final', 'worlds': [612000, 612255], 'maps': 256,
                  'primary': primary, 'primary_success': passed,
                  'groups': {g: groups[g] for g in ids},
                  'figure_files': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(output.iterdir())}}
    (output/'comparison-data.json').write_text(json.dumps(provenance, sort_keys=True, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--analysis', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    render(args.analysis, args.output)
