from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from bdf2rad.solver_log import analyze_log
from bdf2rad.paths import writable_path, WORKSPACE


class LogTests(unittest.TestCase):
    def test_normal_exit_with_no_parts_is_failed(self):
        result = analyze_log('WARNING ID : 1114\r\n0 ERROR(S)\nOpenRadioss Engine\n'
                             'NC= 0 T= 0.0000E+00 DT= 1.0000E+06\n'
                             'NORMAL TERMINATION\nTOTAL NUMBER OF CYCLES : 1')
        self.assertTrue(result['engine_normal_termination'])
        self.assertEqual(result['simulation_status'], 'FAILED')
        self.assertEqual(result['last_printed_progress']['dt'], 1e6)

    def test_short_run_is_not_automatically_failure_or_verified(self):
        result = analyze_log('NORMAL TERMINATION\nTOTAL NUMBER OF CYCLES : 1')
        self.assertEqual(result['simulation_status'], 'REQUIRES_VALIDATION')

    def test_abnormal_not_normal(self):
        result = analyze_log('ABNORMAL TERMINATION')
        self.assertFalse(result['engine_normal_termination'])
        self.assertEqual(result['simulation_status'], 'FAILED')

    def test_output_boundary(self):
        self.assertEqual(writable_path(WORKSPACE/'reports'), WORKSPACE/'reports')
        with self.assertRaises(ValueError):
            writable_path(WORKSPACE.parent/'not-project')
