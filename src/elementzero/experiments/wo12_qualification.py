"""WO-12 synthetic qualification (spec sections 19-22).

Two NEW qualification fixtures, different from EZ-B002-v1, EZ-B003-v1, and
the WO-11 dev fixtures:

    EZ-B002-v2-qual   fresh smooth valley chart, Z 10..64 (all three
                      selection bands), new coefficients / ripple phases /
                      drift, holdout regions selected deterministically.

    EZ-B003-v2-qual   fresh shell chart on the lead region, Z 72..92 x
                      N 116..140, injected closures at the real magic pair
                      N0 = 126 (gap 1.3 MeV) and Z0 = 82 (gap 1.1 MeV).
                      Real physics tables carry shell structure there from
                      their own physics — which is exactly what WO-12 section
                      21 allows and what the federation exists to exploit.

The qualification reuses the FROZEN v1 seal/score mechanics unchanged: the
federation participants are injected through the same scoped registry swap
the WO-11 oracle controls used, each wrapped in a recorder that captures the
decomposed federation uncertainty next to the sealed Gaussian view.

Everything the verdict depends on is frozen in ``V2_QUAL_PROTOCOL`` before
any qualification is scored, thresholds included. A failed qualification is
preserved honestly and blocks evaluated-table v2 runs (section 29).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from elementzero.data.amdc.ame2020 import EDITION as AME2020_SPEC
from elementzero.data.amdc.common import format_ame_line
from elementzero.data.identity import NuclideIdentity, parse_nuclide_id
from elementzero.errors import ProtocolError
from elementzero.evidence.freezes import identity_digest
from elementzero.evidence.hashing import canonical_json, sha256_file, sha256_hex
from elementzero.evidence.ledger import read_json
from elementzero.models.federation import FEDERATION_PROTOCOL_VERSION
from elementzero.models.federation.calibration import (
    CALIBRATION_SPLIT_RULE,
    assert_split_disjoint,
    calibration_metrics,
    split_fit_calibration,
)
from elementzero.models.federation.disagreement import (
    disagreement_by_depth,
    disagreement_rows,
)
from elementzero.models.federation.protocol import (
    STATUS_AVAILABLE,
    FederationPrediction,
    NuclearMassModel,
)
from elementzero.models.federation.runtime_lock import capture_runtime
from elementzero.physics.conversion import mass_excess_keV_from_binding
from elementzero.physics.semf import pairing_sign

B002_V2_QUAL_ID = "EZ-B002-v2-qual"
B003_V2_QUAL_ID = "EZ-B003-v2-qual"
EDITION_ID = "AME2020"
QUAL_CREATED_AT = "2026-08-16T12:00:00Z"

# The WO-12 input baseline: the merge commit that carries the WO-11
# adjudication (PR #10). Qualification runs pin ELEMENTZERO_COMMIT to it so
# every sealed qualification artifact is deterministic across rebuilds.
WO12_BASELINE_COMMIT = "ac6152e1c1a23afe7111e8ba2b218e4487e4ec65"

FIXTURES_RELPATH = "tests/fixtures/wo12"
B002_CHART_NAME = "ez-b002-v2-qual-chart.mas20"
B003_CHART_NAME = "ez-b003-v2-qual-chart.mas20"

# --------------------------------------------------------------------------- #
# Fixture surfaces — deliberately distinct from v1 and the WO-11 dev charts   #
# --------------------------------------------------------------------------- #

QUAL_COEFFS = {"a_v": 15.9, "a_s": 18.1, "a_c": 0.72, "a_a": 23.0, "a_p": 11.8}

# Z starts at 12: the band is then fully covered by both approved physics
# tables (verified cell-by-cell; Z=10 would put Ne-17 beyond both drip lines,
# and a residual model that honestly skips an uncovered training pair would
# trip the frozen training-digest check).
B002_QUAL_Z_MIN, B002_QUAL_Z_MAX = 12, 64
B002_QUAL_ESTIMATED_MODULUS = 53

B003_QUAL_Z_MIN, B003_QUAL_Z_MAX = 72, 92
B003_QUAL_N_MIN, B003_QUAL_N_MAX = 116, 140
B003_QUAL_ESTIMATED_MODULUS = 59
B003_QUAL_NEUTRON_CLOSURE = 126
B003_QUAL_PROTON_CLOSURE = 82
B003_QUAL_NEUTRON_GAP_MEV = 1.3
B003_QUAL_PROTON_GAP_MEV = 1.1

FIXTURE_NOVELTY_RULE = (
    "ez-wo12-fixture-novelty-v1: the v2 qualification charts differ from "
    "EZ-B002-v1/EZ-B003-v1 (new coefficients, phases, windows; closures moved "
    "from N0=50/Z0=28) and from the WO-11 dev fixtures (different "
    "coefficients, phases, windows; closures moved from N0=82/Z0=50 to the "
    "lead region N0=126/Z0=82)."
)


def _qual_ripple_MeV(z: int, n: int) -> float:
    return (
        0.50 * math.cos(0.51 * n + 2.10)
        + 0.42 * math.cos(0.29 * z + 1.70)
        + 0.28 * math.cos(0.15 * (n - z) + 0.90)
    )


def _qual_binding_MeV(z: int, n: int) -> float:
    a = float(z + n)
    return (
        QUAL_COEFFS["a_v"] * a
        - QUAL_COEFFS["a_s"] * a ** (2.0 / 3.0)
        - QUAL_COEFFS["a_c"] * z * (z - 1) / a ** (1.0 / 3.0)
        - QUAL_COEFFS["a_a"] * (n - z) ** 2 / a
        + QUAL_COEFFS["a_p"] * pairing_sign(z, n) / a**0.5
    )


def _qual_shell_term_MeV(z: int, n: int) -> float:
    return -B003_QUAL_NEUTRON_GAP_MEV * max(0, n - B003_QUAL_NEUTRON_CLOSURE) - (
        B003_QUAL_PROTON_GAP_MEV * max(0, z - B003_QUAL_PROTON_CLOSURE)
    )


def _write_chart(path: Path, rows: list[tuple[int, int, float, float, bool]]) -> Path:
    lines = ["   AME synthetic WO-12 v2 qualification chart for ElementZero\n"]
    for z, n, mass_excess, unc, estimated in rows:
        lines.append(
            format_ame_line(
                n=n,
                z=z,
                a=z + n,
                el="X",
                mass_excess_keV=mass_excess,
                uncertainty_keV=unc,
                estimated=estimated,
                spec=AME2020_SPEC,
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_b002_qual_chart(path: str | Path) -> Path:
    rows = []
    for z in range(B002_QUAL_Z_MIN, B002_QUAL_Z_MAX + 1):
        center = round(z + 0.010 * z * z)
        half_width = 4 + z // 20
        for n in range(center - half_width, center + half_width + 1):
            if n < 1:
                continue
            binding = _qual_binding_MeV(z, n) + _qual_ripple_MeV(z, n)
            rows.append(
                (
                    z,
                    n,
                    mass_excess_keV_from_binding(z=z, n=n, binding_MeV=binding),
                    12.0 + (z % 4),
                    (z + n) % B002_QUAL_ESTIMATED_MODULUS == 0,
                )
            )
    return _write_chart(Path(path), rows)


def write_b003_qual_chart(path: str | Path) -> Path:
    rows = []
    for z in range(B003_QUAL_Z_MIN, B003_QUAL_Z_MAX + 1):
        for n in range(B003_QUAL_N_MIN, B003_QUAL_N_MAX + 1):
            binding = (
                _qual_binding_MeV(z, n) + _qual_ripple_MeV(z, n) + _qual_shell_term_MeV(z, n)
            )
            rows.append(
                (
                    z,
                    n,
                    mass_excess_keV_from_binding(z=z, n=n, binding_MeV=binding),
                    11.0 + (z % 3),
                    (z + n) % B003_QUAL_ESTIMATED_MODULUS == 0,
                )
            )
    return _write_chart(Path(path), rows)


# --------------------------------------------------------------------------- #
# Frozen v2 qualification protocol                                            #
# --------------------------------------------------------------------------- #

# EZ-B003-v2 adopts the four v1 rediscovery checks with unchanged threshold
# values, under a new protocol identity. Adoption is a WO-12 decision made on
# synthetic mechanics and the WO-11 oracle behavior (2 MeV of unstructured
# noise still passes; the weak smooth control fails), frozen before any v2
# qualification was scored and long before any evaluated-table truth.
B003_V2_CRITERION = {
    "criterion_id": "ez-b003-v2-rediscovery-criterion-v1",
    "adopts": "ez-b003-rediscovery-criterion-v1",
    "min_sign_fraction": 0.75,
    "min_top_k_fraction": 0.75,
    "min_rank_1_fraction": 0.50,
    "max_calibration_error_90": 0.15,
    "unit_of_evaluation": "supported chains of every evaluable closure",
    "frozen_before": "any v2 qualification scoring and any evaluated-table truth",
}

# EZ-B002-v2 qualification gate: unlike v1 (pure characterization), the v2
# qualification demands that the federation actually reconstructs the withheld
# regions well AND honestly. Values chosen from the WO-11 dev grid (optimized
# GP reached ~10 keV dev MAE) and the WO-11 noise controls, frozen here.
B002_V2_GATE = {
    "gate_id": "ez-b002-v2-qualification-gate-v1",
    "best_model_max_MAE_keV": 150.0,
    "best_model_max_calibration_error_90": 0.15,
    "rule": (
        "the qualification passes when at least one federation participant "
        "reconstructs the withheld regions with pooled MAE at or below "
        "best_model_max_MAE_keV while keeping abs(coverage_90 - 0.90) at or "
        "below best_model_max_calibration_error_90 on the same targets"
    ),
    "frozen_before": "any v2 qualification scoring and any evaluated-table truth",
}

QUALIFICATION_ONLY_RULE = (
    "QUALIFICATION_ONLY: no evaluated mass table has been read under these "
    "protocols. Scoring real hidden truth is a separate later act, allowed "
    "only after this synthetic qualification passes, and it may not change a "
    "threshold."
)


def v2_protocol_payload(*, registry_manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "work_order": "WO-12",
        "federation_protocol_version": FEDERATION_PROTOCOL_VERSION,
        "qualification_ids": [B002_V2_QUAL_ID, B003_V2_QUAL_ID],
        "fixture_novelty_rule": FIXTURE_NOVELTY_RULE,
        "b002_v2_gate": B002_V2_GATE,
        "b003_v2_criterion": B003_V2_CRITERION,
        "calibration_split_rule": CALIBRATION_SPLIT_RULE,
        "registry_hash": registry_manifest["registry_hash"],
        "model_count": registry_manifest["model_count"],
        "independence_group_count": registry_manifest["independence_group_count"],
        "created_at": QUAL_CREATED_AT,
        "qualification_only_rule": QUALIFICATION_ONLY_RULE,
    }


# --------------------------------------------------------------------------- #
# Federation participants inside the frozen seal/score mechanics              #
# --------------------------------------------------------------------------- #


class FederationRunAdapter:
    """Bridge: a federation model speaking the sealed v1 model interface.

    Every prediction's decomposed federation view is recorded into the shared
    ``recorder`` store keyed ``model_id -> fit_digest -> nuclide_id`` during
    the blind predict phase — no truth is involved — so the qualification
    report can show the decomposition next to the sealed Gaussian numbers.
    ``fit_digest`` is the identity digest of the training ids handed to
    ``fit``, which is exactly the training identity the sealed freeze pins:
    when two splits share a target nuclide, each split's independently fitted
    prediction keeps its own instance instead of overwriting the other.
    """

    def __init__(
        self, inner: NuclearMassModel, recorder: dict[str, dict[str, dict[str, Any]]]
    ) -> None:
        self._inner = inner
        self._recorder = recorder
        self._fit_digest: str | None = None
        self.model_id = inner.model_id

    def fit(self, observations) -> None:
        self._inner.fit(observations)
        self._fit_digest = identity_digest(sorted(o.nuclide_id for o in observations))

    def predict(self, nuclide):
        if self._fit_digest is None:
            raise ProtocolError(
                f"{self.model_id}: predict before fit inside the sealed pipeline"
            )
        federation_prediction: FederationPrediction = self._inner.predict(nuclide)
        self._recorder.setdefault(self._inner.model_id, {}).setdefault(
            self._fit_digest, {}
        )[nuclide.nuclide_id] = federation_prediction.to_dict()
        return federation_prediction.to_benchmark_prediction(
            uncertainty_method=self._inner.uncertainty_policy
        )

    def manifest(self) -> dict[str, Any]:
        return self._inner.manifest()


def _federation_builders(registry, recorder: dict[str, dict[str, dict[str, Any]]]):
    return {
        model_id: (lambda m=model_id: FederationRunAdapter(registry.build(m), recorder))
        for model_id in registry.model_ids
    }


# --------------------------------------------------------------------------- #
# Pre-seal coverage audit (section 16)                                        #
# --------------------------------------------------------------------------- #

COVERAGE_AUDIT_RULE = (
    "ez-wo12-coverage-audit-v1: before anything is sealed, every registered "
    "participant is audited against every split's full corpus (training and "
    "targets) through coverage_status alone — no fitting, no truth. A "
    "participant that cannot cover the full corpus of every split is "
    "excluded from the sealed qualification and recorded here with its "
    "per-split statuses; missing coverage is a recorded status, never an "
    "imputed number and never a mid-seal crash."
)


def _audit_coverage(registry, splits: list[dict[str, Any]]) -> dict[str, Any]:
    """Coverage of every participant over every split's corpus, pre-seal."""
    by_model: dict[str, Any] = {}
    excluded: list[str] = []
    for model_id in registry.model_ids:
        model = registry.build(model_id)
        split_reports = []
        fully_covered = True
        for split in splits:
            statuses: dict[str, dict[str, int]] = {"training": {}, "targets": {}}
            missing: dict[str, list[str]] = {"training": [], "targets": []}
            for side, ids in (
                ("training", split["training_nuclide_ids"]),
                ("targets", split["target_nuclide_ids"]),
            ):
                for nuclide_id in ids:
                    z, n = parse_nuclide_id(nuclide_id)
                    status = model.coverage_status(NuclideIdentity.from_zn(z, n))
                    statuses[side][status] = statuses[side].get(status, 0) + 1
                    if status != STATUS_AVAILABLE:
                        missing[side].append(nuclide_id)
            covered = not missing["training"] and not missing["targets"]
            fully_covered = fully_covered and covered
            split_reports.append(
                {
                    "split_id": split["split_id"],
                    "n_training": len(split["training_nuclide_ids"]),
                    "n_targets": len(split["target_nuclide_ids"]),
                    "training_statuses": dict(sorted(statuses["training"].items())),
                    "target_statuses": dict(sorted(statuses["targets"].items())),
                    "uncovered_training_ids": sorted(missing["training"]),
                    "uncovered_target_ids": sorted(missing["targets"]),
                    "fully_covered": covered,
                }
            )
        by_model[model_id] = {"splits": split_reports, "fully_covered": fully_covered}
        if not fully_covered:
            excluded.append(model_id)
    sealed = [m for m in registry.model_ids if m not in excluded]
    if not sealed:
        raise ProtocolError(
            "no federation participant covers the qualification corpus; "
            "nothing can be sealed"
        )
    return {
        "rule": COVERAGE_AUDIT_RULE,
        "by_model": by_model,
        "excluded_models": sorted(excluded),
        "sealed_model_ids": sealed,
    }


