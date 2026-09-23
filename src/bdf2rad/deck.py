"""Engine control generation and minimum structural preflight.

Engine control syntax follows the official ACCELERO miniqa example. This
preflight is necessary, but is not a substitute for Starter or physics checks.
"""
from pathlib import Path
import math
import re
from .paths import writable_path


def job_name(source):
    return re.sub(r'[^A-Za-z0-9_]+', '_', Path(source).stem).strip('_') or 'model'


def write_engine(path, job, termination_time, output_interval, *, incomplete=True, output_policy=None):
    path = writable_path(path, output_policy)
    if incomplete and path.suffix.lower() != '.draft':
        raise ValueError('Incomplete Engine controls must use .draft, never a runnable .rad name')
    if not re.fullmatch(r'[A-Za-z0-9_]+', job):
        raise ValueError('Invalid Radioss job name')
    if any(not math.isfinite(x) or x <= 0 for x in (termination_time, output_interval)):
        raise ValueError('Termination time and output interval must be finite and positive')
    if output_interval > termination_time:
        raise ValueError('Output interval exceeds termination time')
    text = '#RADIOSS ENGINE\n'
    if incomplete:
        text += '# INCOMPLETE MODEL: controls only; do not launch until conversion_report.json permits it.\n'
    text += (f'/RUN/{job}/1\n{termination_time:20.12E}\n/VERS/2022\n'
             f'/ANIM/DT\n{0.:20.12E}{output_interval:20.12E}\n'
             '/ANIM/VECT/VEL\n/ANIM/ELEM/VONM\n'
             f'/TFILE/4\n{output_interval:20.12E}\n')
    path.write_text(text, encoding='ascii')


def preflight(starter, engine):
    keywords = set()
    with Path(starter).open(encoding='ascii') as stream:
        for line in stream:
            if line.startswith('/'):
                keywords.add(line.strip().split('/')[1])
    issues = []
    for key, code in [('PART', 'NO_PART_WARNING_1114'), ('PROP', 'NO_PROPERTY'),
                      ('MAT', 'NO_MATERIAL'), ('NODE', 'NO_NODE')]:
        if key not in keywords:
            issues.append({'code': code, 'message': f'Missing /{key}; incomplete Starter model.'})
    if not keywords.intersection({'BRICK', 'BRICK20', 'TETRA4', 'TETRA10', 'PENTA6', 'SHELL', 'SH3N', 'TRUSS', 'BEAM', 'SPRING'}):
        issues.append({'code': 'NO_ELEMENTS', 'message': 'No supported element block in Starter.'})
    if not Path(engine).is_file():
        issues.append({'code': 'NO_ENGINE_FILE', 'message': 'Missing 0001 Engine controls.'})
    elif Path(engine).suffix.lower() != '.rad':
        issues.append({'code': 'ENGINE_DRAFT_ONLY', 'message': 'Engine controls are a draft, not a runnable model.'})
    return {'status': 'FAILED' if issues else 'STRUCTURE_PRESENT_NOT_VALIDATED',
            'issues': issues, 'solver_launch_allowed': False}
