"""EZ-B003 blind prediction into a withheld shell-closure neighborhood.

The Atlas lineage is the EZ-B002 graph with the shell split in the freeze node
and the competing structure hypotheses attached to it (WO-10 section 10)::

    artifact -> training dataset -> shell split / knowledge freeze
             -> H0/H1 hypothesis set (UNRESOLVED, plus the masking intervention)
             -> model fit -> prediction (one per masked target) -> prediction set

Blindness cannot be enforced at the filesystem boundary: the closure neighborhood
was withheld geometrically from one snapshot. So the boundary is enforced in
code, on every fit, exactly as in EZ-B002:

* only rows whose identity is in ``freeze.training_nuclide_ids`` are loaded,
* the loaded corpus must reproduce ``training_identity_digest`` exactly,
* no loaded row may be inside the mask,
* no target may appear in the fitted identity list,
* the fitted model manifest is scanned for the withheld identities.

EZ-B003 adds two controls of its own:

* the discovery-profile feature firewall runs against the *fitted* model
  manifest, not only against the policy file, so a model that quietly added a
  magic-number feature cannot seal a run,
* the H0/H1 hypothesis fact is written before any hidden truth exists, which is
  what makes the later resolution a prediction rather than a description.

Models predict mass excess only. Binding energy, S2n, S2p, delta2n, and delta2p
are derived afterwards, at scoring time; no model is ever fitted on a derived
target (WO-10 section 3).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero import B003_PROTOCOL_VERSION, BENCHMARK_EZ_B003, BENCHMARK_PROTOCOL_VERSION
from elementzero.benchmark.b001_predict import load_targets
from elementzero.benchmark.b003_finalize import finalize_shell_run
from elementzero.benchmark.b003_freeze import ShellFreeze, assert_split_geometry
from elementzero.benchmark.b003_prepare import (
    PROFILE_DISCOVERY,
    PROFILE_SEPARATION_RULE,
    assert_discovery_features,
    feature_policy_payload,
)
from elementzero.benchmark.distance import nearest_training, training_lattice
from elementzero.benchmark.model_suite import RANKING_RULE, SUITE_MODEL_IDS
from elementzero.benchmark.shell_metrics import (
    HYPOTHESIS_DECISION_RULE,
    hypothesis_statements,
)
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
from elementzero.physics.separation import separation_policy

MODEL_SUITE_ID_B003 = "EZ-B003-SUITE-v1"
SUITE_MANIFEST_NAME = "model_suite.json"

DERIVED_TARGET_RULE = (
    "Models predict mass excess. Binding energy and every separation observable "
    "are derived after the seal, from the sealed predictions and the frozen "
    "training masses. No model is fitted on a derived target."
)


def shell_certificate(
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
    challenge_id: str,
    mask_id: str,
    mask_hash: str,
    challenge_manifest_hash: str,
    split_digest: str,
    profile: str,
    nearest_training_L1: int,
    ledger_state: str = "OPEN",
    atlas_fact_id: str | None = None,
) -> dict[str, Any]:
    """An EZ-B003 certificate: the EZ-B001 field set plus the shell identity.

    ``elementzero.evidence.certificates`` is pinned to ``EZ-B001`` by protocol,
    so a shell certificate is built here instead of relabelling a historical
    one. Field parity with the sealed EZ-B001 contract is asserted, not assumed.
    """
    prediction = {"mass_excess_keV": float(prediction_keV)}
    payload = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "nuclide_id": nuclide_id,
        "prediction": prediction,
        "intervals": {k: list(v) for k, v in intervals.items()},
        "predictive_std_keV": float(predictive_std_keV),
        "model_id": model_id,
        "freeze_id": freeze_id,
        "model_manifest_hash": model_manifest_hash,
        "mask_id": mask_id,
        "split_digest": split_digest,
    }
    if float(predictive_std_keV) <= 0.0:
        raise ProtocolError("certificate predictive_std_keV must be positive")
    certificate = {
        "certificate_id": content_id("crt", payload),
        "benchmark_id": BENCHMARK_EZ_B003,
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
        "challenge_id": challenge_id,
        "mask_id": mask_id,
        "mask_hash": mask_hash,
        "challenge_manifest_hash": challenge_manifest_hash,
        "split_digest": split_digest,
        "profile": profile,
        "nearest_training_L1": int(nearest_training_L1),
    }
    missing = [field for field in CERTIFICATE_FIELDS if field not in certificate]
    if missing:
        raise ProtocolError(f"shell certificate is missing EZ-B001 contract fields: {missing}")
    return certificate


def _assert_manifest_free_of_targets(manifest: dict[str, Any], target_ids: Sequence[str]) -> None:
    """No withheld identity may be quoted anywhere in a fitted model manifest."""
    wanted = set(target_ids)
    text = canonical_json(manifest)
    leaked = sorted(nid for nid in wanted if f'"{nid}"' in text)
    if leaked:
        raise LeakageError(f"fitted model manifest quotes withheld identities: {leaked[:5]}")


def assert_fitted_model_features(
    model_payload: dict[str, Any], *, profile: str, allowed: Sequence[str]
) -> list[str]:
    """Run the discovery firewall against the features the model actually used.

    The feature-policy manifest is the primary protection, but it is a file. This
    check reads the fitted model's own manifest, so a discovery-profile run whose
    model added a shell feature fails before anything is sealed.
    """
    declared = model_payload.get("features")
    if not declared:
        raise ProtocolError(
            f"model {model_payload.get('model_id')!r} does not declare its features; "
            "the discovery profile cannot be enforced against an undeclared feature set"
        )
    names = [str(name) for name in declared]
    if profile != PROFILE_DISCOVERY:
        return names
    assert_discovery_features(
        names, allowed=allowed, where=f"fitted model {model_payload.get('model_id')!r} features"
    )
    extra = sorted(set(names) - set(allowed))
    if extra:
        raise LeakageError(
            f"fitted model {model_payload.get('model_id')!r} used features outside the "
            f"frozen discovery policy: {extra}"
        )
    return names


def predict_shell_run(
    *,
    shell_freeze: ShellFreeze,
    targets: list[dict[str, Any]],
    source: str | Path,
    edition_id: str,
    run_dir: str | Path,
    model_id: str = MODEL_ID_SEMF_GP,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Fit outside one closure neighborhood and predict inside it, then seal."""
    freeze = shell_freeze.freeze
    mask = shell_freeze.mask
    source = Path(source)
    run_dir = Path(run_dir)
    source_hash = sha256_file(source)
    if source_hash not in freeze.allowed_source_hashes:
        raise LeakageError("source hash is not allowed by the shell freeze")
    if source_hash in freeze.forbidden_source_hashes:
        raise LeakageError("source hash is forbidden by the shell freeze")
    if edition_id not in freeze.allowed_edition_ids:
        raise LeakageError(f"edition {edition_id!r} is not allowed by the shell freeze")

    target_ids = [t["nuclide_id"] for t in targets]
    if sorted(target_ids) != sorted(shell_freeze.target_nuclide_ids):
        raise LeakageError("target manifest differs from the target set pinned by the freeze")
    if identity_digest(target_ids) != shell_freeze.target_identity_digest:
        raise LeakageError("target identity digest differs from the freeze")
    assert_split_geometry(
        mask=mask,
        training_nuclide_ids=freeze.training_nuclide_ids,
        target_nuclide_ids=target_ids,
    )
    assert_holdout_disjoint(freeze, target_ids)

    policy = feature_policy_payload(profile=shell_freeze.profile)
    if policy["feature_policy_id"] != freeze.feature_policy_id:
        raise ProtocolError(
            f"freeze feature policy {freeze.feature_policy_id!r} is not the "
            f"{shell_freeze.profile!r} profile policy"
        )

    allowed = set(freeze.training_nuclide_ids)
    observations = [
        obs
        for obs in load_edition(edition_id, str(source))
        if obs.nuclide_id in allowed and obs.ground_truth_eligible
    ]
    inside = sorted(obs.nuclide_id for obs in observations if mask.contains(obs.Z, obs.N))
    if inside:
        raise LeakageError(
            f"training corpus contains nuclei inside the masked closure neighborhood: {inside[:5]}"
        )
    assert_training_digest(freeze, [o.nuclide_id for o in observations])

    model = build_model(model_id)
    model.fit(observations)
    model_payload = model.manifest()
    assert_training_digest(freeze, model_payload["fitted_nuclide_ids"])
    _assert_manifest_free_of_targets(model_payload, target_ids)
    features = assert_fitted_model_features(
        model_payload, profile=shell_freeze.profile, allowed=list(policy["features"])
    )

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
        "challenge_id": shell_freeze.challenge_id,
        "mask_id": mask.mask_id,
        "mask": mask.to_dict(),
        "mask_hash": shell_freeze.mask_hash,
        "challenge_manifest_hash": shell_freeze.challenge_manifest_hash,
        "axis": mask.axis,
        "closure": mask.closure,
        "indicator": mask.indicator,
        "profile": shell_freeze.profile,
        "split_id": shell_freeze.split_id,
        "split_digest": shell_freeze.split_digest,
        "target_identity_digest": shell_freeze.target_identity_digest,
        "supported_chains": list(shell_freeze.supported_chains),
        "unsupported_chains": list(shell_freeze.unsupported_chains),
        "n_targets": len(target_ids),
        "n_training": len(freeze.training_nuclide_ids),
        "derived_target_rule": DERIVED_TARGET_RULE,
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
        shell_split=split_payload,
    )
    adapter.append_fact(freeze_fact)
    adapter.append_provenance(
        entity=freeze_fact.fact_id,
        activity_type="TRANSFORM",
        used=(training_fact.fact_id,),
        generated=(freeze_fact.fact_id,),
    )

    # H0/H1 before any hidden truth exists (WO-10 section 10).
    closure_label = f"{mask.closure_axis_label} = {mask.closure}"
    intervention = adapter.shell_masking_intervention(
        challenge_id=shell_freeze.challenge_id,
        mask=mask.to_dict(),
        mask_id=mask.mask_id,
        indicator=mask.indicator,
    )
    hypotheses = adapter.shell_hypothesis_pair(
        challenge_id=shell_freeze.challenge_id,
        indicator=mask.indicator,
        closure_label=closure_label,
        intervention=intervention,
        derived_from_facts=(freeze_fact.fact_id,),
        assumptions=(f"freeze:{freeze.freeze_id}",),
    )
    hypothesis_fact = adapter.shell_hypothesis_fact(
        challenge_id=shell_freeze.challenge_id,
        axis=mask.axis,
        closure=mask.closure,
        indicator=mask.indicator,
        mask=mask.to_dict(),
        mask_id=mask.mask_id,
        mask_hash=shell_freeze.mask_hash,
        hypotheses=hypotheses,
        statements=hypothesis_statements(
            indicator=mask.indicator, closure_label=closure_label
        ),
        intervention=intervention,
        knowledge_freeze_fact_id=freeze_fact.fact_id,
        decision_rule=HYPOTHESIS_DECISION_RULE,
        freeze_id=freeze.freeze_id,
    )
    adapter.append_fact(hypothesis_fact)
    adapter.append_provenance(
        entity=hypothesis_fact.fact_id,
        activity_type="TRANSFORM",
        used=(freeze_fact.fact_id,),
        generated=(hypothesis_fact.fact_id,),
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
        challenge_id=shell_freeze.challenge_id,
        mask_id=mask.mask_id,
        mask_hash=shell_freeze.mask_hash,
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
        record["challenge_id"] = shell_freeze.challenge_id
        record["mask_id"] = mask.mask_id
        record["nearest_training_L1"] = near["nearest_training_L1"]
        predictions.append(record)
        certificates.append(
            shell_certificate(
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
                challenge_id=shell_freeze.challenge_id,
                mask_id=mask.mask_id,
                mask_hash=shell_freeze.mask_hash,
                challenge_manifest_hash=shell_freeze.challenge_manifest_hash,
                split_digest=shell_freeze.split_digest,
                profile=shell_freeze.profile,
                nearest_training_L1=near["nearest_training_L1"],
                ledger_state="OPEN",
                atlas_fact_id=fact.fact_id,
            )
        )

    write_run_artifact(run_dir, "freeze", shell_freeze.to_dict())
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

    graph_facts = [training_fact, freeze_fact, hypothesis_fact, fit_fact, *pred_facts, set_fact]
    atlas_bundle = write_atlas_bundle(
        run_dir,
        stage="predict",
        facts=graph_facts,
        provenance=adapter.store.provenance(),
        artifacts=[artifact],
        events=[event],
    )

    run_manifest = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b003_protocol_version": B003_PROTOCOL_VERSION,
        "stage": "predict",
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "challenge_id": shell_freeze.challenge_id,
        "mask_id": mask.mask_id,
        "mask": mask.to_dict(),
        "mask_hash": shell_freeze.mask_hash,
        "challenge_manifest_hash": shell_freeze.challenge_manifest_hash,
        "axis": mask.axis,
        "closure": mask.closure,
        "indicator": mask.indicator,
        "profile": shell_freeze.profile,
        "supported_chains": list(shell_freeze.supported_chains),
        "unsupported_chains": list(shell_freeze.unsupported_chains),
        "split_id": shell_freeze.split_id,
        "split_digest": shell_freeze.split_digest,
        "model_id": model_id,
        "model_manifest_hash": m_hash,
        "features": features,
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
        "separation_policy": separation_policy(),
        "derived_target_rule": DERIVED_TARGET_RULE,
        "profile_separation_rule": PROFILE_SEPARATION_RULE,
        "predictions_file_hash": predictions_hash,
        "certificates_file_hash": certificates_hash,
        "training_dataset_fact_id": training_fact.fact_id,
        "knowledge_freeze_fact_id": freeze_fact.fact_id,
        "shell_hypothesis_fact_id": hypothesis_fact.fact_id,
        "model_fit_fact_id": fit_fact.fact_id,
        "prediction_fact_ids": [f.fact_id for f in pred_facts],
        "prediction_set_fact_id": set_fact.fact_id,
        "atlas_bundle_hashes": atlas_bundle,
        **identity,
    }
    write_run_artifact(run_dir, "run_manifest", run_manifest)
    return {
        "run_dir": str(run_dir),
        "challenge_id": shell_freeze.challenge_id,
        "mask_id": mask.mask_id,
        "predictions": predictions,
        "certificates": certificates,
        "run_manifest": run_manifest,
        "atlas_bundle_hashes": atlas_bundle,
        "adapter": adapter,
        "hypotheses": hypotheses,
        "facts": {
            "training_dataset": training_fact,
            "knowledge_freeze": freeze_fact,
            "shell_hypothesis_set": hypothesis_fact,
            "model_fit": fit_fact,
            "predictions": pred_facts,
            "prediction_set": set_fact,
        },
    }


