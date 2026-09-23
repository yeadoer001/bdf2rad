from __future__ import annotations
import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

@dataclass(slots=True)
class PluginSpec:
    name: str
    source_cards: tuple[str, ...]
    order: int
    block_dir: Path
    manifest: dict
    module: ModuleType

class DiscoveryError(RuntimeError):
    pass

def discover_blocks(root: Path, recursive: bool=True) -> list[PluginSpec]:
    root = Path(root)
    if not root.exists():
        raise DiscoveryError(f'block directory does not exist: {root}')
    candidates = root.rglob('manifest.json') if recursive else root.glob('*/manifest.json')
    specs=[]
    for manifest_path in sorted(candidates):
        block_dir=manifest_path.parent
        try:
            manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        except Exception as exc:
            raise DiscoveryError(f'invalid manifest {manifest_path}: {exc}') from exc
        if manifest.get('type') != 'bdf2rad-block':
            continue
        name=str(manifest.get('name') or block_dir.name)
        translator_path=block_dir/'translator.py'
        if not translator_path.exists():
            raise DiscoveryError(f'{name}: missing translator.py')
        module_name=f'bdf2rad_dynamic_{name}_{abs(hash(str(translator_path)))}'
        spec=importlib.util.spec_from_file_location(module_name, translator_path)
        if spec is None or spec.loader is None:
            raise DiscoveryError(f'{name}: cannot load {translator_path}')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        if not hasattr(module,'translate'):
            raise DiscoveryError(f'{name}: translator.py must expose translate(model, ctx, plugin)')
        cards=manifest.get('source_cards',[])
        if isinstance(cards,str): cards=[cards]
        specs.append(PluginSpec(name,tuple(str(x).upper() for x in cards),int(manifest.get('order',1000)),block_dir,manifest,module))
    specs.sort(key=lambda x:(x.order,x.name))
    return specs

def describe(specs: list[PluginSpec]) -> list[dict]:
    return [{
        'name':s.name,'source_cards':list(s.source_cards),'order':s.order,
        'target_blocks':s.manifest.get('target_blocks',[]),
        'status':s.manifest.get('status','active'),
        'block_dir':str(s.block_dir)
    } for s in specs]
