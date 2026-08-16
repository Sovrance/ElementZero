"""HFBTHO adapter: the Skyrme and Gogny families share one solver build.

One executable, two physics families. That is deliberate and it is
recorded: the finite-range Gogny interaction and the zero-range Skyrme
EDF are different functional classes with different parameter vectors,
so they are independent *physics*, while sharing a numerical
implementation. The shared-solver caveat travels with every independence
adjudication rather than being quietly dropped.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from elementzero.data.identity import NuclideIdentity
from elementzero.errors import ProtocolError
from elementzero.evidence.hashing import sha256_hex
from elementzero.physics.conversion import mass_excess_keV_from_binding
from elementzero.physics_backends import (
    BACKEND_GOGNY,
    BACKEND_SKYRME,
    GROUP_GOGNY_HFB,
    GROUP_SKYRME_HFB,
)
from elementzero.physics_backends.convergence import (
    FAILURE_INVALID_OUTPUT,
    FAILURE_NONCONVERGED,
    FAILURE_NONE,
    FAILURE_NUMERICAL_INSTABILITY,
    FAILURE_RESOURCE_FAILURE,
    FAILURE_UNSUPPORTED_NUCLIDE,
    build_record,
)
from elementzero.physics_backends.output_parser import parse_hfbtho
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
from elementzero.physics_backends.runner import hfbtho_binary, run_solver

# Preregistered numerical policy. Fixed before any fit or B004 solve, and
# identical for both families so no family gets a quietly better basis.
BASIS_POLICY_ID = "ez-wo15-hfbtho-basis-v1"
BASIS_N_SHELLS = 14
BASIS_ITERATIONS = 300
BASIS_ACCURACY = 1.0e-5
BASIS_POLICY = (
    f"{BASIS_POLICY_ID}: spherical HFB, {BASIS_N_SHELLS} oscillator shells, "
    f"max {BASIS_ITERATIONS} iterations, accuracy {BASIS_ACCURACY:g}, "
    "Lipkin-Nogami off, identical for every family and every nuclide"
)

# EVEN_EVEN_ONLY (spec section 14). Both HFBTHO's spherical ground-state
# path and DIRHB support even-even systems; odd nuclei need blocking and
# a separate preregistered treatment, so they are excluded outright
# rather than given a synthetic value to keep the roster large.
ODD_POLICY = "EVEN_EVEN_ONLY"

FUNCTIONAL_FAMILY = {
    BACKEND_SKYRME: GROUP_SKYRME_HFB,
    BACKEND_GOGNY: GROUP_GOGNY_HFB,
}

_NAMELIST = """&HFBTHO_GENERAL
  type_of_calculation = 1,
  number_of_shells    = {shells},
  oscillator_length   = -2.3190000000000000,
  basis_deformation   = 0.0000000000000000,
  proton_number       = {z},
  neutron_number      = {n}
/
&HFBTHO_INITIAL
  beta2_deformation = 0.0000000000000000,
  beta3_deformation = 0.0000000000000000,
  beta4_deformation = 0.0000000000000000
/
&HFBTHO_ITERATIONS
  number_iterations = {iterations},
  accuracy          = {accuracy:.10E},
  restart_file      = 1
/
&HFBTHO_FUNCTIONAL
  functional          = '{functional}',
  add_initial_pairing = F,
  type_of_coulomb     = 2,
  include_3N_force    = F
/
&HFBTHO_PAIRING
  user_pairing    = {user_pairing},
  vpair_n         = {vpair_n:.10f},
  vpair_p         = {vpair_p:.10f},
  pairing_cutoff  = 60.0000000000000000,
  pairing_feature = 0.5000000000000000
/
&HFBTHO_CONSTRAINTS
  lambda_values      = 1,2,3,4,5,6,7,8,
  lambda_active      = 0,-1,0,0,0,0,0,0,
  expectation_values = 0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,
/
&HFBTHO_BLOCKING
  proton_blocking = 0,0,0,0,0,
  neutron_blocking = 0,0,0,0,0,
/
&HFBTHO_PROJECTION
  switch_to_THO       = 0,
  projection_is_on    = 0,
  gauge_points        = 1,
  delta_Z             = 0,
  delta_N             = 0
/
&HFBTHO_TEMPERATURE
  set_temperature = F,
  temperature     = 0.0
/
&HFBTHO_FEATURES
  collective_inertia    = F,
  fission_fragments     = F,
  pairing_regularization= F,
  automatic_basis       = F,
  localization_functions= F
/
&HFBTHO_TDDFT
  filter              = F,
  fragment_properties = F,
  real_Z              = 44.0,
  real_N              = 66.0
/
&HFBTHO_NECK
  set_neck_constrain = F,
  neck_value         = 0.0
