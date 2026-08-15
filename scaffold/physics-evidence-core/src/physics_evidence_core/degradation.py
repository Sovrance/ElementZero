"""Conservative certificate degradation comparison extracted from GV CI ideas."""
from __future__ import annotations
from typing import Any, Dict, List, Tuple
from .certificates import VOLATILE_KEYS
FLOAT_RTOL=1e-6
FLOAT_ATOL=1e-9

def _close(a,b): return abs(a-b) <= FLOAT_ATOL + FLOAT_RTOL*max(abs(a),abs(b))

def _diff(a:Any,b:Any,path:str,out:List[str]):
    key=path.rsplit('.',1)[-1]
    if key in VOLATILE_KEYS: return
    if isinstance(a,dict) and isinstance(b,dict):
        for k in a:
            if k in VOLATILE_KEYS: continue
            if k not in b: out.append(f"{path}.{k}: key removed")
            else: _diff(a[k],b[k],f"{path}.{k}",out)
        return
    if isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b): out.append(f"{path}: list length {len(a)} -> {len(b)}"); return
        for i,(x,y) in enumerate(zip(a,b)): _diff(x,y,f"{path}[{i}]",out)
        return
    if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(b,(int,float)) and not isinstance(b,bool):
        if not _close(float(a),float(b)): out.append(f"{path}: numeric {a} -> {b}")
        return
    if a!=b: out.append(f"{path}: {a!r} -> {b!r}")

def is_degradation(committed:Dict, regenerated:Dict)->Tuple[bool,List[str]]:
    reasons=[]; _diff(committed,regenerated,'cert',reasons); return bool(reasons),reasons