def _b002_split_manifests(*, chart: Path, regions_path: Path) -> list[dict[str, Any]]:
    """The exact split corpora the seal will freeze, computed without sealing."""
    from elementzero.benchmark.b002_prepare import prepare_geographic_split
    from elementzero.experiments.b002_runner import read_regions

    regions = read_regions(regions_path)
    manifests = []
    for region in regions["regions"]:
        split = prepare_geographic_split(
            source=chart,
            edition_id=EDITION_ID,
            region=region,
            region_manifest_hash=regions["region_manifest_hash"],
            out_dir=None,
        )
        manifest = split["split_manifest"]
        manifests.append(
            {
                "split_id": manifest["region_id"],
                "training_nuclide_ids": list(manifest["training_nuclide_ids"]),
                "target_nuclide_ids": list(manifest["target_nuclide_ids"]),
            }
        )
    return manifests


def _b003_split_manifests(*, chart: Path, challenges_path: Path) -> list[dict[str, Any]]:
    from elementzero.benchmark.b003_prepare import prepare_shell_split
    from elementzero.experiments.b003_runner import read_challenges

    challenges = read_challenges(challenges_path)
    manifests = []
    for challenge in challenges["challenges"]:
        if challenge["status"] != "EVALUABLE":
            continue
        mask = challenges["masks"][challenge["challenge_id"]]
        split = prepare_shell_split(
            source=chart,
            edition_id=EDITION_ID,
            mask=mask,
            challenge_manifest_hash=challenges["challenge_manifest_hash"],
            out_dir=None,
        )
        manifest = split["split_manifest"]
        manifests.append(
            {
                "split_id": manifest["challenge_id"],
                "training_nuclide_ids": list(manifest["training_nuclide_ids"]),
                "target_nuclide_ids": list(manifest["target_nuclide_ids"]),
            }
        )
    return manifests


