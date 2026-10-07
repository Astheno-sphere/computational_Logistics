import copy
import unittest
from scripts.summarize_provider_quality import summarize


class QualityTest(unittest.TestCase):
    def test_missing_error_soft_targets_and_probability_rounding_are_separate(self):
        golds = [{'request_id':str(i),'request_sha256':'hash','target':target,
                  'answer_keys':['x','y'],'source':'domain','split':'test','group_id':str(i),'kind':'choice'}
                 for i,target in enumerate(([0,1],[.5,.5],[0,1],[0,1]))]
        samples = [{'request_id':'0','request_sha256':'hash','phase':'measured','success':False,
                    'http_status':200,'error':'probabilities do not sum to one','mode':'jev',
                    'response':{'model':'jev','answers':{'decision':{'type':'choice','choice':'y','probabilities':{'x':.01,'y':.98}}}}},
                   {'request_id':'1','request_sha256':'hash','phase':'measured','success':True,'decisions':{'decision':'x'}},
                   {'request_id':'2','request_sha256':'hash','phase':'measured','success':False,'http_status':500}]
        original=copy.deepcopy(samples)
        strict=summarize(golds,samples)
        decision=summarize(golds,samples,categorical_only=True)
        self.assertEqual(samples,original)
        self.assertEqual(strict['pending_count'],1)
        self.assertEqual(strict['overall']['hard_targets'],2)
        self.assertEqual(strict['overall']['hard_accuracy_including_errors'],0)
        self.assertEqual(decision['overall']['hard_accuracy_including_errors'],.5)
        self.assertEqual(decision['overall']['soft_targets'],1)
        self.assertEqual(decision['overall']['usable_decisions_with_probability_mass_failure'],1)
        self.assertEqual(decision['overall']['errors'],1)


if __name__ == '__main__':
    unittest.main()
