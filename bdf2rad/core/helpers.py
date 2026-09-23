from .formatting import fi,fs,dof6,node_group_lines,bdf_velocity_to_rad_mm_ms,bdf_accel_to_rad_mm_ms2,bdf_time_to_rad_ms
from .types import RadBlock,TranslationContext
from pathlib import Path
from ..core.template_engine import load_template,render

def emit_template(spec, values, rows_token=None):
    data=load_template(spec.block_dir)
    lines=data['lines']
    if rows_token is not None:
        values=values.copy();values['ROWS']='\n'.join(rows_token)
    return render(lines,values)

def rb(spec, keyword, lines, order, source_cards):
    return RadBlock(keyword,lines,order,spec.name,tuple(source_cards))

def next_id(ctx,key,start=1):
    k='next:'+key;v=ctx.ids.get(k,start);ctx.ids[k]=v+1;return v
