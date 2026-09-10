#!/usr/bin/env python3
"""Recompute the original natural-matrix predictions from source projections."""
from pathlib import Path
import argparse,importlib.util,json

def run(root,out):
    p=root/'reproducibility/full_core/matrix_rule.py'
    spec=importlib.util.spec_from_file_location('frozen_matrix_rule',p);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=json.loads((root/'reproducibility/runtime_binding/natural_trace_eligibility.json').read_text())
    rows=[r for r in source['rows'] if r['eligibility']=='ELIGIBLE']
    profile={'SGLang':'0.5.6.post2','vLLM':'0.23.0'}
    if any(r['model_family'] not in {'Qwen','Llama','Mistral'} or profile.get(r['backend'])!=r['backend_version'] for r in rows):
        raise ValueError('Input is outside the original frozen matrix profile')
    predictions=[{'cell_id':r['cell_id'],**module.prediction(r['model_family'],r['backend'],r['natural_projection'])} for r in rows]
    out.mkdir(parents=True,exist_ok=True);p=out/'matrix_recomputed_predictions.jsonl'
    p.write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in predictions))
    return {'predictions':len(predictions),'output':str(p),'rule':'verbatim original source-specific prediction()','model_calls':0,'backend_calls':0}
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--out',type=Path)
    a=ap.parse_args();print(json.dumps(run(a.root,a.out or a.root/'reproduction_output'),indent=2))
