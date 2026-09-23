from pathlib import Path
from dataclasses import dataclass, field
from .radioss_schema import canonicalize_keyword_header
@dataclass
class TargetIR:
    nodes: dict=field(default_factory=dict); elements: dict=field(default_factory=dict); materials: dict=field(default_factory=dict); properties: dict=field(default_factory=dict); parts: dict=field(default_factory=dict); groups: dict=field(default_factory=dict); masses: dict=field(default_factory=dict); rbe2: dict=field(default_factory=dict); rbe3: dict=field(default_factory=dict); bcs: dict=field(default_factory=dict); initial_velocities: dict=field(default_factory=dict); gravity: dict=field(default_factory=dict); interfaces: dict=field(default_factory=dict); keywords: list=field(default_factory=list)
def parse_generated_rad(path):
    t=TargetIR(); lines=Path(path).read_text(encoding='ascii').splitlines(); i=0; family=None
    while i<len(lines):
        s=lines[i].strip()
        if s.startswith('/'):
            h=canonicalize_keyword_header(s); t.keywords.append(h); family=h['family']; i+=1
            if family=='/NODE':
                while i<len(lines) and not lines[i].startswith('/'):
                    p=lines[i].split();
                    if len(p)>=4: t.nodes[int(p[0])]=[float(x) for x in p[1:4]]
                    i+=1
                continue
            if family=='/MAT/LAW1':
                mid=h['instance_ids'][0]; title=lines[i].strip(); rho=lines[i+1].split() if i+1<len(lines) else []; en=lines[i+2].split() if i+2<len(lines) else []; i+=3
                t.materials[mid]={'family':'LAW1','title':title,'rho':float(rho[0]) if rho else None,'E':float(en[0]) if en else None,'nu':float(en[1]) if len(en)>1 else None}; continue
            if family=='/PROP/SOLID':
                pid=h['instance_ids'][0]; title=lines[i].strip(); vals=lines[i+1].split() if i+1<len(lines) else []; i+=2
                t.properties[pid]={'title':title,'raw':vals}; continue
            if family=='/PART':
                pid=h['instance_ids'][0]; title=lines[i].strip(); vals=lines[i+1].split() if i+1<len(lines) else []; i+=2
                t.parts[pid]={'title':title,'property':int(vals[0]) if vals else None,'material':int(vals[1]) if len(vals)>1 else None}; continue
            if family=='/ADMAS':
                aid=h['instance_ids'][0]; title=lines[i].strip(); vals=lines[i+1].split() if i+1<len(lines) else []; i+=2
                t.masses[aid]={'title':title,'raw':vals}; continue
            if family in ('/BRICK','/BRIC20','/TETRA10','/TETRA4'):
                while i<len(lines) and not lines[i].startswith('/'):
                    p=lines[i].split();
                    if p: t.elements[int(p[0])]={'family':family.lstrip('/'),'part':h['instance_ids'][0],'nodes':[int(x) for x in p[1:]]}
                    i+=1
                continue
            if family=='/GRNOD/NODE':
                gid=h['instance_ids'][0]; vals=[]; title=lines[i].strip() if i<len(lines) else ''; i+=1
                while i<len(lines) and not lines[i].startswith('/'):
                    vals.extend(int(x) for x in lines[i].split() if x.isdigit()); i+=1
                t.groups[gid]={'type':'NODE','title':title,'nodes':vals}; continue
        else: i+=1
    return t
