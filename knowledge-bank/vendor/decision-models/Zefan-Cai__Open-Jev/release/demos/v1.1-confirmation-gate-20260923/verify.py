#!/usr/bin/env python3
"""Verify this public replay package without model inference or private capture."""
import hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
canon=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
e=json.loads((ROOT/'evidence.json').read_text());raw=(ROOT/'source-records.jsonl').read_bytes().splitlines(keepends=True)
assert e['model']['name']=='Open-Jev-27B-v1.1'
assert e['model']['checkpoint_sha256']=='c49994563c3c4f04a99d9130203c4e526f4ae5086c84deec57698d18cb652e71'
assert e['model']['revision']=='28cf73067d5b337860bbef3c85b8b82ba8730956'
assert e['dataset']['revision']=='10ad6888333fa97f8c948192797bad3de3040802'
assert e['license']=='CC0-1.0' and len(e['cases'])==len(raw)==2
for case,line in zip(e['cases'],raw):
    record=case['record'];p=case['prediction'];provenance=case['source_provenance'];assert json.loads(line)==record
    assert hashlib.sha256(line).hexdigest()==provenance['public_raw_line_sha256']
    assert hashlib.sha256(canon(record).encode()).hexdigest()==p['row_sha256']==provenance['record_canonical_sha256']
    assert record['metadata']['provenance']['license']=='CC0-1.0' and not record['metadata']['provenance']['source_examples_imported']
    assert p['checkpoint_sha256']==e['model']['checkpoint_sha256'] and p['status']=='ok' and p['id']==record['id']
    assert len(record['options'])==len(p['probabilities'])==len(p['logits'])==7
    assert set(record['options'])==set(e['display_order'])==set(e['aliases'])
    assert all(math.isfinite(x) for x in p['logits']+p['probabilities']) and abs(sum(p['probabilities'])-1)<1e-12
    scaled=[x/e['model']['temperature'] for x in p['logits']];maximum=max(scaled);exp=[math.exp(x-maximum) for x in scaled]
    assert max(abs(a-b/sum(exp)) for a,b in zip(p['probabilities'],exp))<1e-12
    assert record['target']==p['target']
a,b=[c['record'] for c in e['cases']];changed=json.loads(json.dumps(a['state']));changed['candidates'][3]['facts']['actual_target']='record_B'
assert changed==b['state'] and a['question']==b['question'] and a['kind']==b['kind']
assert a['options']!=b['options'] and set(a['options'])==set(b['options'])
assert [c['record']['options'][max(range(7),key=c['prediction']['probabilities'].__getitem__)] for c in e['cases']]==['item_63','K11']
manifest=ROOT/'manifest.json'
if manifest.exists():
    for name,entry in json.loads(manifest.read_text())['files'].items():
        payload=(ROOT/name).read_bytes();assert len(payload)==entry['bytes'] and hashlib.sha256(payload).hexdigest()==entry['sha256'],name
print(json.dumps({'status':'passed','cases':2,'probabilities_verified':14,'source_records_exact':True,'model_identity_verified':True,'recorded_order_difference_preserved':True,'model_inference':False}))
