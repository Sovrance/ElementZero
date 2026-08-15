from __future__ import annotations
import math, statistics

def score(rows):
    if not rows: return {"n_targets":0}
    e=[r['prediction_mean_keV']-r['truth_keV'] for r in rows]
    abs_e=[abs(x) for x in e]
    out={"n_targets":len(rows),"MAE_keV":sum(abs_e)/len(e),"RMSE_keV":math.sqrt(sum(x*x for x in e)/len(e)),"median_absolute_error_keV":statistics.median(abs_e)}
    for level,z in [(68,1.0),(90,1.6448536269514722),(95,1.959963984540054)]:
        eligible=[r for r in rows if r.get('prediction_std_keV') is not None]
        if eligible:
            hits=sum(abs(r['truth_keV']-r['prediction_mean_keV']) <= z*r['prediction_std_keV'] for r in eligible)
            out[f'coverage_{level}']=hits/len(eligible)
    return out
