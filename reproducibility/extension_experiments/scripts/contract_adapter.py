"""New declarative consumer adapter around the unchanged controlled P0-P3 core.
The adapter uses source-declared guards and serializer capacity, never template outcomes.
"""
from pathlib import Path
from copy import deepcopy
import importlib.util,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('frozen_contract_core',ROOT/'contract_test/frozen_core/runner.py')
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)

def predict(trace,contract,alias):
    calls=trace['calls'];n=len(calls)
    if contract['guard_kind']=='id_length':
        accepted=all(len(c['id'])==contract['guard_value'] for c in calls)
        observed=[len(c['id']) for c in calls]
    elif contract['guard_kind']=='call_count':
        accepted=n==contract['guard_value'];observed=n
    else:raise ValueError('Unsupported declared predicate')
    limit=contract['serialized_call_limit']
    visible=calls if limit is None else calls[:limit]
    sem={'assistant_text':'','history_roles':['user','assistant','tool'],'observation':{'stage':'next-history'},'calls':[{'name':c['name'],'arguments':c['arguments']} for c in calls]}
    projected=deepcopy(sem)
    if accepted:projected['calls']=[{'name':c['name'],'arguments':c['arguments']} for c in visible]
    pairing=[{'name':c['name'],'arguments':c['arguments'],'transport_call_id':c['id'],'execution_call_id':c['id'],'model_visible_call_id':c['id'],'validator_provenance':'DECLARED_SOURCE_CONTRACT'} for c in calls]
    events=[]
    if not accepted:events.append({'path':'consumer.guard.'+contract['guard_kind'],'semantic_relevant':True,'normative':contract['guard_value'],'observed':observed})
    if accepted and len(visible)!=n:events.append({'path':'consumer.serialization.tool_calls','semantic_relevant':True,'normative':sem['calls'],'observed':projected['calls']})
    fixture={'fixture_id':trace['trace_id'],'integration_id':alias,'official':{'representation':trace,'semantics':sem,'execution':None,'score':None},'observed':{'representation':trace,'semantics':projected,'execution':None,'score':None},'pairing':{'original_calls':pairing,'history_calls':pairing,'history_results':[{'paired_call_index':i,'result':{'status':'OK'}} for i in range(n)],'execution_order':list(range(n)),'scorer_order':list(range(n))},'history':{'runtime_reachable':True,'encoder_accepts_observed':accepted},'ownership':{'normative_owner':contract['owner'],'official_validation':None},'trace':events}
    result=core.predict(fixture)
    return {'verdict':'DEFECT' if result['is_defect'] else 'SAFE','severity':result['severity'],'first_divergence':result['first_divergence'],'core_result':result,'guard_prediction':accepted,'serializer_capacity':limit,'contract_sha256':contract['template_sha256']}
