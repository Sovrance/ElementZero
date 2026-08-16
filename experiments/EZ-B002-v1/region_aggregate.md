# EZ-B002 geographic holdout aggregate

benchmark_id: EZ-B002
protocol_version: 0.3.0
b002_protocol_version: 1.0.0
region_manifest_hash: 9b7d97fdbd617eb550415c385cc42d8f11af7179bba29d431712cbaa471a5976

ranking rule: none

threshold rule: EZ-B002 v1 is characterization. Engineering PASS means correct masking, absent leakage, scored and calibrated outputs, and reproducible results. No accuracy pass/fail threshold is defined here, and none may be added after seeing these numbers; a scientific threshold requires a later preregistered protocol version.

| region_id | z_band | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 | max_nearest_training_L1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rect-Z14-17-N15-19 | light | EZ-SEMF-LS-v1 | 18 | 9.033936862017e+02 | 9.445163470000e+02 | 9.392525295888e+02 | 8.847192478091e+00 | 4.444444444444e-01 | 5.555555555556e-01 | 4.555555555556e-01 | 3.944444444444e-01 | 3 |
| rect-Z14-17-N15-19 | light | EZ-GP-DIRECT-v1 | 18 | 2.242414147464e+03 | 2.196435876430e+03 | 2.512209275566e+03 | 1.595604665874e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 | 5.000000000000e-02 | 3 |
| rect-Z14-17-N15-19 | light | EZ-SEMF-GP-RESIDUAL-v1 | 18 | 2.116570840222e+01 | 2.365653396000e+01 | 2.363278944715e+01 | 1.198474087001e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 | 5.000000000000e-02 | 3 |
| rect-Z33-36-N42-46 | medium | EZ-SEMF-LS-v1 | 20 | 9.211514633150e+02 | 9.698228097050e+02 | 9.307712186956e+02 | 8.832941059836e+00 | 2.500000000000e-01 | 6.500000000000e-01 | 6.500000000000e-01 | 3.000000000000e-01 | 2 |
| rect-Z33-36-N42-46 | medium | EZ-GP-DIRECT-v1 | 20 | 1.349343944678e+03 | 1.176970343030e+03 | 1.559394468608e+03 | 1.593578055273e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 | 5.000000000000e-02 | 2 |
| rect-Z33-36-N42-46 | medium | EZ-SEMF-GP-RESIDUAL-v1 | 20 | 5.684163093250e+01 | 5.652763316000e+01 | 6.215362120748e+01 | 1.190789016104e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 | 5.000000000000e-02 | 2 |
| rect-Z50-53-N70-74 | heavy | EZ-SEMF-LS-v1 | 20 | 6.276744753030e+02 | 6.777288819800e+02 | 6.959934670542e+02 | 8.064262298451e+00 | 6.500000000000e-01 | 9.000000000000e-01 | 2.500000000000e-01 | 5.000000000000e-02 | 2 |
| rect-Z50-53-N70-74 | heavy | EZ-GP-DIRECT-v1 | 20 | 8.968206217060e+02 | 7.819134739900e+02 | 1.058395879405e+03 | 1.589440534838e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 | 5.000000000000e-02 | 2 |
| rect-Z50-53-N70-74 | heavy | EZ-SEMF-GP-RESIDUAL-v1 | 20 | 3.212544744900e+01 | 2.921329155999e+01 | 3.558072982455e+01 | 1.190889702227e+01 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e-01 | 5.000000000000e-02 | 2 |

Extrapolation depth (ASCII):

    nearest_training_L1 = min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)

Worst region per model (reported, never dropped):

| model_id | worst_region_id | MAE_keV | RMSE_keV | coverage_90 | coverage_95 |
| --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | rect-Z33-36-N42-46 | 9.211514633150e+02 | 9.307712186956e+02 | 2.500000000000e-01 | 6.500000000000e-01 |
| EZ-GP-DIRECT-v1 | rect-Z50-53-N70-74 | 8.968206217060e+02 | 1.058395879405e+03 | 1.000000000000e+00 | 1.000000000000e+00 |
| EZ-SEMF-GP-RESIDUAL-v1 | rect-Z33-36-N42-46 | 5.684163093250e+01 | 6.215362120748e+01 | 1.000000000000e+00 | 1.000000000000e+00 |

Pooled metrics by extrapolation depth:

| model_id | depth | n | MAE_keV | RMSE_keV | coverage_90 | coverage_95 | NLPD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | L1=1 | 27 | 784.54 | 833.111 | 0.444444 | 0.777778 | 8.48009 |
| EZ-SEMF-LS-v1 | L1=2 | 26 | 809.999 | 852.206 | 0.5 | 0.692308 | 8.55167 |
| EZ-SEMF-LS-v1 | L1=3 | 5 | 999.009 | 1026.81 | 0.2 | 0.4 | 9.17756 |
| EZ-GP-DIRECT-v1 | L1=1 | 27 | 1491.45 | 1757.86 | 1 | 1 | 15.8935 |
| EZ-GP-DIRECT-v1 | L1=2 | 26 | 1320.72 | 1696.43 | 1 | 1 | 15.9464 |
| EZ-GP-DIRECT-v1 | L1=3 | 5 | 2135.8 | 2297.11 | 1 | 1 | 16.0163 |
| EZ-SEMF-GP-RESIDUAL-v1 | L1=1 | 27 | 36.2414 | 41.6838 | 1 | 1 | 11.897 |
| EZ-SEMF-GP-RESIDUAL-v1 | L1=2 | 26 | 40.0926 | 48.6625 | 1 | 1 | 11.9468 |
| EZ-SEMF-GP-RESIDUAL-v1 | L1=3 | 5 | 27.8797 | 28.816 | 1 | 1 | 12.045 |
