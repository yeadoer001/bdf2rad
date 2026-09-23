from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re, math

@dataclass
class Card:
    name:str; fields:list[str]; lines:list[str]; line_no:int

@dataclass
class Model:
    cards:dict[str,list[Card]]=field(default_factory=dict)
    nodes:dict[int,dict]=field(default_factory=dict)
    elements:dict[int,dict]=field(default_factory=dict)
    props:dict[int,dict]=field(default_factory=dict)
    mats:dict[int,dict]=field(default_factory=dict)
    mats1:dict[int,dict]=field(default_factory=dict)
    spc:list[Card]=field(default_factory=list)
    tic:list[Card]=field(default_factory=list)
    grav:list[Card]=field(default_factory=list)
    bsurfs:list[Card]=field(default_factory=list)
    bcrpara:list[Card]=field(default_factory=list)
    bctset:list[Card]=field(default_factory=list)
    bctadd:list[Card]=field(default_factory=list)
    bgset:list[Card]=field(default_factory=list)
    bgadd:list[Card]=field(default_factory=list)
    rbe2:list[Card]=field(default_factory=list)
    rbe3:list[Card]=field(default_factory=list)
    conm2:list[Card]=field(default_factory=list)
    tstep1:list[Card]=field(default_factory=list)
    controls:list[Card]=field(default_factory=list)
    case_control:list[str]=field(default_factory=list)
    diagnostics:list[str]=field(default_factory=list)

def nf(x, default=0.0):
    if x is None or not str(x).strip(): return default
    s=str(x).strip().upper().replace('D','E')
    if 'E' not in s: s=re.sub(r'(?<=[\d.])([+-]\d+)$',r'E\1',s)
    return float(s)

def ni(x, default=0):
    if x is None or not str(x).strip(): return default
    return int(float(str(x).strip()))

def split_line(line):
    if ',' in line:
        p=[x.strip() for x in line.split(',')]
        return p[0], p[1:]
    large=line[:8].strip().endswith('*') or line[:8].strip().startswith('*')
    w=16 if large else 8
    s=line[:72].ljust(72)
    return s[:8].strip(), [s[i:i+w].strip() for i in range(8,72,w)]

def parse(path, encoding='gb18030'):
    m=Model(); pending=None; in_bulk=False
    lines=Path(path).open('r',encoding=encoding,errors='strict').read().splitlines()
    for ln,raw in enumerate(lines,1):
        line=raw.split('$',1)[0].rstrip()
        if not line.strip(): continue
        up=line.strip().upper()
        if up.startswith('BEGIN BULK') or up.startswith('BEGIN,BULK'): in_bulk=True; continue
        if up.startswith('ENDDATA'): break
        if not in_bulk:
            m.case_control.append(raw); continue
        head, vals=split_line(line)
        if not head or head.startswith(('+','*')):
            if pending is None:
                m.diagnostics.append(f'orphan continuation line {ln}')
                continue
            pending[1].extend(vals); pending[2].append(raw); continue
        if pending is not None:
            c=Card(pending[0].rstrip('*').upper(),pending[1],pending[2],pending[3]); m.cards.setdefault(c.name,[]).append(c); pending=None
        pending=[head.rstrip('*').upper(), vals, [raw], ln]
    if pending:
        c=Card(pending[0],pending[1],pending[2],pending[3]); m.cards.setdefault(c.name,[]).append(c)
    for c in m.cards.get('GRID',[]):
        f=c.fields; 
        try: m.nodes[ni(f[0])]=dict(x=[nf(f[2]),nf(f[3]),nf(f[4])],cp=ni(f[1]),cd=ni(f[5]) if len(f)>5 else 0)
        except Exception as e: m.diagnostics.append(f'GRID line {c.line_no}: {e}')
    for typ in ('CTETRA','CHEXA','CPENTA'):
        for c in m.cards.get(typ,[]):
            f=c.fields
            try: m.elements[ni(f[0])]=dict(type=typ,pid=ni(f[1]),nodes=[ni(x) for x in f[2:] if str(x).strip()])
            except Exception as e: m.diagnostics.append(f'{typ} line {c.line_no}: {e}')
    for c in m.cards.get('PSOLID',[]):
        f=c.fields
        if f: m.props[ni(f[0])]=dict(mid=ni(f[1]),raw=f)
    for c in m.cards.get('MAT1',[]):
        f=c.fields; m.mats[ni(f[0])]=dict(E=nf(f[1]),G=nf(f[2]),nu=nf(f[3]),rho=nf(f[4]),alpha=nf(f[5]))
    for c in m.cards.get('MATS1',[]):
        f=c.fields; m.mats1[ni(f[0])]=dict(tid=ni(f[1]) if len(f)>1 and f[1] else 0, type=f[2].upper() if len(f)>2 else '', H=nf(f[3]), YF=ni(f[4],1), HR=ni(f[5],1), limit1=nf(f[6]))
    m.spc = list(m.cards.get('SPC',[])) + list(m.cards.get('SPC1',[]))
    for name,attr in [('TIC','tic'),('GRAV','grav'),('BSURFS','bsurfs'),('BCRPARA','bcrpara'),('BCTSET','bctset'),('BCTADD','bctadd'),('BGSET','bgset'),('BGADD','bgadd'),('RBE2','rbe2'),('RBE3','rbe3'),('CONM2','conm2'),('TSTEP1','tstep1')]: setattr(m,attr,m.cards.get(name,[]))
    for name in ('NLCNTLG','NLCNTL2','TEMPD','TEMP','PARAM','SPCADD','NLCNTL'): m.controls += m.cards.get(name,[])
    return m

def card_values(c): return c.fields

def selected_case(m):
    d={}
    for line in m.case_control:
        up=line.strip().upper()
        mm=re.match(r'(SPC|IC|LOAD|BCSET|BGSET|TSTEP|TEMP\(INIT\))\s*=\s*(\d+)',up)
        if mm: d[mm.group(1)]=int(mm.group(2))
    return d