# --------------------------------------------------------------------------- #
# Qualification runs                                                          #
# --------------------------------------------------------------------------- #


def _model_groups(registry) -> dict[str, str]:
    manifest = registry.manifest()
    return {
        model_id: payload["independence_group"]
        for model_id, payload in manifest["participants"].items()
    }


def _split_records(experiment_dir: Path, *, kind: str) -> list[dict[str, Any]]:
    """Fit/calibration/benchmark identity digests per sealed split (§17)."""
    from elementzero.benchmark.b002_freeze import load_geographic_freeze
    from elementzero.benchmark.b003_freeze import load_shell_freeze

    records = []
    sealed = read_json(experiment_dir / "SEALED_PREDICTIONS.json")
    entries = sealed["regions"] if kind == "b002" else sealed["challenges"]
    for entry in entries:
        split_dir = experiment_dir / entry.get("region_relpath", entry.get("challenge_relpath"))
        if kind == "b002":
            frozen = load_geographic_freeze(split_dir / "freeze.json")
        else:
            frozen = load_shell_freeze(split_dir / "freeze.json")
        training_ids = sorted(frozen.freeze.training_nuclide_ids)
        target_ids = sorted(frozen.target_nuclide_ids)

        class _Stub:
            def __init__(self, nuclide_id: str) -> None:
                self.nuclide_id = nuclide_id

        fit_set, calibration_set = split_fit_calibration([_Stub(i) for i in training_ids])
        record = assert_split_disjoint(
            fit_ids=[o.nuclide_id for o in fit_set],
            calibration_ids=[o.nuclide_id for o in calibration_set],
            benchmark_target_ids=target_ids,
        )
        record["split_id"] = entry.get("region_id", entry.get("challenge_id"))
        records.append(record)
    return records


