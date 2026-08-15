# EZ-B001 model comparison

benchmark_id: EZ-B001
protocol_version: 0.3.0
model_suite_id: EZ-B001-SUITE-v1
freeze_id: frz_3d3a4532f61e0906
truth_source_hash: e8599c6d7f724fac91934e59f1b9de8fb8f63e820f4b39456b790665ed2a3307

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

| model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | 74 | 2789.26 | 1561.58 | 5055.12 | 10.0753 | 0.878378 | 0.905405 | 0.0216216 | 0.0445946 |
| EZ-GP-DIRECT-v1 | 74 | 1862.71 | 1256.65 | 2746.72 | 16.3463 | 1 | 1 | 0.1 | 0.05 |
| EZ-SEMF-GP-RESIDUAL-v1 | 74 | 388.765 | 229.855 | 575.287 | 13.8894 | 1 | 1 | 0.1 | 0.05 |

Metric definitions (ASCII):

    error_i = prediction_i - truth_i
    MAE     = mean(abs(error_i))
    MedAE   = median(abs(error_i))
    RMSE    = sqrt(mean(error_i^2))
    NLPD_i  = 0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2
    cal_error_90 = abs(coverage_90 - 0.90)
    cal_error_95 = abs(coverage_95 - 0.95)
