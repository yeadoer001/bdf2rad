import argparse, json
from .translator import build,convert

def main(argv=None):
    ap=argparse.ArgumentParser(description='Nastran BDF -> OpenRadioss translator V1')
    sub=ap.add_subparsers(dest='cmd',required=True)
    for cmd in ('inspect','convert'):
        p=sub.add_parser(cmd); p.add_argument('bdf'); p.add_argument('--encoding',default='gb18030')
        p.add_argument('--preserve-high-order',action='store_true',default=True)
        if cmd=='convert': p.add_argument('-o','--output',required=True); p.add_argument('--dtout',type=float)
    a=ap.parse_args(argv)
    if a.cmd=='inspect':
        src,d=build(a.bdf,a.encoding,a.preserve_high_order); print(json.dumps({'status':'FAILED_VALIDATION' if d['errors'] else 'READY_TO_WRITE','summary':d['summary'],'errors':d['errors'][:50],'warnings':d['warnings'][:50],'not_transferred':d['not_transferred'][:50]},indent=2,ensure_ascii=False)); return 2 if d['errors'] else 0
    s,e,r=convert(a.bdf,a.output,a.encoding,a.preserve_high_order,a.dtout); print(json.dumps({'starter':str(s),'engine':str(e),'report':str(r)},indent=2)); return 0
