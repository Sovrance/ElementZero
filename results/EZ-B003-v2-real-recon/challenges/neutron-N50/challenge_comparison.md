# EZ-B003 closure neutron-N50

benchmark_id: EZ-B003
protocol_version: 0.3.0
b003_protocol_version: 1.0.0
scope: real-evaluated-data-wo14
profile: discovery

criterion: ez-b003-rediscovery-criterion-v1 (sign >= 0.75, top-3 >= 0.75, rank-1 >= 0.5, abs(coverage_90 - 0.90) <= 0.15)

boundary: EZ-B003 measures one narrow capability: rediscovery of known shell-related mass structure under controlled masking. A met criterion is not proof of a new magic number, and it is not evidence that a predicted Z = 154 shell gap or an island of stability exists. That claim would require independent physics-model ensembles, deformation calculations, fission calculations, decay competition, and far larger extrapolation uncertainty.

| challenge_id | indicator | model_id | n | MAE_keV | RMSE_keV | coverage_90 | calibration_error_90 | n_evaluable_chains | sign_recovered_fraction | rank_1_fraction | top_k_fraction | mean_absolute_indicator_error_MeV | predicted_hypothesis | truth_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| neutron-N50 | delta2n | EZ-BSKG3-TABLE-v1 | 62 | 533.887 | 660.007 | 0.935484 | 0.0354839 | 17 | 1 | 1 | 1 | 0.937499 | H1 | H1 |
| neutron-N50 | delta2n | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 62 | 379.323 | 466.439 | 0.790323 | 0.109677 | 17 | 1 | 1 | 1 | 1.14758 | H1 | H1 |

Derived observables (ASCII):

    S2n(Z,N)     = B(Z,N) - B(Z,N-2)
    S2p(Z,N)     = B(Z,N) - B(Z-2,N)
    delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)
    delta2p(Z,N) = S2p(Z,N) - S2p(Z+2,N)
