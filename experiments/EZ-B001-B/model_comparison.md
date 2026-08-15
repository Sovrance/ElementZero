# EZ-B001 model comparison

benchmark_id: EZ-B001
protocol_version: 0.3.0
model_suite_id: EZ-B001-SUITE-v1
freeze_id: frz_0883fe445515efe7
truth_source_hash: 2167f57a2a98331e4649b2dd2b658a9006ed4fba1975729ebfe52a42b4b9218a

ranking rule: none: every metric is reported for every model; no single-metric ranking and no 'best model' label is emitted by this report

| model_id | n | MAE_keV | MedAE_keV | RMSE_keV | NLPD | coverage_90 | coverage_95 | calibration_error_90 | calibration_error_95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-SEMF-LS-v1 | 63 | 3165.85 | 1650.19 | 4874.56 | 10.0168 | 0.809524 | 0.857143 | 0.0904762 | 0.0928571 |
| EZ-GP-DIRECT-v1 | 63 | 1767.22 | 1183.77 | 2294.86 | 16.3089 | 1 | 1 | 0.1 | 0.05 |
| EZ-SEMF-GP-RESIDUAL-v1 | 63 | 543.412 | 357.596 | 796.271 | 13.8456 | 1 | 1 | 0.1 | 0.05 |

Metric definitions (ASCII):

    error_i = prediction_i - truth_i
    MAE     = mean(abs(error_i))
    MedAE   = median(abs(error_i))
    RMSE    = sqrt(mean(error_i^2))
    NLPD_i  = 0.5*log(2*pi*sigma_i^2) + 0.5*((truth_i - prediction_i)/sigma_i)^2
    cal_error_90 = abs(coverage_90 - 0.90)
    cal_error_95 = abs(coverage_95 - 0.95)
