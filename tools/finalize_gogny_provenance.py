#!/usr/bin/env python3
"""Record the Gogny pairing-refit finding and seal its published artifact.

The preregistered refit scope — zero-range volume delta pairing strengths
(vpair_n, vpair_p) — does not transfer to a finite-range Gogny functional,
because the Gogny interaction already supplies pairing from its own
finite-range part. Imposing an extra zero-range pairing field on top
double-counts it and over-binds catastrophically.

That was established on training-era evidence alone and is recorded as a
negative result, not quietly dropped. The Gogny family therefore carries
its published D1S parameterization with provenance
HISTORICAL_FROZEN_PARTIAL — blind-eligible on post-1995 targets by the
same publication-date adjudication WO-13 applied to FRDM95, and never
upgraded to REFIT_STRICT on the strength of a fit that does not apply.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from elementzero.evidence.freezes import identity_digest  # noqa: E402
from elementzero.evidence.hashing import canonical_json, sha256_hex  # noqa: E402
from elementzero.evidence.ledger import read_json  # noqa: E402
from elementzero.physics_backends import (  # noqa: E402
    BACKEND_GOGNY,
    HISTORICAL_FROZEN_PARTIAL,
)
from elementzero.physics_backends.adapters.hfbtho import gogny_backend  # noqa: E402
from elementzero.physics_backends.campaign import (  # noqa: E402
    CAMPAIGN_CREATED_AT,
    FAMILY_PARAMETERIZATION,
)
from elementzero.physics_backends.provenance import (  # noqa: E402
    PARAMETERIZATIONS,
    parameterization_admissible,
)

OUT = Path("reports/physics_backends/wo15/fits")

REFIT_INAPPLICABLE_FINDING = {
    "finding_id": "ez-wo15-gogny-pairing-refit-inapplicable-v1",
    "backend_id": BACKEND_GOGNY,
    "attempted_refit_scope": "zero-range volume delta pairing (vpair_n, vpair_p)",
    "outcome": "REFIT_SCOPE_INAPPLICABLE_TO_FUNCTIONAL",
    "evidence": {
        "diagnostic_nuclide_id": "Z54-N80",
        "training_era_truth_keV": -88124.438,
        "published_d1s_native_pairing_keV": -98652.8,
        "with_imposed_zero_range_pairing_keV": -186497.6,
        "calibration_rms_keV_first_evaluations": [
            90839.8,
            121792.4,
            107689.7,
            84877.1,
        ],
        "skyrme_comparison_rms_keV_same_starting_point": 4357.2,
    },
    "physics_reason": (
        "the Gogny interaction supplies pairing from its own finite-range "
        "component; imposing an additional zero-range volume delta pairing "
        "field double-counts the pairing channel and over-binds by tens of "
        "MeV. The refit scope was specified for zero-range Skyrme EDFs and "
        "does not transfer"
    ),
    "decision": (
        "the pairing refit is abandoned for this family and the published "
        "D1S parameterization is used instead, with provenance "
        "HISTORICAL_FROZEN_PARTIAL rather than REFIT_STRICT. Blind "
        "eligibility rests on the publication-date adjudication, not on a "
        "fit"
    ),
    "signal_admissibility": (
        "the decision used training-era masses and physics reasoning only; "
        "no WO-14 truth, no B004 truth, and no post-1995 edition took part, "
        "and it was made before any B004 prediction was sealed"
    ),
    "claim_direction": (
        "this is a downgrade: HISTORICAL_FROZEN_PARTIAL is a weaker "
        "provenance class than REFIT_STRICT, so the change cannot inflate a "
        "claim"
    ),
    "future_work": (
        "a Gogny-appropriate refit would target the interaction's own "
        "parameters or a Gogny-consistent pairing prescription, under a new "
        "preregistered protocol version"
    ),
}


def main() -> int:
    freeze = read_json(OUT / "historical_fit_freeze.json")
    objective = read_json(OUT / "objective_manifest.json")
    partial_log = read_json(OUT / f"fit_log_{BACKEND_GOGNY}.json")

    (OUT / "gogny_refit_finding.json").write_text(
        canonical_json(
            {
                **REFIT_INAPPLICABLE_FINDING,
                "partial_fit_log_hash": sha256_hex(partial_log),
                "n_evaluations_before_abandonment": len(partial_log["evaluations"]),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    parameterization = FAMILY_PARAMETERIZATION[BACKEND_GOGNY]
    backend = gogny_backend(functional=parameterization, repo_root=".")
    artifact = backend.export_parameter_artifact(
        # The published functional is used as distributed: no ElementZero
        # parameter is imposed, so the parameter vector is the named force.
        parameter_names=["functional"],
        parameter_values=[0.0],
        parameter_units=["published parameter set"],
        pairing_definition=(
            "native finite-range Gogny pairing as implemented by HFBTHO's "
            "D1S path; no zero-range pairing field is imposed"
        ),
        optimizer_id="none-published-parameterization",
        optimizer_version="n/a",
        objective_manifest_hash=objective["objective_manifest_hash"],
        freeze_id=freeze["freeze_id"],
        training_identity_digest=freeze["allowed_identity_digest"],
        calibration_identity_digest=identity_digest([]),
        fit_started_at=CAMPAIGN_CREATED_AT,
        fit_completed_at=CAMPAIGN_CREATED_AT,
        convergence_status="PUBLISHED_PARAMETERIZATION",
        objective_value=None,
        covariance_artifact_hash=sha256_hex({"published": parameterization}),
        fit_log_hash=sha256_hex(partial_log),
        provenance_class=HISTORICAL_FROZEN_PARTIAL,
        parameterization_source={
            "base_parameterization": parameterization,
            **PARAMETERIZATIONS[parameterization],
            "freeze_admissible": parameterization_admissible(parameterization),
            "refit_scope": "none — see gogny_refit_finding.json",
            "provenance_reasoning": (
                "D1S was published in 1984, a decade before the 1995 freeze, "
                "so no post-freeze evidence can have entered it. Its exact "
                "calibration nuclide list is published as prose rather than "
                "as machine-readable membership, which is precisely the "
                "HISTORICAL_FROZEN_PARTIAL case: blind-eligible by the "
                "publication-date adjudication, never by assumption"
            ),
            "base_provenance_class": HISTORICAL_FROZEN_PARTIAL,
            "refit_attempted_and_abandoned": True,
        },
    )
    (OUT / f"parameter_artifact_{BACKEND_GOGNY}.json").write_text(
        canonical_json(artifact) + "\n", encoding="utf-8"
    )
    (OUT / f"fit_result_{BACKEND_GOGNY}.json").write_text(
        canonical_json(
            {
                "status": "REFIT_ABANDONED_SCOPE_INAPPLICABLE",
                "n_evaluations": len(partial_log["evaluations"]),
                "finding": REFIT_INAPPLICABLE_FINDING["finding_id"],
                "fit_log_hash": sha256_hex(partial_log),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        canonical_json(
            {
                "artifact_id": artifact["artifact_id"],
                "provenance_class": artifact["provenance_class"],
                "freeze_admissible": artifact["parameterization_source"][
                    "freeze_admissible"
                ],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
