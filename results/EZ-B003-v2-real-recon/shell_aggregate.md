# EZ-B003 hidden shell rediscovery aggregate

benchmark_id: EZ-B003
protocol_version: 0.3.0
b003_protocol_version: 1.0.0
scope: real-evaluated-data-wo14
profile: discovery

criterion: ez-b003-rediscovery-criterion-v1 (sign >= 0.75, top-3 >= 0.75, rank-1 >= 0.5, abs(coverage_90 - 0.90) <= 0.15)

boundary: EZ-B003 measures one narrow capability: rediscovery of known shell-related mass structure under controlled masking. A met criterion is not proof of a new magic number, and it is not evidence that a predicted Z = 154 shell gap or an island of stability exists. That claim would require independent physics-model ensembles, deformation calculations, fission calculations, decay competition, and far larger extrapolation uncertainty.

| challenge_id | indicator | model_id | n | MAE_keV | RMSE_keV | coverage_90 | calibration_error_90 | n_evaluable_chains | sign_recovered_fraction | rank_1_fraction | top_k_fraction | mean_absolute_indicator_error_MeV | predicted_hypothesis | truth_hypothesis |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| neutron-N126 | delta2n | EZ-BSKG3-TABLE-v1 | 40 | 1.861195500000e+03 | 1.947690775722e+03 | 1.500000000000e-01 | 7.500000000000e-01 | 12 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 4.342605666674e+00 | H1 | H1 |
| neutron-N126 | delta2n | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 40 | 4.830381994230e+02 | 5.741592991317e+02 | 6.500000000000e-01 | 2.500000000000e-01 | 12 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 1.404753610285e+00 | H1 | H1 |
| neutron-N20 | delta2n | EZ-BSKG3-TABLE-v1 | 46 | 7.622911380435e+02 | 8.827002454428e+02 | 7.608695652174e-01 | 1.391304347826e-01 | 12 | 1.000000000000e+00 | 2.500000000000e-01 | 5.833333333333e-01 | 1.660227558334e+00 | n/a | n/a |
| neutron-N20 | delta2n | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 46 | 6.738836732141e+02 | 7.859718864073e+02 | 4.130434782609e-01 | 4.869565217391e-01 | 12 | 1.000000000000e+00 | 1.666666666667e-01 | 5.000000000000e-01 | 1.572283052360e+00 | n/a | n/a |
| neutron-N28 | delta2n | EZ-BSKG3-TABLE-v1 | 44 | 5.350837727273e+02 | 6.871053220611e+02 | 8.863636363636e-01 | 1.363636363636e-02 | 12 | 1.000000000000e+00 | 5.000000000000e-01 | 1.000000000000e+00 | 1.227939999999e+00 | n/a | H1 |
| neutron-N28 | delta2n | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 44 | 5.545098460487e+02 | 6.755950412678e+02 | 5.454545454545e-01 | 3.545454545455e-01 | 12 | 1.000000000000e+00 | 5.000000000000e-01 | 7.500000000000e-01 | 1.458704297330e+00 | n/a | H1 |
| neutron-N50 | delta2n | EZ-BSKG3-TABLE-v1 | 62 | 5.338868590323e+02 | 6.600066515812e+02 | 9.354838709677e-01 | 3.548387096774e-02 | 17 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 9.374986694094e-01 | H1 | H1 |
| neutron-N50 | delta2n | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 62 | 3.793230061871e+02 | 4.664390294314e+02 | 7.903225806452e-01 | 1.096774193548e-01 | 17 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 1.147579866207e+00 | H1 | H1 |
| neutron-N82 | delta2n | EZ-BSKG3-TABLE-v1 | 68 | 3.916158088235e+02 | 5.082483084853e+02 | 9.558823529412e-01 | 5.588235294118e-02 | 20 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 9.155601000083e-01 | H1 | H1 |
| neutron-N82 | delta2n | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 68 | 3.297538519593e+02 | 3.782145189869e+02 | 8.676470588235e-01 | 3.235294117647e-02 | 20 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 8.695123418331e-01 | H1 | H1 |
| proton-Z20 | delta2p | EZ-BSKG3-TABLE-v1 | 61 | 8.143886647541e+02 | 9.860346655226e+02 | 7.868852459016e-01 | 1.131147540984e-01 | 13 | 1.000000000000e+00 | 2.307692307692e-01 | 8.461538461538e-01 | 1.550392307692e+00 | n/a | n/a |
| proton-Z20 | delta2p | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 61 | 9.137326909115e+02 | 1.107950985078e+03 | 3.278688524590e-01 | 5.721311475410e-01 | 13 | 1.000000000000e+00 | 1.538461538462e-01 | 4.615384615385e-01 | 1.560513263785e+00 | n/a | n/a |
| proton-Z28 | delta2p | EZ-BSKG3-TABLE-v1 | 69 | 6.708507971014e+02 | 7.800872583324e+02 | 8.550724637681e-01 | 4.492753623188e-02 | 14 | 1.000000000000e+00 | 4.285714285714e-01 | 8.571428571429e-01 | 1.989743714286e+00 | n/a | H1 |
| proton-Z28 | delta2p | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 69 | 4.605221300157e+02 | 5.840064290777e+02 | 7.101449275362e-01 | 1.898550724638e-01 | 14 | 1.000000000000e+00 | 5.714285714286e-01 | 9.285714285714e-01 | 1.673559213383e+00 | H1 | H1 |
| proton-Z50 | delta2p | EZ-BSKG3-TABLE-v1 | 101 | 5.128977920792e+02 | 6.636648109234e+02 | 8.811881188119e-01 | 1.881188118812e-02 | 31 | 1.000000000000e+00 | 6.774193548387e-01 | 7.741935483871e-01 | 1.330860322582e+00 | H1 | H1 |
| proton-Z50 | delta2p | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 101 | 3.885371877299e+02 | 4.867590258833e+02 | 7.425742574257e-01 | 1.574257425743e-01 | 31 | 1.000000000000e+00 | 1.000000000000e+00 | 1.000000000000e+00 | 7.019069803093e-01 | H1 | H1 |
| proton-Z82 | delta2p | EZ-BSKG3-TABLE-v1 | 107 | 4.561154579439e+02 | 6.106880474005e+02 | 9.158878504673e-01 | 1.588785046729e-02 | 27 | 1.000000000000e+00 | 6.666666666667e-01 | 8.518518518519e-01 | 1.103139037029e+00 | H1 | H1 |
| proton-Z82 | delta2p | EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 107 | 2.334791967346e+02 | 2.862048583471e+02 | 9.906542056075e-01 | 9.065420560748e-02 | 27 | 1.000000000000e+00 | 7.037037037037e-01 | 1.000000000000e+00 | 5.072742745772e-01 | H1 | H1 |

Derived observables (ASCII):

    S2n(Z,N)     = B(Z,N) - B(Z,N-2)
    S2p(Z,N)     = B(Z,N) - B(Z-2,N)
    delta2n(Z,N) = S2n(Z,N) - S2n(Z,N+2)
    delta2p(Z,N) = S2p(Z,N) - S2p(Z+2,N)

Pooled criterion per model (all evaluable closures):

| model_id | n_closures | n_evaluable_chains | sign | rank_1 | top_k | calibration_error_90 | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EZ-BSKG3-TABLE-v1 | 9 | 158 | 1 | 0.670886 | 0.873418 | 0.0688963 | CRITERION_MET |
| EZ-BSKG3-TABLE-v1+GP-RESIDUAL-v1 | 9 | 158 | 1 | 0.740506 | 0.892405 | 0.185953 | CRITERION_NOT_MET |
