# EZ-B001 model comparison

benchmark_id: EZ-B001
protocol_version: 0.3.0
model_suite_id: EZ-B001-SUITE-v1
freeze_id: frz_d1ee8dd2efa4dc85
truth_source_hash: 81e887c71c2c54c76caea36fd861b195a7f3eeb77d04b520e05fa97e0eedd7f3

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

| model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | 225 | 3393.29 | 2269.58 | 4934.89 | 10.077 | 0.822222 | 0.848889 | 0.0777778 | 0.101111 |
| EZ-GP-DIRECT-v1 | 225 | 2012.21 | 1392.97 | 4868.76 | 16.329 | 1 | 1 | 0.1 | 0.05 |
| EZ-SEMF-GP-RESIDUAL-v1 | 225 | 510.998 | 294.001 | 827.689 | 13.8519 | 1 | 1 | 0.1 | 0.05 |

Metric definitions (ASCII):

    error_i = prediction_i - truth_i
    MAE     = mean(abs(error_i))
    MedAE   = median(abs(error_i))
    RMSE    = sqrt(mean(error_i^2))
    NLPD_i  = 0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2
    cal_error_90 = abs(coverage_90 - 0.90)
    cal_error_95 = abs(coverage_95 - 0.95)