def run_b002_qualification(
    *,
    chart: Path,
    workspace: Path,
    registry,
) -> dict[str, Any]:
    from elementzero.adjudication.benchmark_controls import control_model_registry
    from elementzero.experiments.b002_runner import (
        score_b002,
        seal_b002,
        select_regions_for_source,
    )

    recorder: dict[str, dict[str, dict[str, Any]]] = {}
    builders = _federation_builders(registry, recorder)
    experiment_dir = workspace / B002_V2_QUAL_ID
    regions_path = workspace / "regions.json"
    select_regions_for_source(
        source=chart,
        edition_id=EDITION_ID,
        output=regions_path,
        candidates_output=workspace / "region_candidates.json",
        source_relpath=B002_CHART_NAME,
    )
    coverage_audit = _audit_coverage(
        registry, _b002_split_manifests(chart=chart, regions_path=regions_path)
    )
    with control_model_registry(builders):
        seal_b002(
            source=chart,
            edition_id=EDITION_ID,
            regions_path=regions_path,
            experiment_dir=experiment_dir,
            created_at=QUAL_CREATED_AT,
            model_ids=tuple(coverage_audit["sealed_model_ids"]),
        )
        score_b002(
            source=chart,
            edition_id=EDITION_ID,
            experiment_dir=experiment_dir,
            created_at=QUAL_CREATED_AT,
        )

    aggregate = read_json(experiment_dir / "region_aggregate.json")
    by_model = {}
    for model_id, payload in aggregate["by_model"].items():
        pooled = payload["pooled"]
        by_model[model_id] = {
            "MAE_keV": float(pooled["MAE_keV"]),
            "MedAE_keV": float(pooled["MedAE_keV"]),
            "RMSE_keV": float(pooled["RMSE_keV"]),
            "NLPD": float(pooled["NLPD"]),
            "coverage_90": float(pooled["coverage_90"]),
            "coverage_95": float(pooled["coverage_95"]),
            "calibration_error_90": float(pooled["cal_error_90"]),
            "calibration_error_95": float(pooled["cal_error_95"]),
            "n": int(pooled["n"]),
        }

    # Frozen B002-v2 gate.
    qualifying = {
        model_id: metrics
        for model_id, metrics in by_model.items()
        if metrics["MAE_keV"] <= B002_V2_GATE["best_model_max_MAE_keV"]
        and metrics["calibration_error_90"] <= B002_V2_GATE["best_model_max_calibration_error_90"]
    }
    split_index = _split_index(experiment_dir, kind="b002")
    truth, instance_meta, decomposition = _collect_rows(
        experiment_dir, recorder, split_index, kind="b002"
    )
    rows = disagreement_rows(
        per_model_points=_points_from_recorder(recorder, split_index),
        target_meta=instance_meta,
        model_groups=_model_groups(registry),
    )
    return {
        "qualification_id": B002_V2_QUAL_ID,
        "chart_sha256": sha256_file(chart),
        "gate": B002_V2_GATE,
        "by_model": dict(sorted(by_model.items())),
        "qualifying_models": sorted(qualifying),
        "status": "PASS" if qualifying else "FAIL",
        "coverage": _coverage_summary(recorder, split_index),
        "coverage_audit": coverage_audit,
        "uncertainty_decomposition": decomposition,
        "calibration_by_model": _calibration_by_model(recorder, truth, split_index),
        "disagreement_by_depth": disagreement_by_depth(rows),
        "split_records": _split_records(experiment_dir, kind="b002"),
        "lineage_inputs": _lineage_inputs(experiment_dir, recorder, split_index, kind="b002"),
        "experiment_dir": str(experiment_dir),
    }


