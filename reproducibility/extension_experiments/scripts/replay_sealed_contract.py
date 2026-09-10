"""Recompute sealed contract predictions without modifying the experiment receipts."""
from pathlib import Path
import json
from contract_adapter import predict
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'contract_test'
cases=[json.loads(s) for s in (folder/'cases.jsonl').read_text().splitlines() if s.strip()]
contracts=json.loads((folder/'contracts.json').read_text())
recomputed=[{'case_id':r['case_id'],'result':predict(r['trace'],contracts[r['contract_id']],r['alias'])} for r in cases]
saved={r['case_id']:r for s in (folder/'sealed_predictions.jsonl').read_text().splitlines() if (r:=json.loads(s))}
assert len(recomputed)==288
for r in recomputed:
 for field in ['verdict','severity','first_divergence','core_result','guard_prediction','serializer_capacity','contract_sha256']:
  assert r['result'][field]==saved[r['case_id']][field],(r['case_id'],field)
print(json.dumps({'ok':True,'sealed_predictions_recomputed':len(recomputed),'new_consumer_validation_calls':0,'new_model_calls':0,'original_receipts_modified':False}))
