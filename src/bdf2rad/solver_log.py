"""Evidence-based log classification; normal termination is not equivalence."""
import re


def analyze_log(text, source=''):
    text = text.replace('\r', '\n')
    warnings = sorted(set(int(x) for x in re.findall(r'WARNING ID\s*:\s*(\d+)', text)))
    errors = [int(x) for x in re.findall(r'(\d+)\s+ERROR\(S\)', text)]
    cycles = [int(x) for x in re.findall(r'TOTAL NUMBER OF CYCLES\s*:\s*(\d+)', text)]
    progress = re.findall(r'NC=\s*(\d+)\s+T=\s*([\d.Ee+\-]+)\s+DT=\s*([\d.Ee+\-]+)', text)
    problems = []
    if 1114 in warnings or 'THERE IS NO DEFINED PART' in text:
        problems.append({'code': 'NO_PART', 'message': 'Starter has no defined Part; full FE model is absent.'})
    if any(errors) or re.search(r'ERROR ID\s*:', text) or 'ABNORMAL TERMINATION' in text:
        problems.append({'code': 'SOLVER_ERROR', 'message': 'Solver reports an error or abnormal termination.'})
    # One cycle alone is not proof of failure: a deliberately short valid run
    # can end after one cycle. Combine it with independent missing-model evidence.
    if cycles and cycles[-1] <= 1 and any(p['code']=='NO_PART' for p in problems):
        problems.append({'code': 'EMPTY_MODEL_RUN', 'message': 'At most one cycle with no Part is not a structural simulation.'})
    normal = 'NORMAL TERMINATION' in text and 'ABNORMAL TERMINATION' not in text
    return {'source': source, 'starter_warning_ids': warnings,
            'engine_started': 'OpenRadioss Engine' in text,
            'engine_normal_termination': normal,
            'total_cycles': cycles[-1] if cycles else None,
            'last_printed_progress': {'cycle': int(progress[-1][0]), 'time': float(progress[-1][1]),
                                      'dt': float(progress[-1][2])} if progress else None,
            'simulation_status': 'FAILED' if problems else 'REQUIRES_VALIDATION',
            'physics_equivalent': False, 'issues': problems,
            'note': 'Printed progress may omit final time. Result file creation and normal exit do not prove physical validity.'}
