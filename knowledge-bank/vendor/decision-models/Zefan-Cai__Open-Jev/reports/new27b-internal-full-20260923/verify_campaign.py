"""CPU-only independent full24 release audit; never imports the campaign/runtime.

Core verification is not publishable. The CLI additionally requires a complete,
immutable capture receipt and all six original process groups to have exited.
"""
import argparse
import hashlib
import importlib.util
import itertools
import math
from pathlib import Path
import sys

ARITHMETIC_PATH = Path(__file__).with_name('verify.py')
ARITHMETIC_ROLE = 'reports/new27b-internal-full-20260923/verify.py'
ARITHMETIC_SHA = hashlib.sha256(ARITHMETIC_PATH.read_bytes()).hexdigest()
_spec = importlib.util.spec_from_file_location('_full24_standalone_math', ARITHMETIC_PATH)
math_audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(math_audit)
require, canonical, object_hash = math_audit.require, math_audit.canonical, math_audit.object_hash
strict_json, file_hash = math_audit.strict_json, math_audit.file_hash
CAMPAIGN_SHA = '491a4ee96d1ef6509ead733daffdf2318f3bb43d9d5bf38715f2cd0be8a0a9d4'
COMMIT = '9eebd42de6137735fc5fd85b499aa1ffa256426d'
LAUNCHER_SHA = '82d4abac72291272aba963181ebd857569698d125640083a3c5878dc84c8013d'
PARTITION = 'remaining_global_indices[ordinal::group_count][rank::4]'
PRODUCTION = {**math_audit.PRODUCTION, 'campaign_sha256': CAMPAIGN_SHA,
              'campaign_commit': COMMIT, 'group_count': 6, 'imported_count': 4491,
              'remaining_count': 123296, 'fixture_count': 9,
              'launches_sha256': '5c51c046aa1f3af02e670af35187555a969fa3123e2b4944572f9c59d1253dc5',
              'package_manifest_sha256': '560103154df84553dfc3b4595a6d80c41d4a16fce149cd7fc520a3719c258e90',
              'fixture_sha256': '2787dcb7c825a06c7c9691846394fbe5230c7f8622397d85cb46768e452891a4'}
# Original formal controller, launcher and four CUDA workers, recorded while live.
PROCESS_PINS = {
 'n1_1_0': [(2080974,960330906),(2080985,960330964),(2081004,960331072),(2081005,960331072),(2081006,960331072),(2081007,960331072)],
 'n1_1_4': [(2080975,960330906),(2080986,960330965),(2081020,960331099),(2081021,960331099),(2081022,960331099),(2081023,960331099)],
 'n4_1_0_fullcachepin': [(2183740,960526253),(2183751,960526298),(2183770,960526446),(2183771,960526446),(2183772,960526446),(2183773,960526446)],
 'n4_1_4_fullcachepin': [(2183741,960526253),(2183750,960526298),(2183774,960526447),(2183775,960526447),(2183776,960526447),(2183777,960526447)],
 'n4_2_0_fullcachepin': [(2745556,960524814),(2745569,960524874),(2745601,960525008),(2745602,960525008),(2745603,960525008),(2745604,960525008)],
 'n4_2_4_fullcachepin': [(2745557,960524815),(2745568,960524873),(2745595,960525004),(2745596,960525005),(2745597,960525005),(2745598,960525005)],
}


def equal(actual, expected, message):
    require(canonical(actual) == canonical(expected), message)


def regular(root, name):
    relative = Path(name)
    require(not relative.is_absolute() and relative.parts and all(p not in ('..', '.') for p in relative.parts), 'Unsafe capture path')
    path = root / relative
    require(all(not (root / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)), 'Symlink in capture')
    require(path.is_file(), 'Missing capture file: ' + name)
    return path


def logits_equal(first, second):
    require(type(first.get('input_tokens')) is int and first['input_tokens'] > 0
            and type(second.get('input_tokens')) is int and first['input_tokens'] == second['input_tokens'], 'Probe token count differs')
    a, b = first['logits'], second['logits']
    require(isinstance(a, list) and isinstance(b, list) and a and len(a) == len(b)
            and all(type(v) in (int, float) and math.isfinite(v) for v in a + b), 'Invalid probe logits')
    error = max(abs(x-y) for x,y in zip(a,b))
    require(error <= .05 and max(range(len(a)), key=a.__getitem__) == max(range(len(b)), key=b.__getitem__), 'Probe logits/argmax differ')
    return error


