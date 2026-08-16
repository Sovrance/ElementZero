"""EZ-B003 scoring: unlock the closure neighborhood only after the run is sealed.

The mass metrics are the EZ-B002 metrics, because a rediscovery claim that rests
on a badly reconstructed surface is not a rediscovery claim. What EZ-B003 adds is
the shell question (WO-10 sections 4, 5, 6):

1. build two binding surfaces over the same lattice::

       truth surface      snapshot mass at every point
       predicted surface  sealed prediction inside the mask,
                          frozen training mass outside it

2. derive S2n/S2p and then delta2n/delta2p on both surfaces,
3. per supported chain, compare the indicator at the withheld closure and rank
   the closure inside the preregistered search window,
4. aggregate, and apply the criterion that was frozen before any closure of an
   evaluated mass table was scored.

Every check EZ-B002 makes is made here too: the truth source must be exactly the
frozen snapshot, the run must be finalized and still hash as sealed, every scored
identity must be inside the mask and absent from training, and sigma is read from
the sealed prediction file rather than re-derived from truth.

Two EZ-B003-specific restraints:

* ``scope`` is a required argument of every criterion verdict, so a synthetic
  mechanics result can never be reported as a statement about an evaluated mass
  table,
* a ``NOT_EVALUABLE`` closure or chain is reported with its reasons and no
  metrics; it is never dropped.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from elementzero import B003_PROTOCOL_VERSION, BENCHMARK_EZ_B003, BENCHMARK_PROTOCOL_VERSION
from elementzero.benchmark.b001_score import _finalization_fact_id as finalization_fact_id
from elementzero.benchmark.b003_freeze import ShellFreeze
from elementzero.benchmark.b003_predict import SUITE_MANIFEST_NAME
from elementzero.benchmark.b003_prepare import (
    PROFILE_SEPARATION_RULE,
    assert_profile_not_mixed,
)
from elementzero.benchmark.distance import (
    DISTANCE_POLICY_ID,
    bucket_summaries,
    distance_bucket,
    error_vs_distance,
    isospin_asymmetry,
    nearest_training,
    region_for_z,
    training_lattice,
)
from elementzero.benchmark.metrics import score_rows
from elementzero.benchmark.shell_masks import (
    MASK_POLICY_ID,
    STATUS_EVALUABLE,
    STATUS_NOT_EVALUABLE,
    SUPPORT_POLICY_ID,
    ShellMask,
)
from elementzero.benchmark.shell_metrics import (
    CRITERION_SCOPE_RULE,
    DISCOVERY_METRICS_POLICY_ID,
    HYPOTHESIS_DECISION_RULE,
    REDISCOVERY_CRITERION_ID,
    SURFACE_PREDICTION,
    SURFACE_TRUTH,
    TOP_K,
    VERDICT_NOT_YET_SCORED,
    aggregate_discovery,
    chain_discovery_row,
    closure_discovery_metrics,
    evaluate_criterion,
    hypothesis_resolution,
    hypothesis_statements,
    rediscovery_criterion,
)
from elementzero.data.amdc import load_edition
from elementzero.data.amdc.common import PARSER_VERSION
from elementzero.data.identity import parse_nuclide_id
from elementzero.data.observations import GROUND_TRUTH_POLICY
from elementzero.errors import LeakageError, ProtocolError, SchemaError
from elementzero.evidence.atlas_adapter import (
    AtlasEvidenceAdapter,
    atlas_bundle_exists,
    read_atlas_facts,
    stable_source_uri,
    write_atlas_bundle,
)
from elementzero.evidence.freezes import assert_holdout_disjoint, identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import (
    assert_finalized_intact,
    finalization_marker_hash,
    is_finalized,
    read_json,
)
from elementzero.identity_meta import provenance_identity
from elementzero.physics.separation import (
    ORIGIN_PREDICTION,
    ORIGIN_TRAINING_TRUTH,
    ORIGIN_TRUTH,
    binding_surface,
    derivation_record,
    separation_policy,
)

CHALLENGE_COMPARISON_JSON = "challenge_comparison.json"
CHALLENGE_COMPARISON_MARKDOWN = "challenge_comparison.md"
SHELL_AGGREGATE_JSON = "shell_aggregate.json"
SHELL_AGGREGATE_MARKDOWN = "shell_aggregate.md"

SCOPE_SYNTHETIC = "synthetic"

COMPARISON_COLUMNS: tuple[str, ...] = (
    "challenge_id",
    "indicator",
    "model_id",
    "n",
    "MAE_keV",
    "RMSE_keV",
    "coverage_90",
    "calibration_error_90",
    "n_evaluable_chains",
    "sign_recovered_fraction",
    "rank_1_fraction",
    "top_k_fraction",
    "mean_absolute_indicator_error_MeV",
    "predicted_hypothesis",
    "truth_hypothesis",
)

BOUNDARY_RULE = (
    "EZ-B003 measures one narrow capability: rediscovery of known shell-related "
    "mass structure under controlled masking. A met criterion is not proof of a "
    "new magic number, and it is not evidence that a predicted Z = 154 shell gap "
    "or an island of stability exists. That claim would require independent "
    "physics-model ensembles, deformation calculations, fission calculations, "
    "decay competition, and far larger extrapolation uncertainty."
)

DERIVED_OBSERVABLE_SCORING_RULE = (
    "The predicted indicator is a frozen mix of the sealed prediction at the "
    "withheld closure and the frozen training masses two steps away. The mix is "
    "fixed by the mask geometry before any hidden truth is read. Every derived "
    "value is recorded as derived, with its inputs and their origins, and is "
    "never counted as independent evidence."
)


# --------------------------------------------------------------------------- #
# Binding surfaces                                                            #
# --------------------------------------------------------------------------- #


def build_surfaces(
    *,
    mask: ShellMask,
    truth_rows: Sequence[Mapping[str, Any]],
    predictions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """The truth surface and the sealed-reconstruction surface over one lattice.

    ``truth_rows`` are the ground-truth-eligible snapshot rows. Inside the mask
    the reconstruction surface uses the sealed prediction; outside it, the same
    frozen training mass the model was allowed to see. Keeping the outside
    identical on both surfaces is deliberate: the only difference between them is
    the withheld closure neighborhood, which is exactly what the benchmark asks
    about.
    """
    truth_points = []
    predicted_points = []
    for row in truth_rows:
        z, n = int(row["Z"]), int(row["N"])
        inside = mask.contains(z, n)
        truth_points.append(
            {
                "Z": z,
                "N": n,
                "mass_excess_keV": float(row["mass_excess_keV"]),
                "origin": ORIGIN_TRUTH if inside else ORIGIN_TRAINING_TRUTH,
            }
        )
        if not inside:
            predicted_points.append(
                {
                    "Z": z,
                    "N": n,
                    "mass_excess_keV": float(row["mass_excess_keV"]),
                    "origin": ORIGIN_TRAINING_TRUTH,
                }
            )
    for pred in predictions:
        z, n = parse_nuclide_id(pred["nuclide_id"])
        if not mask.contains(z, n):
            raise LeakageError(
                f"sealed prediction {pred['nuclide_id']} is outside mask {mask.mask_id}"
            )
        predicted_points.append(
            {
                "Z": z,
                "N": n,
                "mass_excess_keV": float(pred["mass_excess_keV"]),
                "origin": ORIGIN_PREDICTION,
            }
        )
    return {
        "truth": binding_surface(truth_points),
        "prediction": binding_surface(predicted_points),
    }


def chain_rows(
    *,
    mask: ShellMask,
    supported_chains: Sequence[int],
    unsupported_chains: Sequence[int],
    surfaces: Mapping[str, Any],
    top_k: int = TOP_K,
) -> list[dict[str, Any]]:
    """One discovery row per chain of the mask, unsupported chains included."""
    rows = [
        chain_discovery_row(
            mask=mask,
            chain=int(chain),
            truth_surface=surfaces["truth"],
            predicted_surface=surfaces["prediction"],
            top_k=top_k,
        )
        for chain in sorted(int(c) for c in supported_chains)
    ]
    for chain in sorted(int(c) for c in unsupported_chains):
        z, n = mask.point(chain=chain, coordinate=mask.closure)
        indicator = mask.indicator
        rows.append(
            {
                "challenge_id": mask.challenge_id,
                "mask_id": mask.mask_id,
                "axis": mask.axis,
                "closure": mask.closure,
                "chain": chain,
                "chain_axis": mask.span_axis_label,
                "nuclide_id": f"Z{z}-N{n}",
                "Z": z,
                "N": n,
                "indicator": indicator,
                "status": STATUS_NOT_EVALUABLE,
                "reasons": ["chain does not satisfy the preregistered support rule"],
                f"true_{indicator}": None,
                f"predicted_{indicator}": None,
                f"absolute_{indicator}_error": None,
                "sign_recovered": None,
                "true_sign": None,
                "predicted_sign": None,
                "predicted_peak": None,
                "true_peak": None,
                "local_peak_rank": None,
                "local_peak_rank_by_magnitude": None,
                "rank_bucket": None,
                "in_top_k": None,
                "n_peak_candidates": 0,
                "true_local_peak_rank": None,
                "derived": True,
                "independent_evidence": False,
            }
        )
    rows.sort(key=lambda r: r["chain"])
    return rows


# --------------------------------------------------------------------------- #
# One sealed run                                                              #
# --------------------------------------------------------------------------- #


def _rebuild_hypotheses(
    adapter: AtlasEvidenceAdapter,
    *,
    run_manifest: Mapping[str, Any],
    mask: ShellMask,
    sealed_fact: Mapping[str, Any],
) -> dict[str, Any]:
    """Rebuild the sealed H0/H1 pair and check it against the sealed fact.

    Atlas hypotheses are content-addressed, so rebuilding them from the same
    inputs must reproduce the same identities. If it does not, the hypothesis
    bookkeeping was changed between the seal and the scoring, which is exactly
    the failure this check exists to catch.
    """
    closure_label = f"{mask.closure_axis_label} = {mask.closure}"
    intervention = adapter.shell_masking_intervention(
        challenge_id=run_manifest["challenge_id"],
        mask=mask.to_dict(),
        mask_id=mask.mask_id,
        indicator=mask.indicator,
    )
    pair = adapter.shell_hypothesis_pair(
        challenge_id=run_manifest["challenge_id"],
        indicator=mask.indicator,
        closure_label=closure_label,
        intervention=intervention,
        derived_from_facts=(run_manifest["knowledge_freeze_fact_id"],),
        assumptions=(f"freeze:{run_manifest['freeze_id']}",),
    )
    sealed_ids = {
        entry["label"]: entry["hypothesis_id"] for entry in sealed_fact["content"]["hypotheses"]
    }
    rebuilt_ids = {label: hyp.hypothesis_id for label, hyp in pair.items()}
    if sealed_ids != rebuilt_ids:
        raise ProtocolError(
            f"sealed shell hypotheses {sealed_ids} differ from the rebuilt pair {rebuilt_ids}"
        )
    return {
        "hypotheses": pair,
        "intervention": intervention,
        "statements": hypothesis_statements(
            indicator=mask.indicator, closure_label=closure_label
        ),
    }


def score_shell_run(
    *,
    run_dir: str | Path,
    truth_source: str | Path,
    truth_edition_id: str,
    scope: str,
    out_dir: str | Path | None = None,
    created_at: str | None = None,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """Score one sealed EZ-B003 model run against the withheld closure truth."""
    run_dir = Path(run_dir)
    truth_source = Path(truth_source)
    if not scope:
        raise SchemaError("EZ-B003 scoring must declare the scope it is scoring")
    if not is_finalized(run_dir):
        raise LeakageError("prediction ledger was not finalized")
    marker = assert_finalized_intact(run_dir)
    marker_hash = finalization_marker_hash(run_dir)

    shell = ShellFreeze.from_dict(read_json(run_dir / "freeze.json"))
    freeze = shell.freeze
    mask = shell.mask
    predictions = read_json(run_dir / "predictions.json")
    run_manifest = read_json(run_dir / "run_manifest.json")
    if run_manifest.get("benchmark_id") != BENCHMARK_EZ_B003:
        raise ProtocolError(
            f"run {run_dir} is not an {BENCHMARK_EZ_B003} run: "
            f"{run_manifest.get('benchmark_id')!r}"
        )
    if run_manifest["mask_id"] != mask.mask_id:
        raise ProtocolError("run manifest and sealed freeze disagree on the shell mask")
    if run_manifest["split_digest"] != shell.split_digest:
        raise ProtocolError("run manifest and sealed freeze disagree on the split digest")
    if run_manifest["profile"] != shell.profile:
        raise ProtocolError("run manifest and sealed freeze disagree on the benchmark profile")

    truth_hash = sha256_file(truth_source)
    # A hidden-shell holdout has one snapshot. Scoring a different table would
    # silently change the benchmark, so the identity is asserted, not assumed.
    if truth_hash != freeze.raw_source_hash:
        raise ProtocolError(
            "EZ-B003 truth source must be the frozen snapshot itself; "
            f"{truth_hash} is not {freeze.raw_source_hash}"
        )
    if truth_edition_id not in freeze.allowed_edition_ids:
        raise ProtocolError(
            f"truth edition {truth_edition_id!r} is not the frozen edition "
            f"{list(freeze.allowed_edition_ids)}"
        )

    observations = load_edition(truth_edition_id, str(truth_source))
    truth_obs = {o.nuclide_id: o for o in observations}
    eligible = sorted(
        (o for o in observations if o.ground_truth_eligible), key=lambda o: o.nuclide_id
    )
    lattice = training_lattice(freeze.training_nuclide_ids)

    rows = []
    scored_truth = []
    for pred in predictions:
        nid = pred["nuclide_id"]
        if nid in freeze.training_nuclide_ids:
            raise LeakageError(f"held-out nuclide {nid} is present in training IDs")
        if not mask.contains_id(nid):
            raise LeakageError(f"scored nuclide {nid} lies outside mask {mask.mask_id}")
        if nid not in truth_obs:
            raise LeakageError(f"truth source has no record for {nid}")
        if "std_keV" not in pred:
            raise ProtocolError(
                f"sealed prediction for {nid} has no std_keV; sigma must come from "
                "the model, never from truth"
            )
        obs = truth_obs[nid]
        if not obs.ground_truth_eligible:
            raise LeakageError(f"truth record {nid} is not ground-truth eligible")
        z, n = parse_nuclide_id(nid)
        near = nearest_training(z=z, n=n, lattice=lattice)
        scored_truth.append(obs)
        rows.append(
            {
                "nuclide_id": nid,
                "Z": z,
                "N": n,
                "A": z + n,
                "challenge_id": shell.challenge_id,
                "mask_id": mask.mask_id,
                "chain": mask.chain_key(z, n),
                "closure_coordinate": mask.closure_coordinate(z, n),
                "prediction_keV": float(pred["mass_excess_keV"]),
                "std_keV": float(pred["std_keV"]),
                "truth_keV": obs.mass_excess_keV,
                "truth_uncertainty_keV": obs.uncertainty_keV,
                "interval_p90": [float(v) for v in pred["intervals"]["p90"]],
                "interval_p95": [float(v) for v in pred["intervals"]["p95"]],
                "nearest_training_L1": near["nearest_training_L1"],
                "nearest_training_L2": near["nearest_training_L2"],
                "nearest_training_nuclide_id": near["nearest_training_nuclide_id"],
                "distance_bucket": distance_bucket(near["nearest_training_L1"]),
                "region": region_for_z(z),
                "isospin_asymmetry": isospin_asymmetry(z, n),
            }
        )
    if not rows:
        raise ProtocolError(f"mask {mask.mask_id} produced no scored rows")
    assert_holdout_disjoint(freeze, [r["nuclide_id"] for r in rows])
    target_ids = [r["nuclide_id"] for r in rows]
    if identity_digest(target_ids) != shell.target_identity_digest:
        raise ProtocolError("scored identities differ from the target set pinned by the freeze")

    # -- the shell question -------------------------------------------------- #
    surfaces = build_surfaces(
        mask=mask,
        truth_rows=[
            {"Z": o.Z, "N": o.N, "mass_excess_keV": o.mass_excess_keV} for o in eligible
        ],
        predictions=predictions,
    )
    discovery_rows = chain_rows(
        mask=mask,
        supported_chains=shell.supported_chains,
        unsupported_chains=shell.unsupported_chains,
        surfaces=surfaces,
        top_k=top_k,
    )
    discovery = closure_discovery_metrics(discovery_rows, mask=mask, top_k=top_k)
    resolutions = {
        surface: hypothesis_resolution(
            discovery_rows, indicator=mask.indicator, surface=surface
        )
        for surface in (SURFACE_PREDICTION, SURFACE_TRUTH)
    }

    depths = [int(r["nearest_training_L1"]) for r in rows]
    mass_metrics = score_rows(rows)
    metrics = {
        **mass_metrics,
        "benchmark_id": BENCHMARK_EZ_B003,
        "challenge_id": shell.challenge_id,
        "mask_id": mask.mask_id,
        "axis": mask.axis,
        "closure": mask.closure,
        "indicator": mask.indicator,
        "profile": shell.profile,
        "distance_policy_id": DISTANCE_POLICY_ID,
        "mask_policy_id": MASK_POLICY_ID,
        "support_policy_id": SUPPORT_POLICY_ID,
        "discovery_metrics_policy_id": DISCOVERY_METRICS_POLICY_ID,
        "max_nearest_training_L1": max(depths),
        "min_nearest_training_L1": min(depths),
        "distance_buckets": bucket_summaries(rows),
        "discovery": discovery,
        "hypothesis_resolution": resolutions,
        "boundary_rule": BOUNDARY_RULE,
        "profile_separation_rule": PROFILE_SEPARATION_RULE,
    }
    criterion = evaluate_criterion(
        aggregate_discovery([discovery], top_k=top_k),
        calibration_error_90=mass_metrics["cal_error_90"],
        scope=scope,
    )
    metrics["criterion"] = criterion

    # -- Atlas -------------------------------------------------------------- #
    model_id = str(run_manifest.get("model_id", ""))
    for stage in ("predict", "finalize"):
        if not atlas_bundle_exists(run_dir, stage=stage):
            raise ProtocolError(
                f"run {run_dir} has no Atlas {stage} bundle; validation must not exist "
                "without a sealed, lineage-complete prediction set"
            )
    adapter = AtlasEvidenceAdapter(created_at=created_at)
    sealed_facts = read_atlas_facts(run_dir, stage="predict")
    adapter.rehydrate(sealed_facts)
    adapter.rehydrate(read_atlas_facts(run_dir, stage="finalize"))
    prediction_set_fact_id = run_manifest["prediction_set_fact_id"]
    hypothesis_set_fact_id = run_manifest["shell_hypothesis_fact_id"]
    final_fact_id = finalization_fact_id(run_dir, marker_hash)
    sealed_hypothesis_fact = next(
        (f for f in sealed_facts if f["fact_id"] == hypothesis_set_fact_id), None
    )
    if sealed_hypothesis_fact is None:
        raise ProtocolError(
            f"run {run_dir} does not carry the sealed shell hypothesis fact "
            f"{hypothesis_set_fact_id!r}"
        )
    rebuilt = _rebuild_hypotheses(
        adapter, run_manifest=run_manifest, mask=mask, sealed_fact=sealed_hypothesis_fact
    )

    truth_artifact = adapter.source_artifact(
        truth_source.read_bytes(),
        source_uri=stable_source_uri(truth_source),
        acquired_at=scored_truth[0].source_release_date if scored_truth else "1970-01-01",
    )
    truth_event = adapter.observation_event(truth_artifact)
    adapter.append_provenance(
        entity=truth_artifact.artifact_id,
        activity_type="LOAD",
        used=(),
        generated=(truth_artifact.artifact_id,),
    )
    truth_fact = adapter.truth_dataset_fact(
        artifact=truth_artifact,
        truth_edition_id=truth_edition_id,
        truth_source_hash=truth_hash,
        normalized_truth_hash=sha256_hex(
            [o.to_dict() for o in sorted(scored_truth, key=lambda o: o.nuclide_id)]
        ),
        target_identity_digest=identity_digest(target_ids),
        truth_count=len(scored_truth),
        parser_version=PARSER_VERSION,
        ground_truth_policy=GROUND_TRUTH_POLICY,
        event=truth_event,
    )
    adapter.append_fact(truth_fact)
    adapter.append_provenance(
        entity=truth_fact.fact_id,
        activity_type="LOWER",
        used=(truth_artifact.artifact_id,),
        generated=(truth_fact.fact_id,),
    )

    val = adapter.validation_fact(
        benchmark_id=BENCHMARK_EZ_B003,
        metrics=metrics,
        run_id=run_dir.name,
        prediction_set_fact_id=prediction_set_fact_id,
        finalization_fact_id=final_fact_id,
        truth_dataset_fact_id=truth_fact.fact_id,
        protocol_version=BENCHMARK_PROTOCOL_VERSION,
        model_id=model_id,
        truth_source_hash=truth_hash,
        finalization_marker_hash=marker_hash,
    )
    adapter.append_fact(val)
    adapter.append_provenance(
        entity=val.fact_id,
        activity_type="CERTIFY",
        used=(prediction_set_fact_id, final_fact_id, truth_fact.fact_id),
        generated=(val.fact_id,),
    )

    # One derived-observable fact per surface per evaluable chain. Each one says
    # derived = true and independent_evidence = false (WO-10 section 4).
    derived_facts = []
    for row in discovery_rows:
        if row["status"] != STATUS_EVALUABLE:
            continue
        for surface, depends_on in (
            (SURFACE_PREDICTION, (prediction_set_fact_id,)),
            (SURFACE_TRUTH, (truth_fact.fact_id,)),
        ):
            record = derivation_record(
                mask.indicator,
                surfaces[surface],
                z=int(row["Z"]),
                n=int(row["N"]),
            )
            fact = adapter.derived_observable_fact(
                record=record,
                surface=surface,
                depends_on_facts=depends_on,
                challenge_id=shell.challenge_id,
                mask_id=mask.mask_id,
                freeze_id=freeze.freeze_id,
                model_id=model_id if surface == SURFACE_PREDICTION else None,
            )
            adapter.append_fact(fact)
            adapter.append_provenance(
                entity=fact.fact_id,
                activity_type="TRANSFORM",
                used=tuple(depends_on),
                generated=(fact.fact_id,),
            )
            derived_facts.append(fact)

    resolved = {
        surface: adapter.resolve_shell_hypotheses(
            rebuilt["hypotheses"],
            selected_label=resolutions[surface]["selected_label"],
            derived_from_facts=(val.fact_id, truth_fact.fact_id),
        )
        for surface in (SURFACE_PREDICTION, SURFACE_TRUTH)
    }
    discovery_fact = adapter.shell_discovery_fact(
        benchmark_id=BENCHMARK_EZ_B003,
        challenge_id=shell.challenge_id,
        mask_id=mask.mask_id,
        indicator=mask.indicator,
        model_id=model_id,
        run_id=run_dir.name,
        scope=scope,
        protocol_version=B003_PROTOCOL_VERSION,
        discovery_metrics=discovery,
        criterion=criterion,
        resolution=resolutions,
        hypotheses=resolved[SURFACE_PREDICTION],
        validation_fact_id=val.fact_id,
        hypothesis_set_fact_id=hypothesis_set_fact_id,
        derived_observable_fact_ids=[f.fact_id for f in derived_facts],
    )
    adapter.append_fact(discovery_fact)
    adapter.append_provenance(
        entity=discovery_fact.fact_id,
        activity_type="CERTIFY",
        used=tuple(
            sorted(
                {val.fact_id, hypothesis_set_fact_id, *(f.fact_id for f in derived_facts)}
            )
        ),
        generated=(discovery_fact.fact_id,),
    )

    dest = Path(out_dir) if out_dir is not None else run_dir / "scoring"
    dest.mkdir(parents=True, exist_ok=True)
    new_facts = [truth_fact, val, *derived_facts, discovery_fact]
    new_ids = {truth_artifact.artifact_id, *(f.fact_id for f in new_facts)}
    atlas_bundle = write_atlas_bundle(
        dest,
        stage="score",
        facts=new_facts,
        provenance=[r for r in adapter.store.provenance() if r.entity in new_ids],
    )
    report = {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b003_protocol_version": B003_PROTOCOL_VERSION,
        "stage": "score",
        "scope": scope,
        "run_id": run_dir.name,
        "freeze_id": freeze.freeze_id,
        "challenge_id": shell.challenge_id,
        "mask_id": mask.mask_id,
        "mask": mask.to_dict(),
        "mask_hash": shell.mask_hash,
        "challenge_manifest_hash": shell.challenge_manifest_hash,
        "axis": mask.axis,
        "closure": mask.closure,
        "indicator": mask.indicator,
        "profile": shell.profile,
        "split_digest": shell.split_digest,
        "model_id": model_id,
        "truth_source_hash": truth_hash,
        "truth_edition_id": truth_edition_id,
        "parser_version": PARSER_VERSION,
        "ground_truth_policy": GROUND_TRUTH_POLICY,
        "separation_policy": separation_policy(),
        "metrics": metrics,
        "rows": rows,
        "discovery_rows": discovery_rows,
        "error_vs_distance": error_vs_distance(rows),
        "criterion": criterion,
        "hypothesis_resolution": resolutions,
        "hypothesis_decision_rule": HYPOTHESIS_DECISION_RULE,
        "hypothesis_statements": rebuilt["statements"],
        "resolved_hypotheses": {
            surface: [
                {**hyp.to_dict(), "label": label}
                for label, hyp in sorted(resolved[surface].items())
            ]
            for surface in (SURFACE_PREDICTION, SURFACE_TRUTH)
        },
        "finalization": marker,
        "finalization_marker_hash": marker_hash,
        "prediction_set_fact_id": prediction_set_fact_id,
        "finalization_fact_id": final_fact_id,
        "shell_hypothesis_fact_id": hypothesis_set_fact_id,
        "truth_dataset_fact_id": truth_fact.fact_id,
        "validation_fact_id": val.fact_id,
        "shell_discovery_fact_id": discovery_fact.fact_id,
        "derived_observable_fact_ids": [f.fact_id for f in derived_facts],
        "atlas_bundle_hashes": atlas_bundle,
        "boundary_rule": BOUNDARY_RULE,
        "derived_observable_scoring_rule": DERIVED_OBSERVABLE_SCORING_RULE,
        "scope_rule": CRITERION_SCOPE_RULE,
        **provenance_identity(),
    }
    (dest / "metrics.json").write_text(canonical_json(metrics) + "\n", encoding="utf-8")
    (dest / "score_report.json").write_text(canonical_json(report) + "\n", encoding="utf-8")
    return report


# --------------------------------------------------------------------------- #
# One closure, every model                                                    #
# --------------------------------------------------------------------------- #


def score_shell_suite(
    *,
    suite_dir: str | Path,
    truth_source: str | Path,
    truth_edition_id: str,
    scope: str,
    out_dir: str | Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Score every sealed model run of one closure and compare the models."""
    suite_dir = Path(suite_dir)
    suite = read_json(suite_dir / SUITE_MANIFEST_NAME)
    dest = Path(out_dir) if out_dir is not None else suite_dir
    dest.mkdir(parents=True, exist_ok=True)
    reports = []
    for run in suite["runs"]:
        run_dir = Path(run["run_dir"])
        if not run_dir.is_absolute():
            run_dir = suite_dir / run_dir.name
        if not run_dir.is_dir():
            run_dir = suite_dir / run["model_id"]
        if finalization_marker_hash(run_dir) != run["finalization_marker_hash"]:
            raise LeakageError(
                f"finalization marker of {run['model_id']} changed after the seal"
            )
        reports.append(
            score_shell_run(
                run_dir=run_dir,
                truth_source=truth_source,
                truth_edition_id=truth_edition_id,
                scope=scope,
                out_dir=run_dir / "scoring",
                created_at=created_at,
            )
        )
    comparison = build_challenge_comparison(reports, suite=suite, scope=scope)
    (dest / CHALLENGE_COMPARISON_JSON).write_text(
        canonical_json(comparison) + "\n", encoding="utf-8"
    )
    (dest / CHALLENGE_COMPARISON_MARKDOWN).write_text(
        comparison_markdown(
            comparison, title=f"EZ-B003 closure {comparison['challenge_id']}"
        ),
        encoding="utf-8",
    )
    return comparison


