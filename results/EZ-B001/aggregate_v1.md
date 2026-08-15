# EZ-B001 longitudinal aggregate v1

benchmark_id: EZ-B001
protocol_version: 1.0.0
protocol_code_digest: 5c20d931cdef024efe55fdf7bdab04d339e4bd787076385f0a1de36df1660e5f
atlas_pir_ref: 31d76d094f1206e64a6920da4775d0a684618357

Every metric is reported for every model in every epoch. No ranking, no best-model label, and no epoch is dropped for behaving badly.

## Epochs

| experiment_id | training | truth | preregistration_hash |
| --- | --- | --- | --- |
| EZ-B001-A | AME2003 | AME2012 | `3bb01b68dd2d07f4abcc7a2c755332c3a9218b79c9daf900d0c8d9127f756442` |
| EZ-B001-B | AME2012 | AME2016 | `007c1a5267d905c14bf9dca3333778048dc6fec09a17aefe3c7f298f58c5219a` |
| EZ-B001-C | AME2016 | AME2020 | `e563ce856380f4abc51558f91d74d2135d69d0a3379b8c426f4f6e139f4d6c29` |

## Primary metrics

| experiment_id | training_edition | truth_edition | model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | cal_error_90 | cal_error_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-A | AME2003 | AME2012 | EZ-SEMF-LS-v1 | 225 | 3393.29 | 2269.58 | 4934.89 | 10.077 | 0.822222 | 0.848889 | 0.0777778 | 0.101111 |
| EZ-B001-A | AME2003 | AME2012 | EZ-GP-DIRECT-v1 | 225 | 2012.21 | 1392.97 | 4868.76 | 16.329 | 1 | 1 | 0.1 | 0.05 |
| EZ-B001-A | AME2003 | AME2012 | EZ-SEMF-GP-RESIDUAL-v1 | 225 | 510.998 | 294.001 | 827.689 | 13.8519 | 1 | 1 | 0.1 | 0.05 |
| EZ-B001-B | AME2012 | AME2016 | EZ-SEMF-LS-v1 | 63 | 3165.85 | 1650.19 | 4874.56 | 10.0168 | 0.809524 | 0.857143 | 0.0904762 | 0.0928571 |
| EZ-B001-B | AME2012 | AME2016 | EZ-GP-DIRECT-v1 | 63 | 1767.22 | 1183.77 | 2294.86 | 16.3089 | 1 | 1 | 0.1 | 0.05 |
| EZ-B001-B | AME2012 | AME2016 | EZ-SEMF-GP-RESIDUAL-v1 | 63 | 543.412 | 357.596 | 796.271 | 13.8456 | 1 | 1 | 0.1 | 0.05 |
| EZ-B001-C | AME2016 | AME2020 | EZ-SEMF-LS-v1 | 74 | 2789.26 | 1561.58 | 5055.12 | 10.0753 | 0.878378 | 0.905405 | 0.0216216 | 0.0445946 |
| EZ-B001-C | AME2016 | AME2020 | EZ-GP-DIRECT-v1 | 74 | 1862.71 | 1256.65 | 2746.72 | 16.3463 | 1 | 1 | 0.1 | 0.05 |
| EZ-B001-C | AME2016 | AME2020 | EZ-SEMF-GP-RESIDUAL-v1 | 74 | 388.765 | 229.855 | 575.287 | 13.8894 | 1 | 1 | 0.1 | 0.05 |

## Error versus nearest-training L1 distance

| experiment_id | model_id | distance_bucket | n | MAE_keV | RMSE_keV | NLPD |
| --- | --- | --- | --- | --- | --- | --- |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=1 | 170 | 3246.09 | 4915.95 | 10.0694 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=2 | 46 | 3931.71 | 5162.37 | 10.1715 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d=3-4 | 8 | 3544.02 | 4172.34 | 9.79154 |
| EZ-B001-A | EZ-SEMF-LS-v1 | d>=5 | 1 | 2443.4 | 2443.4 | 9.3213 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=1 | 170 | 1388.11 | 1747.97 | 16.2823 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=2 | 46 | 2228.24 | 2712.19 | 16.4067 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d=3-4 | 8 | 7752.72 | 14773 | 16.6917 |
| EZ-B001-A | EZ-GP-DIRECT-v1 | d>=5 | 1 | 52248 | 52248 | 17.7918 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 170 | 530.332 | 881.466 | 13.8052 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 46 | 476.592 | 666.912 | 13.9296 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 8 | 301.204 | 412.082 | 14.2146 |
| EZ-B001-A | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 1 | 485.233 | 485.233 | 15.3147 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=1 | 57 | 3375.59 | 5088.55 | 10.0975 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=2 | 6 | 1173.23 | 1872.94 | 9.24974 |
| EZ-B001-B | EZ-SEMF-LS-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-LS-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=1 | 57 | 1648.65 | 2083.46 | 16.3004 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=2 | 6 | 2893.68 | 3749.58 | 16.3899 |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-GP-DIRECT-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 57 | 525.357 | 759.232 | 13.837 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 6 | 714.927 | 1086.92 | 13.9265 |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 0 | n/a | n/a | n/a |
| EZ-B001-B | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=1 | 62 | 3177.88 | 5492.1 | 10.2462 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=2 | 10 | 826.636 | 1423.95 | 9.20241 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d=3-4 | 2 | 555.315 | 558.653 | 9.13876 |
| EZ-B001-C | EZ-SEMF-LS-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=1 | 62 | 1966.7 | 2891.27 | 16.3196 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=2 | 10 | 1448.88 | 1973.64 | 16.4568 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d=3-4 | 2 | 708.032 | 724.588 | 16.6184 |
| EZ-B001-C | EZ-GP-DIRECT-v1 | d>=5 | 0 | n/a | n/a | n/a |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=1 | 62 | 416.426 | 609.779 | 13.8628 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=2 | 10 | 258.883 | 368.504 | 14 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d=3-4 | 2 | 180.711 | 199.054 | 14.1616 |
| EZ-B001-C | EZ-SEMF-GP-RESIDUAL-v1 | d>=5 | 0 | n/a | n/a | n/a |

