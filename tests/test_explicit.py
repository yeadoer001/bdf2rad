from pathlib import Path
import sys, tempfile, unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from bdf2rad.semantic import scan
from bdf2rad.converter import convert

class ExplicitTests(unittest.TestCase):
    def test_records_and_material_fields(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            p=Path(tmp)/'case.bdf'
            p.write_text('MAT1,1,1000,,.3,2e-6,6e-5\nMATS1,1,,PLASTIC,100,1,1,200\nTIC,401,1,3,,-4430\nTIC,401,2,3,,-4430\nSPC,317,1,123,0\nSPC,317,2,123,0\n')
            m=scan(p)
            self.assertEqual(m.materials[1].data['rho'],2e-6)
            self.assertEqual(m.plasticity[1].data['limit1'],200)
            self.assertEqual(len(m.initial_conditions),2)
            self.assertEqual(len(m.boundary_conditions),2)
            self.assertTrue(all(e.data['velocity']==-4430 for e in m.initial_conditions.values()))
    def test_duplicate_unknown_and_publication_gate(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            p=Path(tmp)/'case.bdf'; p.write_text('GRID,1,,0,0,0\nGRID,1,,1,0,0\nMYSTERY,1\n')
            m=scan(p)
            self.assertEqual(len(m.unsupported),2)
            r=convert(p,Path(tmp)/'out/case_0000.rad')
            self.assertEqual(r['status'],'INCOMPLETE')
            self.assertFalse(list((Path(tmp)/'out').glob('*.rad')))
    def test_external_output_rejected_before_write(self):
        with self.assertRaises(ValueError):
            convert('absent.bdf',Path(__file__).resolve().parents[2]/'external/zero.rad')

    def test_selected_tic_and_set_cycle(self):
        from bdf2rad.active_case import resolve
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            p=Path(tmp)/'case.bdf'
            p.write_text('SOL 402\nCEND\nIC=401\nBGSET=1\nBEGIN BULK\nGRID,1,,0,0,0\nTIC,401,1,3,,-4430\nTIC,402,1,3,,123\nBGADD,1,2\nBGADD,2,1\n')
            result=resolve(scan(p))
            self.assertEqual(result['counts']['TIC'],1)
            self.assertEqual(result['initial_velocity_clusters'],[{'vector':[0.,0.,-4430.],'node_count':1}])
            self.assertTrue(any('cycle' in x for x in result['errors']))

    def test_scoped_output_policy(self):
        from bdf2rad.paths import OutputPolicy, writable_path
        root=Path(__file__).resolve().parents[2]/'authorized'
        policy=OutputPolicy((root,))
        self.assertEqual(writable_path(root/'x.rad',policy),root/'x.rad')
        with self.assertRaises(ValueError): writable_path(root/'../other/x.rad',policy)