def run_b003_qualification(
    *,
    chart: Path,
    workspace: Path,
    registry,
) -> dict[str, Any]:
    from elementzero.adjudication.benchmark_controls import control_model_registry
    from elementzero.experiments.b003_runner import (
        score_b003,
        seal_b003,
        select_challenges_for_source,
    )

    recorder: dict[str, dict[str, dict[str, Any]]] = {}
    builders = _federation_builders(registry, recorder)
    experiment_dir = workspace / B003_V2_QUAL_ID
    challenges_path = workspace / "challenges.json"
    select_challenges_for_source(
        source=chart,
        edition_id=EDITION_ID,
        output=challenges_path,
        source_relpath=B003_CHART_NAME,
    )
    coverage_audit = _audit_coverage(
        registry, _b003_split_manifests(chart=chart, challenges_path=challenges_path)
    )
    with control_model_registry(builders):
        seal_b003(
            source=chart,
            edition_id=EDITION_ID,
            challenges_path=challenges_path,
            experiment_dir=experiment_dir,
            created_at=QUAL_CREATED_AT,
            model_ids=tuple(coverage_audit["sealed_model_ids"]),
        )
        score_b003(
            source=chart,
            edition_id=EDITION_ID,
            experiment_dir=experiment_dir,
            created_at=QUAL_CREATED_AT,
        )

    aggregate = read_json(experiment_dir / "shell_aggregate.json")
    by_model = {}
    for model_id, payload in aggregate["by_model"].items():
        checks = payload["criterion"]["checks"]
        by_model[model_id] = {
            "verdict": payload["criterion"]["verdict"],
            "sign_fraction": float(checks["sign_fraction"]["observed"]),
            "top_k_fraction": float(checks["top_k_fraction"]["observed"]),
            "rank_1_fraction": float(checks["rank_1_fraction"]["observed"]),
            "calibration_error_90": float(checks["calibration_error_90"]["observed"]),
        }
    meeting = sorted(m for m, p in by_model.items() if p["verdict"] == "CRITERION_MET")
    split_index = _split_index(experiment_dir, kind="b003")
    truth, instance_meta, decomposition = _collect_rows(
        experiment_dir, recorder, split_index, kind="b003"
    )
    rows = disagreement_rows(
        per_model_points=_points_from_recorder(recorder, split_index),
        target_meta=instance_meta,
        model_groups=_model_groups(registry),
    )
    return {
        "qualification_id": B003_V2_QUAL_ID,
        "chart_sha256": sha256_file(chart),
        "criterion": B003_V2_CRITERION,
        "by_model": dict(sorted(by_model.items())),
        "models_meeting_criterion": meeting,
        "status": "PASS" if meeting else "FAIL",
        "evaluable_closures": list(aggregate["challenge_ids"]),
        "n_not_evaluable": aggregate["n_not_evaluable_closures"],
        "coverage": _coverage_summary(recorder, split_index),
        "coverage_audit": coverage_audit,
        "uncertainty_decomposition": decomposition,
        "calibration_by_model": _calibration_by_model(recorder, truth, split_index),
        "disagreement_by_depth": disagreement_by_depth(rows),
        "split_records": _split_records(experiment_dir, kind="b003"),
        "lineage_inputs": _lineage_inputs(experiment_dir, recorder, split_index, kind="b003"),
        "experiment_dir": str(experiment_dir),
    }


