from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bdf2rad.parser import BDFParser, nastran_float
from bdf2rad.diagnostics import BDFError


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / "tests")
        self.root = Path(self.temp.name)
        self.reader = BDFParser()

    def tearDown(self):
        self.temp.cleanup()

    def read(self, text):
        p = self.root / "input.bdf"
        p.write_text(text, encoding="utf-8")
        return list(self.reader.parse(p))

    def test_small(self):
        line = "".join(f"{s:<8}" for s in ("GRID", "101", "", "1.0-3", "2.", "3."))
        card, = self.read(line)
        self.assertEqual(card.fields[:5], ("101", "", "1.0-3", "2.", "3."))
        self.assertEqual(card.source.line, 1)
        self.assertEqual(card.raw, (line,))

    def test_simcenter_empty_large_continuation(self):
        line = f"{'TSTEP1*':8}" + ''.join(f'{x:>16}' for x in ('401', '.003', '90', 'YES')) + '+'
        card, = self.read(line + '\n*')
        self.assertEqual(card.fields[:4], ('401', '.003', '90', 'YES'))
        self.assertEqual(card.continuation, ('*',))

    def test_simcenter_preamble_and_end_checksum(self):
        cards = self.read('NASTRAN SYSTEM(674)=1\nID,NASTRAN,Example\nSOL 402\nCEND\nBEGIN BULK\nGRID,1,,0,0,0\nENDDATA abd490b7')
        self.assertEqual([c.name for c in cards], ['GRID'])
        self.assertEqual(self.reader.control_lines[-1][1], 'ENDDATA abd490b7')

    def test_large_continuation_and_new_small_card(self):
        a = f"{'GRID*':8}" + "".join(f"{x:>16}" for x in ("1", "", "1.", "2.")) + "*A"
        b = f"{'*A':8}" + "".join(f"{x:>16}" for x in ("3.", "", "", ""))
        c = "".join(f"{s:<8}" for s in ("GRID", "2", "", "4.", "5.", "6."))
        cards = self.read(a + "\n$ comment\n" + b + "\n" + c)
        self.assertEqual(cards[0].fields[4], "3.")
        self.assertEqual(cards[0].line_numbers, (1, 3))
        self.assertEqual(cards[1].format, "small")
        self.assertEqual(cards[1].fields[0], "2")

    def test_blank_continuation(self):
        a = "".join(f"{s:<8}" for s in ("CHEXA", "1", "2", "1", "2", "3", "4", "5", "6"))
        b = "".join(f"{s:<8}" for s in ("", "7", "8"))
        card, = self.read(a + "\n" + b)
        self.assertEqual(card.fields[8:10], ("7", "8"))

    def test_free_continuation(self):
        card, = self.read("CHEXA,1,2,1,2,3,4,5,6,+A\n+A,7,8")
        self.assertEqual(card.fields, ("1", "2", "1", "2", "3", "4", "5", "6", "7", "8"))

    def test_include_relative_nested_and_dollar_in_filename(self):
        (self.root / "part$1.bdf").write_text("GRID,2,,0,0,0", encoding="utf-8")
        cards = self.read("INCLUDE 'part$1.bdf'\nGRID,1,,1,0,0")
        self.assertEqual([c.fields[0] for c in cards], ["2", "1"])
        self.assertEqual(Path(cards[0].source.file).name, "part$1.bdf")
        self.assertEqual(len(self.reader.include_tree), 1)

    def test_multiline_include(self):
        (self.root / "longname.bdf").write_text("GRID,1,,0,0,0", encoding="utf-8")
        self.assertEqual(len(self.read('INCLUDE "long\nname.bdf"')), 1)

    def test_cycle(self):
        with self.assertRaisesRegex(BDFError, "INCLUDE_CYCLE"):
            self.read("INCLUDE 'input.bdf'")

    def test_missing_include(self):
        with self.assertRaisesRegex(BDFError, "INCLUDE_IO"):
            self.read("INCLUDE 'absent.bdf'")

    def test_bad_continuation(self):
        for text, code in (("+,1", "ORPHAN_CONTINUATION"),
                           ("CHEXA,1,2,1,2,3,4,5,6,+A\n+B,7,8", "CONTINUATION_MISMATCH"),
                           ("CHEXA,1,2,1,2,3,4,5,6,+A", "MISSING_CONTINUATION")):
            with self.subTest(code=code), self.assertRaisesRegex(BDFError, code):
                self.read(text)

    def test_unknown_preserved(self):
        card, = self.read("MYSTERY,1,2,$original")
        self.assertEqual(card.name, "MYSTERY")
        self.assertEqual(card.raw, ("MYSTERY,1,2,$original",))

    def test_control_preserved(self):
        cards = self.read("SOL 101\nCEND\nSUBCASE 1\n SPC = 9\nBEGIN BULK\nGRID,1,,0,0,0\nENDDATA")
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(self.reader.control_lines), 6)

    def test_trailing_data_not_lost(self):
        with self.assertRaisesRegex(BDFError, "DATA_AFTER_ENDDATA"):
            self.read("GRID,1,,0,0,0\nENDDATA\nGRID,2,,1,0,0")

    def test_numeric_formats(self):
        for value, expected in (("1.25-3", .00125), ("-2.0+2", -200), ("1D-3", .001), (".7+1", 7)):
            self.assertAlmostEqual(nastran_float(value), expected)
        for value in ("NaN", "inf", "1.0x", ""):
            with self.assertRaises(ValueError):
                nastran_float(value)


if __name__ == "__main__":
    unittest.main()