def _comparison_row(report: Mapping[str, Any]) -> dict[str, Any]:
    metrics = report["metrics"]
    discovery = metrics["discovery"]
    resolutions = report["hypothesis_resolution"]
    return {
        "challenge_id": report["challenge_id"],
        "mask_id": report["mask_id"],
        "axis": report["axis"],
        "closure": report["closure"],
        "indicator": report["indicator"],
        "profile": report["profile"],
        "model_id": report["model_id"],
        "n": metrics["n"],
        "MAE_keV": metrics["MAE_keV"],
        "MedAE_keV": metrics["MedAE_keV"],
        "RMSE_keV": metrics["RMSE_keV"],
        "NLPD": metrics["NLPD"],
        "coverage_90": metrics["coverage_90"],
        "coverage_95": metrics["coverage_95"],
        "calibration_error_90": metrics["cal_error_90"],
        "calibration_error_95": metrics["cal_error_95"],
        "max_nearest_training_L1": metrics["max_nearest_training_L1"],
        "n_chains": discovery["n_chains"],
        "n_evaluable_chains": discovery["n_evaluable_chains"],
        "n_not_evaluable_chains": discovery["n_not_evaluable_chains"],
        "sign_recovered_fraction": discovery["sign_recovered_fraction"],
        "rank_1_fraction": discovery["rank_1_fraction"],
        "top_k_fraction": discovery["top_k_fraction"],
        "mean_absolute_indicator_error_MeV": discovery["mean_absolute_indicator_error_MeV"],
        "predicted_hypothesis": resolutions[SURFACE_PREDICTION]["selected_label"],
        "truth_hypothesis": resolutions[SURFACE_TRUTH]["selected_label"],
        "criterion_verdict": report["criterion"]["verdict"],
        "run_id": report["run_id"],
        "freeze_id": report["freeze_id"],
        "split_digest": report["split_digest"],
        "validation_fact_id": report["validation_fact_id"],
        "shell_discovery_fact_id": report["shell_discovery_fact_id"],
    }


