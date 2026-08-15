"""Blind prediction: fit and predict using only KnowledgeFreeze-allowed objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero.data.amdc import load_edition
from elementzero.data.identity import NuclideIdentity
from elementzero.errors import LeakageError
from elementzero.evidence.atlas_adapter import NUCLEAR_MASS_INTERFACE, AtlasEvidenceAdapter
from elementzero.evidence.certificates import make_certificate
from elementzero.evidence.freezes import (
    KnowledgeFreeze,
    assert_holdout_disjoint,
    assert_training_digest,
    validate_target_record,
)
from elementzero.evidence.hashing import sha256_file
from elementzero.evidence.ledger import write_run_artifact
from elementzero.identity_meta import provenance_identity, runtime_library_versions
from elementzero.models.gp_residual import MODEL_ID_SEMF_GP, build_model
from elementzero.models.model_manifest import manifest_hash, model_manifest


def _scan_truth_fields(payload: Any, *, where: str) -> None:
    from elementzero.data.observations import TRUTH_BEARING_FIELDS
    from elementzero.errors import LeakageError

    if isinstance(payload, dict):
        extras = TRUTH_BEARING_FIELDS.intersection(payload)
        if extras:
            raise LeakageError(f"{where} contains truth-bearing fields: {sorted(extras)}")
        for value in payload.values():
            _scan_truth_fields(value, where=where)
    elif isinstance(payload, list):
        for item in payload:
            _scan_truth_fields(item, where=where)


def load_targets(path: str | Path) -> list[dict[str, Any]]:
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    _scan_truth_fields(payload, where="target manifest")
    if isinstance(payload, list):
        records = payload
    else:
        records = payload.get("targets", [])
    return [validate_target_record(r) for r in records]


def predict_run(
    *,
    freeze: KnowledgeFreeze,
    targets: list[dict[str, Any]],
    training_source: str | Path,
    training_edition_id: str,
    run_dir: str | Path,
    model_id: str = MODEL_ID_SEMF_GP,
    created_at: str | None = None,
) -> dict[str, Any]:
    training_source = Path(training_source)
    run_dir = Path(run_dir)
    source_hash = sha256_file(training_source)
    if source_hash not in freeze.allowed_source_hashes:
        raise LeakageError("training source hash is not allowed by the freeze")
    if source_hash in freeze.forbidden_source_hashes:
        raise LeakageError("training source hash is forbidden by the freeze")

    observations = [
        obs
        for obs in load_edition(training_edition_id, str(training_source))
        if obs.nuclide_id in set(freeze.training_nuclide_ids) and obs.ground_truth_eligible
    ]
    assert_training_digest(freeze, [o.nuclide_id for o in observations])
    assert_holdout_disjoint(freeze, [t["nuclide_id"] for t in targets])

    model = build_model(model_id)
    model.fit(observations)
    assert_training_digest(freeze, model.manifest()["fitted_nuclide_ids"])

    adapter = AtlasEvidenceAdapter(created_at=created_at)
    raw = training_source.read_bytes()
    artifact = adapter.source_artifact(
        raw,
        source_uri=training_source.resolve().as_uri(),
        acquired_at=freeze.cutoff_date,
    )
    event = adapter.observation_event(artifact)
    adapter.append_provenance(
        entity=artifact.artifact_id,
        activity_type="LOAD",
        used=(),
        generated=(artifact.artifact_id,),
    )
    obs_facts = []
    for obs in observations:
        fact = adapter.observation_fact(obs, artifact=artifact, event=event)
        adapter.append_fact(fact)
        obs_facts.append(fact)
        adapter.append_provenance(
            entity=fact.fact_id,
            activity_type="LOWER",
            used=(artifact.artifact_id,),
            generated=(fact.fact_id,),
        )

    predictions = []
    certificates = []
    pred_facts = []
    manifest = model_manifest(
        model_id=model_id,
        model_payload=model.manifest(),
        freeze_id=freeze.freeze_id,
        feature_policy_id=freeze.feature_policy_id,
    )
    m_hash = manifest_hash(manifest)
    created = adapter.created_at
    identity = provenance_identity()
    for target in targets:
        pred = model.predict(NuclideIdentity.from_zn(int(target["Z"]), int(target["N"])))
        fact = adapter.prediction_fact(
            nuclide_id=pred.nuclide.nuclide_id,
            z=pred.nuclide.Z,
            n=pred.nuclide.N,
            a=pred.nuclide.A,
            prediction_keV=pred.mass_excess_keV,
            intervals=pred.intervals,
            model_id=model_id,
            freeze_id=freeze.freeze_id,
            depends_on_facts=[f.fact_id for f in obs_facts[:1]],
        )
        adapter.append_fact(fact)
        pred_facts.append(fact)
        adapter.append_provenance(
            entity=fact.fact_id,
            activity_type="ANALYZE",
            agent_id="elementzero.models.predict",
            used=tuple(f.fact_id for f in obs_facts[:1]),
            generated=(fact.fact_id,),
        )
        cert = make_certificate(
            nuclide_id=pred.nuclide.nuclide_id,
            prediction_keV=pred.mass_excess_keV,
            intervals=pred.intervals,
            model_id=model_id,
            model_manifest_hash=m_hash,
            freeze_id=freeze.freeze_id,
            training_identity_digest=freeze.training_identity_digest,
            feature_policy_id=freeze.feature_policy_id,
            atlas_pir_ref=freeze.atlas_pir_ref,
            elementzero_commit=freeze.elementzero_commit,
            source_hashes=freeze.allowed_source_hashes,
            created_at=created,
            ledger_state="OPEN",
            atlas_fact_id=fact.fact_id,
        )
        predictions.append(pred.to_dict())
        certificates.append(cert.to_dict())

    run_manifest = {
        "benchmark_id": "EZ-B001",
        "legacy_id": "ZME-B001",
        "stage": "predict",
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "model_id": model_id,
        "model_manifest_hash": m_hash,
        "target_ids": [t["nuclide_id"] for t in targets],
        "observable": NUCLEAR_MASS_INTERFACE,
        "library_versions": runtime_library_versions(),
        "random_seeds": {"model": 0},
        "source_hashes": list(freeze.allowed_source_hashes),
        "normalizer_version": freeze.normalizer_version,
        "feature_policy_id": freeze.feature_policy_id,
        "prediction_fact_ids": [f.fact_id for f in pred_facts],
        **identity,
    }
    write_run_artifact(run_dir, "freeze", freeze.to_dict())
    write_run_artifact(run_dir, "model_manifest", manifest)
    write_run_artifact(run_dir, "predictions", predictions)
    write_run_artifact(run_dir, "certificates", certificates)
    write_run_artifact(run_dir, "run_manifest", run_manifest)
    return {
        "run_dir": str(run_dir),
        "predictions": predictions,
        "certificates": certificates,
        "run_manifest": run_manifest,
        "adapter": adapter,
    }
