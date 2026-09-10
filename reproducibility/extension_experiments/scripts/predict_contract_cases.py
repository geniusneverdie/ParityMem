from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
from contract_adapter import predict
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'contract_test'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
seal=json.loads((folder/'DESIGN_SEAL.json').read_text())
for rel,digest in seal['predictor_files'].items():assert sha(ROOT/rel)==digest,rel
cases=[json.loads(s) for s in (folder/'cases.jsonl').read_text().splitlines() if s.strip()]
contracts=json.loads((folder/'contracts.json').read_text());output=[]
for case in cases:
 result=predict(case['trace'],contracts[case['contract_id']],case['alias'])
 output.append({'case_id':case['case_id'],'condition_id':case['condition_id'],'trace_id':case['trace']['trace_id'],'contract_id':case['contract_id'],'alias':case['alias'],**result})
p=folder/'sealed_predictions.jsonl';p.write_text(''.join(json.dumps(r,sort_keys=True,ensure_ascii=False)+'\n' for r in output))
receipt={'created_utc':datetime.now(timezone.utc).isoformat(),'prediction_count':len(output),'prediction_sha256':sha(p),'cases_sha256':sha(folder/'cases.jsonl'),'contracts_sha256':sha(folder/'contracts.json'),'validation_output_exists':(folder/'validation_results.jsonl').exists(),'design_seal_sha256':sha(folder/'DESIGN_SEAL.json'),'new_model_calls':0}
assert not receipt['validation_output_exists']
(folder/'PREDICTION_SEAL.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
