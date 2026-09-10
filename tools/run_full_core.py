#!/usr/bin/env python3
"""Execute the original P0-P3 controlled-validation predictor on recorded fixtures."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys

def load_runner(root):
    core=root/'reproducibility/full_core'
    binding=json.loads((core/'binding_manifest.json').read_text())
    for item in binding['copied_files']:
        if '/vendor/' not in item['package_path'] and not item['package_path'].endswith('.py.txt'):
            continue
        if hashlib.sha256((root/item['package_path']).read_bytes()).hexdigest()!=item['sha256']:
            raise RuntimeError('Frozen source hash mismatch: '+item['package_path'])
    if hashlib.sha256((core/'runner.py').read_bytes()).hexdigest()!=binding['portable_runner_sha256']:
        raise RuntimeError('Portable runner hash mismatch')
    spec=importlib.util.spec_from_file_location('paritymem_frozen_runner',core/'runner.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    import paritymem.contract_ir.equivalence as eq
    if not Path(eq.__file__).resolve().is_relative_to((core/'vendor').resolve()):
        raise RuntimeError('Frozen vendor import isolation failed')
    return module

def run(root,out,demo=False):
    core=root/'reproducibility/full_core';runner=load_runner(root)
    rows=[json.loads(s) for s in (core/'holdout_inputs.jsonl').read_text().splitlines() if s.strip()]
    if demo:
        # Fixed illustrative selection from the original recorded inputs.
        wanted={'P1H-01-01','P1H-01-10','P1H-01-16','P1H-01-24'}
        rows=[r for r in rows if r['fixture_id'] in wanted]
    results=[]
    for fixture in rows:
        prediction=runner.predict(fixture)
        event=next((r for r in fixture['trace'] if r.get('path')==prediction['first_divergence']),None)
        results.append({'prediction':prediction,'source_link':{'integration_id':fixture['integration_id'],'normative_owner':fixture['ownership']['normative_owner'],'contract_schema':'P1_HOLDOUT_V1','trace_event':event}})
    out.mkdir(parents=True,exist_ok=True)
    path=out/('core_demo.jsonl' if demo else 'core_predictions.jsonl')
    path.write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in results))
    return {'fixtures':len(results),'output':str(path),'prediction_source':'executed frozen predict() and vendored P0-P3/identity functions','model_calls':0,'backend_calls':0}
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--out',type=Path);ap.add_argument('--demo',action='store_true')
    args=ap.parse_args();print(json.dumps(run(args.root,args.out or args.root/'reproduction_output',args.demo),indent=2))
