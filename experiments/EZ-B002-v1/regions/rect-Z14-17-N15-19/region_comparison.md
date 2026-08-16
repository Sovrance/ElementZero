# EZ-B002 region rect-Z14-17-N15-19

benchmark_id: EZ-B002
protocol_version: 0.3.0
b002_protocol_version: 1.0.0
region_manifest_hash: 9b7d97fdbd617eb550415c385cc42d8f11af7179bba29d431712cbaa471a5976

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

threshold rule: EZ-B002 v1 is characterization. Engineering PASS means correct masking, absent leakage, scored and calibrated outputs, and reproducible results. No accuracy pass/fail threshold is defined here, and none may be added after seeing these numbers; a scientific threshold requires a later preregistered protocol version.

| region_id | z_band | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 | max_nearest_training_L1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rect-Z14-17-N15-19 | light | EZ-SEMF-LS-v1 | 18 | 903.394 | 944.516 | 939.253 | 8.84719 | 0.444444 | 0.555556 | 0.455556 | 0.394444 | 3 |
| rect-Z14-17-N15-19 | light | EZ-GP-DIRECT-v1 | 18 | 2242.41 | 2196.44 | 2512.21 | 15.956 | 1 | 1 | 0.1 | 0.05 | 3 |
| rect-Z14-17-N15-19 | light | EZ-SEMF-GP-RESIDUAL-v1 | 18 | 21.1657 | 23.6565 | 23.6328 | 11.9847 | 1 | 1 | 0.1 | 0.05 | 3 |

Extrapolation depth (ASCII):

    nearest_training_L1 = min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)
