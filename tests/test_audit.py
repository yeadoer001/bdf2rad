import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from bdf2rad.audit import review


class AuditTests(unittest.TestCase):
    def test_unknown_and_missing_reference_block_success(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            root=Path(tmp)
            model=root/'case.bdf'
            model.write_text('GRID,1,,0,0,0\nCTETRA,2,8,1,2,3,4\nMYSTERY,3,4\nENDDATA\n')
            report=review(model,root/'output',encoding='utf-8',termination_time=.003)
            self.assertFalse(report['conversion_success'])
            self.assertFalse(report['engine_allowed'])
            self.assertEqual(report['mesh_reference_checks']['missing_node_references'],3)
            self.assertEqual(report['mesh_reference_checks']['missing_property_references'],1)
            retained=(root/'output/preserved_cards.jsonl').read_text()
            self.assertIn('MYSTERY',retained)
            self.assertIn('CTETRA',retained)
            self.assertIn('INCOMPLETE',Path(report['artifact']).read_text())
            self.assertTrue(Path(report['engine_artifact']).exists())
            self.assertIn('/RUN/case_INCOMPLETE_nodes/1', Path(report['engine_artifact']).read_text())
            self.assertEqual(report['preflight']['status'], 'FAILED')
            with self.assertRaises(FileExistsError):
                review(model,root/'output')