/
&HFBTHO_DEBUG
  number_Gauss    = 40,
  number_Laguerre = 40,
  number_Legendre = 80,
  compatibility_HFODD = F,
  number_states       = 500,
  force_parity        = T,
  print_time          = 0
/
&HFBTHO_RESTORATION
  PNP_is_on   = 0,
  number_of_gauge_points = 9,
  delta_Z     = 0,
  delta_N     = 0,
  AMP_is_on   = 0,
  number_of_rotational_angles = 27,
  maximal_angular_momentum    = 10
/
"""


def namelist(
    *,
    z: int,
    n: int,
    functional: str,
    vpair_n: float | None = None,
    vpair_p: float | None = None,
    shells: int = BASIS_N_SHELLS,
    iterations: int = BASIS_ITERATIONS,
    accuracy: float = BASIS_ACCURACY,
) -> str:
    """The exact solver input for one nuclide under one parameter set."""
    user_pairing = "T" if (vpair_n is not None and vpair_p is not None) else "F"
    return _NAMELIST.format(
        shells=shells,
        z=z,
        n=n,
        iterations=iterations,
        accuracy=accuracy,
        functional=functional,
        user_pairing=user_pairing,
        vpair_n=-250.0 if vpair_n is None else float(vpair_n),
        vpair_p=-250.0 if vpair_p is None else float(vpair_p),
    )


def unedf_namelist(*, repo_root: str | Path | None = None) -> str:
    """The UNEDF namelist HFBTHO reads alongside its own; shipped upstream."""
    from elementzero.physics_backends.provenance import backend_data_dir

    path = (
        backend_data_dir(repo_root=repo_root)
        / "hfbtho/src/hfbtho_ad/unedf_UNEDF0_Z20_N20_sphGS.dat"
    )
    if not path.is_file():
        raise ProtocolError(f"{path} is missing; extract the pinned archive first")
    return path.read_text(encoding="utf-8")


class HfbthoBackend(PhysicsBackend):
    """One HFBTHO build serving one declared physics family."""

    solver_name = "HFBTHO"

    def __init__(
        self,
        *,
        backend_id: str,
        functional: str,
        repo_root: str | Path | None = None,
    ) -> None:
        if backend_id not in FUNCTIONAL_FAMILY:
            raise ProtocolError(f"{backend_id!r} is not an HFBTHO family id")
        self.backend_id = backend_id
        self.physics_family = FUNCTIONAL_FAMILY[backend_id]
        self.functional = functional.upper()
        self._repo_root = repo_root
        self._binary: Path | None = None

    # -- contract: identity and build ------------------------------------- #

    def source_identity(self) -> dict[str, Any]:
        return {**SOLVER_SOURCES["HFBTHO"], "functional": self.functional}

    def verify_source_hash(self) -> dict[str, Any]:
        return verify_archive("HFBTHO", repo_root=self._repo_root)

    def build(self) -> dict[str, Any]:
        """The build is performed by tools/build_physics_backends.sh; this
        records what that produced. Upstream sources are never edited."""
        return self.verify_build()

    def verify_build(self) -> dict[str, Any]:
        binary = hfbtho_binary(repo_root=self._repo_root)
        self._binary = binary
        return build_manifest(
            solver="HFBTHO",
            binary_path=binary,
            compiler="gfortran",
            compiler_version=compiler_version(),
            build_flags=(
                "COMPILER=GFORTRAN AD=0 GOGNY=1 GOGNY_SYMMETRIES=1 "
                "GOGNY_HYPER=1 USE_OPENMP=1 -O3"
            ),
            notes=(
                "upstream sources unmodified; the finite-range Gogny module is "
                "pre-compiled and injected because the shipped sub-Makefile's "
                "ifeq ($GOGNY,1) guard is missing parentheses and never fires"
            ),
        )

    def verify_golden_cases(self) -> dict[str, Any]:
        """Reproduce the packaged UNEDF0 Z=20 N=20 spherical ground state."""
        from elementzero.physics_backends.provenance import backend_data_dir

        root = backend_data_dir(repo_root=self._repo_root)
        golden_in = root / "hfbtho/src/hfbtho_ad/hfbtho_UNEDF0_Z20_N20_sphGS.dat"
        work = root / "golden/hfbtho"
        result = run_solver(
            binary=hfbtho_binary(repo_root=self._repo_root),
            work_dir=work,
            input_files={
                "hfbtho_NAMELIST.dat": golden_in.read_text(encoding="utf-8"),
                "UNEDF_NAMELIST.dat": unedf_namelist(repo_root=self._repo_root),
            },
        )
        parsed = parse_hfbtho(work)
        return {
            "golden_case": "UNEDF0_Z20_N20_sphGS",
            "input_sha256": sha256_hex(golden_in.read_text(encoding="utf-8")),
            "solver_ok": parsed["solver_ok"],
            "energy_MeV": parsed["energy_MeV"],
            "energy_LN_MeV": parsed["energy_LN_MeV"],
            "returncode": result["returncode"],
        }

    # -- contract: prediction ---------------------------------------------- #

    def supports(self, nuclide: NuclideIdentity) -> bool:
        return nuclide.Z % 2 == 0 and nuclide.N % 2 == 0 and nuclide.Z >= 2

    def solve_one(
        self,
        nuclide: NuclideIdentity,
        *,
        work_dir: str | Path,
        vpair_n: float | None = None,
        vpair_p: float | None = None,
        shells: int = BASIS_N_SHELLS,
    ) -> dict[str, Any]:
        """One solve; returns parsed physics plus the raw run record."""
        result = run_solver(
            binary=hfbtho_binary(repo_root=self._repo_root),
            work_dir=work_dir,
            input_files={
                "hfbtho_NAMELIST.dat": namelist(
                    z=nuclide.Z,
                    n=nuclide.N,
                    functional=self.functional,
                    vpair_n=vpair_n,
                    vpair_p=vpair_p,
                    shells=shells,
                ),
                "UNEDF_NAMELIST.dat": unedf_namelist(repo_root=self._repo_root),
            },
        )
        parsed = parse_hfbtho(work_dir)
        return {**parsed, **result}

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
        params = dict(
            zip(
                parameter_artifact["parameter_names"],
                parameter_artifact["parameter_values"],
                strict=True,
            )
        )
        artifact_id = parameter_artifact["artifact_id"]
        source_hash = SOLVER_SOURCES["HFBTHO"]["archive_sha256"]
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
            solved = self.solve_one(
                nuclide,
                work_dir=work,
                vpair_n=params.get("vpair_n"),
                vpair_p=params.get("vpair_p"),
            )
            status, failure = _classify(solved)
            converged = status == SOLVER_OK
            record = build_record(
                nuclide_id=nuclide.nuclide_id,
                backend_id=self.backend_id,
                parameter_artifact_id=artifact_id,
                converged=converged,
                iterations=int(solved.get("iterations") or 0),
                basis_policy=BASIS_POLICY,
                retry_count=0,
                failure_class=failure,
                output_hash=solved["output_hash"],
                detail={"functional": self.functional},
            )
            value = None
            if converged:
                value = mass_excess_keV_from_binding(
                    z=nuclide.Z, n=nuclide.N, binding_MeV=-solved["energy_MeV"]
                )
            predictions.append(
                self._prediction(
                    nuclide, value, status, record, artifact_id, source_hash,
                    extra={"binding_MeV": (
                        -solved["energy_MeV"] if converged else None
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

    # -- contract: artifacts ------------------------------------------------ #

    def export_parameter_artifact(self, **kwargs: Any) -> dict[str, Any]:
        from elementzero.physics_backends.artifact import build_parameter_artifact

        return build_parameter_artifact(
            backend_id=self.backend_id,
            physics_family=self.physics_family,
            solver_name=self.solver_name,
            solver_version=SOLVER_SOURCES["HFBTHO"]["solver_version"],
            solver_source_hash=SOLVER_SOURCES["HFBTHO"]["archive_sha256"],
            build_manifest_hash=self.verify_build()["build_manifest_hash"],
            basis_policy=BASIS_POLICY,
            **kwargs,
        )

    def export_provenance(self) -> dict[str, Any]:
        return {
            "backend_id": self.backend_id,
            "physics_family": self.physics_family,
            "functional": self.functional,
            "odd_policy": ODD_POLICY,
            "basis_policy": BASIS_POLICY,
            "source": self.source_identity(),
        }


def _classify(solved: dict[str, Any]) -> tuple[str, str]:
    """Map one parsed solve onto (solver status, failure class)."""
    if solved.get("timed_out"):
        return SOLVER_RESOURCE_FAILURE, FAILURE_RESOURCE_FAILURE
    if solved.get("nan_detected") and solved.get("energy_MeV") is None:
        return SOLVER_NUMERICAL_INSTABILITY, FAILURE_NUMERICAL_INSTABILITY
    if solved.get("energy_MeV") is None:
        if solved.get("solver_ok"):
            return SOLVER_INVALID_OUTPUT, FAILURE_INVALID_OUTPUT
        return SOLVER_NONCONVERGED, FAILURE_NONCONVERGED
    if not solved.get("solver_ok"):
        return SOLVER_NONCONVERGED, FAILURE_NONCONVERGED
    return SOLVER_OK, FAILURE_NONE


def skyrme_backend(*, functional: str = "SKM*", repo_root=None) -> HfbthoBackend:
    return HfbthoBackend(
        backend_id=BACKEND_SKYRME, functional=functional, repo_root=repo_root
    )


def gogny_backend(*, functional: str = "D1S", repo_root=None) -> HfbthoBackend:
    return HfbthoBackend(
        backend_id=BACKEND_GOGNY, functional=functional, repo_root=repo_root
    )