## Stability diagnostics

### EZ-SEMF-LS-v1

| quantity | first epoch | last epoch | delta | direction |
| --- | --- | --- | --- | --- |
| MAE_keV | 3393.29 | 2789.26 | -604.024 | decreasing |
| MedAE_keV | 2269.58 | 1561.58 | -708.005 | decreasing |
| RMSE_keV | 4934.89 | 5055.12 | 120.228 | increasing |
| NLPD | 10.077 | 10.0753 | -0.00178076 | decreasing |
| coverage_90 | 0.822222 | 0.878378 | 0.0561562 | increasing |
| coverage_95 | 0.848889 | 0.905405 | 0.0565165 | increasing |
| cal_error_90 | 0.0777778 | 0.0216216 | -0.0561562 | decreasing |
| cal_error_95 | 0.101111 | 0.0445946 | -0.0565165 | decreasing |
| n_targets | 225 | 74 | -151 | decreasing |

- EZ-B001-A: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['3246.09', '3931.71', '3544.02', '2443.4'], non-decreasing with distance: False
- EZ-B001-B: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['3375.59', '1173.23', 'n/a', 'n/a'], non-decreasing with distance: False
- EZ-B001-C: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['3177.88', '826.636', '555.315', 'n/a'], non-decreasing with distance: False

### EZ-GP-DIRECT-v1

| quantity | first epoch | last epoch | delta | direction |
| --- | --- | --- | --- | --- |
| MAE_keV | 2012.21 | 1862.71 | -149.502 | decreasing |
| MedAE_keV | 1392.97 | 1256.65 | -136.317 | decreasing |
| RMSE_keV | 4868.76 | 2746.72 | -2122.04 | decreasing |
| NLPD | 16.329 | 16.3463 | 0.0172097 | increasing |
| coverage_90 | 1 | 1 | 0 | flat |
| coverage_95 | 1 | 1 | 0 | flat |
| cal_error_90 | 0.1 | 0.1 | 0 | flat |
| cal_error_95 | 0.05 | 0.05 | 0 | flat |
| n_targets | 225 | 74 | -151 | decreasing |

- EZ-B001-A: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['1388.11', '2228.24', '7752.72', '52248'], non-decreasing with distance: True
- EZ-B001-B: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['1648.65', '2893.68', 'n/a', 'n/a'], non-decreasing with distance: True
- EZ-B001-C: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['1966.7', '1448.88', '708.032', 'n/a'], non-decreasing with distance: False

### EZ-SEMF-GP-RESIDUAL-v1

| quantity | first epoch | last epoch | delta | direction |
| --- | --- | --- | --- | --- |
| MAE_keV | 510.998 | 388.765 | -122.233 | decreasing |
| MedAE_keV | 294.001 | 229.855 | -64.1461 | decreasing |
| RMSE_keV | 827.689 | 575.287 | -252.401 | decreasing |
| NLPD | 13.8519 | 13.8894 | 0.037542 | increasing |
| coverage_90 | 1 | 1 | 0 | flat |
| coverage_95 | 1 | 1 | 0 | flat |
| cal_error_90 | 0.1 | 0.1 | 0 | flat |
| cal_error_95 | 0.05 | 0.05 | 0 | flat |
| n_targets | 225 | 74 | -151 | decreasing |

- EZ-B001-A: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['530.332', '476.592', '301.204', '485.233'], non-decreasing with distance: False
- EZ-B001-B: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['525.357', '714.927', 'n/a', 'n/a'], non-decreasing with distance: True
- EZ-B001-C: MAE by bucket ['d=1', 'd=2', 'd=3-4', 'd>=5'] = ['416.426', '258.883', '180.711', 'n/a'], non-decreasing with distance: False
