# EZ-B002 region rect-Z10-13-N10-14

benchmark_id: EZ-B002
protocol_version: 0.3.0
b002_protocol_version: 1.0.0
region_manifest_hash: 8da2aa5dfa2e9388bc3c5e3f6ac0f6cd5f6e9af757f34b3a68ce34c097a57bed

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

threshold rule: EZ-B002 v1 is characterization. Engineering PASS means correct masking, absent leakage, scored and calibrated outputs, and reproducible results. No accuracy pass/fail threshold is defined here, and none may be added after seeing these numbers; a scientific threshold requires a later preregistered protocol version.

| region_id | z_band | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 | max_nearest_training_L1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rect-Z10-13-N10-14 | light | EZ-SEMF-LS-v1 | 20 | 4388.21 | 4404.54 | 4456.63 | 9.85888 | 1 | 1 | 0.1 | 0.05 | 2 |
| rect-Z10-13-N10-14 | light | EZ-GP-DIRECT-v1 | 20 | 1665.44 | 1401.37 | 2142.43 | 16.2792 | 1 | 1 | 0.1 | 0.05 | 2 |
| rect-Z10-13-N10-14 | light | EZ-SEMF-GP-RESIDUAL-v1 | 20 | 1165.38 | 1119.08 | 1370.43 | 13.814 | 1 | 1 | 0.1 | 0.05 | 2 |
| rect-Z10-13-N10-14 | light | EZ-GP-OPTIMIZED-CONTROL-v1 | 20 | 965.016 | 556.123 | 1262.75 | 10.1305 | 0.6 | 0.65 | 0.3 | 0.3 | 2 |

Extrapolation depth (ASCII):

    nearest_training_L1 = min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)
