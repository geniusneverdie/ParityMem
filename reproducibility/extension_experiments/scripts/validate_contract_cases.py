from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,time
from transformers import AutoTokenizer
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'contract_test'
assert (folder/'PREDICTION_SEAL.json').is_file()
contracts=json.loads((folder/'contracts.json').read_text());cases=[json.loads(s) for s in (folder/'cases.jsonl').read_text().splitlines() if s.strip()]
paths={'Mistral':Path('/data9/amx/fourth/paritymem/runs/paper_p2_r1/mistral_exact_snapshot'),'Llama':Path('/data5/hanwen/llm_file/Meta-Llama-3.1-8B-Instruct')}
tokenizers={k:AutoTokenizer.from_pretrained(p,local_files_only=True,trust_remote_code=False) for k,p in paths.items()}
tools=[{'type':'function','function':{'name':'probe','description':'Record an opaque marker.','parameters':{'type':'object','properties':{'marker':{'type':'string'}},'required':['marker']}}}]
output=[];cache={};started=time.monotonic()
for case in cases:
    contract=contracts[case['contract_id']];trace=case['trace'];template=(ROOT/contract['template_file']).read_text()
    assert hashlib.sha256(template.encode()).hexdigest()==contract['template_sha256']
    calls=[{'id':c['id'],'type':'function','function':{'name':c['name'],'arguments':c['arguments']}} for c in trace['calls']]
    messages=[{'role':'user','content':'Continue after these tool results.'},{'role':'assistant','content':'','tool_calls':calls}]+[{'role':'tool','tool_call_id':c['id'],'content':'OK'} for c in calls]
    rendered=None;error=None
    try:rendered=tokenizers[contract['family']].apply_chat_template(messages,tools=tools,chat_template=template,tokenize=False,add_generation_prompt=True)
    except Exception as e:error={'type':type(e).__name__,'message':str(e)}
    if error:
        expected_message='Tool call IDs should be alphanumeric strings with length 9!' if contract['family']=='Mistral' else 'This model only supports single tool-calls at once!'
        if error['message']!=expected_message:raise RuntimeError('Unexpected validation error: '+str(error))
        verdict='DEFECT';severity='R3';fd='consumer.guard.'+contract['guard_kind'];missing=[]
    else:
        missing=[c['arguments']['marker'] for c in trace['calls'] if c['arguments']['marker'] not in rendered]
        verdict='DEFECT' if missing else 'SAFE';severity='R2' if missing else 'R0';fd='consumer.serialization.tool_calls' if missing else 'NONE'
    output.append({'case_id':case['case_id'],'condition_id':case['condition_id'],'trace_id':trace['trace_id'],'contract_id':case['contract_id'],'alias':case['alias'],'verdict':verdict,'severity':severity,'first_divergence':fd,'accepted':rendered is not None,'missing_argument_markers':missing,'error':error,'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest() if rendered else None})
    if len(output)%72==0:print(json.dumps({'validated':len(output)}),flush=True)
p=folder/'validation_results.jsonl';p.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in output))
(folder/'VALIDATION_RECEIPT.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'evaluations':len(output),'prediction_file_read_by_validator':False,'validation_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'wall_seconds':time.monotonic()-started,'model_calls':0},indent=2)+'\n')
print('Template validation complete',len(output),flush=True)
