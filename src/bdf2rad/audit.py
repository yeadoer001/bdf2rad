"""Disk-backed semantic inventory and explicitly incomplete node review export.

No physical definitions are invented to make an incomplete deck run.
"""
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import json
import sqlite3
import time

from .parser import BDFParser, nastran_float
from .deck import job_name, write_engine, preflight
from .paths import writable_path


REASONS = {
    'CHEXA': 'High-order connectivity and formulation need verified node-order mapping; no silent downgrade.',
    'CPENTA': '15-node wedge present; validated native target or explicit conversion policy required.',
    'CTETRA': 'TETRA10 native syntax exists; node order/formulation and regression evidence still required.',
    'PSOLID': 'Target solid property/formulation mapping not implemented.',
    'MAT1': 'Thermal expansion and elastic constants require unit-aware material mapping.',
    'MATS1': 'Plastic hardening definition must be mapped together with MAT1; elastic replacement forbidden.',
    'BCTSET': 'Contact surface, gap, friction and active BCSET selection require mapping.',
    'BCTADD': 'Resolve selected contact set union.',
    'BGSET': 'Gluing search tolerance and tie semantics require validated native interface mapping.',
    'BGADD': 'Resolve selected glue set union.',
    'BSURFS': 'Element faces defined by three nodes require topology-aware surface extraction.',
    'BCRPARA': 'Surface rigidity/offset semantics require validation.',
    'RBE2': 'Rigid constraints and dependent DOF require conflict checking.',
    'RBE3': 'Weighted interpolation must not be replaced by an unverified rigid body.',
    'CONM2': 'Mass, offset and full inertia tensor require mapping.',
    'TIC': 'Selected initial velocity/displacement and local DOF require mapping.',
    'SPC': 'Selected constraints require DOF mapping and conflict checking.',
    'GRAV': 'Active load direction and magnitude require function/group mapping.',
    'TSTEP1': 'SOL 402 step timing is not a direct explicit timestep parameter.',
    'NLCNTLG': 'Implicit SOL 402 control is not equivalent to explicit controls.',
    'NLCNTL2': 'Implicit nonlinear integration controls require explicit-case design.',
    'PARAM': 'Solver parameters need individual disposition.',
    'TEMPD': 'Initial temperature and thermal expansion must be considered.',
    'DESC': 'Description metadata retained.',
}


