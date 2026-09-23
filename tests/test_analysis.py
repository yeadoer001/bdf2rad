from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from bdf2rad.analysis import analyze


class AnalysisTests(unittest.TestCase):
    def run_case(self, text):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        source=root/'case.bdf'
        source.write_text(text)
        return analyze(source,root/'out','utf-8'),root/'out'

    def test_all_unknowns_preserved_and_case_inheritance(self):
        result,out=self.run_case('SOL 402\nCEND\nLOAD=1\nBGSET=400\nSUBCASE 1\nSPC=7\nSUBCASE 2\nSPC=8\nBEGIN BULK\nNLCNTLG,INLY,1\nMYSTERY,9\nBGADD,400,401\nBGSET,401,1,2\nGRAV,1,0,1,0,0,-9810\nSPC,7,1,123,0\nENDDATA')
        self.assertEqual(result['counts']['MYSTERY'],1)
        self.assertEqual(result['case_control']['effective_subcases']['2']['LOAD']['value'],'1')
        self.assertEqual(result['selected_definitions']['2']['SPC']['status'],'MISSING')
        self.assertEqual(result['selected_definitions']['1']['BGSET']['definitions'][0]['children'][0]['definitions'][0]['card'],'BGSET')
        self.assertFalse(list(out.glob('*.rad')))
        self.assertIsNone(result['termination_time'])

    def test_cycles_reported(self):
        result,_=self.run_case('SOL 402\nCEND\nBGSET=1\nBEGIN BULK\nBGADD,1,2\nBGADD,2,1\nENDDATA')
        branch=result['selected_definitions']['GLOBAL']['BGSET']['definitions'][0]['children'][0]['definitions'][0]['children'][0]['definitions'][0]
        self.assertEqual(branch['status'],'CYCLE')

    def test_parse_failure_still_produces_report(self):
        result,out=self.run_case('NLCNTLG,INLY,1\nINCLUDE "missing.bdf"')
        self.assertEqual(result['status'],'PARSE_FAILED')
        self.assertTrue((out/'analysis.json').exists())

    def test_time_is_candidate_not_automatic_explicit_time(self):
        result,_=self.run_case('TSTEP1,401,.003,90,YES\nENDDATA')
        self.assertEqual(result['nonlinear_and_time_controls'][0]['end_time_candidate'],.003)
        self.assertIsNone(result['termination_time'])
