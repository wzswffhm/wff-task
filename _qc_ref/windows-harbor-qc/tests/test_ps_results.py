import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from qc_utils import save
from run_trials import formal_result

class PowerShellResultTests(unittest.TestCase):
    def evaluate(self, report, reward):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save(root/'tests/rubric.json', {'required_fail_to_pass':['f'], 'required_pass_to_pass':['p']})
            save(root/'verifier/report.json', report)
            return formal_result({'trial_root':str(root), 'rewards':{'reward':reward}}, {'root':str(root)})

    def report(self):
        return {'status':'VALID', 'score':1, 'f2p':['f'], 'p2p':['p'],
                'tests':[{'test_id':'f','status':'PASS'}, {'test_id':'p','status':'PASS'}]}

    def test_complete_powershell_one_and_zero(self):
        report = self.report()
        self.assertEqual(self.evaluate(report,1)['score'],1)
        report['score']=0
        report['tests'][0]['status']='FAIL'
        self.assertEqual(self.evaluate(report,0)['score'],0)

    def test_incomplete_duplicate_skip_and_forged_required_invalid(self):
        for mutation in ('missing','duplicate','SKIP','group-change'):
            report=self.report()
            if mutation=='missing': report['tests'].pop()
            elif mutation=='duplicate': report['tests'][1]=copy.deepcopy(report['tests'][0])
            elif mutation=='SKIP': report['tests'][0]['status']='SKIP'
            else: report['p2p']=[]
            with self.subTest(mutation=mutation):
                self.assertEqual(self.evaluate(report,1)['validity'],'INVALID')

    def test_boolean_or_reward_mismatch_is_invalid(self):
        report=self.report()
        report['score']=True
        self.assertEqual(self.evaluate(report,1)['validity'],'INVALID')
        self.assertEqual(self.evaluate(self.report(),0)['validity'],'INVALID')

    def aggregate(self, report, reward):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            save(root/'tests/rubric.json',{'items':[{'test_ids':['f2p-f','p2p-p']}]})
            target=root/'verifier/test-stdout.txt'
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps(report),encoding='utf-8-sig')
            return formal_result({'trial_root':str(root),'rewards':{'reward':reward}},{'root':str(root)})

    def aggregate_report(self):
        return {'schema_version':'aggregate-v1','run_validity':'VALID','formal_score':1,
                'total':2,'passed':2,'failed':0,'invalid':0,
                'cases':[{'test_id':'f2p-f','passed':True},{'test_id':'p2p-p','passed':True}]}

    def test_complete_stdout_aggregate_one_and_zero(self):
        report=self.aggregate_report()
        self.assertEqual(self.aggregate(report,1)['score'],1)
        report.update(formal_score=0,passed=1,failed=1)
        report['cases'][0]['passed']=False
        result=self.aggregate(report,0)
        self.assertEqual(result['score'],0)
        self.assertEqual(result['cases'][1]['group'],'P2P')

    def test_empty_missing_duplicate_and_nonboolean_aggregate_are_invalid(self):
        for mutation in ('empty','missing','duplicate','nonboolean'):
            report=self.aggregate_report()
            if mutation=='empty': report.update(cases=[],total=0,passed=0)
            elif mutation=='missing': report['cases'].pop()
            elif mutation=='duplicate': report['cases'][1]=copy.deepcopy(report['cases'][0])
            else: report['cases'][0]['passed']='PASS'
            with self.subTest(mutation=mutation):
                self.assertEqual(self.aggregate(report,1)['validity'],'INVALID')

    def test_aggregate_counter_and_reward_mismatch_are_invalid(self):
        report=self.aggregate_report()
        report['passed']=1
        self.assertEqual(self.aggregate(report,1)['validity'],'INVALID')
        self.assertEqual(self.aggregate(self.aggregate_report(),0)['validity'],'INVALID')

    def test_malformed_aggregate_objects_ids_and_counts_are_invalid(self):
        for mutation in ('object','id','count'):
            report=self.aggregate_report()
            if mutation=='object': report['cases'][0]=None
            elif mutation=='id': report['cases'][0]['test_id']=[]
            else: report['invalid']=False
            with self.subTest(mutation=mutation):
                self.assertEqual(self.aggregate(report,1)['validity'],'INVALID')

if __name__=='__main__': unittest.main()