def build_challenge_comparison(
    reports: Sequence[Mapping[str, Any]],
    *,
    suite: Mapping[str, Any],
    scope: str,
) -> dict[str, Any]:
    """Every model of one closure, every metric. No ranking, nothing dropped."""
    expected = list(suite["model_ids"])
    by_model = {r["model_id"]: r for r in reports}
    missing = [m for m in expected if m not in by_model]
    if missing:
        raise ProtocolError(f"challenge comparison is missing scored models: {missing}")
    freeze_ids = sorted({r["freeze_id"] for r in reports})
    splits = sorted({r["split_digest"] for r in reports})
    challenges = sorted({r["challenge_id"] for r in reports})
    if len(freeze_ids) != 1 or len(splits) != 1 or len(challenges) != 1:
        raise ProtocolError(
            f"compared models do not share one shell split: freezes={freeze_ids} "
            f"splits={splits} challenges={challenges}"
        )
    profile = assert_profile_not_mixed(
        (r["profile"] for r in reports), where="challenge comparison"
    )
    return {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b003_protocol_version": B003_PROTOCOL_VERSION,
        "model_suite_id": suite["model_suite_id"],
        "scope": scope,
        "challenge_id": challenges[0],
        "mask_id": reports[0]["mask_id"],
        "mask": reports[0]["mask"],
        "mask_hash": reports[0]["mask_hash"],
        "challenge_manifest_hash": reports[0]["challenge_manifest_hash"],
        "axis": reports[0]["axis"],
        "closure": reports[0]["closure"],
        "indicator": reports[0]["indicator"],
        "profile": profile,
        "freeze_id": freeze_ids[0],
        "split_digest": splits[0],
        "truth_source_hash": sorted({r["truth_source_hash"] for r in reports})[0],
        "columns": list(COMPARISON_COLUMNS),
        "ranking_rule": suite["ranking_rule"],
        "criterion": rediscovery_criterion(),
        "boundary_rule": BOUNDARY_RULE,
        "profile_separation_rule": PROFILE_SEPARATION_RULE,
        "hypothesis_decision_rule": HYPOTHESIS_DECISION_RULE,
        "rows": [_comparison_row(by_model[model_id]) for model_id in expected],
        **provenance_identity(),
    }


