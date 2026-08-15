import pytest

from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import MassObservation
from elementzero.errors import SchemaError
from elementzero.evidence.certificates import make_certificate, validate_certificate
from elementzero.evidence.freezes import build_freeze, identity_digest


def test_freeze_serialization_contains_commits():
    train = [
        MassObservation(
            nuclide=NuclideIdentity.from_zn(8, 8),
            mass_excess_keV=-4737.0,
            uncertainty_keV=0.1,
            source_edition="AME2003",
            source_release_date="2003-12-22",
            source_record_status="evaluated_non_estimated",
            raw_source_hash="11" * 32,
        )
    ]
    targets = [{"nuclide_id": "Z18-N19", "Z": 18, "N": 19, "A": 37}]
    freeze = build_freeze(
        training=train,
        targets=targets,
        cutoff_date="2003-12-22",
        edition_id="AME2003",
        raw_source_hash="11" * 32,
        atlas_ref="31d76d094f1206e64a6920da4775d0a684618357",
        ez_commit="deadbeef",
    )
    payload = freeze.to_dict()
    assert payload["atlas_pir_ref"] == "31d76d094f1206e64a6920da4775d0a684618357"
    assert payload["elementzero_commit"] == "deadbeef"
    assert payload["training_identity_digest"] == identity_digest(["Z8-N8"])
    again = type(freeze).from_dict(payload)
    assert again.freeze_id == freeze.freeze_id


def test_certificate_validation():
    cert = make_certificate(
        nuclide_id="Z18-N19",
        prediction_keV=-1.0,
        intervals={"p90": [-2.0, 0.0], "p95": [-3.0, 1.0]},
        model_id="EZ-SEMF-GP-RESIDUAL-v1",
        model_manifest_hash="aa" * 32,
        freeze_id="frz",
        training_identity_digest="bb" * 32,
        feature_policy_id="ez-b001-identity-zn-v1",
        atlas_pir_ref="31d76d094f1206e64a6920da4775d0a684618357",
        elementzero_commit="deadbeef",
        source_hashes=["cc" * 32],
        created_at="2026-08-15T00:00:00Z",
    )
    validate_certificate(cert.to_dict())
    bad = cert.to_dict()
    bad["benchmark_id"] = "ZME-B001"
    with pytest.raises(SchemaError):
        validate_certificate(bad)
