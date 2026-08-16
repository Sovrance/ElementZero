# EZ-B002 region rect-Z20-23-N20-24

benchmark_id: EZ-B002
protocol_version: 0.3.0
b002_protocol_version: 1.0.0
region_manifest_hash: 8da2aa5dfa2e9388bc3c5e3f6ac0f6cd5f6e9af757f34b3a68ce34c097a57bed

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

threshold rule: EZ-B002 v1 is characterization. Engineering PASS means correct masking, absent leakage, scored and calibrated outputs, and reproducible results. No accuracy pass/fail threshold is defined here, and none may be added after seeing these numbers; a scientific threshold requires a later preregistered protocol version.

| region_id | z_band | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 | max_nearest_training_L1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rect-Z20-23-N20-24 | medium | EZ-SEMF-LS-v1 | 20 | 4967.51 | 4901.83 | 5076.1 | 10.0745 | 0.85 | 1 | 0.05 | 0.05 | 2 |
| rect-Z20-23-N20-24 | medium | EZ-GP-DIRECT-v1 | 20 | 1838.85 | 1537.6 | 2308.9 | 16.2785 | 1 | 1 | 0.1 | 0.05 | 2 |
| rect-Z20-23-N20-24 | medium | EZ-SEMF-GP-RESIDUAL-v1 | 20 | 687.764 | 347.499 | 980.325 | 13.8098 | 1 | 1 | 0.1 | 0.05 | 2 |
| rect-Z20-23-N20-24 | medium | EZ-GP-OPTIMIZED-CONTROL-v1 | 20 | 443.222 | 275.078 | 649.958 | 7.98007 | 0.8 | 0.85 | 0.1 | 0.1 | 2 |

Extrapolation depth (ASCII):

    nearest_training_L1 = min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)