# --------------------------------------------------------------------------- #
# Post-pass helpers                                                           #
# --------------------------------------------------------------------------- #


def _instance_key(split_id: str, nuclide_id: str) -> str:
    return f"{split_id}::{nuclide_id}"


def _split_index(experiment_dir: Path, *, kind: str) -> list[dict[str, Any]]:
    """Sealed splits in seal order, with freeze identities and target sets.

    The recorder attributes every prediction instance to the split whose
    frozen training identity digest matches the fit the adapter observed —
    a target shared by two splits keeps both instances.
    """
    from elementzero.benchmark.b002_freeze import load_geographic_freeze
    from elementzero.benchmark.b003_freeze import load_shell_freeze

    sealed = read_json(experiment_dir / "SEALED_PREDICTIONS.json")
    entries = sealed["regions"] if kind == "b002" else sealed["challenges"]
    index = []
    for entry in entries:
        split_dir = experiment_dir / entry.get(
            "region_relpath", entry.get("challenge_relpath")
        )
        if kind == "b002":
            frozen = load_geographic_freeze(split_dir / "freeze.json")
        else:
            frozen = load_shell_freeze(split_dir / "freeze.json")
        index.append(
            {
                "split_id": entry.get("region_id", entry.get("challenge_id")),
                "freeze_id": entry["freeze_id"],
                "training_identity_digest": frozen.freeze.training_identity_digest,
                "target_ids": sorted(frozen.target_nuclide_ids),
            }
        )
    digests = [s["training_identity_digest"] for s in index]
    if len(set(digests)) != len(digests):
        raise ProtocolError(
            "two sealed splits share one training identity digest; recorded "
            "fits could not be attributed to splits"
        )
    return index


def _instances(recorder, split_index) -> dict[str, list[dict[str, Any]]]:
    """Every recorded prediction instance per model, in sealed split order.

    A recorded fit whose training identity matches no sealed split means a
    model was fitted on a corpus the seal does not know — a protocol error,
    never something to drop silently.
    """
    known = {s["training_identity_digest"] for s in split_index}
    out: dict[str, list[dict[str, Any]]] = {}
    for model_id, fits in sorted(recorder.items()):
        unknown = sorted(set(fits) - known)
        if unknown:
            raise ProtocolError(
                f"{model_id}: recorded fits match no sealed split: {unknown}"
            )
        rows = []
        for split in split_index:
            per_nuclide = fits.get(split["training_identity_digest"], {})
            targets = set(split["target_ids"])
            for nuclide_id in sorted(per_nuclide):
                if nuclide_id in targets:
                    rows.append(
                        {
                            "split_id": split["split_id"],
                            "nuclide_id": nuclide_id,
                            "payload": per_nuclide[nuclide_id],
                        }
                    )
        out[model_id] = rows
    return out