def validate_row(row, expected, temperature):
    equal({k:row.get(k) for k in expected}, expected, 'Raw row coordinate/content/source identity differs')
    require(row.get('status') == 'ok', 'Failed raw inference row')
    logits = row.get('logits')
    require(isinstance(logits, list) and len(logits) == len(expected['target'])
            and all(type(v) in (int,float) and math.isfinite(v) for v in logits), 'Invalid raw logits')
    weights = [math.exp((v-max(logits))/temperature) for v in logits]
    probabilities = [v/math.fsum(weights) for v in weights]
    stored = row.get('probabilities')
    math_audit.distribution(stored)
    require(len(stored) == len(probabilities), 'Probability cardinality differs')
    error = max(abs(x-y) for x,y in zip(stored, probabilities))
    require(error <= 1e-12, 'Saved temperature/softmax probabilities differ')
    require(type(row.get('input_tokens')) is int and row['input_tokens'] > 0, 'Invalid input tokens')
    require(type(row.get('wall_seconds')) in (int,float) and math.isfinite(row['wall_seconds']) and row['wall_seconds'] >= 0, 'Invalid wall time')
    return error


def probe_contract(manifest, group):
    return object_hash({'schema_version':1,'checkpoint':manifest['checkpoint'],'data':manifest['data'],
        'implementation_sha256':manifest['implementation_sha256'],'fixtures_sha256':manifest['probe_fixtures']['sha256'],
        'group':{k:group[k] for k in ('id','node','policy','policy_sha256','paths')}})


def check_probe(probe, manifest, group, fixtures, items, imported):
    require(probe.get('status') == 'passed' and probe['campaign_group_id'] == group['id']
            and probe['probe_contract_sha256'] == probe_contract(manifest,group)
            and probe['fixtures_sha256'] == manifest['probe_fixtures']['sha256'], 'Invalid group probe identity')
    require(len(probe['rows']) == len(fixtures['rows']), 'Probe row count differs')
    error, references = 0., 0
    for pos, (actual, expected) in enumerate(zip(probe['rows'], fixtures['rows'])):
        idx = expected['global_index']; source = items[idx][2]
        require(actual['global_index'] == idx and actual['rank'] == pos%4
                and actual['row_sha256'] == expected['row_sha256'] == source['row_sha256']
                and expected['candidate_count'] == len(source['target']) == len(actual['different_row']['logits']), 'Probe source/rank/order differs')
        error = max(error, logits_equal(actual['different_row'], actual['same_row']))
        if expected['reference'] is not None:
            require(idx in imported, 'Probe reference was not imported')
            wrapper = imported[idx]
            reference = {**{k:wrapper['result'][k] for k in ('logits','input_tokens')},
                'source_identity_sha256':wrapper['origin']['source_identity_sha256'],
                'source_record_sha256':object_hash(wrapper['result'])}
            equal(expected['reference'], reference, 'Probe reference differs from original raw row')
            error = max(error, logits_equal(actual['different_row'], reference)); references += 1
    require(references >= 4, 'Missing preserved reference probes')
    return {'rows':len(probe['rows']),'old_reference_rows':references,'maximum_logit_absolute_error':error}


