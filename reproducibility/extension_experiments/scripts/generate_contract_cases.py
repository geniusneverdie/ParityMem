from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,random,secrets
ROOT=Path(__file__).resolve().parents[1];folder=ROOT/'contract_test'
seed=secrets.token_hex(16);rng=random.Random(int(seed,16));contracts={};templates=folder/'templates';templates.mkdir()
for family,values in [('Mistral',[6,9,12]),('Llama',[1,2,3])]:
    original=(folder/f'{family}_original.jinja').read_text()
    for n in values:
        if family=='Mistral':
            needle='|length != 9';assert original.count(needle)==2
            template=original.replace(needle,f'|length != {n}')
            kind='id_length';capacity=None
        else:
            needle='message.tool_calls|length == 1';assert original.count(needle)==1
            assert 'message.tool_calls[0].function' in original
            template=original.replace(needle,f'message.tool_calls|length == {n}')
            kind='call_count';capacity=1
        cid=f'{family}_{n}';p=templates/f'{cid}.jinja';p.write_text(template)
        contracts[cid]={'family':family,'guard_kind':kind,'guard_value':n,'serialized_call_limit':capacity,'owner':'released-template controlled copy','template_file':str(p.relative_to(ROOT)),'template_sha256':hashlib.sha256(template.encode()).hexdigest(),'source_template_sha256':hashlib.sha256(original.encode()).hexdigest(),'guard_replacements':2 if family=='Mistral' else 1}
cases=[];traces=[]
for family,levels in [('Mistral',range(5,14)),('Llama',[1,2,3])]:
    for level in levels:
        for repeat in range(4):
            tid=f'{family}_trace_{level}_{repeat}';ncall=1 if family=='Mistral' else level;length=level if family=='Mistral' else 9
            calls=[]
            for j in range(ncall):
                identity=''.join(rng.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(length))
                calls.append({'id':identity,'name':'probe','arguments':{'marker':'ARG_'+secrets.token_hex(8)+'_'+str(j)}})
            trace={'trace_id':tid,'family':family,'calls':calls};traces.append(trace)
            for cid,c in contracts.items():
                if c['family']!=family:continue
                condition=tid+'__'+cid
                for alias in ['consumer_alpha','consumer_beta']:
                    cases.append({'case_id':condition+'__'+alias,'condition_id':condition,'contract_id':cid,'alias':alias,'trace':trace})
assert len(traces)==48 and len(cases)==288 and len({x['condition_id'] for x in cases})==144
(folder/'contracts.json').write_text(json.dumps(contracts,indent=2)+'\n')
(folder/'cases.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in cases))
(folder/'GENERATION_RECORD.json').write_text(json.dumps({'created_utc':datetime.now(timezone.utc).isoformat(),'seed_for_ID_generation':seed,'marker_values_recorded_in_cases':True,'unique_traces':48,'semantic_conditions':144,'alias_evaluations':288,'outcome_labels_generated':False},indent=2)+'\n')
print('Generated 48 traces, 144 semantic conditions, 288 alias evaluations')