# --------------------------------------------------------------------------- #
# Every closure, every model                                                  #
# --------------------------------------------------------------------------- #


def aggregate_challenges(
    reports: Sequence[Mapping[str, Any]],
    *,
    challenge_ids: Sequence[str],
    model_ids: Sequence[str],
    challenge_manifest_hash: str,
    scope: str,
    not_evaluable: Sequence[Mapping[str, Any]] = (),
    top_k: int = TOP_K,
) -> dict[str, Any]:
    """One table over every evaluable closure and every model, plus the criterion.

    Every evaluable closure must appear for every model, and the closures the
    support rule refused are carried alongside as ``NOT_EVALUABLE`` rather than
    omitted (WO-10 section 2).
    """
    rows = [_comparison_row(r) for r in reports]
    present = {(row["challenge_id"], row["model_id"]) for row in rows}
    missing = sorted(
        f"{challenge_id}/{model_id}"
        for challenge_id in challenge_ids
        for model_id in model_ids
        if (challenge_id, model_id) not in present
    )
    if missing:
        raise ProtocolError(f"aggregate is missing scored closure/model pairs: {missing}")
    extra = sorted({row["challenge_id"] for row in rows} - set(challenge_ids))
    if extra:
        raise ProtocolError(f"aggregate contains closures outside the frozen manifest: {extra}")
    hashes = sorted({r["challenge_manifest_hash"] for r in reports})
    if hashes != [challenge_manifest_hash]:
        raise ProtocolError(
            f"scored runs quote challenge manifest hashes {hashes}, "
            f"not {challenge_manifest_hash!r}"
        )
    profile = assert_profile_not_mixed((r["profile"] for r in reports), where="shell aggregate")

    ordered_rows = sorted(
        rows, key=lambda row: (row["challenge_id"], model_ids.index(row["model_id"]))
    )
    by_model: dict[str, Any] = {}
    for model_id in model_ids:
        model_reports = [r for r in reports if r["model_id"] == model_id]
        model_rows = [row for r in model_reports for row in r["rows"]]
        pooled_mass = score_rows(model_rows)
        pooled_discovery = aggregate_discovery(
            [r["metrics"]["discovery"] for r in model_reports], top_k=top_k
        )
        by_model[model_id] = {
            "n_closures": len(model_reports),
            "pooled_mass": {**pooled_mass, "distance_buckets": bucket_summaries(model_rows)},
            "pooled_discovery": pooled_discovery,
            "criterion": evaluate_criterion(
                pooled_discovery,
                calibration_error_90=pooled_mass["cal_error_90"],
                scope=scope,
            ),
            "per_closure": [
                {
                    "challenge_id": r["challenge_id"],
                    "indicator": r["indicator"],
                    "MAE_keV": r["metrics"]["MAE_keV"],
                    "RMSE_keV": r["metrics"]["RMSE_keV"],
                    "coverage_90": r["metrics"]["coverage_90"],
                    "calibration_error_90": r["metrics"]["cal_error_90"],
                    "n_evaluable_chains": r["metrics"]["discovery"]["n_evaluable_chains"],
                    "sign_recovered_fraction": r["metrics"]["discovery"][
                        "sign_recovered_fraction"
                    ],
                    "rank_1_fraction": r["metrics"]["discovery"]["rank_1_fraction"],
                    "top_k_fraction": r["metrics"]["discovery"]["top_k_fraction"],
                    "predicted_hypothesis": r["hypothesis_resolution"][SURFACE_PREDICTION][
                        "selected_label"
                    ],
                    "truth_hypothesis": r["hypothesis_resolution"][SURFACE_TRUTH][
                        "selected_label"
                    ],
                }
                for r in sorted(model_reports, key=lambda r: r["challenge_id"])
            ],
        }
    return {
        "benchmark_id": BENCHMARK_EZ_B003,
        "protocol_version": BENCHMARK_PROTOCOL_VERSION,
        "b003_protocol_version": B003_PROTOCOL_VERSION,
        "scope": scope,
        "profile": profile,
        "challenge_manifest_hash": challenge_manifest_hash,
        "challenge_ids": list(challenge_ids),
        "model_ids": list(model_ids),
        "columns": list(COMPARISON_COLUMNS),
        "criterion": rediscovery_criterion(),
        "criterion_id": REDISCOVERY_CRITERION_ID,
        "n_scored_targets": sum(len(r["rows"]) for r in reports),
        "rows": ordered_rows,
        "by_model": by_model,
        "not_evaluable_closures": [dict(entry) for entry in not_evaluable],
        "n_not_evaluable_closures": len(not_evaluable),
        "boundary_rule": BOUNDARY_RULE,
        "profile_separation_rule": PROFILE_SEPARATION_RULE,
        "scope_rule": CRITERION_SCOPE_RULE,
        "hypothesis_decision_rule": HYPOTHESIS_DECISION_RULE,
        **provenance_identity(),
    }