def b003_suite_manifest(*, model_ids: Sequence[str] = SUITE_MODEL_IDS) -> dict[str, Any]:
    """Frozen, ordered EZ-B003 suite: the three EZ-B001 models, unchanged."""
    ordered = list(model_ids)
    if len(set(ordered)) != len(ordered):
        raise ValueError(f"model suite contains duplicates: {ordered}")
    return {
        "model_suite_id": MODEL_SUITE_ID_B003,
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": B003_PROTOCOL_VERSION,
        "evidence_protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "model_ids": ordered,
        "ranking_rule": RANKING_RULE,
        "weak_baseline_rule": (
            "No baseline is removed. A weak model is reported, which is what makes "
            "a rediscovery claim checkable."
        ),
        "derived_target_rule": DERIVED_TARGET_RULE,
    }


def run_shell_suite(
    *,
    shell_freeze: ShellFreeze,
    targets: list[dict[str, Any]],
    source: str | Path,
    edition_id: str,
    suite_dir: str | Path,
    model_ids: Sequence[str] = SUITE_MODEL_IDS,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Predict and seal one run per model for a single masked closure."""
    suite_dir = Path(suite_dir)
    manifest = b003_suite_manifest(model_ids=model_ids)
    runs = []
    for model_id in manifest["model_ids"]:
        run_dir = suite_dir / model_id
        result = predict_shell_run(
            shell_freeze=shell_freeze,
            targets=targets,
            source=source,
            edition_id=edition_id,
            run_dir=run_dir,
            model_id=model_id,
            created_at=created_at,
        )
        marker = finalize_shell_run(run_dir, created_at=created_at)
        runs.append(
            {
                "model_id": model_id,
                "run_dir": str(run_dir),
                "challenge_id": result["run_manifest"]["challenge_id"],
                "mask_id": result["run_manifest"]["mask_id"],
                "freeze_id": result["run_manifest"]["freeze_id"],
                "profile": result["run_manifest"]["profile"],
                "split_digest": result["run_manifest"]["split_digest"],
                "target_identity_digest": result["run_manifest"]["target_identity_digest"],
                "model_manifest_hash": result["run_manifest"]["model_manifest_hash"],
                "prediction_set_fact_id": result["run_manifest"]["prediction_set_fact_id"],
                "shell_hypothesis_fact_id": result["run_manifest"]["shell_hypothesis_fact_id"],
                "finalization_marker_hash": marker["finalization_marker_hash"],
            }
        )
    assert_one_split_per_suite(runs)
    payload = {
        **manifest,
        "suite_dir": str(suite_dir),
        "challenge_id": shell_freeze.challenge_id,
        "mask_id": shell_freeze.mask_id,
        "mask": shell_freeze.mask.to_dict(),
        "mask_hash": shell_freeze.mask_hash,
        "challenge_manifest_hash": shell_freeze.challenge_manifest_hash,
        "indicator": shell_freeze.mask.indicator,
        "profile": shell_freeze.profile,
        "split_id": shell_freeze.split_id,
        "split_digest": shell_freeze.split_digest,
        "freeze_id": shell_freeze.freeze_id,
        "target_identity_digest": shell_freeze.target_identity_digest,
        "supported_chains": list(shell_freeze.supported_chains),
        "unsupported_chains": list(shell_freeze.unsupported_chains),
        "n_targets": len(targets),
        "source_hashes": list(shell_freeze.freeze.allowed_source_hashes),
        "feature_policy_id": shell_freeze.freeze.feature_policy_id,
        "runs": runs,
        **provenance_identity(),
    }
    suite_dir.mkdir(parents=True, exist_ok=True)
    (suite_dir / SUITE_MANIFEST_NAME).write_text(canonical_json(payload) + "\n", encoding="utf-8")
    return payload


def assert_one_split_per_suite(runs: Sequence[dict[str, Any]]) -> None:
    """Every model of a closure must have seen exactly one split and one profile."""
    for key in (
        "challenge_id",
        "mask_id",
        "freeze_id",
        "profile",
        "split_digest",
        "target_identity_digest",
    ):
        values = sorted({run[key] for run in runs})
        if len(values) != 1:
            raise ProtocolError(f"suite runs do not share one {key}: {values}")


def load_shell_targets(path: str | Path) -> list[dict[str, Any]]:
    """Identity-only target loader (reuses the EZ-B001 leakage-checked loader)."""
    targets = load_targets(path)
    for target in targets:
        leaked = sorted(TRUTH_BEARING_FIELDS.intersection(target))
        if leaked:
            raise LeakageError(f"target record carries truth fields: {leaked}")
    return targets
