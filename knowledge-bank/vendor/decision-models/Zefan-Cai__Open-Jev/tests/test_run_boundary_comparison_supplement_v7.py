import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts import run_boundary_comparison_supplement_v7 as supplement


class ComparisonSupplementTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.old, self.new = self.root/'original', self.root/'supplement'
        self.old.mkdir(); self.new.mkdir()
        self.source = self.new/'evaluation-source'; self.source.mkdir()
        self.declaration = self.root/'declaration.json'
        self.request_path = self.new/'comparison-supplement-request.json'
        self.receipt = dict(gpu_uuid='GPU-8e9ce19f-1174-0848-8e17-3201e3bb8775',
            source_commit=supplement.SOURCE_COMMIT,checkpoint=dict(directory_sha256='d'*64),
            execution_request_path=str(self.old/'execution-request.json'))
        self.original = dict(evaluation_commit=supplement.ORIGINAL_EVALUATION,
            plan_sha256='f'*64, gpu_uuid=self.receipt['gpu_uuid'], runtime={name:'fixture-'+name for name in supplement.RUNTIME_NAMES},
            comparison_output=str(self.old/'comparison'),
            **{key:str(self.old/name) for key,name in (('dataset','data'),('released_checkpoint','released'),
                ('training_run','adaptation'),('completion_receipt','completion-receipt.json'))})
        for filename, value in (('execution-request.json',self.original),('completion-receipt.json',self.receipt)):
            self.write(self.old/filename,value)
        failed=self.old/'comparison'; failed.mkdir()
        self.write(failed/'comparison.lock.json',dict(status='locked_before_model_loading'))
        (self.old/'comparison.log').write_text('ValueError: Published/final comparison runtime or recorded training packages differ\n')
        self.controller=self.new/'queue-v7-handoff-origin.json'
        self.audit=self.new/'origin-audit.json'
        self.write(self.controller,dict(status='v7_failed_original_queue_verified',queue_restoration=supplement.RESTORED,
            source_commit=supplement.SOURCE_COMMIT,evaluation_commit=supplement.ORIGINAL_EVALUATION))
        self.write(self.audit,dict(status='independently_verified_original_queue_restored_owned_controller_guard_driver_gone',
            controller_status='v7_failed_original_queue_verified',queue_restoration=supplement.RESTORED,
            evaluation_commit=supplement.ORIGINAL_EVALUATION,source_commit=supplement.SOURCE_COMMIT,controller_receipt=str(self.controller),
            restoration_evidence_complete=True,full_hashes=True,failed_checks=[],checks=dict(full=True),
            controller_current_identity=None,guard_current_identity=None,driver_current_identity=None))
        self.write(self.old/'experiment-completion.json',dict(training_status='complete',comparison_returncode=1,
            automatic_promotion=False,training_completion_receipt_sha256=supplement.sha(self.old/'completion-receipt.json'),
            execution_request_sha256=supplement.sha(self.old/'execution-request.json')))
        self.public=dict(schema_version=1,kind=supplement.KIND,supplement_id=supplement.SUPPLEMENT_ID,
            status='declared_not_executed',training_calls=0,automatic_retry=False,automatic_promotion=False,
            training_source_commit=supplement.SOURCE_COMMIT,plan_sha256='f'*64,
            completed_checkpoint_directory_sha256='d'*64,physical_gpu_uuid=self.receipt['gpu_uuid'],
            origin=dict(evaluation_commit=supplement.ORIGINAL_EVALUATION,
                **{key:supplement.sha(path) for key,path in (
                    ('execution_request_sha256',self.old/'execution-request.json'),
                    ('completion_receipt_sha256',self.old/'completion-receipt.json'),
                    ('experiment_completion_sha256',self.old/'experiment-completion.json'),
                    ('failure_log_sha256',self.old/'comparison.log'),
                    ('controller_final_sha256',self.controller),('restoration_audit_sha256',self.audit))},
                failed_comparison_files_sha256=supplement.file_inventory(failed)))
        self.request=dict(schema_version=1,kind=supplement.KIND,supplement_id=supplement.SUPPLEMENT_ID,
            evaluation_commit='b'*40,original_task=str(self.old),original_controller_receipt=str(self.controller),
            original_restoration_audit=str(self.audit),resource_receipt=str(self.new/'resource-ready.json'),
            controller_plan=str(self.new/'controller-plan.json'),
            **{key:self.original[key] for key in ('dataset','released_checkpoint','training_run','completion_receipt',
                'plan_sha256','gpu_uuid','runtime')},comparison_output=str(self.new/'comparison'))
        self.seal()
        self.args=SimpleNamespace(supplemental_request=str(self.request_path),expected_commit='b'*40,
            **{key:self.original[key] for key in ('dataset','released_checkpoint','training_run','completion_receipt')})
        self.addCleanup(patch.stopall)
        patch.object(supplement,'DECLARATION',self.declaration).start()
        patch.object(supplement,'ROOT',self.source).start()

    @staticmethod
    def write(path,value):
        path.write_text(json.dumps(value,indent=2)+'\n')

    def seal(self):
        self.write(self.declaration,self.public)
        self.request['declaration_sha256']=supplement.sha(self.declaration)
        self.write(self.request_path,self.request)

    def validate(self):
        return supplement.validate_supplement(self.args,self.receipt,self.original,self.new/'comparison')

    def launch_fixture(self,provenance,pid):
        controller=self.new/'pause_v7_comparison_restore.py';controller.write_text('# authored controller fixture\n')
        rows=dict(v7_test=[{}]*256,v7_ood=[{}]*256,v4_test=[{}]*128,v4_ood=[{}]*128,
            v5_test=[{}]*32,v5_ood=[{}]*32,v6_test=[{}]*36,v6_ood=[{}]*36)
        inputs=dict(supplemental_provenance=provenance,evaluation_source=dict(commit='b'*40),
            files_sha256=provenance['files_sha256'],checkpoint_directory_sha256=dict(released='a'*64,adapted='d'*64))
        preflight=self.new/'comparison-supplement-preflight.json'
        self.write(preflight,supplement.preflight_record(self.request_path,rows,inputs))
        plan=dict(schema_version=1,kind=supplement.KIND,supplement_id=supplement.SUPPLEMENT_ID,
            source_commit=supplement.SOURCE_COMMIT,evaluation_commit='b'*40,gpu_uuid=self.receipt['gpu_uuid'],
            controller_sha256=supplement.sha(controller),driver_sha256=supplement.sha(supplement.__file__),
            execution_request_sha256=provenance['request_sha256'],cpu_preflight_receipt_sha256=supplement.sha(preflight),
            controller_command=['/usr/bin/python3',str(controller.resolve()),'--execute'],controller_working_directory=str(self.new.resolve()),
            declaration_sha256=provenance['declaration_sha256'])
        self.write(Path(self.request['controller_plan']),plan)
        resource=dict(restoration_required=True,kind=supplement.KIND,supplement_id=supplement.SUPPLEMENT_ID,
            source_commit=supplement.SOURCE_COMMIT,evaluation_commit='b'*40,driver_sha256=plan['driver_sha256'],
            execution_request_sha256=provenance['request_sha256'],controller_plan_sha256=supplement.sha(self.request['controller_plan']),
            declaration_sha256=provenance['declaration_sha256'],controller_identity=dict(pid=42,uid=1,start_ticks=43,boot_id='boot'),
            restoration_guard_identity=dict(pid=44,uid=1,start_ticks=45,boot_id='boot'),
            checked_at_utc='2026-10-03T02:39:50+00:00',
            boot_id='boot')
        self.write(self.new/'resource-ready.json',resource)
        lock=dict(status='single_comparison_supplement_started_no_retry',pid=pid,
            started_at_utc='2026-10-03T02:40:00+00:00',
            request_sha256=provenance['request_sha256'],runner_sha256=supplement.sha(supplement.__file__),evaluation_commit='b'*40,
            preflight_receipt_sha256=supplement.sha(preflight),controller_plan_sha256=supplement.sha(self.request['controller_plan']),
            resource_receipt_sha256=supplement.sha(self.new/'resource-ready.json'),controller_identity=resource['controller_identity'])
        self.write(self.new/'attempt.lock.json',lock)
        return rows,inputs,lock

    def test_origin_preserved_and_cpu_provenance_complete(self):
        inventory={str(p):p.read_bytes() for p in self.old.rglob('*') if p.is_file()}
        result=self.validate()
        self.assertEqual(result['training_calls'],0)
        self.assertEqual(result['original_evaluation_commit'],supplement.ORIGINAL_EVALUATION)
        self.assertEqual(result['request'],self.request)
        self.assertEqual(inventory,{str(p):p.read_bytes() for p in self.old.rglob('*') if p.is_file()})
        self.assertFalse((self.new/'comparison').exists())

    def test_source_requires_exact_canonical_nested_layout(self):
        for source in (self.root/'evaluation-source', self.new/'source',
                       self.source/'nested', self.new):
            source.mkdir(exist_ok=True)
            with self.subTest(source=source),patch.object(supplement,'ROOT',source),\
                    self.assertRaisesRegex(ValueError,'canonical evaluation-source'):
                self.validate()

    def test_source_symlink_and_resolved_external_target_rejected(self):
        self.source.rmdir()
        target=self.root/'external-source';target.mkdir()
        self.source.symlink_to(target,target_is_directory=True)
        for source in (self.source,self.source.resolve()):
            with self.subTest(source=source),patch.object(supplement,'ROOT',source),\
                    self.assertRaisesRegex(ValueError,'canonical evaluation-source'):
                self.validate()

    def test_new_task_disjoint_from_original_task_dataset_and_checkpoint(self):
        request,original,receipt=map(copy.deepcopy,(self.request,self.original,self.receipt))
        for key in ('original_task','dataset','released_checkpoint'):
            for old in (self.new,self.new/'old-input',self.new.parent):
                self.request=copy.deepcopy(request);self.original=copy.deepcopy(original)
                self.receipt=copy.deepcopy(receipt)
                if key == 'original_task':
                    self.request[key]=str(old)
                    self.receipt['execution_request_path']=str(old/'execution-request.json')
                    value=str(old/'completion-receipt.json')
                    self.request['completion_receipt']=self.original['completion_receipt']=value
                    args_key='completion_receipt'
                else:
                    value=str(old);args_key=key
                    self.request[key]=self.original[key]=value
                self.seal()
                with self.subTest(key=key,old=old),patch.object(self.args,args_key,value),\
                        self.assertRaisesRegex(ValueError,'overlaps original evidence or inputs'):
                    self.validate()
        self.request,self.original,self.receipt=request,original,receipt
        self.seal()
        self.validate()

    def test_origin_bytes_or_extra_predictions_fail(self):
        for name in ('execution-request.json','completion-receipt.json','experiment-completion.json','comparison.log','comparison/comparison.lock.json'):
            path=self.old/name;raw=path.read_bytes();path.write_bytes(raw+b' ')
            with self.subTest(name=name),self.assertRaises(ValueError):self.validate()
            path.write_bytes(raw)
        extra=self.old/'comparison/released_v7_test.jsonl';extra.write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'inventory'):self.validate()

    def test_input_hardware_runtime_and_output_overrides_refused(self):
        original=copy.deepcopy(self.request)
        for key,value in (('training_run',str(self.root/'different')),
                          ('completion_receipt',str(self.root/'different')),
                          ('comparison_output',str(self.old/'comparison')),
                          ('resource_receipt',str(self.old/'resource-ready.json')),
                          ('gpu_uuid','GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'),
                          ('runtime',dict(torch='different')),('evaluation_commit','c'*40),
                          ('plan_sha256','e'*64),('kind','training')):
            self.request=copy.deepcopy(original);self.request[key]=value;self.seal()
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_incomplete_restoration_and_live_process_rejected_even_if_rehashed(self):
        original=json.loads(self.audit.read_text())
        for key,value in (('full_hashes',False),('restoration_evidence_complete',False),
                          ('failed_checks',['rank']),('checks',{}),('checks',dict(full=1)),
                          ('guard_current_identity',dict(pid=123)),('controller_status','restoring')):
            current=copy.deepcopy(original);current[key]=value;self.write(self.audit,current)
            self.public['origin']['restoration_audit_sha256']=supplement.sha(self.audit);self.seal()
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate()

    def test_declaration_and_origin_identity_cannot_be_silently_changed(self):
        self.request['declaration_sha256']='0'*64;self.write(self.request_path,self.request)
        with self.assertRaisesRegex(ValueError,'declaration'):self.validate()
        self.seal();self.public['origin']['evaluation_commit']='c'*40;self.seal()
        with self.assertRaisesRegex(ValueError,'evaluation'):self.validate()

    def test_consumed_s1_identity_cannot_be_reused_for_new_supplement(self):
        self.request['supplement_id']=self.public['supplement_id']='boundary-v7-comparison-s1-20261003'
        self.seal()
        with self.assertRaisesRegex(ValueError,'Unknown comparison-only declaration/request'):
            self.validate()

    def test_launch_requires_current_process_new_session_lock_and_live_resource(self):
        provenance=self.validate();pid=4321
        rows,inputs,lock=self.launch_fixture(provenance,pid)
        with patch.object(supplement.os,'getpid',return_value=pid),patch.object(supplement.os,'getsid',return_value=pid),\
                patch.object(supplement,'datetime',wraps=datetime) as clock,\
                patch.object(supplement,'version',side_effect=self.request['runtime'].__getitem__),\
                patch.object(supplement,'verify_controller_parent') as parent,\
                patch.object(supplement,'verify_restoration_guard'),\
                patch.object(supplement,'validate_resource',return_value=dict(live=True)) as validate:
            clock.now.return_value=datetime(2026,10,3,2,40,tzinfo=timezone.utc)
            self.assertTrue(supplement.validate_launch(self.args,provenance,rows,inputs)['resource']['live'])
            validate.assert_called_once_with(self.request)
            self.assertEqual(parent.call_count,2)
            lock['pid']=123;self.write(self.new/'attempt.lock.json',lock)
            with self.assertRaises(ValueError):supplement.validate_launch(self.args,provenance,rows,inputs)
            self.assertEqual(validate.call_count,1)

    def test_resource_failure_cannot_be_bypassed(self):
        provenance=self.validate();pid=4321
        rows,inputs,_=self.launch_fixture(provenance,pid)
        with patch.object(supplement.os,'getpid',return_value=pid),patch.object(supplement.os,'getsid',return_value=pid),\
                patch.object(supplement,'version',side_effect=self.request['runtime'].__getitem__),\
                patch.object(supplement,'verify_controller_parent'),\
                patch.object(supplement,'verify_restoration_guard'),\
                patch.object(supplement,'validate_resource',side_effect=ValueError('stale guard')):
            with self.assertRaisesRegex(ValueError,'stale guard'):supplement.validate_launch(self.args,provenance,rows,inputs)

    def test_direct_comparator_cannot_skip_preflight_package_or_restoration_guard(self):
        provenance=self.validate();pid=4321
        rows,inputs,lock=self.launch_fixture(provenance,pid)
        preflight=self.new/'comparison-supplement-preflight.json';raw=preflight.read_bytes()
        with patch.object(supplement.os,'getpid',return_value=pid),patch.object(supplement.os,'getsid',return_value=pid),\
                patch.object(supplement,'version',side_effect=self.request['runtime'].__getitem__),\
                patch.object(supplement,'verify_restoration_guard'),\
                patch.object(supplement,'verify_controller_parent'),patch.object(supplement,'validate_resource') as resource:
            preflight.write_text('{}')
            with self.assertRaisesRegex(ValueError,'preflight'):supplement.validate_launch(self.args,provenance,rows,inputs)
            preflight.write_bytes(raw)
            with patch.object(supplement,'version',return_value='changed'):
                with self.assertRaisesRegex(ValueError,'packages'):supplement.validate_launch(self.args,provenance,rows,inputs)
            path=self.new/'resource-ready.json';record=json.loads(path.read_text());record['restoration_required']=False
            self.write(path,record);lock['resource_receipt_sha256']=supplement.sha(path);self.write(self.new/'attempt.lock.json',lock)
            with self.assertRaisesRegex(ValueError,'guarded acquisition'):supplement.validate_launch(self.args,provenance,rows,inputs)
            resource.assert_not_called()

    def test_restoration_guard_cannot_alias_controller_or_driver(self):
        controller=dict(pid=42,uid=1,start_ticks=43,boot_id='boot')
        with patch.object(supplement.os,'getpid',return_value=4321),patch.object(supplement.os,'getuid',return_value=1):
            for pid in (42,4321,True):
                guard={**controller,'pid':pid}
                with self.subTest(pid=pid),self.assertRaisesRegex(ValueError,'distinct restoration guard'):
                    supplement.verify_restoration_guard(guard,controller,'boot')

    def test_gpu_queries_cannot_expire_resource_or_hide_lost_controller(self):
        provenance=self.validate();pid=4321
        rows,inputs,_=self.launch_fixture(provenance,pid)
        with patch.object(supplement.os,'getpid',return_value=pid),patch.object(supplement.os,'getsid',return_value=pid),\
                patch.object(supplement,'version',side_effect=self.request['runtime'].__getitem__),\
                patch.object(supplement,'verify_restoration_guard'),\
                patch.object(supplement,'verify_controller_parent') as parent,\
                patch.object(supplement,'validate_resource',return_value={}),\
                patch.object(supplement,'datetime',wraps=datetime) as clock:
            for now in (datetime(2026,10,3,2,39,55,tzinfo=timezone.utc),datetime(2026,10,3,2,41,51,tzinfo=timezone.utc)):
                clock.now.return_value=now
                with self.subTest(now=now),self.assertRaisesRegex(ValueError,'stale during GPU queries'):
                    supplement.validate_launch(self.args,provenance,rows,inputs)
            parent.side_effect=[None,ValueError('controller exited during probe')]
            with self.assertRaisesRegex(ValueError,'controller exited'):
                supplement.validate_launch(self.args,provenance,rows,inputs)

    def test_exclusive_fsynced_lock_cannot_be_overwritten(self):
        path=self.new/'once.json'
        with patch.object(supplement.os,'fsync',wraps=supplement.os.fsync) as fsync:
            supplement.write_once(path,dict(training_calls=0));fsync.assert_called_once()
        with self.assertRaises(FileExistsError):supplement.write_once(path,dict(training_calls=948))
        self.assertEqual(json.loads(path.read_text()),dict(training_calls=0))


if __name__ == '__main__':
    unittest.main()
