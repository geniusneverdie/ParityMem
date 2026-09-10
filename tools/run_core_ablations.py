#!/usr/bin/env python3
"""Post-hoc component interventions on the frozen 300-case controlled suite."""
from pathlib import Path
from copy import deepcopy
import argparse,json,types
from run_full_core import load_runner
VARIANTS=('Full','No pairing rejection','No history-closure rejection','P0/P1 only','Literal transport-ID pairing')

def predict_variant(runner,fixture,variant):
    if variant=='Full':return runner.predict(fixture)
    view=deepcopy(fixture);namespace=dict(runner.predict.__globals__)
    if variant in {'No pairing rejection','P0/P1 only','Literal transport-ID pairing'}:
        original=runner.evaluate_pairing
        def pairing(*args,**kwargs):
            out=original(*args,**kwargs)
            if variant=='Literal transport-ID pairing':
                out['pairing_preserving_closure']=out['pairing_preserving_closure'] and out['strict_transport_id_literal_preservation']
            else:out['pairing_preserving_closure']=True
            return out
        namespace['evaluate_pairing']=pairing
    if variant in {'No history-closure rejection','P0/P1 only'}:
        # Intervene on the decision input in a local copy; frozen records stay intact.
        view['history']['encoder_accepts_observed']=True
    if variant=='P0/P1 only':
        compare=runner.compare_contract_ir
        def projections(*args,**kwargs):
            for k in ['left_execution','right_execution','left_score','right_score']:kwargs[k]=None
            return compare(*args,**kwargs)
        namespace['compare_contract_ir']=projections
    fn=types.FunctionType(runner.predict.__code__,namespace,runner.predict.__name__,runner.predict.__defaults__,runner.predict.__closure__)
    result=fn(view);result['component_intervention']=variant
    return result

def run(root,out):
    runner=load_runner(root);core=root/'reproducibility/full_core'
    inputs=[json.loads(s) for s in (core/'holdout_inputs.jsonl').read_text().splitlines() if s.strip()]
    # Compute all decisions before opening the separate gold file.
    predictions=[{'variant':v,**predict_variant(runner,f,v)} for v in VARIANTS for f in inputs]
    out.mkdir(parents=True,exist_ok=True)
    (out/'core_ablation_predictions.jsonl').write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in predictions))
    gold={r['fixture_id']:r for s in (core/'holdout_gold.jsonl').read_text().splitlines() if (r:=json.loads(s))}
    safe=sum(not r['is_defect'] for r in gold.values());defects=len(gold)-safe;metrics=[]
    for variant in VARIANTS:
        rows=[r for r in predictions if r['variant']==variant]
        correct=sum(r['is_defect']==gold[r['fixture_id']]['is_defect'] for r in rows)
        fp=sum(r['is_defect'] and not gold[r['fixture_id']]['is_defect'] for r in rows)
        tp=sum(r['is_defect'] and gold[r['fixture_id']]['is_defect'] for r in rows)
        metrics.append({'variant':variant,'cells':len(rows),'outcome_correct':correct,'safe_false_alarms':fp,'safe_denominator':safe,'defects_detected':tp,'defect_denominator':defects,
                        'severity_label_agreement':sum(r['severity']==gold[r['fixture_id']]['severity'] for r in rows)})
    report={'kind':'new_post_hoc_controlled_component_interventions','input_cases':len(inputs),'prediction_rows':len(predictions),'rows':metrics,'model_calls':0,'backend_calls':0,'gold_read_after_prediction_generation':True,'scope':'Controlled P1 holdout only; distinct from the 354-cell F2 matrix and four-root aggregate tables. Interventions suppress one rejection condition, remove P2/P3 evidence, or require literal transport identity in the frozen predictor.'}
    (out/'core_ablation_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--out',type=Path)
    a=ap.parse_args();print(json.dumps(run(a.root,a.out or a.root/'reproduction_output'),indent=2))
