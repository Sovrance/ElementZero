from pathlib import Path
import json
from zero_mass_element.benchmark.b001 import run_b001, prepare_discovery_target_manifest, BenchmarkStateError

def test_b001_synthetic(tmp_path):
    here=Path(__file__).parent/'fixtures'
    targets=tmp_path/'targets.json'
    prepare_discovery_target_manifest(here/'ame_old_synthetic.csv',here/'ame_later_synthetic.csv',targets)
    # Assert target manifest carries identity only, never answer values.
    text=targets.read_text()
    assert 'mass_excess_keV' not in text and 'uncertainty_keV' not in text
    r=run_b001(here/'ame_old_synthetic.csv',targets,here/'ame_later_synthetic.csv',tmp_path/'run',seed=0)
    assert r['benchmark']=='ZME-B001'
    assert r['metrics']['n_targets'] > 0
    assert (tmp_path/'run'/'LEDGER_FINALIZED').exists()
    assert r['metrics']['RMSE_keV'] < 5000

def test_target_manifest_rejects_truth_fields(tmp_path):
    here=Path(__file__).parent/'fixtures'
    targets=tmp_path/'targets.json'
    body=prepare_discovery_target_manifest(here/'ame_old_synthetic.csv',here/'ame_later_synthetic.csv',targets)
    body['targets'][0]['mass_excess_keV']=123.0
    from physics_evidence_core.canonical import sha256_hex
    body['identity_content_sha256']=sha256_hex(body['targets'])
    targets.write_text(json.dumps(body))
    try:
        run_b001(here/'ame_old_synthetic.csv',targets,here/'ame_later_synthetic.csv',tmp_path/'run2',seed=0)
    except BenchmarkStateError: pass
    else: raise AssertionError('truth-bearing target manifest should be rejected')