def _lineage_inputs(
    experiment_dir: Path, recorder, split_index, *, kind: str
) -> dict[str, Any]:
    """Per-model, per-split inputs for the Atlas federation facts (section 18).

    Every split fits its own model on its own frozen training identity, so
    the lineage carries one prediction-set digest (and, for residual models,
    one fit identity) per split — never the first split's identity standing
    in for all of them. ``fitted_nuclide_ids`` is trimmed from the recorded
    manifests: the fit identity is already pinned by the freeze digests.
    """
    from elementzero.models.federation.lineage import prediction_set_digest

    sealed = read_json(experiment_dir / "SEALED_PREDICTIONS.json")
    entries = sealed["regions"] if kind == "b002" else sealed["challenges"]
    manifests: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        split_id = entry.get("region_id", entry.get("challenge_id"))
        for run in entry["runs"]:
            manifest = read_json(
                experiment_dir / run["run_relpath"] / "model_manifest.json"
            )
            manifests[(split_id, run["model_id"])] = {
                k: v for k, v in manifest["model"].items() if k != "fitted_nuclide_ids"
            }
    lineage = {}
    for model_id, rows in _instances(recorder, split_index).items():
        splits = []
        for split in split_index:
            split_rows = [
                {**r["payload"], "nuclide_id": r["nuclide_id"]}
                for r in rows
                if r["split_id"] == split["split_id"]
            ]
            available = [r for r in split_rows if r["status"] == STATUS_AVAILABLE]
            splits.append(
                {
                    "split_id": split["split_id"],
                    "freeze_id": split["freeze_id"],
                    "training_identity_digest": split["training_identity_digest"],
                    "prediction_set_digest": prediction_set_digest(split_rows),
                    "n_predictions": len(available),
                    "n_missing": len(split_rows) - len(available),
                    "model_manifest": manifests.get((split["split_id"], model_id), {}),
                }
            )
        lineage[model_id] = {"splits": splits}
    return lineage


def _collect_rows(experiment_dir: Path, recorder, split_index, *, kind: str):
    """Truth per target, per-instance metadata, and mean decomposition."""
    sealed = read_json(experiment_dir / "SEALED_PREDICTIONS.json")
    entries = sealed["regions"] if kind == "b002" else sealed["challenges"]
    truth: dict[str, float] = {}
    instance_meta: dict[str, dict[str, Any]] = {}
    for entry in entries:
        split_id = entry.get("region_id", entry.get("challenge_id"))
        run = entry["runs"][0]  # rows are identical across models for one split
        report = read_json(
            experiment_dir / run["run_relpath"] / "scoring" / "score_report.json"
        )
        for row in report["rows"]:
            truth[row["nuclide_id"]] = float(row["truth_keV"])
            instance_meta[_instance_key(split_id, row["nuclide_id"])] = {
                "nearest_training_L1": int(row["nearest_training_L1"])
            }
    decomposition: dict[str, dict[str, float]] = {}
    for model_id, rows in _instances(recorder, split_index).items():
        payloads = [r["payload"] for r in rows]
        if not payloads:
            continue
        n = len(payloads)
        decomposition[model_id] = {
            "n": n,
            "mean_within_model_std_keV": sum(p["within_model_std_keV"] for p in payloads) / n,
            "mean_residual_std_keV": sum(p["residual_std_keV"] for p in payloads) / n,
            "mean_model_disagreement_std_keV": (
                sum(p["model_disagreement_std_keV"] for p in payloads) / n
            ),
            "mean_predictive_std_keV": (
                sum(p["predictive_std_keV"] or 0.0 for p in payloads) / n
            ),
        }
    return truth, instance_meta, decomposition


def _points_from_recorder(recorder, split_index) -> dict[str, dict[str, float]]:
    return {
        model_id: {
            _instance_key(r["split_id"], r["nuclide_id"]): r["payload"]["point_keV"]
            for r in rows
            if r["payload"]["status"] == STATUS_AVAILABLE
        }
        for model_id, rows in _instances(recorder, split_index).items()
    }


def _coverage_summary(recorder, split_index) -> dict[str, Any]:
    """Recorded coverage statuses counted over prediction *instances*."""
    summary = {}
    for model_id, rows in _instances(recorder, split_index).items():
        statuses: dict[str, int] = {}
        for r in rows:
            status = r["payload"]["status"]
            statuses[status] = statuses.get(status, 0) + 1
        summary[model_id] = statuses
    return summary


