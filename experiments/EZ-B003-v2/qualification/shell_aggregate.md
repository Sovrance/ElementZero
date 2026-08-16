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
| neutron-N126 | delta2n | EZ-SEMF-LS-v1 | 63 | 2.913672901551e+03 | 3.159955061441e+03 | 7.301587301587e-01 | 1.698412698413e-01 | 21 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 6.683666410296e+00 | H0 | H1 |
| neutron-N126 | delta2n | EZ-GP-DIRECT-v1 | 63 | 6.819010789761e+02 | 8.258658559879e+02 | 1.000000000000e+00 | 1.000000000000e-01 | 21 | 6.666666666667e-01 | 2.857142857143e-01 | 3.809523809524e-01 | 2.164003753267e+00 | n/a | H1 |
| neutron-N126 | delta2n | EZ-SEMF-GP-RESIDUAL-v1 | 63 | 5.438204249193e+02 | 6.276655016677e+02 | 1.000000000000e+00 | 1.000000000000e-01 | 21 | 9.523809523810e-01 | 9.523809523810e-02 | 1.904761904762e-01 | 1.873951023078e+00 | n/a | H1 |
| neutron-N126 | delta2n | EZ-GP-OPTIMIZED-CONTROL-v1 | 63 | 3.460572865450e+02 | 4.374651069484e+02 | 5.079365079365e-01 | 3.920634920635e-01 | 21 | 1.000000000000e+00 | 7.619047619048e-01 | 9.523809523810e-01 | 1.415702609390e+00 | H1 | H1 |
| neutron-N126 | delta2n | EZ-BSKG3-TABLE-v1 | 63 | 1.518768290938e+04 | 1.576753035866e+04 | 0.000000000000e+00 | 9.000000000000e-01 | 21 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 2.974502879428e+01 | H0 | H1 |
| neutron-N126 | delta2n | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 63 | 5.460102427285e+02 | 6.247098642876e+02 | 2.857142857143e-01 | 6.142857142857e-01 | 21 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 1.518032524087e+00 | H1 | H1 |
| neutron-N126 | delta2n | EZ-FRDM95-TABLE-v1 | 63 | 1.625022259192e+04 | 1.666816209090e+04 | 0.000000000000e+00 | 9.000000000000e-01 | 21 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 3.252788593713e+01 | H0 | H1 |
| neutron-N126 | delta2n | EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | 63 | 1.686862508080e+02 | 2.058770286843e+02 | 8.730158730159e-01 | 2.698412698413e-02 | 21 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 3.030556288138e-01 | H1 | H1 |
| neutron-N126 | delta2n | EZ-FED-UNIFORM-ENSEMBLE-v1 | 63 | 7.709832504573e+03 | 7.967897647197e+03 | 1.000000000000e+00 | 1.000000000000e-01 | 21 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 1.521011747394e+01 | H0 | H1 |
| neutron-N126 | delta2n | EZ-FED-VALIDATION-WEIGHTED-v1 | 63 | 3.157101251876e+02 | 3.751169394963e+02 | 9.365079365079e-01 | 3.650793650794e-02 | 21 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 7.561026868362e-01 | H1 | H1 |
| proton-Z82 | delta2p | EZ-SEMF-LS-v1 | 75 | 2.422665429229e+03 | 2.931802107298e+03 | 7.333333333333e-01 | 1.666666666667e-01 | 25 | 4.000000000000e-01 | 2.000000000000e-01 | 2.800000000000e-01 | 5.456736331889e+00 | H0 | H1 |
| proton-Z82 | delta2p | EZ-GP-DIRECT-v1 | 75 | 7.181082405890e+02 | 9.051839653725e+02 | 1.000000000000e+00 | 1.000000000000e-01 | 25 | 9.600000000000e-01 | 8.000000000000e-02 | 4.000000000000e-01 | 2.708540378572e+00 | n/a | H1 |
| proton-Z82 | delta2p | EZ-SEMF-GP-RESIDUAL-v1 | 75 | 4.634813795012e+02 | 5.498374735722e+02 | 1.000000000000e+00 | 1.000000000000e-01 | 25 | 1.000000000000e+00 | 2.000000000000e-01 | 9.600000000000e-01 | 1.626398639437e+00 | n/a | H1 |
| proton-Z82 | delta2p | EZ-GP-OPTIMIZED-CONTROL-v1 | 75 | 2.440562376728e+02 | 3.390017753823e+02 | 6.400000000000e-01 | 2.600000000000e-01 | 25 | 1.000000000000e+00 | 9.600000000000e-01 | 1.000000000000e+00 | 1.100732174388e+00 | H1 | H1 |
| proton-Z82 | delta2p | EZ-BSKG3-TABLE-v1 | 75 | 1.709935557029e+04 | 1.719207053552e+04 | 0.000000000000e+00 | 9.000000000000e-01 | 25 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 3.393709245016e+01 | H0 | H1 |
| proton-Z82 | delta2p | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 75 | 3.284592308909e+02 | 4.044278921339e+02 | 6.800000000000e-01 | 2.200000000000e-01 | 25 | 1.000000000000e+00 | 9.600000000000e-01 | 1.000000000000e+00 | 1.021278904746e+00 | H1 | H1 |
| proton-Z82 | delta2p | EZ-FRDM95-TABLE-v1 | 75 | 1.740295557029e+04 | 1.744575698417e+04 | 0.000000000000e+00 | 9.000000000000e-01 | 25 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 3.479069245016e+01 | H0 | H1 |
| proton-Z82 | delta2p | EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | 75 | 1.598201867995e+02 | 2.096538246054e+02 | 8.933333333333e-01 | 6.666666666667e-03 | 25 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 3.771656739083e-01 | H1 | H1 |
| proton-Z82 | delta2p | EZ-FED-UNIFORM-ENSEMBLE-v1 | 75 | 8.581462607332e+03 | 8.615290079536e+03 | 1.000000000000e+00 | 1.000000000000e-01 | 25 | 0.000000000000e+00 | 0.000000000000e+00 | 0.000000000000e+00 | 1.703617104495e+01 | H0 | H1 |
| proton-Z82 | delta2p | EZ-FED-VALIDATION-WEIGHTED-v1 | 75 | 1.780831622251e+02 | 2.272349543591e+02 | 9.733333333333e-01 | 7.333333333333e-02 | 25 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 5.171078577902e-01 | H1 | H1 |

