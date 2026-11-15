"""Plot the frozen, paired fresh-world comparison as a standalone figure."""

import json
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/planner-lab-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from .common import OUT, file_hash, utc, write


def main():
    report=json.loads((OUT/'final/summary.json').read_text()); selection=json.loads((OUT/'selection.json').read_text())
    names=[a['name'] for a in selection['arms']]
    labels={'reference':'Frozen reference','old_extra_trees':'Previous Extra Trees',
        'static_best':'Best fixed strategy','learned_extra_trees':'New Extra Trees',
        'learned_random_forest':'New Random Forest','learned_pooled_forest':'Pooled forest','learned_mlp':'Neural network (MLP)'}
    table=report['table']; primary=report['primary']
    colors={n:('#1266cc' if n==primary else '#8495a5') for n in names}; colors['reference']='#253648'
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':13,'axes.labelsize':11,
        'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False})
    fig,(left,right)=plt.subplots(1,2,figsize=(13,5.7),gridspec_kw={'width_ratios':[1.15,1]})
    fig.patch.set_facecolor('#ffffff'); fig.subplots_adjust(left=.19,right=.97,bottom=.24,top=.78,wspace=.27)
    y=np.arange(len(names)); values=[100*table[n]['mean'] for n in names]
    left.barh(y,values,color=[colors[n] for n in names],height=.58)
    left.set_yticks(y,[labels[n] for n in names]); left.invert_yaxis(); left.set_xlim(0,max(values)*1.27)
    left.set_xlabel('Mean mission score (%)'); left.set_title('Performance on 192 fresh worlds',loc='left',pad=16)
    left.set_axisbelow(True); left.grid(axis='x',alpha=.15)
    for i,n in enumerate(names):
        left.text(values[i]+.65,i,f"{values[i]:.2f}%",va='center',fontsize=10)
        left.text(left.get_xlim()[1]-.1,i,f"{table[n]['home_alive']}/192",va='center',ha='right',fontsize=9,color='#536476')
    left.text(1.0,1.02,'Home / alive',transform=left.transAxes,ha='right',fontsize=9,color='#536476')
    right.axvline(0,color='#8895a0',lw=1); right.axvline(1,color='#a6adb5',lw=1,ls='--')
    for i,n in enumerate(names):
        if n=='reference': continue
        t=table[n]; center=t['delta']*100
        lo,hi=[100*x for x in t['ci_family95']]; a,b=[100*x for x in t['ci95']]
        right.hlines(i,lo,hi,color=colors[n],lw=3,alpha=.25)
        right.hlines(i,a,b,color=colors[n],lw=2)
        right.plot(center,i,'o',color=colors[n],ms=6)
    right.set_yticks(y,['']*len(names)); right.set_ylim(left.get_ylim())
    right.set_xlabel('Gain over reference (percentage points)'); right.set_title('Paired uncertainty',loc='left',pad=16)
    right.tick_params(axis='y',length=0); right.grid(axis='x',alpha=.15)
    right.text(1.0,.98,'+1 point target',transform=right.get_xaxis_transform(),ha='center',va='top',fontsize=9,color='#6d7783')
    fig.text(.045,.93,'Can earlier strategy selection improve the reference?',fontsize=20,weight='bold',color='#253648')
    fig.text(.045,.865,'Four model families trained; two selected on validation; both controls kept frozen.',fontsize=11,color='#536476')
    verdict='Practical upgrade gate passed.' if report['confirmed'] else 'Practical upgrade gate did not pass.'
    fig.text(.045,.12,verdict+' Primary: '+labels[primary]+'.',fontsize=11,weight='bold',color='#253648')
    fig.text(.045,.069,'20,000 paired bootstrap draws. Dark intervals: 95%; pale intervals: 95% across four comparisons.\n'
        'Fresh worlds 572000–572191 were excluded from training and model selection.',fontsize=9,color='#536476',linespacing=1.5)
    paths=[]
    for extension in ('png','svg','pdf'):
        path=OUT/('fresh-comparison.'+extension); fig.savefig(path,dpi=180,facecolor=fig.get_facecolor())
        paths.append({'path':path.name,'sha256':file_hash(path)})
    plt.close(fig)
    write(OUT/'figure-receipt.json',{'created_utc':utc(),'matplotlib':matplotlib.__version__,
        'summary_sha256':file_hash(OUT/'final/summary.json'),'files':paths})
    print('Wrote PNG, SVG and PDF fresh comparison figures.')


if __name__=='__main__': main()
