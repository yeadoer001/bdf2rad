from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from bdf2rad.solid import load_solid,write_solid


class SolidTests(unittest.TestCase):
    def test_real_parts_and_connectivity(self):
        root=Path(__file__).resolve().parents[1]
        model=load_solid(root/'benchmarks/elastic_tetra.bdf')
        with tempfile.TemporaryDirectory(dir=root/'tests') as tmp:
            a,b=write_solid(model,tmp,'tet',1e-6,1e-7)
            text=a.read_text()
            for keyword in ('/PART/1','/PROP/SOLID/1','/MAT/LAW1/1','/TETRA4/1'):
                self.assertIn(keyword,text)
            self.assertIn('/RUN/tet/1', b.read_text())

    def test_plasticity_and_high_order_fail_closed(self):
        root=Path(__file__).resolve().parents[1]
        base=(root/'benchmarks/elastic_tetra.bdf').read_text().replace('ENDDATA','')
        with tempfile.TemporaryDirectory(dir=root/'tests') as tmp:
            p=Path(tmp)/'input.bdf'
            for text in (base+'MATS1,1,,PLASTIC,100,1,1,200',
                         base.replace('CTETRA,1,1,1,2,3,4','CTETRA,1,1,1,2,3,4,1,2')):
                p.write_text(text)
                with self.assertRaises(ValueError):
                    load_solid(p)
