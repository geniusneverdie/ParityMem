from pathlib import Path
from collections import Counter,defaultdict
import json,hashlib,itertools
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'contract_test'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
seal=json.loads((folder/'PREDICTION_SEAL.json').read_text());receipt=json.loads((folder/'VALIDATION_RECEIPT.json').read_text());design=json.loads((folder/'DESIGN_SEAL.json').read_text())
assert sha(folder/'sealed_predictions.jsonl')==seal['prediction_sha256'];assert sha(folder/'cases.jsonl')==seal['cases_sha256'];assert sha(folder/'contracts.json')==seal['contracts_sha256']
assert sha(folder/'DESIGN_SEAL.json')==seal['design_seal_sha256'];assert seal['created_utc']<receipt['created_utc'];assert receipt['prediction_file_read_by_validator'] is False
for rel,digest in design['predictor_files'].items():assert sha(ROOT/rel)==digest,rel
assert sha(ROOT/'scripts/validate_contract_cases.py')==design['validation_program_sha256']
read=lambda p:[json.loads(s) for s in p.read_text().splitlines() if s.strip()]
pred=read(folder/'sealed_predictions.jsonl');gold={r['case_id']:r for r in read(folder/'validation_results.jsonl')}
assert len(pred)==len(gold)==288 and len({r['case_id'] for r in pred})==288
primary=[r for r in pred if r['alias']=='consumer_alpha'];safe=[r for r in primary if gold[r['case_id']]['verdict']=='SAFE'];defects=[r for r in primary if gold[r['case_id']]['verdict']=='DEFECT']
by_condition=defaultdict(list)
for r in pred:by_condition[r['condition_id']].append(r)
fields=['verdict','severity','first_divergence']
invariance=sum(len(rs)==2 and all(rs[0][k]==rs[1][k] for k in fields) for rs in by_condition.values())
by_trace=defaultdict(list)
for r in primary:by_trace[r['trace_id']].append(r)
contrasts=[]
for tid,rs in by_trace.items():
 for a,b in itertools.combinations(rs,2):
  ga,gb=gold[a['case_id']],gold[b['case_id']]
  changed=ga['severity']!=gb['severity'] or ga['verdict']!=gb['verdict']
  if changed:contrasts.append({'trace_id':tid,'contract_a':a['contract_id'],'contract_b':b['contract_id'],'correct':all(a[k]==ga[k] and b[k]==gb[k] for k in fields)})
summary={'primary_semantic_conditions':len(primary),'unique_traces':len(by_trace),'total_alias_evaluations':len(pred),'gold_severity_counts':dict(Counter(gold[r['case_id']]['severity'] for r in primary)),
 'outcome_agreement':sum(r['verdict']==gold[r['case_id']]['verdict'] for r in primary),
 'severity_agreement':sum(r['severity']==gold[r['case_id']]['severity'] for r in primary),
 'first_divergence_agreement':sum(r['first_divergence']==gold[r['case_id']]['first_divergence'] for r in primary),
 'safe_false_alarms':sum(r['verdict']=='DEFECT' for r in safe),'safe_conditions':len(safe),'defect_recall':sum(r['verdict']=='DEFECT' for r in defects),'defect_conditions':len(defects),
 'name_invariance':{'correct':invariance,'total':len(by_condition)},'contract_change_contrasts':{'correct':sum(r['correct'] for r in contrasts),'total':len(contrasts)},
 'all_alias_evaluation_agreement':sum(all(r[k]==gold[r['case_id']][k] for k in fields) for r in pred),
 'prediction_seal_verified':True,'new_model_calls':0,'new_gpu_runs':0,
 'scope':'New declarative adapter plus unchanged controlled core, tested on source-grounded controlled template variants. Primary denominator is 144 conditions on 48 traces; name aliases are not extra independent cases. Pre-outcome sealing does not imply independent external double-blind design.'}
(folder/'CONTRACT_TEST_REPORT.json').write_text(json.dumps(summary,indent=2)+'\n');(folder/'contract_change_contrasts.json').write_text(json.dumps(contrasts,indent=2)+'\n');print(json.dumps(summary,indent=2))
