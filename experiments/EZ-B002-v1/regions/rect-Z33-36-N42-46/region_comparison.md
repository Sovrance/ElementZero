# EZ-B002 region rect-Z33-36-N42-46

benchmark_id: EZ-B002
protocol_version: 0.3.0
b002_protocol_version: 1.0.0
region_manifest_hash: 9b7d97fdbd617eb550415c385cc42d8f11af7179bba29d431712cbaa471a5976

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

threshold rule: EZ-B002 v1 is characterization. Engineering PASS means correct masking, absent leakage, scored and calibrated outputs, and reproducible results. No accuracy pass/fail threshold is defined here, and none may be added after seeing these numbers; a scientific threshold requires a later preregistered protocol version.

| region_id | z_band | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 | max_nearest_training_L1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rect-Z33-36-N42-46 | medium | EZ-SEMF-LS-v1 | 20 | 921.151 | 969.823 | 930.771 | 8.83294 | 0.25 | 0.65 | 0.65 | 0.3 | 2 |
| rect-Z33-36-N42-46 | medium | EZ-GP-DIRECT-v1 | 20 | 1349.34 | 1176.97 | 1559.39 | 15.9358 | 1 | 1 | 0.1 | 0.05 | 2 |
| rect-Z33-36-N42-46 | medium | EZ-SEMF-GP-RESIDUAL-v1 | 20 | 56.8416 | 56.5276 | 62.1536 | 11.9079 | 1 | 1 | 0.1 | 0.05 | 2 |

Extrapolation depth (ASCII):

    nearest_training_L1 = min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)
