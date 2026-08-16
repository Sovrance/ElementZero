"""DIRHB adapter: the covariant / relativistic Hartree-Bogoliubov family.

The scientifically important finding lives in this file's data, not its
code: the distributed DIRHB package ships only DD-ME2 (2005) and DD-PC1
(2008). Both postdate the 1995 freeze, so this family cannot be made
historically blind by choosing a different shipped force. It qualifies as
a *backend* — reproducible, hash-pinned, golden-verified — while its
claims stay MODERN_REFERENCE.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero.data.identity import NuclideIdentity
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex
from elementzero.physics.conversion import mass_excess_keV_from_binding
from elementzero.physics_backends import BACKEND_COVARIANT, GROUP_COVARIANT_RHB
from elementzero.physics_backends.convergence import (
    FAILURE_INVALID_OUTPUT,
    FAILURE_NONCONVERGED,
    FAILURE_NONE,
    FAILURE_NUMERICAL_INSTABILITY,
    FAILURE_RESOURCE_FAILURE,
    FAILURE_UNSUPPORTED_NUCLIDE,
    build_record,
)
from elementzero.physics_backends.output_parser import parse_dirhb
from elementzero.physics_backends.protocol import (
    OBSERVABLE_MASS_EXCESS,
    SOLVER_INVALID_OUTPUT,
    SOLVER_NONCONVERGED,
    SOLVER_NUMERICAL_INSTABILITY,
    SOLVER_OK,
    SOLVER_RESOURCE_FAILURE,
    SOLVER_UNSUPPORTED_NUCLIDE,
    PhysicsBackend,
    PhysicsPrediction,
)
from elementzero.physics_backends.provenance import (
    SOLVER_SOURCES,
    build_manifest,
    compiler_version,
    verify_archive,
)
from elementzero.physics_backends.runner import dirhb_binary, run_solver

# Only these two forces exist in the distributed package; both postdate
# the freeze. Enumerated so the limitation is data, not a comment.
SHIPPED_FORCES = ("DD-ME2", "DD-PC1")

BASIS_POLICY_ID = "ez-wo15-dirhb-basis-v1"
BASIS_N0F = 12
BASIS_N0B = 20
BASIS_POLICY = (
    f"{BASIS_POLICY_ID}: DIRHB spherical, {BASIS_N0F} fermionic and "
    f"{BASIS_N0B} bosonic oscillator shells, initial gap 1.0/1.0 MeV, "
    "identical for every nuclide"
)

ODD_POLICY = "EVEN_EVEN_ONLY"

_INPUT = """n0f,n0b  =   {n0f}   {n0b}               ! number of oscillator shells(F,B)
inin     =    1    1               ! initialization of potentials
{symbol:<2} {a:<3}                            ! nucleus under consideration
c-------------------------------------------------------------------
Init.Gap =    1.000     1.000      ! Initial values for the Gap par
c-------------------------------------------------------------------
Force    =  {force}                 ! Parameterset of the Lagrangian
c-------------------------------------------------------------------
"""


def dirhb_input(*, z: int, n: int, force: str) -> str:
    from elementzero.visuals.metadata import metadata_for

    if force not in SHIPPED_FORCES:
        raise ProtocolError(
            f"force {force!r} is not in the distributed DIRHB package "
            f"{SHIPPED_FORCES}; inventing a parameterization is not allowed"
        )
    return _INPUT.format(
        n0f=BASIS_N0F,
        n0b=BASIS_N0B,
        symbol=metadata_for(z)["symbol"],
        a=z + n,
        force=force,
    )


class DirhbBackend(PhysicsBackend):
    """Covariant RHB backend over the spherical DIRHB solver."""

    backend_id = BACKEND_COVARIANT
    physics_family = GROUP_COVARIANT_RHB
    solver_name = "DIRHB"

    def __init__(self, *, force: str = "DD-ME2", repo_root: str | Path | None = None) -> None:
        if force not in SHIPPED_FORCES:
            raise ProtocolError(f"unknown DIRHB force {force!r}")
        self.force = force
        self._repo_root = repo_root

    def source_identity(self) -> dict[str, Any]:
        return {**SOLVER_SOURCES["DIRHB"], "force": self.force}

    def verify_source_hash(self) -> dict[str, Any]:
        return verify_archive("DIRHB", repo_root=self._repo_root)

    def build(self) -> dict[str, Any]:
        return self.verify_build()

    def verify_build(self) -> dict[str, Any]:
        return build_manifest(
            solver="DIRHB",
            binary_path=dirhb_binary(repo_root=self._repo_root),
            compiler="gfortran",
            compiler_version=compiler_version(),
            build_flags="gfortran -O2 (package makefile, sources unmodified)",
            notes="dirhbs (spherical) solver only; deformed variants unused",
        )

    def verify_golden_cases(self) -> dict[str, Any]:
        """Reproduce the packaged compareout-DDME2 reference (78Kr)."""
        from elementzero.physics_backends.provenance import backend_data_dir

        root = backend_data_dir(repo_root=self._repo_root)
        reference = (
            root / "Dirhb-package-revised/dirhbs/compareout-DDME2/dirhb.out"
        )
        expected = None
        if reference.is_file():
            from elementzero.physics_backends.output_parser import DIRHB_ENERGY_RE

            found = DIRHB_ENERGY_RE.findall(
                reference.read_text(encoding="utf-8", errors="replace")
            )
            expected = float(found[-1]) if found else None
        work = root / "golden/dirhb"
        result = run_solver(
            binary=dirhb_binary(repo_root=self._repo_root),
            work_dir=work,
            input_files={"dirhb.dat": dirhb_input(z=36, n=42, force="DD-ME2")},
            stdout_name="screen.log",
        )
        parsed = parse_dirhb(work)
        matched = (
            expected is not None
            and parsed["energy_MeV"] is not None
            and abs(parsed["energy_MeV"] - expected) < 1.0e-6
        )
        return {
            "golden_case": "78Kr_DD-ME2",
            "expected_total_energy_MeV": expected,
            "observed_total_energy_MeV": parsed["energy_MeV"],
            "reproduced_exactly": matched,
            "iterations": parsed["iterations"],
            "returncode": result["returncode"],
        }

    def supports(self, nuclide: NuclideIdentity) -> bool:
        return nuclide.Z % 2 == 0 and nuclide.N % 2 == 0 and nuclide.Z >= 8

    def predict(
        self,
        nuclides: Sequence[NuclideIdentity],
        parameter_artifact: dict[str, Any],
        *,
        work_root: str | Path | None = None,
    ) -> list[PhysicsPrediction]:
        from elementzero.physics_backends.provenance import backend_data_dir

        root = Path(
            work_root or backend_data_dir(repo_root=self._repo_root) / "runs"
        )
        artifact_id = parameter_artifact["artifact_id"]
        source_hash = SOLVER_SOURCES["DIRHB"]["archive_sha256"]
        predictions: list[PhysicsPrediction] = []
        for nuclide in nuclides:
            work = root / artifact_id / nuclide.nuclide_id
            if not self.supports(nuclide):
                record = build_record(
                    nuclide_id=nuclide.nuclide_id,
                    backend_id=self.backend_id,
                    parameter_artifact_id=artifact_id,
                    converged=False,
                    iterations=0,
                    basis_policy=BASIS_POLICY,
                    retry_count=0,
                    failure_class=FAILURE_UNSUPPORTED_NUCLIDE,
                    output_hash=sha256_hex({"unsupported": nuclide.nuclide_id}),
                    detail={"odd_policy": ODD_POLICY},
                )
                predictions.append(
                    self._prediction(
                        nuclide, None, SOLVER_UNSUPPORTED_NUCLIDE, record,
                        artifact_id, source_hash,
                    )
                )
                continue
            run = run_solver(
                binary=dirhb_binary(repo_root=self._repo_root),
                work_dir=work,
                input_files={
                    "dirhb.dat": dirhb_input(
                        z=nuclide.Z, n=nuclide.N, force=self.force
                    )
                },
                stdout_name="screen.log",
            )
            parsed = parse_dirhb(work)
            status, failure = _classify({**parsed, **run})
            converged = status == SOLVER_OK
            record = build_record(
                nuclide_id=nuclide.nuclide_id,
                backend_id=self.backend_id,
                parameter_artifact_id=artifact_id,
                converged=converged,
                iterations=int(parsed.get("iterations") or 0),
                basis_policy=BASIS_POLICY,
                retry_count=0,
                failure_class=failure,
                output_hash=parsed["output_hash"],
                detail={"force": self.force},
            )
            value = None
            if converged:
                value = mass_excess_keV_from_binding(
                    z=nuclide.Z, n=nuclide.N, binding_MeV=-parsed["energy_MeV"]
                )
            predictions.append(
                self._prediction(
                    nuclide, value, status, record, artifact_id, source_hash,
                    extra={"binding_MeV": (
                        -parsed["energy_MeV"] if converged else None
                    )},
                )
            )
        return predictions

    def _prediction(
        self,
        nuclide: NuclideIdentity,
        value: float | None,
        status: str,
        record: dict[str, Any],
        artifact_id: str,
        source_hash: str,
        extra: dict[str, Any] | None = None,
    ) -> PhysicsPrediction:
        return PhysicsPrediction(
            nuclide_id=nuclide.nuclide_id,
            observable=OBSERVABLE_MASS_EXCESS,
            value=value,
            unit="keV",
            solver_status=status,
            convergence_record_id=record["convergence_record_id"],
            parameter_artifact_id=artifact_id,
            backend_id=self.backend_id,
            physics_family=self.physics_family,
            source_hash=source_hash,
            output_hash=record["output_hash"],
            detail={"convergence": record, **(extra or {})},
        )

    def export_parameter_artifact(self, **kwargs: Any) -> dict[str, Any]:
        from elementzero.physics_backends.artifact import build_parameter_artifact

        kwargs.setdefault("basis_policy", BASIS_POLICY)
        return build_parameter_artifact(
            backend_id=self.backend_id,
            physics_family=self.physics_family,
            solver_name=self.solver_name,
            solver_version=SOLVER_SOURCES["DIRHB"]["solver_version"],
            solver_source_hash=SOLVER_SOURCES["DIRHB"]["archive_sha256"],
            build_manifest_hash=self.verify_build()["build_manifest_hash"],
            **kwargs,
        )

    def export_provenance(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "physics_family": self.physics_family,
            "force": self.force,
            "shipped_forces": list(SHIPPED_FORCES),
            "odd_policy": ODD_POLICY,
            "basis_policy": BASIS_POLICY,
            "source": self.source_identity(),
            "refittable": False,
            "not_refittable_reason": (
                "the distributed DIRHB package exposes published force "
                "parameter sets through a compiled-in table; refitting the "
                "Lagrangian would require modifying upstream source, which "
                "WO-15 forbids for provenance reasons"
            ),
        }


def _classify(solved: dict[str, Any]) -> tuple[str, str]:
    if solved.get("timed_out"):
        return SOLVER_RESOURCE_FAILURE, FAILURE_RESOURCE_FAILURE
    if solved.get("nan_detected") and solved.get("energy_MeV") is None:
        return SOLVER_NUMERICAL_INSTABILITY, FAILURE_NUMERICAL_INSTABILITY
    if solved.get("energy_MeV") is None:
        return SOLVER_NONCONVERGED, FAILURE_NONCONVERGED
    if not solved.get("solver_ok"):
        return SOLVER_INVALID_OUTPUT, FAILURE_INVALID_OUTPUT
    return SOLVER_OK, FAILURE_NONE


def dirhb_backend(*, force: str = "DD-ME2", repo_root=None) -> DirhbBackend:
    return DirhbBackend(force=force, repo_root=repo_root)
