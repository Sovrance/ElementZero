from __future__ import annotations
import json, hashlib
from pathlib import Path
from physics_evidence_core import KnowledgeFreeze, PredictionRecord, HeldOutObservation, compare_held_out, create_certificate
from physics_evidence_core.canonical import sha256_hex
from ..io import read_normalized_mass_csv
from ..models.semf import SEMFModel
from ..models.gp_residual import SEMFResidualGP
from ..metrics import score

class BenchmarkStateError(RuntimeError): pass


def file_sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for c in iter(lambda:f.read(65536),b''): h.update(c)
    return h.hexdigest()


def prepare_discovery_target_manifest(old_csv, later_csv, out_json):
    """UNBLINDED benchmark-preparation step.

    Reads both normalized snapshots, but emits target identity metadata only.
    This output is reviewed/frozen before the blind prediction run. It MUST NOT
    contain mass values, uncertainties, or later evaluator fields that encode
    the answer.
    """
    old=read_normalized_mass_csv(old_csv)
    later=read_normalized_mass_csv(later_csv)
    train_ids={r.nuclide_id for r in old if r.ground_truth_eligible}
    targets=[r for r in later if r.ground_truth_eligible and r.nuclide_id not in train_ids]
    body={
        'manifest_version':'ZME-B001-TARGETS-1',
        'preparation_mode':'UNBLINDED_PREPARATION',
        'old_snapshot_sha256':file_sha256(old_csv),
        'truth_snapshot_sha256':file_sha256(later_csv),
        'targets':[{'nuclide_id':r.nuclide_id,'Z':r.Z,'N':r.N,'A':r.A} for r in sorted(targets,key=lambda x:x.nuclide_id)]
    }
    body['identity_content_sha256']=sha256_hex(body['targets'])
    Path(out_json).write_text(json.dumps(body,indent=2,sort_keys=True)+'\n')
    return body


def _read_target_manifest(path):
    body=json.loads(Path(path).read_text())
    forbidden={'mass_excess_keV','uncertainty_keV','truth','value','source_record_status'}
    for row in body.get('targets',[]):
        if forbidden & set(row):
            raise BenchmarkStateError(f'target manifest contains forbidden truth fields: {forbidden & set(row)}')
        if row['A'] != row['Z']+row['N'] or row['nuclide_id'] != f"Z{row['Z']}-N{row['N']}":
            raise BenchmarkStateError('invalid target identity metadata')
    if body.get('identity_content_sha256') != sha256_hex(body.get('targets',[])):
        raise BenchmarkStateError('target manifest identity hash mismatch')
    return body