def _calibration_by_model(recorder, truth, split_index) -> dict[str, Any]:
    payload = {}
    for model_id, rows in _instances(recorder, split_index).items():
        calibration_rows = [
            {
                "prediction_keV": r["payload"]["point_keV"],
                "truth_keV": truth[r["nuclide_id"]],
                "std_keV": r["payload"]["predictive_std_keV"],
            }
            for r in rows
            if r["nuclide_id"] in truth and r["payload"]["status"] == STATUS_AVAILABLE
        ]
        payload[model_id] = calibration_metrics(calibration_rows)
    return payload


# --------------------------------------------------------------------------- #
# Entry point                                                                 #
# --------------------------------------------------------------------------- #


def run_wo12_qualification(
    *,
    workspace: str | Path,
    registry=None,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    from elementzero.adjudication.artifact_audit import _pinned_commit
    from elementzero.models.federation.registry import build_default_federation

    workspace = Path(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    registry = registry or build_default_federation(repo_root=repo_root)
    registry_manifest = registry.manifest()
    if registry_manifest["independence_group_count"] < 2:
        raise ProtocolError(
            "fewer than two independence groups are available; v2 protocols "
            "may not be frozen (WO-12 section 29)"
        )
    protocol = v2_protocol_payload(registry_manifest=registry_manifest)
    b002_chart = write_b002_qual_chart(workspace / B002_CHART_NAME)
    b003_chart = write_b003_qual_chart(workspace / B003_CHART_NAME)
    with _pinned_commit(WO12_BASELINE_COMMIT):
        b002 = run_b002_qualification(
            chart=b002_chart, workspace=workspace / "b002", registry=registry
        )
        b003 = run_b003_qualification(
            chart=b003_chart, workspace=workspace / "b003", registry=registry
        )
    overall = "PASS" if b002["status"] == b003["status"] == "PASS" else "FAIL"
    return {
        "work_order": "WO-12",
        "protocol": protocol,
        "protocol_hash": sha256_hex(protocol),
        "registry_manifest": registry_manifest,
        "runtime": capture_runtime(),
        "EZ-B002-v2-qual": b002,
        "EZ-B003-v2-qual": b003,
        "qualification_status": overall,
        "evaluated_table_rule": (
            "evaluated-table EZ-B002-v2 / EZ-B003-v2 runs stay blocked until "
            "this synthetic qualification passes and every stop condition of "
            "WO-12 section 29 is clear"
        ),
    }


def write_qual_fixtures(*, repo_root: str | Path) -> dict[str, str]:
    """Commit-side fixture generation; byte-reproducible."""
    root = Path(repo_root)
    b002 = write_b002_qual_chart(root / FIXTURES_RELPATH / B002_CHART_NAME)
    b003 = write_b003_qual_chart(root / FIXTURES_RELPATH / B003_CHART_NAME)
    return {B002_CHART_NAME: sha256_file(b002), B003_CHART_NAME: sha256_file(b003)}


def write_preregistrations(*, repo_root: str | Path, protocol: dict[str, Any]) -> None:
    """experiments/EZ-B002-v2 and EZ-B003-v2, marked QUALIFICATION_ONLY."""
    root = Path(repo_root)
    for experiment_id, gate_key in (
        ("EZ-B002-v2", "b002_v2_gate"),
        ("EZ-B003-v2", "b003_v2_criterion"),
    ):
        directory = root / "experiments" / experiment_id
        directory.mkdir(parents=True, exist_ok=True)
        payload = {
            "experiment_id": experiment_id,
            "state": "QUALIFICATION_ONLY",
            "qualification_only_rule": QUALIFICATION_ONLY_RULE,
            "frozen_thresholds": protocol[gate_key],
            "protocol_hash": sha256_hex(protocol),
            "registry_hash": protocol["registry_hash"],
            "fixture_novelty_rule": FIXTURE_NOVELTY_RULE,
        }
        (directory / "PROTOCOL.json").write_text(canonical_json(payload) + "\n", encoding="utf-8")
        (directory / "PREREGISTRATION.md").write_text(
            _preregistration_markdown(experiment_id, payload), encoding="utf-8"
        )


def _preregistration_markdown(experiment_id: str, payload: dict[str, Any]) -> str:
    thresholds = canonical_json(payload["frozen_thresholds"])
    return (
        f"# {experiment_id} — preregistration\n\n"
        "State: **QUALIFICATION_ONLY**\n\n"
        f"{QUALIFICATION_ONLY_RULE}\n\n"
        "## Frozen thresholds\n\n"
        "```json\n"
        f"{thresholds}\n"
        "```\n\n"
        f"Protocol hash: `{payload['protocol_hash']}`\n\n"
        f"Registry hash: `{payload['registry_hash']}`\n\n"
        f"{FIXTURE_NOVELTY_RULE}\n\n"
        "Running this protocol against an evaluated mass table requires: the "
        "synthetic qualification to have passed, every WO-12 section 29 stop "
        "condition to be clear, and a new experiment id under this frozen "
        "protocol — never an edit of a v1 result.\n"
    )
