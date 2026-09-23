from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from bdf2rad.deck import write_engine, preflight, job_name


class DeckTests(unittest.TestCase):
    def test_engine_matches_root_and_records_time(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            engine = Path(tmp)/'case_0001.rad.draft'
            write_engine(engine, 'case', .003, .00003)
            text = engine.read_text()
            self.assertIn('/RUN/case/1\n', text)
            self.assertIn('3.000000000000E-03', text)
            self.assertIn('/ANIM/DT', text)
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                write_engine(Path(tmp)/'case_0001.rad', 'case', .003, .00003)
            for invalid in (0, -1, float('nan'), float('inf')):
                with self.assertRaises(ValueError):
                    write_engine(engine, 'case', invalid, .00003)

    def test_node_deck_cannot_pass_preflight(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            starter = Path(tmp)/'case_0000.rad'
            starter.write_text('/BEGIN\ncase\n/NODE\n/END\n')
            report = preflight(starter, Path(tmp)/'case_0001.rad')
            self.assertFalse(report['solver_launch_allowed'])
            self.assertIn('NO_PART_WARNING_1114', [x['code'] for x in report['issues']])

    def test_name_is_based_on_input(self):
        self.assertEqual(job_name('Solution 3-1.bdf'), 'Solution_3_1')
