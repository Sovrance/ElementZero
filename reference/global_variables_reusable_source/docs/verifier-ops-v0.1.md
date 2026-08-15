# Verifier Ops v0.1 — the frozen certification-primitive set

**Status:** Stage 1 (Substrate). Freezes the existing verifier-op vocabulary so
Stage 2's symbolic bridge and analyzer runtime build on a fixed contract. This
document is descriptive of code already in the repository; it changes no
behavior and promotes no atlas cell.

A **verifier op** is a primitive that turns a domain representation into a
*certified* structural fact with an exact or interval witness. These are the
operations PIR SOUND passes are allowed to invoke to assert E0/E1 facts. The
six ops below (architecture.yaml `verifier_ops`) cover every B1–B12 benchmark.

Legend — certificate format is what the op returns and what a PIR
`fact.witness` / `fact.impossibility_certificate` stores.

---

## SCHUR_PIVOT_EXACT — exact PSD test by symmetric elimination
- **Implementation:** `b1_moment_solver/exact.py::psd_certificate(M) ->
  (status, pivots, rank)`.
- **Signature:** symmetric rational matrix `M` → `status ∈ {PD_CERTIFIED,
  PSD_CERTIFIED, NOT_PSD_CERTIFIED}`, the successive Schur-complement `pivots`
  (exact `Fraction`s), and `rank` (count of strictly positive pivots).
- **Certificate format:** the pivot chain. A non-negative chain (zero pivots on
  vanishing rows) certifies PSD (E0); a negative pivot is an **impossibility
  certificate** — an exact witness of indefiniteness/violation.
- **Used by:** B1 (moment-matrix positivity, forced/permitted/rejected), B6
  (QNEC Schur-pivot benchmark), B2 (Choi positivity, complex extension below),
  and the M1 PSD-signature feature.

## RANK_TEST — exact rank over ℚ
- **Implementation:** `b1_moment_solver/exact.py::hankel_rank` (via the pivot
  count) and `b3_electroweak/rank.py::matrix_rank(A)` (exact Gaussian
  elimination over ℚ).
- **Signature:** rational matrix → integer rank, exact.
- **Certificate format:** the elimination pivots / echelon witness; rank equals
  the number of nonzero pivots.
- **Used by:** B1 (Hankel rank → flat extension), B3 (constraint-Jacobian rank
  → `d_identifiable`), B5/M1/M2 (rank sequences as canonical invariants), B10
  (covariance rank).

## FLAT_EXTENSION — Curto–Fialkow flatness and forced recurrence
- **Implementation:** `b1_moment_solver/exact.py::is_flat`,
  `kernel_recurrence`, `extend_by_recurrence`.
- **Signature:** moment sequence + order `t` → flatness boolean; if flat, the
  exact kernel recurrence polynomial and the forced tail extension.
- **Certificate format:** the recurrence coefficients (exact `Fraction`s); a
  flat extension is an E0 **FORCED** witness (unique determination).
- **Used by:** B1 (hidden-moment recovery), S2-b (exact-kernel GNS probe).

## JACOBIAN_RANK_IDENTIFIABILITY — structural identifiability
- **Implementation:** `b3_electroweak/rank.py::_jacobian`, `d_identifiable`.
- **Signature:** constraint residual system → constraint Jacobian → exact rank →
  `d_identifiable = n_quantities − rank(J)`.
- **Certificate format:** the rank and the residual/holding-residual witnesses;
  `d_identifiable = 0` certifies a FORCED (uniquely identified) system,
  `> 0` yields NONIDENTIFIABLE with the free-direction count as cause.
- **Used by:** B3 (electroweak closed-system identifiability), and the
  Stage-2/P7 intervention-search `d_identifiable_reduction` objective.

## CPTP_GATE — complete positivity / trace preservation via Choi
- **Implementation:** `b2_process_solver/choi.py` (`choi_of_unitary`, `mix`,
  `is_trace_preserving`, `block_traces`) with positivity from
  `SCHUR_PIVOT_EXACT` over the Hermitian Choi matrix.
- **Signature:** channel representation → Choi matrix `J`; CP ⇔ `J ⪰ 0`
  (Choi's theorem), TP ⇔ partial-trace-identity check, both exact.
- **Certificate format:** the Choi positivity pivots (CP witness) + the
  trace-preservation residual; a negative pivot rejects the channel as
  non-CP with an exact witness.
- **Used by:** B2 (process/channel completion, negative control = corrupted
  Choi rejected), B12-RGRC quantum families.

## SYMPLECTIC_GATE — Gaussian-channel positivity + symplectic structure
- **Implementation:** `b10_cv_channel/gaussian_channel.py` (`omega`,
  `cp_matrix`, `certify_channel`, `permitted_noise_interval`,
  `force_symplectic_entry`).
- **Signature:** Gaussian channel `(T, N)` → CP condition
  `N + i(Ω − TΩTᵀ)/2 ⪰ 0` and the symplectic condition `det T = 1`, exact where
  rational, interval-certified for permitted-noise holes.
- **Certificate format:** the CP-matrix pivots + the symplectic determinant
  witness; `force_symplectic_entry` returns the forced hidden entry (FORCED),
  `permitted_noise_interval` returns a certified feasible interval (PERMITTED).
- **Used by:** B10 (CV Gaussian-channel completion, amplifier-noise forcing).

---

## Benchmark → op coverage map (DoD: every B1–B12 maps to documented ops)

| Benchmark | Verifier ops used |
|---|---|
| B1 moment solver | SCHUR_PIVOT_EXACT, RANK_TEST, FLAT_EXTENSION |
| B2 process solver | CPTP_GATE (Choi + SCHUR_PIVOT_EXACT) |
| B3 electroweak | JACOBIAN_RANK_IDENTIFIABILITY, RANK_TEST |
| B4 area pipeline | RANK_TEST (monotone area) + statistical (E2, Clopper–Pearson) |
| B5 cluster | RANK_TEST (spectral class), SCHUR_PIVOT_EXACT |
| B6 QNEC | SCHUR_PIVOT_EXACT |
| B7 Onsager | RANK_TEST, SCHUR_PIVOT_EXACT (transport-matrix completion) |
| B8 grammar | RANK_TEST + fingerprinting (Stage-2/P5b) |
| B9 circuit | CPTP_GATE / covariance positivity (SCHUR_PIVOT_EXACT), RANK_TEST |
| B10 CV channel | SYMPLECTIC_GATE, RANK_TEST |
| B12 RGRC / B12-b | CPTP_GATE, RANK_TEST (shared-latent discrimination) |
| M1 canon / M2 generator | RANK_TEST, SCHUR_PIVOT_EXACT (canonical invariants) |

Notes: statistical (E2) and simulation (E3) results still pass through a
verifier op for their structural claims; only the exact/interval structural
core is a verifier-op certificate. Verdicts remain SPEC §4/§6; a verifier op
never emits a candidate-class label.
