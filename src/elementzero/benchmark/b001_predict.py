"""Blind prediction: fit and predict using only KnowledgeFreeze-allowed objects.

The Atlas lineage written here is the compact WO-02 graph:

    artifact -> training dataset -> knowledge freeze -> model fit
             -> prediction (one per target) -> prediction set

No prediction depends on a single arbitrary observation, and no later-edition
truth is reachable from this process.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from elementzero import BENCHMARK_PROTOCOL_VERSION
from elementzero.data.amdc import load_edition
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import GROUND_TRUTH_POLICY
from elementzero.errors import LeakageError
from elementzero.evidence.atlas_adapter import (
    NUCLEAR_MASS_INTERFACE,
    AtlasEvidenceAdapter,
    stable_source_uri,
    write_atlas_bundle,
)
from elementzero.evidence.certificates import make_certificate
from elementzero.evidence.freezes import (
    KnowledgeFreeze,
    assert_holdout_disjoint,
    assert_training_digest,
    identity_digest,
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
    model_payload = model.manifest()
    assert_training_digest(freeze, model_payload["fitted_nuclide_ids"])

    manifest = model_manifest(
        model_id=model_id,
        model_payload=model_payload,
        freeze_id=freeze.freeze_id,
        feature_policy_id=freeze.feature_policy_id,
    )
    m_hash = manifest_hash(manifest)

    adapter = AtlasEvidenceAdapter(created_at=created_at)
    created = adapter.created_at
    raw = training_source.read_bytes()
    artifact = adapter.source_artifact(
        raw,
        source_uri=stable_source_uri(training_source),
        acquired_at=freeze.cutoff_date,
    )
    event = adapter.observation_event(artifact)
    adapter.append_provenance(
        entity=artifact.artifact_id,
        activity_type="LOAD",
        used=(),
        generated=(artifact.artifact_id,),
    )

    # Aggregate training-corpus identity: hashes and digests, not every datum.
    training_fact = adapter.training_dataset_fact(
        artifact=artifact,
        edition_id=training_edition_id,
        raw_source_hash=freeze.raw_source_hash,
        normalized_table_hash=freeze.normalized_table_hash,
        training_identity_digest=freeze.training_identity_digest,
        training_count=len(observations),
        normalizer_version=freeze.normalizer_version,
        parser_version=PARSER_VERSION,
        ground_truth_policy=GROUND_TRUTH_POLICY,
        event=event,
    )
    adapter.append_fact(training_fact)
    adapter.append_provenance(
        entity=training_fact.fact_id,
        activity_type="LOWER",
        used=(artifact.artifact_id,),
        generated=(training_fact.fact_id,),
    )

    freeze_fact = adapter.knowledge_freeze_fact(
        freeze_id=freeze.freeze_id,
        cutoff_date=freeze.cutoff_date,
        allowed_source_hashes=freeze.allowed_source_hashes,
        forbidden_source_hashes=freeze.forbidden_source_hashes,
        allowed_edition_ids=freeze.allowed_edition_ids,
        training_identity_digest=freeze.training_identity_digest,
        feature_policy_id=freeze.feature_policy_id,
        feature_policy_hash=freeze.feature_policy_hash,
        training_dataset_fact_id=training_fact.fact_id,
        atlas_pir_ref=freeze.atlas_pir_ref,
        elementzero_commit=freeze.elementzero_commit,
    )
    adapter.append_fact(freeze_fact)
    adapter.append_provenance(
        entity=freeze_fact.fact_id,
        activity_type="TRANSFORM",
        used=(training_fact.fact_id,),
        generated=(freeze_fact.fact_id,),
    )

    fit_fact = adapter.model_fit_fact(
        model_id=model_id,
        model_manifest_hash=m_hash,
        freeze_id=freeze.freeze_id,
        training_identity_digest=freeze.training_identity_digest,
        fitted_nuclide_count=len(model_payload["fitted_nuclide_ids"]),
        feature_policy_id=freeze.feature_policy_id,
        random_state=int(manifest["random_seed"]),
        runtime_versions=runtime_library_versions(),
        knowledge_freeze_fact_id=freeze_fact.fact_id,
        training_dataset_fact_id=training_fact.fact_id,
        uncertainty_method=manifest["uncertainty_method"],
    )
    adapter.append_fact(fit_fact)
    adapter.append_provenance(
        entity=fit_fact.fact_id,
        activity_type="ANALYZE",
        agent_id="elementzero.models.predict",
        used=(freeze_fact.fact_id, training_fact.fact_id),
        generated=(fit_fact.fact_id,),
    )

    predictions = []
    certificates = []
    pred_facts = []
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
            model_fit_fact_id=fit_fact.fact_id,
            std_keV=pred.std_keV,
            uncertainty_method=pred.uncertainty_method,
        )
        adapter.append_fact(fact)
        pred_facts.append(fact)
        adapter.append_provenance(
            entity=fact.fact_id,
            activity_type="ANALYZE",
            agent_id="elementzero.models.predict",
            used=(fit_fact.fact_id,),
            generated=(fact.fact_id,),
        )
        cert = make_certificate(
            nuclide_id=pred.nuclide.nuclide_id,
            prediction_keV=pred.mass_excess_keV,
            intervals=pred.intervals,
            predictive_std_keV=pred.std_keV,
            uncertainty_method=pred.uncertainty_method,
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

    write_run_artifact(run_dir, "freeze", freeze.to_dict())
    write_run_artifact(run_dir, "model_manifest", manifest)
    predictions_hash = write_run_artifact(run_dir, "predictions", predictions)
    certificates_hash = write_run_artifact(run_dir, "certificates", certificates)

    target_ids = [t["nuclide_id"] for t in targets]
    set_fact = adapter.prediction_set_fact(
        model_id=model_id,
        freeze_id=freeze.freeze_id,
        target_identity_digest=identity_digest(target_ids),
        n_predictions=len(predictions),
        predictions_file_hash=predictions_hash,
        certificates_file_hash=certificates_hash,
        prediction_fact_ids=[f.fact_id for f in pred_facts],
    )
    adapter.append_fact(set_fact)
    adapter.append_provenance(
        entity=set_fact.fact_id,
        activity_type="ANALYZE",
        agent_id="elementzero.models.predict",
        used=tuple(sorted(f.fact_id for f in pred_facts)),
        generated=(set_fact.fact_id,),
    )

    graph_facts = [training_fact, freeze_fact, fit_fact, *pred_facts, set_fact]
    atlas_bundle = write_atlas_bundle(
        run_dir,
        stage="predict",
        facts=graph_facts,
        provenance=adapter.store.provenance(),
        artifacts=[artifact],
        events=[event],
    )

    run_manifest = {
        "benchmark_id": "EZ-B001",
        "legacy_id": "ZME-B001",
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "stage": "predict",
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "model_id": model_id,
        "model_manifest_hash": m_hash,
        "predictive_distribution": manifest["predictive_distribution"],
        "uncertainty_method": manifest["uncertainty_method"],
        "target_ids": target_ids,
        "target_identity_digest": identity_digest(target_ids),
        "observable": NUCLEAR_MASS_INTERFACE,
        "library_versions": runtime_library_versions(),
        "random_seeds": {"model": int(manifest["random_seed"])},
        "source_hashes": list(freeze.allowed_source_hashes),
        "normalizer_version": freeze.normalizer_version,
        "parser_version": PARSER_VERSION,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "feature_policy_id": freeze.feature_policy_id,
        "predictions_file_hash": predictions_hash,
        "certificates_file_hash": certificates_hash,
        "training_dataset_fact_id": training_fact.fact_id,
        "knowledge_freeze_fact_id": freeze_fact.fact_id,
        "model_fit_fact_id": fit_fact.fact_id,
        "prediction_fact_ids": [f.fact_id for f in pred_facts],
        "prediction_set_fact_id": set_fact.fact_id,
        "atlas_bundle_hashes": atlas_bundle,
        **identity,
    }
    write_run_artifact(run_dir, "run_manifest", run_manifest)
    return {
        "run_dir": str(run_dir),
        "predictions": predictions,
        "certificates": certificates,
        "run_manifest": run_manifest,
        "atlas_bundle_hashes": atlas_bundle,
        "adapter": adapter,
        "facts": {
            "training_dataset": training_fact,
            "knowledge_freeze": freeze_fact,
            "model_fit": fit_fact,
            "predictions": pred_facts,
            "prediction_set": set_fact,
        },
    }
