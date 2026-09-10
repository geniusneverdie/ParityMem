#!/usr/bin/env python3
"""Post-hoc record comparisons over frozen inputs; no ParityMem or outcome imports."""
import json

def decode(value):
    if isinstance(value,str):
        try:return json.loads(value)
        except (ValueError,TypeError):pass
    return value

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def raw_equality(source,target):
    return canonical(source)!=canonical(target)

def local_schema(source,target):
    if not isinstance(target,dict) or set(target)!={'assistant_content','calls','results'}:return True
    if not isinstance(target['assistant_content'],str):return True
    if not isinstance(target['calls'],list) or not isinstance(target['results'],list):return True
    allowed={c['name'] for c in source['calls']}
    for call in target['calls']:
        if not isinstance(call,dict) or set(call)!={'id','name','arguments'}:return True
        if not isinstance(call['id'],str) or not call['id']:return True
        if not isinstance(call['name'],str) or call['name'] not in allowed:return True
        if not isinstance(decode(call['arguments']),dict):return True
    for result in target['results']:
        if not isinstance(result,dict) or set(result)!={'id','content'}:return True
        if not isinstance(result['id'],str) or not result['id']:return True
        if not isinstance(result['content'],(str,dict,list,int,float,bool)) and result['content'] is not None:return True
    return False

def generic_normalization(source,target):
    def norm(record):
        return {'assistant_content':record['assistant_content'],
            'calls':[{'name':c['name'],'arguments':decode(c['arguments'])} for c in record['calls']],
            'results':[{'content':decode(r['content'])} for r in record['results']]}
    return canonical(norm(source))!=canonical(norm(target))

METHODS={'Raw equality':raw_equality,'Strict schema':local_schema,'Generic normalization':generic_normalization}

def main():
    from pathlib import Path
    import argparse,hashlib
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=ap.parse_args();folder=args.root/'reproducibility/offline_baselines'
    rows=[json.loads(s) for s in (folder/'inputs.jsonl').read_text().splitlines() if s.strip()]
    output=[]
    for r in rows:
        if set(r)!={'cell_id','source','target'}:raise ValueError('Unexpected field in outcome-free input')
        for name,fn in METHODS.items():
            output.append({'cell_id':r['cell_id'],'method':name,'predicted_block':fn(r['source'],r['target'])})
    out=folder/'predictions.jsonl'
    out.write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in output))
    print(json.dumps({'decisions':len(output),'input_sha256':hashlib.sha256((folder/'inputs.jsonl').read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'study_type':'post_hoc_offline_record_comparison','model_calls':0}))
if __name__=='__main__':main()
