# EZ-B002 region rect-Z50-53-N56-60

benchmark_id: EZ-B002
protocol_version: 0.3.0
b002_protocol_version: 1.0.0
region_manifest_hash: 8da2aa5dfa2e9388bc3c5e3f6ac0f6cd5f6e9af757f34b3a68ce34c097a57bed

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

threshold rule: EZ-B002 v1 is characterization. Engineering PASS means correct masking, absent leakage, scored and calibrated outputs, and reproducible results. No accuracy pass/fail threshold is defined here, and none may be added after seeing these numbers; a scientific threshold requires a later preregistered protocol version.

| region_id | z_band | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 | max_nearest_training_L1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rect-Z50-53-N56-60 | heavy | EZ-BSKG3-TABLE-v1 | 20 | 698.021 | 726.76 | 810.037 | 8.14627 | 0.85 | 0.95 | 0.05 | 0 | 3 |
| rect-Z50-53-N56-60 | heavy | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 20 | 298.411 | 309.705 | 353.269 | 7.31289 | 0.9 | 0.95 | 0 | 0 | 3 |

Extrapolation depth (ASCII):

    nearest_training_L1 = min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)
