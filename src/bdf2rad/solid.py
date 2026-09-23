"""Restricted elastic TETRA4 conversion benchmark, not a SOL402 converter.

Unsupported physics fail closed before a solver deck is published.
"""
from dataclasses import dataclass, field
from .parser import BDFParser, nastran_float
from .paths import writable_path
from .deck import job_name, write_engine


@dataclass
class SolidModel:
    nodes: dict = field(default_factory=dict)
    elements: dict = field(default_factory=dict)
    properties: dict = field(default_factory=dict)
    materials: dict = field(default_factory=dict)


def put(table, key, value):
    key = int(key)
    if key <= 0 or key in table:
        raise ValueError(f'Invalid or duplicate ID {key}')
    table[key] = value


def node(model, f):
    if any(x not in ('', '0') for x in (f[1], f[5], f[6], f[7])):
        raise ValueError('GRID local coordinates, PS or SEID not supported')
    put(model.nodes, f[0], tuple(nastran_float(x or '0') for x in f[2:5]))


def tetra(model, f):
    if len(f) > 8 and any(f[8:]) or any(f[6:8]):
        raise ValueError('High-order CTETRA requires a separately validated mapper; downgrade forbidden')
    put(model.elements, f[0], (int(f[1]), tuple(int(x) for x in f[2:6])))


def prop(model, f):
    if f[2] not in ('', '0') or any(f[3:6]) or f[6] not in ('', 'SMECH') or any(f[7:]):
        raise ValueError('Nondefault PSOLID formulation not supported')
    put(model.properties, f[0], int(f[1]))


def material(model, f):
    if any(nastran_float(x) != 0 for x in f[5:] if x):
        raise ValueError('MAT1 thermal, damping or strength fields require another mapper')
    e, nu, rho = (nastran_float(f[i]) for i in (1, 3, 4))
    if e <= 0 or rho <= 0 or not -1 < nu < .5:
        raise ValueError('Invalid elastic constants or density')
    if f[2] and abs(nastran_float(f[2])-e/(2*(1+nu))) > e*1e-6:
        raise ValueError('Inconsistent E/G/NU')
    put(model.materials, f[0], (e, nu, rho))


MAPPERS = {'GRID': node, 'CTETRA': tetra, 'PSOLID': prop, 'MAT1': material}


def load_solid(source, encoding='utf-8-sig'):
    model = SolidModel()
    parser = BDFParser(encoding=encoding)
    for card in parser.parse(source):
        if card.name not in MAPPERS:
            raise ValueError(f'{card.source.file}:{card.source.line}: UNSUPPORTED {card.name}')
        try:
            MAPPERS[card.name](model, card.fields + ('',)*max(0, 8-len(card.fields)))
        except (ValueError, IndexError) as exc:
            raise ValueError(f'{card.source.file}:{card.source.line}: {card.name}: {exc}') from exc
    if any(not raw.strip().upper().startswith(('BEGIN BULK', 'BEGIN,BULK', 'ENDDATA'))
           for _, raw in parser.control_lines):
        raise ValueError('Case/executive control requires semantic mapping; bulk-only benchmark accepted')
    if not all((model.nodes, model.elements, model.properties, model.materials)):
        raise ValueError('Nodes, elements, properties and materials are required')
    for pid, mid in model.properties.items():
        if mid not in model.materials:
            raise ValueError(f'Property {pid} references absent material {mid}')
    for eid, (pid, nodes) in model.elements.items():
        if pid not in model.properties or len(set(nodes)) != 4 or any(n not in model.nodes for n in nodes):
            raise ValueError(f'Invalid element references: {eid}')
        a,b,c,d = (model.nodes[n] for n in nodes)
        u,v,w = ([p[i]-a[i] for i in range(3)] for p in (b,c,d))
        det = u[0]*(v[1]*w[2]-v[2]*w[1])-u[1]*(v[0]*w[2]-v[2]*w[0])+u[2]*(v[0]*w[1]-v[1]*w[0])
        if det <= 0:
            raise ValueError(f'Nonpositive tetra volume: {eid}')
    return model


def write_solid(model, directory, job, end_time, interval):
    directory = writable_path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    starter, engine = (directory/f'{job}_{i:04d}.rad' for i in (0,1))
    if starter.exists() or engine.exists():
        raise FileExistsError('Refusing to overwrite existing benchmark deck')
    lines = ['#RADIOSS STARTER', '# Elastic tetra benchmark; formulation equivalence requires validation',
             '/BEGIN', job, f'{2022:10d}{0:10d}', f'{"kg":>20}{"mm":>20}{"s":>20}',
             f'{"kg":>20}{"mm":>20}{"s":>20}']
    for mid,(e,nu,rho) in sorted(model.materials.items()):
        lines += [f'/MAT/LAW1/{mid}', f'MAT1_{mid}', f'{rho:20.12E}', f'{e:20.12E}{nu:20.12E}']
    for pid,mid in sorted(model.properties.items()):
        lines += [f'/PROP/SOLID/{pid}', f'PSOLID_{pid}',
                  '         0         0                   0                   0         0         0                   0',
                  f'{0.:20.12E}'*5, f'{0.:20.12E}{0:10d}{0:10d}',
                  f'/PART/{pid}', f'PART_{pid}', f'{pid:10d}{mid:10d}{0:10d}']
    lines += ['/NODE']
    for nid,xyz in sorted(model.nodes.items()):
        lines += [f'{nid:10d}'+''.join(f'{x:20.12E}' for x in xyz)]
    for pid in sorted(model.properties):
        elems = [(eid,nodes) for eid,(p,nodes) in sorted(model.elements.items()) if p==pid]
        if elems:
            lines += [f'/TETRA4/{pid}']
            lines += [''.join(f'{x:10d}' for x in (eid,*nodes)) for eid,nodes in elems]
    lines += ['/END']
    write_engine(engine, job, end_time, interval, incomplete=False)
    starter.write_text('\n'.join(lines)+'\n', encoding='ascii')
    return starter, engine
