from __future__ import annotations
import argparse, json
from pathlib import Path
from bdf2rad.core.discovery import discover_blocks, describe
from bdf2rad.core.converter import convert

# ================= USER CONFIGURATION =================
INPUT_BDF = r'E:\openradioss\input\02_MAT1_PSOLID_CHEXA8.bdf'
OUTPUT_DIR = r'D:\BDF2RAD-X\bdf2rad\0-output'
BLOCK_ROOT = Path(__file__).resolve().parent / 'blocks'
ENCODING = 'gb18030'
# ======================================================

def cmd_scan(root: str|Path):
    specs=discover_blocks(Path(root))
    print(json.dumps({'root':str(Path(root).resolve()),'count':len(specs),'blocks':describe(specs)},ensure_ascii=False,indent=2))

def main():
    ap=argparse.ArgumentParser(description='BDF -> OpenRadioss modular translator')
    sub=ap.add_subparsers(dest='cmd')
    sc=sub.add_parser('scan',help='scan a blocks directory recursively; new plugins are auto-discovered')
    sc.add_argument('--root',default=str(BLOCK_ROOT),help='directory to scan; can be a whole drive such as D:\\')
    c=sub.add_parser('convert',help='convert using all discovered plugins')
    c.add_argument('--input',default=INPUT_BDF)
    c.add_argument('--output',default=OUTPUT_DIR)
    c.add_argument('--blocks',default=str(BLOCK_ROOT))
    c.add_argument('--encoding',default=ENCODING)
    args=ap.parse_args()
    if args.cmd=='scan':
        cmd_scan(args.root);return
    if args.cmd=='convert':
        result=convert(args.input,args.output,Path(__file__).resolve().parent,args.encoding,Path(args.blocks))
        print(json.dumps(result,ensure_ascii=False,indent=2));return
    result=convert(INPUT_BDF,OUTPUT_DIR,Path(__file__).resolve().parent,ENCODING,BLOCK_ROOT)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
