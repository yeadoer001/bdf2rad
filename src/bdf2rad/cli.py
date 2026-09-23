import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from .diagnostics import BDFError
from .parser import BDFParser
from .runtime import discover
from .paths import WORKSPACE, writable_path, OutputPolicy

# Default locations are module-level configuration, not hidden inside main.
DEFAULT_ANALYSIS_OUTPUT = WORKSPACE / 'reports' / 'analysis'
DEFAULT_REVIEW_OUTPUT = WORKSPACE / 'reports' / 'review'


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bridge", description="BDF2RAD-X staged implementation")
    commands = parser.add_subparsers(dest="command", required=True)
    analysis = commands.add_parser('analyze', help='Full model inventory and case-control analysis; no benchmark defaults')
    analysis.add_argument('model', type=Path)
    analysis.add_argument('--output', type=Path, default=DEFAULT_ANALYSIS_OUTPUT)
    analysis.add_argument('--encoding', default='gb18030')
    doctor = commands.add_parser("doctor", help="Discover environment without changing the installation")
    doctor.add_argument("--search-root", action="append", default=[])
    doctor.add_argument("--online", action="store_true")
    doctor.add_argument("--solver-help", action="store_true")
    doctor.add_argument("--output", type=Path, default=Path("reports/environment"))
    inspect = commands.add_parser("inspect", help="Lexical inventory; no physical mapping claims")
    inspect.add_argument("model", type=Path)
    inspect.add_argument("--output", type=Path, default=Path("reports/inspect"))
    inspect.add_argument("--encoding", default="utf-8-sig")
    review = commands.add_parser('review', help='Disk-backed semantic audit and incomplete node review RAD')
    review.add_argument('model', type=Path, nargs='?', default=None)
    review.add_argument('--input-dir', type=Path, default=Path('E:/openradioss/input'))
    review.add_argument('--output', type=Path, default=DEFAULT_REVIEW_OUTPUT)
    review.add_argument('--encoding', default='gb18030')
    review.add_argument('--termination-time', type=float)
    review.add_argument('--output-interval', type=float)
    logs = commands.add_parser('analyze-log', help='Classify solver execution separately from simulation validity')
    logs.add_argument('log', type=Path)
    logs.add_argument('--output', type=Path, default=WORKSPACE / 'reports/log_analysis')
    logs.add_argument('--encoding', default='utf-8-sig')
    solid = commands.add_parser('solid-benchmark', help='Restricted bulk-only elastic TETRA4 benchmark, kg/mm/s')
    solid.add_argument('model', type=Path)
    solid.add_argument('--output', type=Path, default=WORKSPACE/'reports/solid_benchmark')
    solid.add_argument('--termination-time', type=float, required=True)
    solid.add_argument('--output-interval', type=float, required=True)
    conv = commands.add_parser('convert-explicit', help='Convert SOL402 BDF to OpenRadioss explicit Starter + Engine')
    conv.add_argument('model', type=Path)
    conv.add_argument('--output', type=Path, required=True, help='Starter output path, usually *_0000.rad')
    conv.add_argument('--encoding', default='gb18030')
    conv.add_argument('--termination-time', type=float, default=3e-3)
    conv.add_argument('--output-interval', type=float, default=3e-5)
    conv.add_argument('--allow-output-dir', type=Path, action='append', default=[])
    args = parser.parse_args(argv)
    policy = OutputPolicy(tuple(args.allow_output_dir)) if args.command == 'convert-explicit' else OutputPolicy()
    if args.command == 'convert-explicit':
        policy = OutputPolicy((*policy.external_roots, Path('E:/openradioss/output'))) 
    try:
        args.output = writable_path(args.output, policy)
    except ValueError as exc:
        parser.error(str(exc))
    if args.command != 'convert-explicit':
        args.output.mkdir(parents=True, exist_ok=True)
    if args.command == 'analyze':
        from .analysis import analyze
        try:
            result = analyze(args.model, args.output, args.encoding)
        except (OSError,ValueError) as exc:
            print(f'FAILED: {exc}')
            return 2
        print(json.dumps({k:result[k] for k in ('status','counts','element_orders','conversion_success')},indent=2))
        print(f"SOL {result['case_control']['solution']}; all {len(result['mapping_blockers'])} card types reported.\nReport: {args.output/'ANALYSIS.md'}")
        return 2 if not result['conversion_success'] else 0
    if args.command == 'solid-benchmark':
        from .solid import load_solid, write_solid
        from .deck import job_name
        try:
            model = load_solid(args.model)
            pair = write_solid(model, args.output, job_name(args.model), args.termination_time, args.output_interval)
        except (OSError, ValueError) as exc:
            print(f'FAILED: {exc}')
            return 2
        print('BENCHMARK ONLY; physics equivalence not verified.\n' + '\n'.join(map(str,pair)))
        return 0
    if args.command == 'convert-explicit':
        from .converter import convert
        try:
            result = convert(args.model, args.output, args.encoding, args.termination_time, args.output_interval, output_policy=policy)
        except (OSError, ValueError) as exc:
            print(f'FAILED: {exc}')
            return 2
        print(json.dumps({k:result[k] for k in ('status','model_counts','warnings')}, indent=2, ensure_ascii=True))
        return 0 if result['status'] == 'CONVERSION_SUCCESS' else 2
    if args.command == 'analyze-log':
        from .solver_log import analyze_log
        result = analyze_log(args.log.read_text(encoding=args.encoding), str(args.log.resolve()))
        (args.output/'solver_log_report.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
        return 2 if result['simulation_status'] == 'FAILED' else 0
    if args.command == 'review':
        from .audit import review
        if args.model is None:
            candidates = sorted(args.input_dir.glob('*.bdf'))
            if len(candidates) != 1:
                parser.error('Expected exactly one BDF in --input-dir; specify a model explicitly otherwise.')
            args.model = candidates[0]
        elif not args.model.is_absolute() and not args.model.is_file():
            args.model = args.input_dir / args.model
        try:
            result = review(args.model, args.output, args.encoding,
                            args.termination_time, args.output_interval)
        except (OSError, ValueError) as exc:
            print(f'FAILED: {exc}')
            return 2
        print(json.dumps({k: result[k] for k in ('status','counts','element_orders','mesh_reference_checks','artifact','engine_artifact','preflight')}, indent=2))
        return 2
    if args.command == "doctor":
        report = discover(args.search_root, args.output, args.online, args.solver_help)
        destination = args.output / "environment.json"
        destination.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Environment report: {destination.resolve()}")
        print(f"Executables: {len(report['executables'])}; source archives: {len(report['source_archives'])}")
        return 0
    reader = BDFParser(encoding=args.encoding)
    counts = Counter()
    diagnostics = []
    try:
        with (args.output / "cards.jsonl").open("w", encoding="utf-8") as records:
            for card in reader.parse(args.model):
                counts[card.name] += 1
                records.write(json.dumps(asdict(card), ensure_ascii=False) + "\n")
    except (BDFError, UnicodeError, OSError) as exc:
        diagnostics.append(exc.diagnostic.to_dict() if isinstance(exc, BDFError) else {"code": "INPUT_ERROR", "message": str(exc)})
    report = {"status": "FAILED" if diagnostics else "PARSED", "card_counts": dict(counts),
              "mapping_status": "NOT_IMPLEMENTED", "physics_equivalence": "NOT_VERIFIED",
              "diagnostics": diagnostics, "include_tree": [asdict(e) for e in reader.include_tree],
              "control_lines": [{"source": asdict(loc), "raw": raw} for loc, raw in reader.control_lines]}
    (args.output / "inspection.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 2 if diagnostics else 0


if __name__ == "__main__":
    raise SystemExit(main())