def real_closure_status(*, scope: str) -> dict[str, Any]:
    """The explicit record that evaluated-table closures are not scored yet.

    WO-10 section 9 allows the thresholds to be frozen on synthetic mechanics
    before any real closure is scored, but it does not allow that state to be
    implicit. This is the record: the criterion exists, it is frozen, and its
    verdict for evaluated mass tables is NOT_YET_SCORED.
    """
    return {
        "criterion": rediscovery_criterion(),
        "thresholds_frozen": True,
        "calibrated_on": SCOPE_SYNTHETIC,
        "scored_scope": scope,
        "evaluated_mass_table_verdict": VERDICT_NOT_YET_SCORED,
        "evaluated_mass_table_rule": (
            "No closure of an evaluated mass table has been scored under "
            f"{REDISCOVERY_CRITERION_ID}. The thresholds above are frozen; scoring "
            "a real closure is a separate, later act that may not change them."
        ),
        "boundary_rule": BOUNDARY_RULE,
        "scope_rule": CRITERION_SCOPE_RULE,
    }


def _format_cell(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return format(value, ".6g")
    return str(value)


def comparison_markdown(payload: Mapping[str, Any], *, title: str) -> str:
    columns = list(payload["columns"])
    criterion = payload["criterion"]
    lines = [
        f"# {title}",
        "",
        f"benchmark_id: {payload['benchmark_id']}",
        f"protocol_version: {payload['protocol_version']}",
        f"b003_protocol_version: {payload['b003_protocol_version']}",
        f"scope: {payload['scope']}",
        f"profile: {payload['profile']}",
        "",
        f"criterion: {criterion['criterion_id']}"
        f" (sign >= {criterion['min_sign_fraction']},"
        f" top-{criterion['top_k']} >= {criterion['min_top_k_fraction']},"
        f" rank-1 >= {criterion['min_rank_1_fraction']},"
        f" abs(coverage_90 - 0.90) <= {criterion['max_calibration_error_90']})",
        "",
        f"boundary: {payload['boundary_rule']}",
        "",
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in payload["rows"]:
        lines.append("| " + " | ".join(_format_cell(row.get(c)) for c in columns) + " |")
    lines.extend(
        [
            "",
            "Derived observables (ASCII):",
            "",
            "    S2n(Z,N)     = B(Z,N) - B(Z,N-2)",
            "    S2p(Z,N)     = B(Z,N) - B(Z-2,N)",
            "    delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)",
            "    delta2p(Z,N) = S2p(Z,N) - S2p(Z+2,N)",
            "",
        ]
    )
    by_model = payload.get("by_model")
    if by_model:
        lines.extend(
            [
                "Pooled criterion per model (all evaluable closures):",
                "",
                "| model_id | n_closures | n_evaluable_chains | sign | rank_1 | top_k "
                "| calibration_error_90 | verdict |",
                "| --- | --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for model_id in payload["model_ids"]:
            entry = by_model[model_id]
            discovery = entry["pooled_discovery"]
            lines.append(
                f"| {model_id} | {entry['n_closures']} | {discovery['n_evaluable_chains']} | "
                f"{_format_cell(discovery['sign_recovered_fraction'])} | "
                f"{_format_cell(discovery['rank_1_fraction'])} | "
                f"{_format_cell(discovery['top_k_fraction'])} | "
                f"{_format_cell(entry['pooled_mass']['cal_error_90'])} | "
                f"{entry['criterion']['verdict']} |"
            )
        lines.append("")
    not_evaluable = payload.get("not_evaluable_closures")
    if not_evaluable:
        lines.extend(
            [
                "Closures refused by the support rule (reported, never dropped):",
                "",
                "| challenge_id | status | reasons |",
                "| --- | --- | --- |",
            ]
        )
        for entry in not_evaluable:
            reasons = "; ".join(entry.get("reasons", [])) or "n/a"
            lines.append(
                f"| {entry.get('challenge_id')} | {entry.get('status', STATUS_NOT_EVALUABLE)} "
                f"| {reasons} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_shell_aggregate(
    *,
    out_dir: str | Path,
    reports: Sequence[Mapping[str, Any]],
    challenge_ids: Sequence[str],
    model_ids: Sequence[str],
    challenge_manifest_hash: str,
    scope: str,
    not_evaluable: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    aggregate = aggregate_challenges(
        reports,
        challenge_ids=challenge_ids,
        model_ids=model_ids,
        challenge_manifest_hash=challenge_manifest_hash,
        scope=scope,
        not_evaluable=not_evaluable,
    )
    aggregate["real_closure_status"] = real_closure_status(scope=scope)
    dest = Path(out_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / SHELL_AGGREGATE_JSON).write_text(canonical_json(aggregate) + "\n", encoding="utf-8")
    (dest / SHELL_AGGREGATE_MARKDOWN).write_text(
        comparison_markdown(
            aggregate, title="EZ-B003 hidden shell rediscovery aggregate"
        ),
        encoding="utf-8",
    )
    return aggregate
