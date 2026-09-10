#!/usr/bin/env python3
"""Inspect frozen evidence or run a bounded, offline symbolic-code demonstration."""
from pathlib import Path
from collections import Counter
import argparse,csv,hashlib,json,re,statistics,sys

ROOT=Path(__file__).resolve().parents[1]
DEMO_IDS={'P1H-01-01','P1H-01-10','P1H-01-16','P1H-01-24'}

def require(condition,message):
    if not condition:raise ValueError(message)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def rows(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]

def verify_manifest(root):
    root=root.resolve();seen=set()
    for line in (root/'MANIFEST.sha256').read_text().splitlines():
        digest,rel=line.split('  ',1)
        require(re.fullmatch('[0-9a-f]{64}',digest) is not None,'Invalid digest')
        p=Path(rel)
        require(not p.is_absolute() and '..' not in p.parts and rel not in seen,'Invalid manifest path')
        seen.add(rel);target=root/p
        require(not target.is_symlink() and target.resolve().is_relative_to(root),'Unsafe manifest target')
        require(target.is_file(),'Missing file: '+rel)
        require(sha(target)==digest,'Hash mismatch: '+rel)
    require(bool(seen),'Empty manifest')
    return len(seen)

def canonical_hash(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def verify_records(root):
    with (root/'reproducibility/frozen_evidence/TABLE1_CELLWISE_354.csv').open() as f:
        all_rows=list(csv.DictReader(f))
    full=[r for r in all_rows if r['method'].startswith('Full')]
    require(len(full)==354 and len({r['cell_id'] for r in full})==354,'Matrix denominator')
    require(all(r['gold_block']==r['pred_block'] and r['gold_FD']==r['pred_FD'] for r in full),'Frozen matrix mismatch')
    safe=sum(r['gold_block']=='FALSE' for r in full);require(safe==295,'Safe-cell count')
    pairs=json.loads((root/'reproducibility/action_comparison/cross_backend_modal_results.json').read_text())['pairs']
    require(len(pairs)==len({p['pair_id'] for p in pairs})==36,'Action-pair denominator')
    equal=0
    for pair in pairs:
        hashes=[]
        for backend in ['sglang','vllm']:
            r=pair[backend];repeat=r['repeat_actions'];h=canonical_hash(r['modal_action'])
            require(len(repeat)==5 and len({v['repeat'] for v in repeat})==5,'Five repeats required')
            require(r['modal_count']==5 and h==r['modal_action_sha256'],'Stored modal hash/count')
            require(all(canonical_hash(v['action'])==h for v in repeat),'Within-backend stability')
            hashes.append(h)
        equal+=hashes[0]==hashes[1]
    require(equal==33,'Cross-backend agreement')
    folder=root/'reproducibility/extension_experiments/contract_test'
    pred={r['case_id']:r for r in rows(folder/'sealed_predictions.jsonl')}
    val={r['case_id']:r for r in rows(folder/'validation_results.jsonl')}
    require(len(pred)==len(val)==288 and pred.keys()==val.keys(),'Alias evaluations')
    primary={}
    for key,r in val.items():
        require(all(r[k]==pred[key][k] for k in ['verdict','severity','first_divergence']),'Adapter label mismatch')
        value=tuple(r[k] for k in ['verdict','severity','first_divergence'])
        require(primary.setdefault(r['condition_id'],value)==value,'Name-alias inconsistency')
    require(len(primary)==144 and sum(v[0]=='SAFE' for v in primary.values())==16,'Primary adapter conditions')
    timing=rows(root/'reproducibility/timing_records/original_e3/raw/E3_REAL_TRACE_TIMINGS.jsonl')
    latency=[r for r in timing if r['measurement_type']=='REAL_TRACE_LATENCY']
    decisions=Counter(r['input_id'] for r in latency)
    require(len(latency)==7200 and len(decisions)==72 and set(decisions.values())=={100},'Timing units')
    require(all(r['status']=='PASS' and r['expected_frozen_verdict']==r['final_verdict'] for r in latency),'Recorded timing verdict')
    return {'matrix_cells':354,'safe_cells':safe,'blocked_cells':354-safe,
            'adapter_primary_conditions':144,'adapter_safe':16,'adapter_defective':128,
            'action_pairs':36,'same_action':equal,'stable_action_differences':36-equal,
            'timing_decisions':72,'timed_repetitions':7200,
            'recorded_median_latency_ms':statistics.median(r['T_total_ns'] for r in latency)/1e6,
            'interpretation':'Read-only checks of existing records; denominators are not pooled.'}

def run_demo(root,out):
    # Check the source bindings before importing the original symbolic predictor.
    verify_manifest(root)
    out=out.resolve()
    require(not out.exists(),'Output directory already exists; select a new directory')
    from run_full_core import load_runner
    runner=load_runner(root)
    require(Path(runner.__file__).resolve()==(root/'reproducibility/full_core/runner.py').resolve(),'Unexpected runner')
    fixtures=[r for r in rows(root/'reproducibility/full_core/holdout_inputs.jsonl') if r['fixture_id'] in DEMO_IDS]
    require(len(fixtures)==4,'Four frozen demonstration fixtures required')
    computed=[runner.predict(r) for r in fixtures]
    # Read saved predictions only after the demonstration decisions have been computed.
    saved={r['fixture_id']:r for r in rows(root/'reproducibility/full_core/holdout_predictions.jsonl')}
    require(all(r==saved[r['fixture_id']] for r in computed),'Demo differs from frozen predictions')
    out.mkdir(parents=True,exist_ok=False)
    with (out/'predictions.jsonl').open('x') as stream:
        for r in computed:stream.write(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n')
    report={'scope':'Four existing fixtures; code smoke check, not a new scientific sample',
            'frozen_fixtures':4,'match_frozen_predictions':True,
            'decisions':[{'fixture_id':r['fixture_id'],'classification':r['classification'],'severity':r['severity'],'first_divergence':r['first_divergence']} for r in computed],
            'NEW_MODEL_CALLS':0,'NEW_BACKEND_CALLS':0,'NEW_GPU_RUNS':0,'NEW_TIMING_MEASUREMENTS':0}
    (out/'DEMO_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('verify',help='Check package hashes and existing recorded endpoints; run no predictions')
    demo=sub.add_parser('demo',help='Execute the frozen symbolic core on four existing recorded inputs')
    demo.add_argument('--output',type=Path,default=ROOT/'outputs/demo')
    args=parser.parse_args(argv)
    try:
        if args.command=='verify':
            result={'status':'PASS','files_verified':verify_manifest(ROOT),'record_checks':verify_records(ROOT),
                    'NEW_MODEL_CALLS':0,'NEW_BACKEND_CALLS':0,'NEW_GPU_RUNS':0,'NEW_TIMING_MEASUREMENTS':0}
        else:result=run_demo(ROOT,args.output)
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as exc:
        print(str(exc),file=sys.stderr);return 1
    print(json.dumps(result,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
