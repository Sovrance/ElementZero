# EZ-B003 hidden shell rediscovery aggregate

benchmark_id: EZ-B003
protocol_version: 0.3.0
b003_protocol_version: 1.0.0
scope: synthetic
profile: discovery

criterion: ez-b003-rediscovery-criterion-v1 (sign >= 0.75, top-3 >= 0.75, rank-1 >= 0.5, abs(coverage_90 - 0.90) <= 0.15)

boundary: EZ-B003 measures one narrow capability: rediscovery of known shell-related mass structure under controlled masking. A met criterion is not proof of a new magic number, and it is not evidence that a predicted Z = 154 shell gap or an island of stability exists. That claim would require independent physics-model ensembles, deformation calculations, fission calculations, decay competition, and far larger extrapolation uncertainty.

| challenge_id | indicator | model_id | n | MAE_keV | RMSE_keV | coverage_90 | calibration_error_90 | n_evaluable_chains | sign_recovered_fraction | rank_1_fraction | top_k_fraction | mean_absolute_indicator_error_MeV | predicted_hypothesis | truth_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| neutron-N50 | delta2n | EZ-SEMF-LS-v1 | 60 | 3.104368019726e+03 | 3.201596399769e+03 | 5.333333333333e-01 | 3.666666666667e-01 | 18 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 7.091333048683e+00 | H0 | H1 |
| neutron-N50 | delta2n | EZ-GP-DIRECT-v1 | 60 | 1.027753843692e+03 | 1.251115674689e+03 | 1.000000000000e+00 | 1.000000000000e-01 | 18 | 8.333333333333e-01 | 3.333333333333e-01 | 4.444444444444e-01 | 2.673415442048e+00 | n/a | H1 |
| neutron-N50 | delta2n | EZ-SEMF-GP-RESIDUAL-v1 | 60 | 6.601113831534e+02 | 7.430578345249e+02 | 1.000000000000e+00 | 1.000000000000e-01 | 18 | 1.000000000000e+00 | 0.000000000000e+00 | 6.111111111111e-01 | 2.195334332042e+00 | n/a | H1 |
| proton-Z28 | delta2p | EZ-SEMF-LS-v1 | 60 | 1.984251267013e+03 | 2.382456383315e+03 | 8.166666666667e-01 | 8.333333333333e-02 | 17 | 8.235294117647e-01 | 4.117647058824e-01 | 5.882352941176e-01 | 4.035737867810e+00 | n/a | H1 |
| proton-Z28 | delta2p | EZ-GP-DIRECT-v1 | 60 | 1.080288172024e+03 | 1.408396146778e+03 | 1.000000000000e+00 | 1.000000000000e-01 | 17 | 1.000000000000e+00 | 4.705882352941e-01 | 5.882352941176e-01 | 1.962150691203e+00 | n/a | H1 |
| proton-Z28 | delta2p | EZ-SEMF-GP-RESIDUAL-v1 | 60 | 4.705114565096e+02 | 5.869982866138e+02 | 1.000000000000e+00 | 1.000000000000e-01 | 17 | 1.000000000000e+00 | 1.764705882353e-01 | 1.000000000000e+00 | 1.652503310866e+00 | n/a | H1 |

Derived observables (ASCII):

    S2n(Z,N)     = B(Z,N) - B(Z,N-2)
    S2p(Z,N)     = B(Z,N) - B(Z-2,N)
    delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)
    delta2p(Z,N) = S2p(Z,N) - S2p(Z+2,N)

Pooled criterion per model (all evaluable closures):

| model_id | n_closures | n_evaluable_chains | sign | rank_1 | top_k | calibration_error_90 | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | 2 | 35 | 0.4 | 0.2 | 0.285714 | 0.225 | CRITERION_NOT_MET |
| EZ-GP-DIRECT-v1 | 2 | 35 | 0.914286 | 0.4 | 0.514286 | 0.1 | CRITERION_NOT_MET |
| EZ-SEMF-GP-RESIDUAL-v1 | 2 | 35 | 1 | 0.0857143 | 0.8 | 0.1 | CRITERION_NOT_MET |

Closures refused by the support rule (reported, never dropped):

| challenge_id | status | reasons |
| --- | --- | --- |
| neutron-N20 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| neutron-N28 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| neutron-N82 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| neutron-N126 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| proton-Z20 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| proton-Z50 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| proton-Z82 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