def audit_core(campaign, capture_root, data, old_data, checkpoint_dir, merged, *, spec=PRODUCTION):
    """Independently replay the raw union and four panels; never grants publication."""
    campaign,capture_root,data,old_data,checkpoint_dir,merged = map(Path,(campaign,capture_root,data,old_data,checkpoint_dir,merged))
    snapshot = math_audit.Snapshot()
    manifest = snapshot.json('campaign/manifest.json', campaign)
    snapshot.check('campaign/manifest.json',spec['campaign_sha256'])
    require(manifest['status']=='frozen' and manifest['schema_version']==1 and manifest['partition']==PARTITION
            and manifest['implementation_commit']==spec['campaign_commit'], 'Frozen campaign contract differs')
    require(manifest['implementation_sha256'].get(ARITHMETIC_ROLE)==ARITHMETIC_SHA==file_hash(ARITHMETIC_PATH),
            'Executing arithmetic implementation differs from frozen campaign')
    groups=manifest['groups']; require(len(groups)==manifest['group_count']==spec['group_count'], 'Campaign group count differs')
    require(len({g['id'] for g in groups})==len(groups) and [g['ordinal'] for g in groups]==list(range(len(groups))), 'Duplicate/moved campaign group')
    require(manifest['checkpoint']['checkpoint_sha256']==spec['checkpoint']
            and manifest['checkpoint']['temperature']==spec['temperature'], 'Campaign checkpoint/temperature differs')
    for group in groups:
        require(group['policy_sha256']==object_hash(group['policy']) and group['probe_contract_sha256']==probe_contract(manifest,group), 'Policy/probe contract differs')
    for name,sha in manifest['implementation_sha256'].items():
        snapshot.remember('new-implementation/'+name,regular(capture_root/'implementation',name),file_hash(capture_root/'implementation'/name))
        snapshot.check('new-implementation/'+name,sha)
    require(manifest['old_prefix']['directory']=='old-prefix','Unexpected imported directory')
    old_root=campaign.parent/'old-prefix'
    old_identity=snapshot.json('old-prefix/identity.json',old_root/'identity.json'); old_sha=object_hash(old_identity)
    require(old_sha==manifest['old_prefix']['identity_sha256'],'Original identity hash differs')
    equal(old_identity['checkpoint'],manifest['checkpoint'],'Original checkpoint differs')
    equal(old_identity['data'],manifest['data'],'Original data differs')
    equal(old_identity['implementation_sha256'],spec['implementation_sha256'],'Original implementation differs')
    for name,sha in spec['implementation_sha256'].items():
        snapshot.remember('old-prefix/implementation/'+name,regular(old_root/'implementation',name),file_hash(old_root/'implementation'/name))
        snapshot.check('old-prefix/implementation/'+name,sha)
    math_audit.checkpoint(checkpoint_dir,manifest['checkpoint'],spec,snapshot)
    new=math_audit.load_data(data,'new-data',spec['new'],snapshot)
    old=math_audit.load_data(old_data,'old-data',spec['old'],snapshot)
    subsets={}
    for split in math_audit.SPLITS:
        by_id={r['id']:i for i,r in enumerate(new[split])}; subsets[split]=[]
        for row in old[split]:
            require(row['id'] in by_id and row==new[split][by_id[row['id']]],'Old source record changed/moved')
            subsets[split].append(by_id[row['id']])
    expected_data={'manifest_sha256':spec['new']['manifest'],'split_sha256':spec['new']['hashes'],'counts':spec['new']['counts'],
        'ordered_ids_sha256':{s:object_hash([r['id'] for r in new[s]]) for s in math_audit.SPLITS},
        'old_manifest_sha256':spec['old']['manifest'],'old_split_sha256':spec['old']['hashes'],'old_counts':spec['old']['counts'],
        'old_subset_indices_sha256':object_hash(subsets)}
    equal(manifest['data'],expected_data,'Data panel identity differs')
    items=[(s,i,r) for s in math_audit.SPLITS for i,r in enumerate(new[s])]; total=len(items)
    indices=[r['global_index'] for r in manifest['imported_rows']]; remaining=manifest['remaining_global_indices']
    require(all(type(i) is int and 0<=i<total for i in indices+remaining),'Invalid global index')
    require(indices==sorted(set(indices)) and remaining==sorted(set(remaining)),'Duplicate/unordered campaign indices')
    require(set(indices).isdisjoint(remaining) and set(indices)|set(remaining)==set(range(total)),'Campaign union missing/duplicate')
    require(manifest['total_rows']==total and len(indices)==manifest['imported_count']==spec['imported_count']
            and len(remaining)==manifest['remaining_count']==spec['remaining_count'],'Frozen partition counts differ')
    require(old_identity['schema_version']==1 and old_identity['backend']=='fsdp4' and old_identity['world_size']==4
            and old_identity['row_batch_size']==1 and old_identity['max_length']==4096 and old_identity['prefix_cache'] is False
            and old_identity['temperature_fitted'] is False and old_identity['partition']=='concatenated_test_ood_index_mod4','Original execution identity differs')
    old_probe=snapshot.json('old-prefix/probe.json',old_root/'probe.json')
    positions=[i*(total-1)//3 for i in range(4)]
    require(old_probe['status']=='passed' and old_probe['eval_identity_sha256']==old_sha and old_probe['probe_indices']==positions
            and old_probe['max_logit_error_allowed']==.05 and len(old_probe['checks'])==4,'Original parity evidence differs')
    for rank,p in enumerate(old_probe['checks']):
        src=items[positions[rank]][2]
        require(p['rank']==rank and p['row_id']==src['id'] and p['row_sha256']==src['row_sha256']
                and p['passed'] is True and p['argmax_equal'] is True and type(p['max_logit_error']) in (int,float)
                and 0<=p['max_logit_error']<=.05,'Original parity check differs')
    records={}; imported_map=[]; max_probability_error=0.
    for rank in range(4):
        for pos,row in enumerate(snapshot.lines(f'old-prefix/shard-{rank}.jsonl',old_root/f'shard-{rank}.jsonl')):
            idx=rank+4*pos;require(idx<total,'Extra original raw row'); split,index,source=items[idx]
            fields={**source,'round':pos,'split':split,'index':index,'rank':rank,'eval_identity_sha256':old_sha,
                    'checkpoint_sha256':spec['checkpoint'],'data_split_sha256':spec['new']['hashes'][split]}
            max_probability_error=max(max_probability_error,validate_row(row,fields,spec['temperature']))
            records[idx]={'global_index':idx,'origin':{'type':'imported_old','source_identity_sha256':old_sha},'result':row}
            imported_map.append({'global_index':idx,'source_rank':rank,'source_line':pos+1,'record_sha256':object_hash(row),'source_identity_sha256':old_sha})
    equal(sorted(imported_map,key=lambda r:r['global_index']),manifest['imported_rows'],'Imported row map differs')
    for name,sha in manifest['old_prefix']['files_sha256'].items():
        role='old-prefix/'+name
        if role not in snapshot.files:snapshot.remember(role,regular(old_root,name),file_hash(old_root/name))
        snapshot.check(role,sha)
    require(manifest['probe_fixtures']['path']=='probe-fixtures.json','Unexpected fixtures path')
    fixtures=snapshot.json('campaign/probe-fixtures.json',campaign.parent/'probe-fixtures.json')
    snapshot.check('campaign/probe-fixtures.json',spec['fixture_sha256'])
    require(manifest['probe_fixtures']['sha256']==spec['fixture_sha256'] and len(fixtures['rows'])==spec['fixture_count']
            and len({r['global_index'] for r in fixtures['rows']})==len(fixtures['rows'])
            and fixtures['checkpoint_sha256']==spec['checkpoint'] and fixtures['data_manifest_sha256']==spec['new']['manifest']
            and fixtures['temperature']==spec['temperature'],'Frozen fixture identity differs')
    imported=dict(records);probes={};probe_checks={}
    for group in groups:
        gid=group['id']; directory=capture_root/'groups'/gid; role='groups/'+gid+'/'
        identity=snapshot.json(role+'identity.json',directory/'identity.json'); identity_sha=object_hash(identity)
        expected={'schema_version':1,'checkpoint':manifest['checkpoint'],'data':manifest['data'],'backend':'fsdp4','world_size':4,
            'row_batch_size':1,'max_length':4096,'prefix_cache':False,'temperature_fitted':False,'partition':PARTITION,
            'campaign_sha256':spec['campaign_sha256'],'campaign_group_id':gid,'group_ordinal':group['ordinal'],
            'group_count':len(groups),'policy':group['policy'],'implementation_sha256':manifest['implementation_sha256'],'allocator_config':'expandable_segments:True'}
        equal(identity,expected,'Formal group identity differs')
        summary=snapshot.json(role+'summary.json',directory/'summary.json')
        require(summary.get('status')=='complete' and summary['campaign_sha256']==spec['campaign_sha256']
                and summary['campaign_group_id']==gid and summary['eval_identity_sha256']==identity_sha
                and summary['padding_included_in_denominators'] is False and summary['aggregate_metrics_produced'] is False,'Group summary incomplete or identity differs')
        equal(summary['identity'],identity,'Group summary identity differs')
        assigned=remaining[group['ordinal']::len(groups)];require(summary['total_rows']==len(assigned),'Group total differs')
        probe=snapshot.json(role+'probe.json',directory/'probe.json')
        probe_checks[gid]=check_probe(probe,manifest,group,fixtures,items,imported);probes[gid]=probe
        require(summary['probe_receipt']['path']=='probe.json','Unexpected resume probe')
        snapshot.check(role+'probe.json',summary['probe_receipt']['sha256'])
        require(set(summary['raw_sha256'])=={f'shard-{r}.jsonl' for r in range(4)},'Group raw inventory differs')
        for rank in range(4):
            plan=assigned[rank::4]; progress=snapshot.json(role+f'progress-{rank}.json',directory/f'progress-{rank}.json')
            require(progress.get('status')=='complete' and progress['campaign_group_id']==gid and progress['rank']==rank
                    and progress['planned_rows']==progress['successful_rows']==len(plan) and progress['failed_rows']==progress['pending_rows']==0
                    and progress['eval_identity_sha256']==identity_sha and progress['resumed_at_round']==0
                    and progress['padding_forwards']==(len(assigned)+3)//4-len(plan),'Rank progress/denominator/padding differs')
            count=0; raw_role=role+f'shard-{rank}.jsonl'
            for row in snapshot.lines(raw_role,directory/f'shard-{rank}.jsonl'):
                require(count<len(plan),'Extra/duplicate group raw row');idx=plan[count];split,index,source=items[idx]
                fields={**source,'round':count,'split':split,'index':index,'rank':rank,'global_index':idx,'campaign_sha256':spec['campaign_sha256'],
                    'campaign_group_id':gid,'group_ordinal':group['ordinal'],'eval_identity_sha256':identity_sha,
                    'checkpoint_sha256':spec['checkpoint'],'data_split_sha256':spec['new']['hashes'][split]}
                max_probability_error=max(max_probability_error,validate_row(row,fields,spec['temperature']))
                require(idx not in records,'Duplicate original/new result')
                records[idx]={'global_index':idx,'origin':{'type':'campaign_group','campaign_group_id':gid,'source_identity_sha256':identity_sha},'result':row};count+=1
            require(count==len(plan),'Missing group raw row')
            snapshot.check(raw_role,summary['raw_sha256'][f'shard-{rank}.jsonl']);snapshot.check(raw_role,progress['output_sha256'])
    require(set(records)==set(range(total)),'Incomplete final raw union')
    cross=max(logits_equal(a['different_row'],b['different_row']) for x,y in itertools.combinations(probes.values(),2) for a,b in zip(x['rows'],y['rows']))
    # The merger reports comparison against its first group; independently also check every pair.
    anchor=probes[groups[0]['id']]
    anchor_error=max(logits_equal(a['different_row'],b['different_row']) for probe in probes.values() for a,b in zip(anchor['rows'],probe['rows']))
    source_hashes={role:sha for role,(_,sha) in snapshot.files.items()}
    summary=snapshot.json('merged/summary.json',merged/'summary.json')
    require(summary.get('status')=='complete' and summary['schema_version']==1 and summary['campaign_sha256']==spec['campaign_sha256']
            and summary['total_rows']==total and summary['imported_rows']==len(imported) and summary['new_rows']==len(remaining)
            and summary['old_subset_rows']==sum(map(len,subsets.values())) and summary['temperature_fitted'] is False
            and summary['padding_included_in_denominators'] is False and summary['imported_backend_identity_preserved'] is True,'Merged summary contract differs')
    equal(summary['input_sources_sha256'],source_hashes,'Merged input-source hash inventory differs')
    equal(summary['group_probe_checks'],probe_checks,'Merged probe checks differ')
    require(summary['cross_group_maximum_logit_error']==anchor_error,'Merged cross-group error differs')
    count=0;expected_digest=hashlib.sha256()
    for wrapper in snapshot.lines('merged/merged-records.jsonl',merged/'merged-records.jsonl'):
        require(count<total,'Extra merged record');equal(wrapper,records[count],'Merged row/origin/order differs')
        expected_digest.update((canonical(records[count])+'\n').encode());count+=1
    require(count==total,'Missing merged record')
    snapshot.check('merged/merged-records.jsonl',summary['merged_records_sha256'])
    require(expected_digest.hexdigest()==summary['merged_records_sha256'],'Merged canonical bytes differ')
    panels={};denominators={};offset=0;metric_errors=[]
    for split in math_audit.SPLITS:
        observed=[math_audit.observation(records[i]['result']) for i in range(offset,offset+len(new[split]))]
        old_observed=[observed[i] for i in subsets[split]]
        require(sum(r['hard'] for r in observed)==spec['new']['hard_counts'][split]
                and sum(r['hard'] for r in old_observed)==spec['old']['hard_counts'][split],'Hard denominators differ')
        require(all(r['correct'] in (0.,1.) for r in observed if r['hard']),'Nonbinary hard target')
        full_metrics,old_metrics=math_audit.grouped(observed),math_audit.grouped(old_observed)
        metric_errors+=math_audit.compare(summary['splits'][split],full_metrics)
        metric_errors+=math_audit.compare(summary['old_release_subset'][split],old_metrics)
        denominators[split]={'count':len(observed),'hard_count':sum(r['hard'] for r in observed),'soft_count':sum(not r['hard'] for r in observed),
            'hard_correct':sum(int(r['correct']) for r in observed if r['hard']),'old_count':len(old_observed),
            'old_hard_count':sum(r['hard'] for r in old_observed),'old_soft_count':sum(not r['hard'] for r in old_observed),
            'old_hard_correct':sum(int(r['correct']) for r in old_observed if r['hard'])}
        panels[split]={'expanded':full_metrics,'old_release_subset':old_metrics};offset+=len(observed)
    equal(summary['denominators'],denominators,'Merged denominator/numerator differs')
    snapshot.stable()
    require(file_hash(ARITHMETIC_PATH)==ARITHMETIC_SHA,'Arithmetic implementation changed during audit')
    return {'status':'core_verified_not_publishable','publishable':False,'campaign_sha256':spec['campaign_sha256'],
        'total_rows':total,'imported_rows':len(imported),'new_rows':len(remaining),'denominators':denominators,'panels':panels,
        'maximum_probability_error':max_probability_error,'maximum_metric_error':max(metric_errors,default=0.),
        'metric_relative_absolute_tolerance':3e-11,'probability_absolute_tolerance':1e-12,'pairwise_probe_maximum_logit_error':cross,
        'source_hashes':{k:sha for k,(_,sha) in snapshot.files.items()},'source_paths':{k:str(p) for k,(p,_) in snapshot.files.items()}}


def verify_capture(capture_root, manifest, *, spec=PRODUCTION, process_pins=PROCESS_PINS, launcher_sha=LAUNCHER_SHA):
    """Inspect captured bytes and both remote observations, not status flags alone."""
    root=Path(capture_root);receipt_path=regular(root,'capture-receipt.json')
    receipt=strict_json(receipt_path.read_bytes())
    require(receipt.get('schema_version')==1 and receipt.get('status')=='captured_complete_full24'
            and receipt['campaign_sha256']==spec['campaign_sha256'] and receipt['code_commit']==spec['campaign_commit']
            and receipt['read_only_remote'] is True,'Final capture is not complete/pinned')
    plans={g['id']:g for g in manifest['groups']};require(set(plans)==set(process_pins),'Unexpected final process group set')
    nodes={g['policy']['hostname'] for g in plans.values()}
    require(set(receipt['nodes'])==set(receipt['source_before'])==set(receipt['source_after'])==nodes,'Capture node set differs')
    equal(receipt['source_before'],receipt['source_after'],'Remote evidence changed during capture')
    covered={};common_inputs=None
    for hostname in sorted(nodes):
        node=receipt['source_after'][hostname]
        require(node['status']=='ready' and node['hostname']==hostname and node['code_commit']==spec['campaign_commit']
                and node['campaign_sha256']==spec['campaign_sha256'],'Remote node provenance differs')
        equal(receipt['nodes'][hostname],{k:v for k,v in node.items() if k!='files'},'Node summary differs from source snapshot')
        expected_groups={g for g,p in plans.items() if p['policy']['hostname']==hostname}
        require(set(node['groups'])==expected_groups,'Remote group ownership differs')
        for gid in expected_groups:
            proof=node['groups'][gid];pins=process_pins[gid]
            require(proof['status']=='completed' and proof['exit_code']==0 and proof['controller_exited'] is True
                    and proof['owned_processes_exited'] is True and proof['owned_gpu_cleanup_confirmed'] is True,'Remote controller/cleanup incomplete')
            equal(proof['controller'],dict(zip(('pid','start_time'),pins[0])),'Remote controller identity differs')
            checks=proof['process_checks'];observed=[]
            for check in checks:
                rec=check['recorded'];key=(rec['pid'],rec['start_time']);observed.append(key)
                require(check['same_process_present'] is False and check['same_process_live'] is False,'Recorded process still present')
                current=check['current']
                require(current is None or (current['pid']==rec['pid'] and current['start_time']!=rec['start_time']), 'Process exit flags contradict actual identity')
            require(len(observed)==len(set(observed))==len(pins) and set(observed)==set(pins),'Missing/extra original live process identity')
        for name,info in node['files'].items():
            require(name not in covered,'Duplicate destination from multiple nodes')
            covered[name]={'source_host':hostname,'source_path':info['source_path'],'bytes':info['bytes'],
                'before_sha256':info['sha256'],'after_sha256':info['sha256'],'local_sha256':info['sha256']}
        inputs=node['input_sha256']
        if common_inputs is None:common_inputs=dict(inputs)
        else:
            for name in set(common_inputs)&set(inputs):require(common_inputs[name]==inputs[name],'Cross-node input hash differs')
    equal(receipt['files'],covered,'Capture file/source inventory differs')
    for name,info in covered.items():
        path=regular(root,name)
        require(type(info['bytes']) is int and path.stat().st_size==info['bytes'] and file_hash(path)==info['local_sha256'],'Captured local file hash/size differs: '+name)
    generated=receipt.get('generated_files',{});local=receipt.get('local_files',{})
    require('group-directories.json' in generated,'Missing generated group mapping binding')
    require(set(covered).isdisjoint(generated) and set(covered).isdisjoint(local) and set(generated).isdisjoint(local)
            and 'capture-receipt.json' not in set(covered)|set(generated)|set(local),'Overlapping/reserved capture file roles')
    for name,info in generated.items():
        path=regular(root,name)
        require(type(info['bytes']) is int and path.stat().st_size==info['bytes'] and file_hash(path)==info['sha256'],
                'Generated evidence hash/size differs')
    for name,info in local.items():
        path=regular(root,name)
        require(type(info['bytes']) is int and path.stat().st_size==info['bytes']
                and info['before_sha256']==info['after_sha256']==info['local_sha256']==file_hash(path),
                'Local provenance changed during capture or hash/size differs')
    mapping=strict_json(regular(root,'group-directories.json').read_bytes())
    equal(mapping,{gid:str((root/'groups'/gid).resolve()) for gid in plans},'Generated group mapping differs')
    provenance={}
    for name,pin_key in (('launches.json','launches_sha256'),('package.json','package_manifest_sha256')):
        role='provenance/full24-launch/'+name
        require(role in local and local[role]['local_sha256']==spec[pin_key],'Pinned launch provenance differs: '+name)
        provenance[name]=strict_json(regular(root,role).read_bytes())
        require(provenance[name]['campaign_sha256']==spec['campaign_sha256'],'Launch/package campaign differs')
    launches={r['group_id']:r for r in provenance['launches.json']['launches']}
    require(len(launches)==len(provenance['launches.json']['launches']) and set(launches)==set(plans),'Pinned launch group set differs')
    package=provenance['package.json']
    # Every node must attest all shared model/data/code inputs, not merely an intersection.
    shared={'campaign/manifest.json':spec['campaign_sha256'],'campaign/probe-fixtures.json':spec['fixture_sha256']}
    for label,pin in (('community-hard-mix-v2-final',spec['new']),('release-v2',spec['old'])):
        # Dataset directory names are fixed by the captured campaign's paths.
        dataset_name=Path(plans[next(iter(plans))]['paths']['data' if pin is spec['new'] else 'old_data']).name
        shared['data/'+dataset_name+'/manifest.json']=pin['manifest']
        shared.update({'data/'+dataset_name+'/'+s+'.jsonl':sha for s,sha in pin['hashes'].items()})
    shared.update({'checkpoint/'+name:sha for name,sha in manifest['checkpoint']['files_sha256'].items()})
    shared.update({'implementation/'+name:sha for name,sha in manifest['implementation_sha256'].items()})
    shared['implementation/scripts/run_eval_stage.py']=launcher_sha
    for node in receipt['nodes'].values():
        require(all(node['input_sha256'].get(k)==v for k,v in shared.items()),'Node lacks pinned common input attestation')
    require(all(name in covered and covered[name]['local_sha256']==sha for name,sha in shared.items()),'Common input capture binding absent')
    for gid,group in plans.items():
        def load(name):
            require(name in covered,'Unbound controller/result evidence: '+name)
            return strict_json(regular(root,name).read_bytes())
        stage=load('controllers/'+gid+'/stage.json');dispatch=load('dispatch/full-'+gid+'.json')
        policy=group['policy'];pins=process_pins[gid];launch=launches[gid]
        equal({k:dispatch[k] for k in ('argv','cwd','node','host')},
              {k:launch[k] for k in ('argv','cwd','node','host')},'Dispatch differs from pinned launch')
        equal(launch['policy'],policy,'Pinned launch hardware policy differs')
        require(launch['node']==group['node'],'Pinned launch node differs from campaign')
        require(stage['status']=='completed' and stage['exit_code']==0 and stage['automatic_retries']==0,'Controller failed/incomplete/retried')
        require((stage['controller']['pid'],stage['controller']['start_time'])==pins[0]
                and (stage['leader']['pid'],stage['leader']['start_time'])==pins[1]
                and (dispatch['pid'],dispatch['start_time'])==pins[0],'Controller/leader launch identity differs')
        require(dispatch['campaign_sha256']==spec['campaign_sha256'] and dispatch['code_commit']==spec['campaign_commit'],'Dispatch identity differs')
        remote_root=Path(group['paths']['resource_policy']).parent.parent
        require(stage['cwd']==dispatch['cwd']==str(remote_root/'repo'),'Wrong runtime cwd')
        stage_spec=load('stages/'+gid+'.json')
        require(covered['stages/'+gid+'.json']['local_sha256']==package['files_sha256']['full24-stages/'+gid+'.json'],
                'Stage bytes differ from pinned deployment package')
        equal(stage['stage'],stage_spec,'Stage specification differs')
        equal(load('controllers/'+gid+'/stage-spec.json'),stage_spec,'Controller saved stage differs')
        equal(stage['policy'],policy,'Controller hardware policy differs')
        equal(load('policies/'+gid+'.json'),policy,'Captured hardware policy differs')
        equal(load('controllers/'+gid+'/policy.json'),policy,'Controller saved policy differs')
        require(stage['cuda_visible_devices']==','.join(policy['gpu_uuids']),'Controller CUDA UUID order differs')
        require(stage['policy_sha256']==group['policy_sha256']==object_hash(policy)
                and stage['stage_sha256']==object_hash(stage_spec),'Controller stage/policy digest differs')
        argv=stage_spec['argv'];controller_argv=dispatch['argv']
        require('--resume' not in argv and '--probe-only' not in argv,'Resume/probe-only execution is not publishable')
        for flag,value in (('--campaign-sha256',spec['campaign_sha256']),('--group-id',gid),('--campaign',str(remote_root/'full24-campaign/manifest.json')),('--output',str(remote_root/'results'/gid))):
            require(argv.count(flag)==1 and argv[argv.index(flag)+1]==value,'Stage argument differs: '+flag)
        for flag,value in (('--policy',group['paths']['resource_policy']),('--stage',str(remote_root/'full24-stages'/f'{gid}.json')),('--output',str(remote_root/'controllers'/gid))):
            require(controller_argv.count(flag)==1 and controller_argv[controller_argv.index(flag)+1]==value,'Controller argument differs: '+flag)
        require('scripts.run_eval_stage' in controller_argv and 'scripts.evaluate_internal_shard' in argv,'Wrong controller/worker module')
        cleanup=stage['cleanup']
        require(cleanup['confirmed'] is True and cleanup['remaining']==[] and cleanup['term_signals']==cleanup['kill_signals']==0
                and stage['owned_gpu_cleanup_confirmed'] is True,'Controller cleanup incomplete or signalled')
        require(all(k not in stage for k in ('stop_reason','cleanup_error','error','error_type')),'Controller recorded failure')
        require(all(type(stage[k]) in (int,float) and math.isfinite(stage[k]) for k in ('started_at','finished_at'))
                and stage['finished_at']>=stage['started_at'],'Controller completion time missing/invalid')
        require(set(stage['post_cleanup_owned_mib'])=={str(i) for i in policy['gpu_indices']}
                and all(type(v) in (int,float) and v==0 for v in stage['post_cleanup_owned_mib'].values()),'Residual owned GPU memory')
        require(set(stage['own_peak_mib'])=={str(i) for i in policy['gpu_indices']}
                and all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=policy['own_limit_mib'] for v in stage['own_peak_mib'].values()),'Owned GPU memory exceeded cap')
        for rank in range(4):
            allocation=load(f'groups/{gid}/allocation-{rank}.json')
            require(allocation['logical_device']==rank and allocation['physical_gpu']==policy['gpu_indices'][rank]
                    and allocation['gpu_uuid']==policy['gpu_uuids'][rank] and allocation['policy_sha256']==group['policy_sha256']
                    and allocation['allocator_limit_mib']==policy['allocator_limit_mib'],'Allocator device/policy differs')
            total_bytes=allocation['total_device_bytes'];fraction=allocation['allocator_fraction']
            require(type(total_bytes) is int and total_bytes>0 and type(fraction) in (int,float) and math.isfinite(fraction)
                    and 0<fraction<=1 and math.isclose(fraction,policy['allocator_limit_mib']*2**20/total_bytes,rel_tol=1e-12,abs_tol=1e-12),'Allocator fraction differs')
        if group['node'].startswith('N4'):
            cache_dir='runtime/'+policy['hostname']+'/cache/'
            profile=load(cache_dir+'open-jev-reference-provenance.json')
            profile_pin={'N4-1':'87d82acdc5d2eac29903dd4b1cb5de9a082d474f128626a75d8a966ec0b7e801',
                         'N4-2':'d1ed1c14ee3e649e5127fdb10317f15cc09d87736f3f9fb15553c94823ed1ae8'}[group['node']]
            require(covered[cache_dir+'open-jev-reference-provenance.json']['local_sha256']==profile_pin,'Cache provenance pin differs')
            require(len(profile['records'])==len(dispatch['cache_profile_before'])==24,'Fixed forward cache inventory differs')
            require('TRITON_CACHE_DIR='+str(remote_root/'n1-reference-full-triton-cache') in argv,'Wrong private runtime cache')
            for record in profile['records']:
                name=record['target_namespace']+'/'+record['kernel'];row=load(cache_dir+name)
                require(covered[cache_dir+name]['local_sha256']==dispatch['cache_profile_before'][name]==record['source_sha256'],'Fixed autotune profile changed')
                equal(row['key'],record['key'],'Autotune key changed')
                equal([v[0] for v in row['configs_timings']],record['ordered_configs'],'Autotune configuration set changed')
    return receipt


def audit(campaign, capture_root, data, old_data, checkpoint_dir, merged, *, spec=PRODUCTION, process_pins=PROCESS_PINS, launcher_sha=LAUNCHER_SHA):
    campaign,capture_root=Path(campaign),Path(capture_root)
    require(campaign.resolve()==(capture_root/'campaign/manifest.json').resolve(),'Audit must use captured campaign')
    manifest=strict_json(campaign.read_bytes());require(file_hash(campaign)==spec['campaign_sha256'],'Campaign pin differs')
    receipt_path=regular(capture_root,'capture-receipt.json');receipt_sha=file_hash(receipt_path)
    receipt=verify_capture(capture_root,manifest,spec=spec,process_pins=process_pins,launcher_sha=launcher_sha)
    report=audit_core(campaign,capture_root,data,old_data,checkpoint_dir,merged,spec=spec)
    for role,name in report.pop('source_paths').items():
        if role.startswith('merged/'):continue
        try:relative=Path(name).resolve().relative_to(capture_root.resolve()).as_posix()
        except ValueError:raise ValueError('Audit input lies outside completed capture: '+role) from None
        require(relative in receipt['files'] and receipt['files'][relative]['local_sha256']==report['source_hashes'][role],'Core input missing capture binding: '+role)
    # Re-read every captured byte after arithmetic so concurrent mutation cannot pass.
    final_receipt=verify_capture(capture_root,manifest,spec=spec,process_pins=process_pins,launcher_sha=launcher_sha)
    require(file_hash(receipt_path)==receipt_sha,'Capture receipt changed during audit')
    equal(final_receipt,receipt,'Capture receipt changed during audit')
    report.update(status='passed_complete_full24_audit',publishable=True,
        capture_receipt_sha256=receipt_sha,
        auditor_sha256=file_hash(__file__),arithmetic_sha256=ARITHMETIC_SHA,
        scope='Complete four-panel quality audit; shared multi-GPU timings do not establish API or single-GPU speedup.')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('campaign','capture-root','data','old-data','checkpoint','merged','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists(),'Preserve existing audit output')
    report=audit(args.campaign,args.capture_root,args.data,args.old_data,args.checkpoint,args.merged)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as stream:stream.write(canonical(report)+'\n')
    print(canonical({k:report[k] for k in ('status','publishable','total_rows','denominators')}))


if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,TypeError,OSError,OverflowError) as error:
        print('Independent campaign audit failed: '+type(error).__name__+': '+str(error),file=sys.stderr)
        sys.exit(1)
