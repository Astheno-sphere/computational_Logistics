import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev.data import SPLITS, _write_dataset
from jev.train import _file_sha256, _json_sha256, read_rows
from scripts import prepare_policy_training_v6 as preparation


class PolicyTrainingPreparationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources, self.rows, self.locks = {}, {}, {}
        for name,version in preparation.VERSIONS.items():
            directory = self.root/name
            rows = []
            for split in SPLITS:
                group = name+'/'+split+'/group'
                for variant in range(4):
                    kind = 'noul' if variant == 3 else 'choice'
                    rows.append(dict(id=group+'/'+str(variant),group_id=group,split=split,
                        source=version,kind=kind,question='Apply the stated case facts.',
                        state={'case_ref':group,'amount_cents':1000+variant},
                        options=['no','yes'] if kind == 'noul' else ['accept','reject'],target=[1.,0.],
                        metadata={'family':'policy','scenario_family':'fixture-policy',
                            'template_id':name+('/ood' if split == 'ood' else '/id'),'entity_ids':[group],
                            'provenance':{'type':'synthetic','license':'CC0-1.0','generator_version':version,
                                'seed':20261002,'group_index':0,'variant':variant,'split_policy':'whole_groups'}}))
            _write_dataset(rows,directory,{'generator_version':version})
            self.sources[name] = directory
            self.rows[name] = {s:[r for r in rows if r['split'] == s] for s in SPLITS}
            if name != 'v6':
                selection = {'manifest_sha256':_file_sha256(directory/'manifest.json'),
                    'selected_ids':{},'selected_sha256':{}}
                for split in ('test','ood'):
                    selected = list(reversed(self.rows[name][split]))
                    selection['selected_ids'][split] = [r['id'] for r in selected]
                    selection['selected_sha256'][split] = _json_sha256(selected)
                key = 'selection' if name == 'v4' else 'v5_selection'
                path = self.root/(name+'-lock.json')
                path.write_text(json.dumps({key:selection}))
                self.locks[name] = (path,key)
        v6_lock = self.root/'v6-frozen.json'
        v6_lock.write_text(json.dumps({'dataset_manifest_sha256':_file_sha256(self.sources['v6']/'manifest.json'),
            'split_sha256':json.loads((self.sources['v6']/'manifest.json').read_text())['files_sha256']}))
        for name,value in (('COUNTS',{n:(4,4,4,4,4) for n in self.sources}),('LOCKS',self.locks),
                           ('V6_LOCK',v6_lock),('V6_LOCK_SHA256',_file_sha256(v6_lock))):
            patched = patch.object(preparation,name,value)
            patched.start();self.addCleanup(patched.stop)
        patched = patch.object(preparation,'committed_source',return_value='a'*40)
        patched.start();self.addCleanup(patched.stop)
        self.output = self.root/'mixed'

    def prepare(self):
        return preparation.prepare(self.sources['v4'],self.sources['v5'],self.sources['v6'],
            self.output,'/future-training-host/released/checkpoint','/future-training-host/adaptation')

    def rewrite_split(self,name,split,rows):
        directory = self.sources[name]
        preparation.write_rows(directory/(split+'.jsonl'),rows)
        manifest = json.loads((directory/'manifest.json').read_text())
        manifest['files_sha256'][split+'.jsonl'] = _file_sha256(directory/(split+'.jsonl'))
        (directory/'manifest.json').write_text(json.dumps(manifest))

    def test_only_train_is_mixed_and_existing_loader_consumes_one_full_pass(self):
        manifest,plan = self.prepare()
        self.assertEqual(manifest['summary']['splits'],dict(train=12,calibration=12,validation=12,test=4,ood=4))
        selected = read_rows(self.output/'train.jsonl',12,20261002,balanced=False)
        expected = {r['id'] for splits in self.rows.values() for r in splits['train']}
        self.assertEqual({r['id'] for r in selected},expected)
        self.assertEqual(plan['settings']['steps']*plan['settings']['accumulation'],len(selected))
        for split in ('test','ood'):
            self.assertEqual({r['source'] for r in read_rows(self.output/(split+'.jsonl'),0,1)},
                             {preparation.VERSIONS['v6']})
        for name in self.sources:
            for split in ('calibration','validation'):
                self.assertEqual((self.output/'heldout'/name/(split+'.jsonl')).read_bytes(),
                                 (self.sources[name]/(split+'.jsonl')).read_bytes())
        self.assertEqual(plan['status'],'predeclared_candidate_not_trained')
        self.assertIn('--initial-checkpoint',plan['training_argv'])
        self.assertEqual(plan['settings']['checkpoint_every'],0)
        self.assertEqual(plan['required_future_comparison']['status'],'not_run_not_automatically_provided_by_jev.train')

    def test_observed_regression_order_and_original_hashes_are_frozen(self):
        manifest,plan = self.prepare()
        for name,(path,key) in self.locks.items():
            selected = json.loads(path.read_text())[key]['selected_ids']
            for split in ('test','ood'):
                actual = [json.loads(x) for x in (self.output/'observed-regression'/name/(split+'.jsonl')).read_text().splitlines()]
                self.assertEqual([r['id'] for r in actual],selected[split])
            proof = manifest['configuration']['sources'][name]
            self.assertEqual(proof['manifest_sha256'],_file_sha256(self.sources[name]/'manifest.json'))
            self.assertEqual(proof['rows_sha256']['train'],_json_sha256(self.rows[name]['train']))
        self.assertEqual(plan['data_manifest_sha256'],_file_sha256(self.output/'manifest.json'))

    def test_changed_bytes_and_wrong_split_are_rejected_before_output_creation(self):
        path = self.sources['v6']/'train.jsonl'
        path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'hash changed'):
            self.prepare()
        self.assertFalse(self.output.exists())
        path.write_text(path.read_text()[:-1])
        rows = self.rows['v4']['train']
        rows[0]['split'] = 'test'
        self.rewrite_split('v4','train',rows)
        with self.assertRaisesRegex(ValueError,'count/split/provenance'):
            self.prepare()

    def test_cross_source_train_to_test_group_leak_is_rejected(self):
        rows = self.rows['v4']['train']
        for row in rows:
            row['group_id'] = self.rows['v6']['test'][0]['group_id']
        self.rewrite_split('v4','train',rows)
        with self.assertRaisesRegex(ValueError,'group appears in multiple splits'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_rewritten_v6_rows_and_manifest_cannot_change_public_frozen_candidate(self):
        rows = self.rows['v6']['train']
        rows[0]['state']['amount_cents'] += 100
        self.rewrite_split('v6','train',rows)
        with self.assertRaisesRegex(ValueError,'public frozen candidate'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_observed_selection_hash_mismatch_and_overwrite_are_rejected(self):
        path,key = self.locks['v4']
        lock = json.loads(path.read_text())
        lock[key]['selected_sha256']['test'] = '0'*64
        path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError,'regression selection changed'):
            self.prepare()
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
