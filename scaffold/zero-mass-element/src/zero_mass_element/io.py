from __future__ import annotations
import csv
from pathlib import Path
from .data_model import MassObservation

def read_normalized_mass_csv(path):
    out=[]
    with Path(path).open(newline='',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            out.append(MassObservation(
                nuclide_id=r['nuclide_id'],Z=int(r['Z']),N=int(r['N']),A=int(r['A']),
                mass_excess_keV=float(r['mass_excess_keV']),
                uncertainty_keV=(None if not r.get('uncertainty_keV') else float(r['uncertainty_keV'])),
                source_edition=r['source_edition'],source_release_date=r['source_release_date'],
                source_record_status=r['source_record_status'],
                ground_truth_eligible=r['ground_truth_eligible'].lower() in ('1','true','yes'),
                raw_source_hash=r['raw_source_hash'],normalizer_version=r['normalizer_version']))
    return out
