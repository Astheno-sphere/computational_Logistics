"""Independent stdlib audit of frozen drone pilot archives; no model/evaluator imports."""
import argparse,base64,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path


def enc(x,sort=False):return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=sort,allow_nan=False).encode()
def sha(x):return hashlib.sha256(x).hexdigest()
def rank(x):return sha(enc(x,True))
def read(p):return json.loads(p.read_bytes())
def lines(p):return [json.loads(x) for x in p.read_bytes().splitlines() if x.strip()]
def same(a,b):
 if isinstance(a,dict):return isinstance(b,dict) and a.keys()==b.keys() and all(same(v,b[k]) for k,v in a.items())
 if isinstance(a,list):return isinstance(b,list) and len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
 if type(a) in (float,int) and type(b) in (float,int):return math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-8)
 return a==b

def identity(c):return {'case_id':c['id'],'group_id':c['group_id'],'split':c['split'],'variant':c['variant'],'request_sha256':sha(enc(c['request']))}

def audit(archive,source):
 errors=[];checks=0
 def check(ok,msg):
  nonlocal checks
  checks+=1
  if not ok:errors.append(msg)
 raw=source.read_bytes();all_cases=lines(source);source_manifest=source.with_name('manifest.json').read_bytes()
 manifest=read(archive/'suite-manifest-final.json')
 check(manifest['status'] in ('complete','complete_with_measurement_failures') and manifest['current_phase']=='finished','suite incomplete')
 check(manifest['hostname']=='kwade5342000001' and manifest['physical_gpu']==3,'allocation')
 check(manifest['resource_policy']['allowed_gpu_indices']==[0,1,2,3],'resource policy')
 check(manifest['configuration']['measurements']==['drone'],'measurement scope')
 check(set(manifest['models'])==set(manifest['configuration']['models'])=={'2b','9b','27b'},'complete three-model roster')
 check(sha(source_manifest)=='6eefc11815640ad9ded3d6846fdc4483b8c867d270e8852835e8d0cb7cb7066a','frozen source manifest')
 sm=json.loads(source_manifest);check(sm['cases_sha256']==sha(raw) and sm['case_count']==len(all_cases),'frozen cases')
 pools={s:defaultdict(list) for s in ('test','ood')}
 for c in all_cases:
  if c['split'] in pools:pools[c['split']][c['group_id']].append(c)
 ranked={s:[sorted(pools[s][g],key=lambda c:rank([42,c['id']]))[:3] for g in sorted(pools[s],key=lambda g:rank([42,s,g]))[:20]] for s in pools}
 selected=[ranked[s][p][v] for v in range(3) for p in range(20) for s in pools if v<len(ranked[s][p])]
 ids=[identity(c) for c in selected];selection_sha=rank(ids);check(len(selected)==120,'expected120')
 models={};request_hashes=set();reference_hashes=set()
 for tag,m in manifest['models'].items():
  folder=archive/tag/'drone';selection=read(folder/'selection.json');report=read(folder/'report.json')
  requests=lines(folder/'requests.jsonl');refs=lines(folder/'references.jsonl');outcomes=lines(folder/'outcomes.jsonl')
  request_hashes.add(sha((folder/'requests.jsonl').read_bytes()));reference_hashes.add(sha((folder/'references.jsonl').read_bytes()))
  check(selection['cases']==ids and selection['selection_sha256']==selection_sha,tag+' selection')
  check(selection['source_sha256']==sha(raw) and selection['source_manifest_sha256']==sha(source_manifest),tag+' source identity')
  check((folder/'source-manifest.json').read_bytes()==source_manifest,tag+' manifest copy')
  check(len(requests)==len(refs)==len(outcomes)==len(selected),tag+' row counts')
  check(report['complete'] and report['pending_cases']==0 and report['attempted_cases']==120 and report['completed_attempts']==120,tag+' completion')
  check(m['measurements']['drone']['exit_code']==int(any(o['status']!='ok' for o in outcomes)) and m['gpu_after_shutdown']['compute_processes']==[],tag+' exit and clean shutdown')
  check(m['gpu_loaded']['uuid']==manifest['child_cuda_visible_devices'],tag+' GPU UUID')
  expected=m['expected_identity'];calc=[]
  revisions={'2b':'15852e8c16360a2fea060d615a32b45270f8a8fc','9b':'c202236235762e1c871ad0ccb60c8ee5ba337b9a','27b':'1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0'}
  names={'2b':'Qwen/Qwen3.5-2B','9b':'Qwen/Qwen3.5-9B','27b':'Qwen/Qwen3.8-27B'}
  check(expected['model']==names[tag] and expected['base_revision']==revisions[tag] and expected['method']=='lora_decision_head' and expected['code_commit']==manifest['code_commit'],tag+' pinned model and code')
  for c,q,ref,o in zip(selected,requests,refs,outcomes):
   label=tag+'/'+c['id']; ident=identity(c)
   for obj in (q,ref,o):check(all(obj.get(k)==v for k,v in ident.items()),label+' row identity')
   body=enc({'model':'open-jev',**c['request']})
   check(q['request_json'].encode()==body and q['request_body_sha256']==sha(body)==o['request_body_sha256'],label+' wire request')
   check(ref['answers']==c['answers'] and ref['derivation']==c['derivation'],label+' references')
   wire=base64.b64decode(o['response_body_base64'],validate=True);check(sha(wire)==o['response_body_sha256'],label+' raw response hash')
   result={'split':c['split'],'forced':len(c['request']['questions']['maneuver']['criteria'])==1,'gold':c['answers'],'valid':o['status']=='ok'}
   if o['status']=='ok':
    check(o['http_status']==200 and o['transport_error'] is None,label+' successful HTTP transport')
    response=json.loads(wire);check(response==o['response'],label+' raw response JSON')
    actual={'model':response['model'],**{k:response['metadata'].get(k) for k in expected if k!='model'}}
    check(actual==expected and o['service_identity']==expected,label+' scorer identity')
    a=response['answers'];check(set(a)=={'maneuver','risk','target_truly_lost'},label+' heads')
    fields={'maneuver':{'type','choice','probabilities','confidence'},'risk':{'type','score','probabilities','confidence','legend'},'target_truly_lost':{'type','noul'}}
    check(all(set(a[k])==v for k,v in fields.items()),label+' complete typed fields')
    legal=list(c['request']['questions']['maneuver']['criteria']);check(response['metadata']['candidate_sequences']==len(legal)+4,label+' sequence count')
    for key,keys,kind in [('maneuver',legal,'choice'),('risk',['0','1','2'],'score')]:
     x=a[key];check(x['type']==kind and set(x['probabilities'])==set(keys),label+' type and candidates')
     p=[x['probabilities'][k] for k in keys];check(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in p) and abs(sum(p)-1)<=2e-6,label+' simplex')
     z=[v/sum(p) for v in p];mode=max(range(len(z)),key=z.__getitem__)
     if kind=='choice':
      confidence=1. if len(z)==1 else (max(z)-1/len(z))/(1-1/len(z));check(x['choice'] in keys and p[keys.index(x['choice'])]==max(p),label+' maximal action')
     else:
      center=(len(z)-1)/2;ud=sum(abs(i-center) for i in range(len(z)))/len(z);confidence=max(0.,1.-sum(v*abs(i-mode) for i,v in enumerate(z))/ud)
      check(type(x['score']) in (int,float) and math.isfinite(x['score']) and 0<=x['score']<=2 and math.isclose(x['score'],sum(i*v for i,v in enumerate(z)),abs_tol=1e-6),label+' expected Score')
      check(x['legend']==dict(zip(keys,c['request']['questions']['risk']['criteria'])),label+' legend')
     check(type(x['confidence']) in (int,float) and math.isfinite(x['confidence']) and 0<=x['confidence']<=1 and math.isclose(x['confidence'],confidence,abs_tol=1e-6),label+' confidence')
    p=a['target_truly_lost']['noul'];check(type(p) in (int,float) and 0<=p<=1 and a['target_truly_lost']['type']=='noul',label+' Noul')
    risk=max(['0','1','2'],key=lambda k:a['risk']['probabilities'][k]);lost=p>=.5;g=c['answers']
    decision={'maneuver':a['maneuver']['choice'],'risk_level':risk,'target_truly_lost':lost}
    correct={'forced_maneuver' if result['forced'] else 'maneuver':int(decision['maneuver']==g['maneuver']),'risk_level':int(risk==g['risk']),'target_loss':int(lost==(g['target_truly_lost']=='true'))};correct['complete_decision']=int(all(correct.values()))
    err=a['risk']['score']-int(g['risk']);pe={'risk_brier':sum((v-int(k==g['risk']))**2 for k,v in a['risk']['probabilities'].items()),'risk_scalar_absolute_error':abs(err),'risk_scalar_squared_error':err**2,'target_loss_brier':(p-int(g['target_truly_lost']=='true'))**2}
    check(o['correct']==correct and o['decision']==decision and same(o['probability_errors'],pe),label+' independently rescored')
    result.update(correct=correct,probability_errors=pe,risk_probs=a['risk']['probabilities'])
   calc.append(result)
  metrics={}
  for split,rows,r in [('overall',calc,report['overall'])]+[(s,[x for x in calc if x['split']==s],report['by_split'][s]) for s in ('test','ood')]:
   totals=Counter(maneuver=sum(not x['forced'] for x in rows),forced_maneuver=sum(x['forced'] for x in rows),risk_level=len(rows),target_loss=len(rows),complete_decision=len(rows));correct=Counter();sums=Counter();dist=Counter();valid=0
   for x in rows:
    if x['valid']:valid+=1;correct.update(x['correct']);sums.update(x['probability_errors']);dist.update(x['risk_probs'])
   expected_metrics={k:{'correct':correct[k],'total':v,'accuracy':correct[k]/v if v else None} for k,v in totals.items()}
   check(same(r['metrics'],expected_metrics),tag+'/'+split+' aggregate accuracy')
   pm={'valid_cases':valid,'selected_cases':len(rows),'coverage':valid/len(rows) if rows else None,**{k:sums[k]/valid if valid else None for k in ('risk_brier','risk_scalar_absolute_error','risk_scalar_squared_error','target_loss_brier')},'risk_mean_probabilities':{str(i):dist[str(i)]/valid if valid else None for i in range(3)}}
   check(same(r['probability_metrics_valid_only'],pm),tag+'/'+split+' probability errors')
   baseline=sum(x['gold']=={'maneuver':'brake','risk':'2','target_truly_lost':'false'} for x in rows)
   metrics[split]={'metrics':expected_metrics,'probability_metrics_valid_only':pm,'constant_brake_risk2_lossfalse':{'correct':baseline,'total':len(rows)}}
  check(report['error_cases']==sum(not x['valid'] for x in calc),tag+' errors')
  models[tag]=metrics
 check(len(request_hashes)==len(reference_hashes)==1,'same requests and references across models')
 return {'status':'passed' if not errors else 'failed','checks':checks,'errors':errors,'selection_sha256':selection_sha,'source_sha256':sha(raw),'source_manifest_sha256':sha(source_manifest),'suite_manifest_sha256':sha((archive/'suite-manifest-final.json').read_bytes()),'models':models,'scope':'Independent request/raw-response/identity/metric audit; frozen source references are not independently relabeled here. Constant brake/risk2/lossfalse fixed before model requests; no flight or closed-loop competence claim.'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();result=audit(a.archive,a.source);result['audit_script_sha256']=sha(Path(__file__).read_bytes());a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'checks':result['checks'],'errors':result['errors']}));raise SystemExit(bool(result['errors']))
