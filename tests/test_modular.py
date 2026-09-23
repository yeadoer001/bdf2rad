from pathlib import Path
import json, tempfile
from bdf2rad.core.discovery import discover_blocks
from bdf2rad.parser import read_model
from bdf2rad.core.types import TranslationContext

ROOT=Path(__file__).resolve().parents[1]

def test_discovers_all_current_blocks():
    specs=discover_blocks(ROOT/'blocks')
    names={s.name for s in specs}
    assert 'grid' in names and 'bsurfs' in names and 'rbe3' in names
    assert len(specs) >= 20

def test_no_rad_files_inside_repo():
    assert not list(ROOT.rglob('*.rad'))

def test_plugin_hot_add(tmp_path):
    d=tmp_path/'blocks'/'DEMO';d.mkdir(parents=True)
    (d/'manifest.json').write_text(json.dumps({'type':'bdf2rad-block','name':'demo','source_cards':['DEMO'],'order':1,'target_blocks':['/DEMO']}),encoding='utf-8')
    (d/'template.json').write_text(json.dumps({'lines':['/DEMO/{{ID}}','{{VALUE}}']}),encoding='utf-8')
    (d/'translator.py').write_text('from bdf2rad.core.types import RadBlock\ndef translate(model,ctx,plugin):\n return [RadBlock("/DEMO/1",["/DEMO/1","1"],1,plugin.name,plugin.source_cards)],[{"card":"DEMO"}]',encoding='utf-8')
    specs=discover_blocks(tmp_path/'blocks')
    assert specs[0].name=='demo'

def test_real_bdf_inventory():
    bdf=Path('/mnt/data/Solution 3-1(6).bdf')
    if not bdf.exists(): return
    m=read_model(bdf,'gb18030')
    assert len(m.nodes)==551461
    assert len(m.elements)==257641
    assert m.card_counts['RBE3']==14
    assert m.card_counts['BSURFS']==420
