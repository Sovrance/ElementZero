"""EZ-B002 blind prediction into a withheld region of the chart.

The Atlas lineage is the EZ-B001 graph with the geographic split in the freeze
node (WO-09 section 11)::

    artifact -> training dataset -> geographic split / knowledge freeze
             -> model fit -> prediction (one per target) -> prediction set

Blindness in EZ-B001 is enforced at the filesystem boundary: the later edition
is a different file with a different hash. A geographic holdout cannot work that
way, because training and truth live in the same snapshot. Here the boundary is
enforced in code, on every fit:

* only rows whose identity is in ``freeze.training_nuclide_ids`` are loaded,
* the loaded corpus must reproduce ``training_identity_digest`` exactly,
* no loaded row may be inside the region,
* no target may appear in the fitted identity list,
* the model manifest handed to the certificate is scanned for the target
  identities, so a model that memorized a withheld row cannot seal a run.

The three frozen EZ-B001 models are reused unchanged, and every model in a
region's suite gets the same freeze, the same targets, and the same source.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero import B002_PROTOCOL_VERSION, BENCHMARK_EZ_B002, BENCHMARK_PROTOCOL_VERSION
from elementzero.benchmark.b001_predict import load_targets
from elementzero.benchmark.b002_finalize import finalize_region_run
from elementzero.benchmark.b002_freeze import GeographicFreeze, assert_split_geometry
from elementzero.benchmark.distance import nearest_training, training_lattice
from elementzero.benchmark.model_suite import RANKING_RULE, SUITE_MODEL_IDS
from elementzero.data.amdc import load_edition
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.identity import NuclideIdentity
from elementzero.data.observations import GROUND_TRUTH_POLICY, TRUTH_BEARING_FIELDS
from elementzero.errors import LeakageError, ProtocolError
from elementzero.evidence.atlas_adapter import (
    NUCLEAR_MASS_INTERFACE,
    AtlasEvidenceAdapter,
    stable_source_uri,
    write_atlas_bundle,
)
from elementzero.evidence.certificates import PREDICTIVE_DISTRIBUTION_GAUSSIAN
from elementzero.evidence.certificates import REQUIRED_FIELDS as CERTIFICATE_FIELDS
from elementzero.evidence.freezes import (
    assert_holdout_disjoint,
    assert_training_digest,
    identity_digest,
)
from elementzero.evidence.hashing import canonical_json, content_id, sha256_file
from elementzero.evidence.ledger import write_run_artifact
from elementzero.identity_meta import provenance_identity, runtime_library_versions
from elementzero.models.gp_residual import MODEL_ID_SEMF_GP, build_model
from elementzero.models.model_manifest import manifest_hash, model_manifest

MODEL_SUITE_ID_B002 = "EZ-B002-SUITE-v1"
SUITE_MANIFEST_NAME = "model_suite.json"


def geographic_certificate(
    *,
    nuclide_id: str,
    prediction_keV: float,
    intervals: dict[str, Sequence[float]],
    predictive_std_keV: float,
    uncertainty_method: str,
    model_id: str,
    model_manifest_hash: str,
    freeze_id: str,
    training_identity_digest: str,
    feature_policy_id: str,
    atlas_pir_ref: str,
    elementzero_commit: str,
    source_hashes: Sequence[str],
    created_at: str,
    region_id: str,
    region_manifest_hash: str,
    split_digest: str,
    nearest_training_L1: int,
    ledger_state: str = "OPEN",
    atlas_fact_id: str | None = None,
) -> dict[str, Any]:
    """An EZ-B002 certificate: the EZ-B001 field set plus the region identity.

    ``elementzero.evidence.certificates`` is pinned to ``EZ-B001`` by protocol,
    so a geographic certificate is built here instead of relabelling a
    historical one. Field parity with the sealed EZ-B001 contract is asserted,
    not assumed.
    """
    prediction = {"mass_excess_keV": float(prediction_keV)}
    payload = {
        "benchmark_id": BENCHMARK_EZ_B002,
        "nuclide_id": nuclide_id,
        "prediction": prediction,
        "intervals": {k: list(v) for k, v in intervals.items()},
        "predictive_std_keV": float(predictive_std_keV),
        "model_id": model_id,
        "freeze_id": freeze_id,
        "model_manifest_hash": model_manifest_hash,
        "region_id": region_id,
        "split_digest": split_digest,
    }
    if float(predictive_std_keV) <= 0.0:
        raise ProtocolError("certificate predictive_std_keV must be positive")
    certificate = {
        "certificate_id": content_id("crt", payload),
        "benchmark_id": BENCHMARK_EZ_B002,
        "legacy_id": "none",
        "nuclide_id": nuclide_id,
        "observable": NUCLEAR_MASS_INTERFACE,
        "prediction": prediction,
        "intervals": {k: list(v) for k, v in intervals.items()},
        "predictive_distribution": PREDICTIVE_DISTRIBUTION_GAUSSIAN,
        "predictive_std_keV": float(predictive_std_keV),
        "uncertainty_method": uncertainty_method,
        "uncertainty_scope": "model_and_training_freeze",
        "model_id": model_id,
        "model_manifest_hash": model_manifest_hash,
        "freeze_id": freeze_id,
        "training_identity_digest": training_identity_digest,
        "feature_policy_id": feature_policy_id,
        "atlas_pir_ref": atlas_pir_ref,
        "elementzero_commit": elementzero_commit,
        "source_hashes": list(source_hashes),
        "created_at": created_at,
        "ledger_state": ledger_state,
        "atlas_fact_id": atlas_fact_id,
        "region_id": region_id,
        "region_manifest_hash": region_manifest_hash,
        "split_digest": split_digest,
        "nearest_training_L1": int(nearest_training_L1),
    }
    missing = [field for field in CERTIFICATE_FIELDS if field not in certificate]
    if missing:
        raise ProtocolError(f"geographic certificate is missing EZ-B001 contract fields: {missing}")
    return certificate


def _assert_manifest_free_of_targets(manifest: dict[str, Any], target_ids: Sequence[str]) -> None:
    """No withheld identity may be quoted anywhere in a fitted model manifest."""
    wanted = set(target_ids)
    text = canonical_json(manifest)
    leaked = sorted(nid for nid in wanted if f'"{nid}"' in text)
    if leaked:
        raise LeakageError(f"fitted model manifest quotes withheld identities: {leaked[:5]}")


def predict_region_run(
    *,
    geographic_freeze: GeographicFreeze,
    targets: list[dict[str, Any]],
    source: str | Path,
    edition_id: str,
    run_dir: str | Path,
    model_id: str = MODEL_ID_SEMF_GP,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Fit outside one region and predict inside it, then seal the artifacts."""
    freeze = geographic_freeze.freeze
    region = geographic_freeze.region
    source = Path(source)
    run_dir = Path(run_dir)
    source_hash = sha256_file(source)
    if source_hash not in freeze.allowed_source_hashes:
        raise LeakageError("source hash is not allowed by the geographic freeze")
    if source_hash in freeze.forbidden_source_hashes:
        raise LeakageError("source hash is forbidden by the geographic freeze")
    if edition_id not in freeze.allowed_edition_ids:
        raise LeakageError(f"edition {edition_id!r} is not allowed by the geographic freeze")

    target_ids = [t["nuclide_id"] for t in targets]
    if sorted(target_ids) != sorted(geographic_freeze.target_nuclide_ids):
        raise LeakageError("target manifest differs from the target set pinned by the freeze")
    if identity_digest(target_ids) != geographic_freeze.target_identity_digest:
        raise LeakageError("target identity digest differs from the freeze")
    assert_split_geometry(
        region=region,
        training_nuclide_ids=freeze.training_nuclide_ids,
        target_nuclide_ids=target_ids,
    )
    assert_holdout_disjoint(freeze, target_ids)

    allowed = set(freeze.training_nuclide_ids)
    observations = [
        obs
        for obs in load_edition(edition_id, str(source))
        if obs.nuclide_id in allowed and obs.ground_truth_eligible
    ]
    inside = sorted(obs.nuclide_id for obs in observations if region.contains(obs.Z, obs.N))
    if inside:
        raise LeakageError(f"training corpus contains nuclei inside the region: {inside[:5]}")
    assert_training_digest(freeze, [o.nuclide_id for o in observations])

    model = build_model(model_id)
    model.fit(observations)
    model_payload = model.manifest()
    assert_training_digest(freeze, model_payload["fitted_nuclide_ids"])
    _assert_manifest_free_of_targets(model_payload, target_ids)

    manifest = model_manifest(
        model_id=model_id,
        model_payload=model_payload,
        freeze_id=freeze.freeze_id,
        feature_policy_id=freeze.feature_policy_id,
    )
    m_hash = manifest_hash(manifest)
    lattice = training_lattice(freeze.training_nuclide_ids)

    adapter = AtlasEvidenceAdapter(created_at=created_at)
    created = adapter.created_at
    artifact = adapter.source_artifact(
        source.read_bytes(),
        source_uri=stable_source_uri(source),
        acquired_at=freeze.cutoff_date,
    )
    event = adapter.observation_event(artifact)
    adapter.append_provenance(
        entity=artifact.artifact_id,
        activity_type="LOAD",
        used=(),
        generated=(artifact.artifact_id,),
    )

    training_fact = adapter.training_dataset_fact(
        artifact=artifact,
        edition_id=edition_id,
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

    split_payload = {
        "region_id": region.region_id,
        "region": region.to_dict(),
        "region_manifest_hash": geographic_freeze.region_manifest_hash,
        "split_id": geographic_freeze.split_id,
        "split_digest": geographic_freeze.split_digest,
        "target_identity_digest": geographic_freeze.target_identity_digest,
        "n_targets": len(target_ids),
        "n_training": len(freeze.training_nuclide_ids),
    }
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
        geographic_split=split_payload,
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
        region_id=region.region_id,
        region_manifest_hash=geographic_freeze.region_manifest_hash,
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
        z, n = int(target["Z"]), int(target["N"])
        pred = model.predict(NuclideIdentity.from_zn(z, n))
        near = nearest_training(z=z, n=n, lattice=lattice)
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
        record = pred.to_dict()
        record["region_id"] = region.region_id
        record["nearest_training_L1"] = near["nearest_training_L1"]
        predictions.append(record)
        certificates.append(
            geographic_certificate(
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
                region_id=region.region_id,
                region_manifest_hash=geographic_freeze.region_manifest_hash,
                split_digest=geographic_freeze.split_digest,
                nearest_training_L1=near["nearest_training_L1"],
                ledger_state="OPEN",
                atlas_fact_id=fact.fact_id,
            )
        )

    write_run_artifact(run_dir, "freeze", geographic_freeze.to_dict())
    write_run_artifact(run_dir, "model_manifest", manifest)
    predictions_hash = write_run_artifact(run_dir, "predictions", predictions)
    certificates_hash = write_run_artifact(run_dir, "certificates", certificates)

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
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b002_protocol_version": B002_PROTOCOL_VERSION,
        "stage": "predict",
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "region_id": region.region_id,
        "region": region.to_dict(),
        "region_manifest_hash": geographic_freeze.region_manifest_hash,
        "split_id": geographic_freeze.split_id,
        "split_digest": geographic_freeze.split_digest,
        "z_band": region.z_band,
        "model_id": model_id,
        "model_manifest_hash": m_hash,
        "predictive_distribution": manifest["predictive_distribution"],
        "uncertainty_method": manifest["uncertainty_method"],
        "target_ids": target_ids,
        "target_identity_digest": identity_digest(target_ids),
        "n_training": len(observations),
        "observable": NUCLEAR_MASS_INTERFACE,
        "library_versions": runtime_library_versions(),
        "random_seeds": {"model": int(manifest["random_seed"])},
        "source_hashes": list(freeze.allowed_source_hashes),
        "edition_id": edition_id,
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
        "region_id": region.region_id,
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


def b002_suite_manifest(*, model_ids: Sequence[str] = SUITE_MODEL_IDS) -> dict[str, Any]:
    """Frozen, ordered EZ-B002 suite: the three EZ-B001 models, unchanged."""
    ordered = list(model_ids)
    if len(set(ordered)) != len(ordered):
        raise ValueError(f"model suite contains duplicates: {ordered}")
    return {
        "model_suite_id": MODEL_SUITE_ID_B002,
        "benchmark_id": BENCHMARK_EZ_B002,
        "protocol_version": B002_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "model_ids": ordered,
        "ranking_rule": RANKING_RULE,
        "weak_baseline_rule": (
            "No baseline is removed. A weak model is reported, which is what makes "
            "a strong extrapolation claim checkable."
        ),
    }


def run_region_suite(
    *,
    geographic_freeze: GeographicFreeze,
    targets: list[dict[str, Any]],
    source: str | Path,
    edition_id: str,
    suite_dir: str | Path,
    model_ids: Sequence[str] = SUITE_MODEL_IDS,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Predict and seal one run per model for a single region."""
    suite_dir = Path(suite_dir)
    manifest = b002_suite_manifest(model_ids=model_ids)
    runs = []
    for model_id in manifest["model_ids"]:
        run_dir = suite_dir / model_id
        result = predict_region_run(
            geographic_freeze=geographic_freeze,
            targets=targets,
            source=source,
            edition_id=edition_id,
            run_dir=run_dir,
            model_id=model_id,
            created_at=created_at,
        )
        marker = finalize_region_run(run_dir, created_at=created_at)
        runs.append(
            {
                "model_id": model_id,
                "run_dir": str(run_dir),
                "region_id": result["run_manifest"]["region_id"],
                "freeze_id": result["run_manifest"]["freeze_id"],
                "split_digest": result["run_manifest"]["split_digest"],
                "target_identity_digest": result["run_manifest"]["target_identity_digest"],
                "model_manifest_hash": result["run_manifest"]["model_manifest_hash"],
                "prediction_set_fact_id": result["run_manifest"]["prediction_set_fact_id"],
                "finalization_marker_hash": marker["finalization_marker_hash"],
            }
        )
    assert_one_split_per_suite(runs)
    payload = {
        **manifest,
        "suite_dir": str(suite_dir),
        "region_id": geographic_freeze.region_id,
        "region": geographic_freeze.region.to_dict(),
        "region_manifest_hash": geographic_freeze.region_manifest_hash,
        "split_id": geographic_freeze.split_id,
        "split_digest": geographic_freeze.split_digest,
        "freeze_id": geographic_freeze.freeze_id,
        "target_identity_digest": geographic_freeze.target_identity_digest,
        "n_targets": len(targets),
        "source_hashes": list(geographic_freeze.freeze.allowed_source_hashes),
        "feature_policy_id": geographic_freeze.freeze.feature_policy_id,
        "runs": runs,
        **provenance_identity(),
    }
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / SUITE_MANIFEST_NAME).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return payload


def assert_one_split_per_suite(runs: Sequence[dict[str, Any]]) -> None:
    """Every model of a region must have seen exactly one split."""
    for key in ("region_id", "freeze_id", "split_digest", "target_identity_digest"):
        values = sorted({run[key] for run in runs})
        if len(values) != 1:
            raise ProtocolError(f"suite runs do not share one {key}: {values}")


def load_region_targets(path: str | Path) -> list[dict[str, Any]]:
    """Identity-only target loader (reuses the EZ-B001 leakage-checked loader)."""
    targets = load_targets(path)
    for target in targets:
        leaked = sorted(TRUTH_BEARING_FIELDS.intersection(target))
        if leaked:
            raise LeakageError(f"target record carries truth fields: {leaked}")
    return targets