Derived observables (ASCII):

    S2n(Z,N)     = B(Z,N) - B(Z,N-2)
    S2p(Z,N)     = B(Z,N) - B(Z-2,N)
    delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)
    delta2p(Z,N) = S2p(Z,N) - S2p(Z+2,N)

Pooled criterion per model (all evaluable closures):

| model_id | n_closures | n_evaluable_chains | sign | rank_1 | top_k | calibration_error_90 | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | 2 | 46 | 0.217391 | 0.108696 | 0.152174 | 0.168116 | CRITERION_NOT_MET |
| EZ-GP-DIRECT-v1 | 2 | 46 | 0.826087 | 0.173913 | 0.391304 | 0.1 | CRITERION_NOT_MET |
| EZ-SEMF-GP-RESIDUAL-v1 | 2 | 46 | 0.978261 | 0.152174 | 0.608696 | 0.1 | CRITERION_NOT_MET |
| EZ-GP-OPTIMIZED-CONTROL-v1 | 2 | 46 | 1 | 0.869565 | 0.978261 | 0.32029 | CRITERION_NOT_MET |
| EZ-BSKG3-TABLE-v1 | 2 | 46 | 0 | 0 | 0 | 0.9 | CRITERION_NOT_MET |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 2 | 46 | 1 | 0.978261 | 1 | 0.4 | CRITERION_NOT_MET |
| EZ-FRDM95-TABLE-v1 | 2 | 46 | 0 | 0 | 0 | 0.9 | CRITERION_NOT_MET |
| EZ-FRDM95-TABLE-v1+GP-RESIDUAL-v1 | 2 | 46 | 1 | 1 | 1 | 0.015942 | CRITERION_MET |
| EZ-FED-UNIFORM-ENSEMBLE-v1 | 2 | 46 | 0 | 0 | 0 | 0.1 | CRITERION_NOT_MET |
| EZ-FED-VALIDATION-WEIGHTED-v1 | 2 | 46 | 1 | 1 | 1 | 0.0565217 | CRITERION_MET |

Closures refused by the support rule (reported, never dropped):

| challenge_id | status | reasons |
| --- | --- | --- |
| neutron-N20 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| neutron-N28 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| neutron-N50 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| neutron-N82 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| proton-Z20 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| proton-Z28 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
| proton-Z50 | NOT_EVALUABLE | 0 chains satisfy the support rule; MIN_EVALUABLE_CHAINS is 3 |
