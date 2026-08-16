# EZ-B002 geographic holdout aggregate

benchmark_id: EZ-B002
protocol_version: 0.3.0
b002_protocol_version: 1.0.0
region_manifest_hash: 8da2aa5dfa2e9388bc3c5e3f6ac0f6cd5f6e9af757f34b3a68ce34c097a57bed

ranking rule: none

threshold rule: EZ-B002 v1 is characterization. Engineering PASS means correct masking, absent leakage, scored and calibrated outputs, and reproducible results. No accuracy pass/fail threshold is defined here, and none may be added after seeing these numbers; a scientific threshold requires a later preregistered protocol version.

| region_id | z_band | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 | max_nearest_training_L1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rect-Z10-13-N10-14 | light | EZ-BSKG3-TABLE-v1 | 20 | 7.818185655000e+02 | 6.939575000000e+02 | 9.876729203013e+02 | 8.484341415213e+00 | 8.500000000000e-01 | 9.000000000000e-01 | 5.000000000000e-02 | 5.000000000000e-02 | 2 |
| rect-Z10-13-N10-14 | light | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 20 | 6.895375067399e+02 | 5.247966652730e+02 | 8.634218025935e+02 | 9.808796805186e+00 | 6.000000000000e-01 | 6.500000000000e-01 | 3.000000000000e-01 | 3.000000000000e-01 | 2 |
| rect-Z20-23-N20-24 | medium | EZ-BSKG3-TABLE-v1 | 20 | 7.957680500000e+02 | 8.419885000000e+02 | 8.683907367689e+02 | 8.249957863241e+00 | 9.000000000000e-01 | 9.000000000000e-01 | 0.000000000000e+00 | 5.000000000000e-02 | 2 |
| rect-Z20-23-N20-24 | medium | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 20 | 3.602708213130e+02 | 3.150863370300e+02 | 4.264073341916e+02 | 7.489992972839e+00 | 8.000000000000e-01 | 9.000000000000e-01 | 1.000000000000e-01 | 5.000000000000e-02 | 2 |
| rect-Z50-53-N56-60 | heavy | EZ-BSKG3-TABLE-v1 | 20 | 6.980213500000e+02 | 7.267595000000e+02 | 8.100374535692e+02 | 8.146270281587e+00 | 8.500000000000e-01 | 9.500000000000e-01 | 5.000000000000e-02 | 0.000000000000e+00 | 3 |
| rect-Z50-53-N56-60 | heavy | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 20 | 2.984109442640e+02 | 3.097054014100e+02 | 3.532694017960e+02 | 7.312886170944e+00 | 9.000000000000e-01 | 9.500000000000e-01 | 0.000000000000e+00 | 0.000000000000e+00 | 3 |

Extrapolation depth (ASCII):

    nearest_training_L1 = min over training nuclei of abs(Z_t - Z_r) + abs(N_t - N_r)

Worst region per model (reported, never dropped):

| model_id | worst_region_id | MAE_keV | RMSE_keV | coverage_90 | coverage_95 |
| --- | --- | --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | rect-Z20-23-N20-24 | 7.957680500000e+02 | 8.683907367689e+02 | 9.000000000000e-01 | 9.000000000000e-01 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | rect-Z10-13-N10-14 | 6.895375067399e+02 | 8.634218025935e+02 | 6.000000000000e-01 | 6.500000000000e-01 |

Pooled metrics by extrapolation depth:

| model_id | depth | n | MAE_keV | RMSE_keV | coverage_90 | coverage_95 | NLPD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | L1=1 | 40 | 737.193 | 836.281 | 0.9 | 0.95 | 8.19201 |
| EZ-BSKG3-TABLE-v1 | L1=2 | 19 | 811.003 | 1009.48 | 0.789474 | 0.842105 | 8.53044 |
| EZ-BSKG3-TABLE-v1 | L1=3 | 1 | 615.399 | 615.399 | 1 | 1 | 7.85255 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | L1=1 | 40 | 417.38 | 537.013 | 0.775 | 0.875 | 8.01219 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | L1=2 | 19 | 529.486 | 705.744 | 0.736842 | 0.736842 | 8.66904 |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | L1=3 | 1 | 208.967 | 208.967 | 1 | 1 | 7.03408 |
