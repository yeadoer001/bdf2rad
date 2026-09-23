from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bdf2rad.model import IdManager, Model, MappingRegistry, Confidence
from bdf2rad.parser import Card
from bdf2rad.diagnostics import SourceLocation


class ModelTests(unittest.TestCase):
    def test_ids_preserved_and_remapped_stably(self):
        a, b = IdManager(10), IdManager(10)
        self.assertEqual(a.allocate("nodes", [15, 2, 1]), b.allocate("nodes", [1, 2, 15]))
        self.assertEqual(a.reference("nodes", 15), 3)
        self.assertEqual(a.reference("nodes", 2), 2)

    def test_duplicate_and_dangling(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            IdManager().allocate("nodes", [1, 1])
        with self.assertRaisesRegex(ValueError, "Dangling"):
            IdManager().reference("nodes", 1)

    def test_unknown_not_successful(self):
        card = Card("MAT9", ("1",), SourceLocation("input.bdf", 1), ("MAT9,1",), (1,), "free")
        result = MappingRegistry().map(card, Model())
        self.assertEqual(result.confidence, Confidence.UNSUPPORTED)
        self.assertIsNone(result.target)

    def test_namespace_isolation(self):
        manager = IdManager()
        manager.allocate("nodes", [1])
        manager.allocate("elements", [1])
        self.assertEqual(manager.reference("elements", 1), 1)