def review(model, output, encoding='gb18030', termination_time=None, output_interval=None):
    output = writable_path(output)
    output.mkdir(parents=True, exist_ok=True)
    # A fresh directory protects prior user results and partial-run databases.
    dbpath = output / 'model.sqlite'
    if dbpath.exists():
        raise FileExistsError(f'Use a new output directory; refusing to overwrite {dbpath}')
    db = sqlite3.connect(dbpath)
    db.executescript('CREATE TABLE nodes(id INTEGER PRIMARY KEY,x REAL,y REAL,z REAL,line INTEGER);'
                     'CREATE TABLE elements(id INTEGER PRIMARY KEY,card TEXT,pid INTEGER,nodes TEXT,line INTEGER);'
                     'CREATE TABLE refs(eid INTEGER,nid INTEGER);'
                     'CREATE TABLE properties(id INTEGER PRIMARY KEY,mid INTEGER);'
                     'CREATE TABLE materials(id INTEGER PRIMARY KEY);')
    reader = BDFParser(encoding=encoding)
    counts, orders = Counter(), Counter()
    first, errors = {}, []
    start = time.monotonic()
    timing = []
    try:
        with (output / 'preserved_cards.jsonl').open('w', encoding='utf-8') as retained:
            for card in reader.parse(model):
                n, f = card.name, card.fields + ('',) * max(0, 8-len(card.fields))
                counts[n] += 1
                if n == 'TSTEP1':
                    timing.append(f)
                first.setdefault(n, asdict(card.source))
                try:
                    if n == 'GRID':
                        if int(f[1] or 0) or int(f[5] or 0):
                            raise ValueError('Nonbasic coordinate system not implemented')
                        db.execute('INSERT INTO nodes VALUES(?,?,?,?,?)', (int(f[0]), *(nastran_float(x or '0') for x in f[2:5]), card.source.line))
                    elif n in ('CHEXA', 'CPENTA', 'CTETRA'):
                        nodes = [int(x) for x in f[2:] if x]
                        orders[f'{n}{len(nodes)}'] += 1
                        db.execute('INSERT INTO elements VALUES(?,?,?,?,?)', (int(f[0]), n, int(f[1]), json.dumps(nodes), card.source.line))
                        db.executemany('INSERT INTO refs VALUES(?,?)', ((int(f[0]), node) for node in nodes))
                        retained.write(json.dumps(asdict(card), ensure_ascii=False)+'\n')
                    else:
                        if n == 'PSOLID':
                            db.execute('INSERT INTO properties VALUES(?,?)', (int(f[0]), int(f[1])))
                        elif n == 'MAT1':
                            db.execute('INSERT INTO materials VALUES(?)', (int(f[0]),))
                        retained.write(json.dumps(asdict(card), ensure_ascii=False)+'\n')
                except (ValueError, sqlite3.IntegrityError) as exc:
                    errors.append({'source': asdict(card.source), 'card': n, 'error': str(exc)})
                    if n == 'GRID':
                        retained.write(json.dumps(asdict(card), ensure_ascii=False)+'\n')
            db.commit()
        missing_nodes = db.execute('SELECT count(*) FROM refs r LEFT JOIN nodes n ON r.nid=n.id WHERE n.id IS NULL').fetchone()[0]
        missing_props = db.execute('SELECT count(*) FROM elements e LEFT JOIN properties p ON e.pid=p.id WHERE p.id IS NULL').fetchone()[0]
        missing_mats = db.execute('SELECT count(*) FROM properties p LEFT JOIN materials m ON p.mid=m.id WHERE m.id IS NULL').fetchone()[0]
        bounds = db.execute('SELECT min(x),max(x),min(y),max(y),min(z),max(z) FROM nodes').fetchone()
        # Do not publish runnable .rad names for a node-only incomplete model.
        job = job_name(model) + '_INCOMPLETE_nodes'
        deck = output / (job + '_0000.rad.draft')
        with deck.open('w', encoding='ascii') as rad:
            rad.write('#RADIOSS STARTER\n# INCOMPLETE NODE REVIEW ONLY - NOT A CONVERTED SIMULATION MODEL\n')
            rad.write('# Elements, properties, materials, contact and loads are NOT mapped.\n')
            rad.write(f'/BEGIN\n{job}\n      2022         0\n')
            for _ in range(2):
                rad.write(f'{"kg":>20}{"mm":>20}{"s":>20}\n')
            rad.write('/NODE\n')
            for nid,x,y,z,_ in db.execute('SELECT * FROM nodes ORDER BY id'):
                rad.write(f'{nid:10d}{x:20.12E}{y:20.12E}{z:20.12E}\n')
            rad.write('/END\n')
        # TSTEP1 end time is retained as a candidate, not an explicit stable dt.
        # Multiple steps require an explicit caller-supplied end time.
        candidate = termination_time
        timing_source = 'explicit CLI value'
        if candidate is None and len(timing) == 1:
            candidate = nastran_float(timing[0][1])
            timing_source = 'TSTEP1 end time candidate; SOL402/explicit equivalence NOT VERIFIED'
        engine = output / (job + '_0001.rad.draft')
        if candidate is not None:
            interval = output_interval if output_interval is not None else candidate / 100
            write_engine(engine, job, candidate, interval)
        checks = preflight(deck, engine)
        report = {'status': 'INCOMPLETE', 'conversion_success': False,
                  'physics_equivalent': False, 'engine_allowed': False,
                  'source': str(Path(model).resolve()), 'encoding': encoding,
                  'counts': dict(counts), 'element_orders': dict(orders),
                  'mesh_reference_checks': {'missing_node_references': missing_nodes,
                      'missing_property_references': missing_props, 'missing_material_references': missing_mats},
                  'bounds_xyz_min_max': bounds, 'errors': errors,
                  'capabilities': [{'card': n, 'count': count, 'status': 'REQUIRES_VALIDATION' if n=='GRID' else 'UNSUPPORTED',
                    'first_source': first[n], 'reason': 'Basic node coordinates exported for review only.' if n=='GRID' else REASONS.get(n, 'UNKNOWN_CARD; original retained.')}
                    for n,count in counts.items()],
                  'control_lines': [{'source':asdict(s),'raw':raw} for s,raw in reader.control_lines],
                  'starter': 'NOT_RUN', 'engine': 'NOT_RUN_INCOMPLETE_DRAFT',
                  'elapsed_seconds': time.monotonic()-start, 'artifact': str(deck),
                  'engine_artifact': str(engine) if engine.exists() else None,
                  'termination_time': candidate, 'timing_source': timing_source,
                  'preflight': checks,
                  'warning_1114': 'ROOT_CAUSE_UNRESOLVED: missing mapped parts/elements/materials; no runnable deck published',
                  'artifact_kind': 'REVIEW_DRAFT_NOT_SOLVER_INPUT'}
        (output/'conversion_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        return report
    finally:
        db.close()
