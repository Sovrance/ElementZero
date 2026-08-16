# EZ-B003 closure proton-Z20

benchmark_id: EZ-B003
protocol_version: 0.3.0
b003_protocol_version: 1.0.0
scope: real-evaluated-data-wo14
profile: discovery

criterion: ez-b003-rediscovery-criterion-v1 (sign >= 0.75, top-3 >= 0.75, rank-1 >= 0.5, abs(coverage_90 - 0.90) <= 0.15)

boundary: EZ-B003 measures one narrow capability: rediscovery of known shell-related mass structure under controlled masking. A met criterion is not proof of a new magic number, and it is not evidence that a predicted Z = 154 shell gap or an island of stability exists. That claim would require independent physics-model ensembles, deformation calculations, fission calculations, decay competition, and far larger extrapolation uncertainty.

| challenge_id | indicator | model_id | n | MAE_keV | RMSE_keV | coverage_90 | calibration_error_90 | n_evaluable_chains | sign_recovered_fraction | rank_1_fraction | top_k_fraction | mean_absolute_indicator_error_MeV | predicted_hypothesis | truth_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| proton-Z20 | delta2p | EZ-BSKG3-TABLE-v1 | 61 | 814.389 | 986.035 | 0.786885 | 0.113115 | 13 | 1 | 0.230769 | 0.846154 | 1.55039 | n/a | n/a |
| proton-Z20 | delta2p | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 61 | 913.733 | 1107.95 | 0.327869 | 0.572131 | 13 | 1 | 0.153846 | 0.461538 | 1.56051 | n/a | n/a |

Derived observables (ASCII):

    S2n(Z,N)     = B(Z,N) - B(Z,N-2)
    S2p(Z,N)     = B(Z,N) - B(Z-2,N)
    delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)
    delta2p(Z,N) = S2p(Z,N) - S2p(Z+2,N)