def run_b001(old_csv,target_manifest_json,later_truth_csv,outdir,seed=0):
    """Run the blind stage, then unlock later truth only after prediction ledger finalization."""
    out=Path(outdir); out.mkdir(parents=True,exist_ok=True)
    old_hash=file_sha256(old_csv)
    # Hashing binds the later source artifact but does not parse target values.
    later_hash=file_sha256(later_truth_csv)
    old=read_normalized_mass_csv(old_csv)
    train=[r for r in old if r.ground_truth_eligible]
    train_map={r.nuclide_id:r for r in train}
    target_manifest=_read_target_manifest(target_manifest_json)
    targets=target_manifest['targets']
    if target_manifest['old_snapshot_sha256'] != old_hash or target_manifest['truth_snapshot_sha256'] != later_hash:
        raise BenchmarkStateError('target manifest snapshot hashes do not match run inputs')
    if not train or not targets: raise ValueError('benchmark requires train and target identities')
    target_ids=[t['nuclide_id'] for t in targets]
    overlap=set(train_map)&set(target_ids)
    if overlap: raise BenchmarkStateError(f'targets appear in training set: {sorted(overlap)[:5]}')

    freeze=KnowledgeFreeze(
        freeze_id='freeze_'+sha256_hex({'old_hash':old_hash,'training':sorted(train_map)})[:16],
        cutoff_date=max(r.source_release_date for r in train), allowed_source_hashes=(old_hash,),
        training_ids=frozenset(train_map), forbidden_source_hashes=(later_hash,), feature_policy_id='ZME-FEATURES-DISCOVERY-MIN-v1')
    semf=SEMFModel().fit(train)
    gp=SEMFResidualGP(semf,random_seed=seed).fit(train)
    model_manifest=gp.manifest(); model_hash=sha256_hex(model_manifest)
    predictions=[]; certs=[]
    for t in targets:
        freeze.assert_target_is_held_out(t['nuclide_id'])
        mean,std=gp.predict(t['Z'],t['N'])
        p=PredictionRecord(t['nuclide_id'],'mass_excess_keV',mean,std,gp.model_id,freeze.freeze_id,
                           {'feature_policy_id':freeze.feature_policy_id,'model_manifest_sha256':model_hash})
        predictions.append(p)
        certs.append(create_certificate({
            'certificate_version':'PEC-PRED-1','prediction_id':p.prediction_id,'subject_id':p.subject_id,
            'observable':p.observable,'knowledge_freeze_id':freeze.freeze_id,'cutoff_date':freeze.cutoff_date,
            'training_ids_sha256':freeze.training_ids_sha256,'allowed_source_hashes':list(freeze.allowed_source_hashes),
            'model_id':gp.model_id,'model_manifest_sha256':model_hash,'feature_policy_id':freeze.feature_policy_id,
            'prediction_mean':mean,'prediction_std':std,'uncertainty_scope':'statistical_surrogate_conditioned_on_model',
            'domain_status':'HISTORICALLY_VALIDATED_EXTRAPOLATION','random_seed':seed}))

    # Blind-stage artifacts are serialized and finalized BEFORE parsing later truth.
    (out/'model_manifest.json').write_text(json.dumps(model_manifest,indent=2,sort_keys=True)+'\n')
    (out/'predictions.json').write_text(json.dumps([p.to_dict()|{'prediction_id':p.prediction_id} for p in predictions],indent=2,sort_keys=True)+'\n')
    (out/'prediction_certificates.json').write_text(json.dumps(certs,indent=2,sort_keys=True)+'\n')
    ledger_hash=sha256_hex([p.prediction_id for p in predictions])
    (out/'LEDGER_FINALIZED').write_text(ledger_hash+'\n')
    if not (out/'LEDGER_FINALIZED').exists(): raise BenchmarkStateError('ledger not finalized')

    # TRUTH UNLOCK: only here is the later file parsed into MassObservation values.
    later=read_normalized_mass_csv(later_truth_csv)
    truth_map={r.nuclide_id:r for r in later if r.ground_truth_eligible}
    pred_by={p.subject_id:p for p in predictions}
    scored=[]
    for tid in target_ids:
        if tid not in truth_map: raise BenchmarkStateError(f'target {tid} missing eligible later truth')
        t=truth_map[tid]; p=pred_by[tid]
        truth=HeldOutObservation(t.nuclide_id,'mass_excess_keV',t.mass_excess_keV,later_hash,t.source_edition)
        comp=compare_held_out(p,truth,freeze)
        scored.append({'nuclide_id':t.nuclide_id,'prediction_mean_keV':p.mean,'prediction_std_keV':p.std,
                       'truth_keV':t.mass_excess_keV,'absolute_error_keV':comp.residual})
    metrics=score(scored)
    split={'split_id':'split_'+sha256_hex({'train':sorted(train_map),'test':target_ids})[:16],
           'track':'DISCOVERY_HOLDOUT','cutoff_edition':train[0].source_edition,'truth_edition':truth_map[target_ids[0]].source_edition,
           'training_nuclide_ids':sorted(train_map),'target_nuclide_ids':target_ids,
           'training_ids_sha256':freeze.training_ids_sha256,'target_manifest_sha256':file_sha256(target_manifest_json)}
    run={'benchmark':'ZME-B001','seed':seed,'old_snapshot_sha256':old_hash,'truth_snapshot_sha256':later_hash,
         'target_manifest_sha256':file_sha256(target_manifest_json),'knowledge_freeze_id':freeze.freeze_id,
         'model_manifest_sha256':model_hash,'prediction_ledger_sha256':ledger_hash,'metrics':metrics}
    (out/'split_manifest.json').write_text(json.dumps(split,indent=2,sort_keys=True)+'\n')
    (out/'scored_predictions.json').write_text(json.dumps(scored,indent=2,sort_keys=True)+'\n')
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2,sort_keys=True)+'\n')
    (out/'run_manifest.json').write_text(json.dumps(run,indent=2,sort_keys=True)+'\n')
    return run
