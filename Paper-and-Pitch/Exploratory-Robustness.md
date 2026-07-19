# Post-hoc Exploratory Diagnostics: Not an Inferential Robustness Test

This work was designed and run after the repository-plan outcome was known. It is a record of
implementation experiments, not evidence that a negative result "survives" alternatives.
The current primary status is **`INCONCLUSIVE_LOW_POWER`**.

Reproduce the descriptive outputs with `python -m src.exploratory`. Raw values are in
[`exploratory_robustness.csv`](exploratory_robustness.csv).

## What was tried

| Post-hoc path | Descriptive score | What can be concluded |
|---|---:|---|
| Optuna TPE, maximum over 60 trials | 0.199 | uncalibrated selected maximum, with no inferential comparison |
| Spherical K-Means folds | 0.033-0.240 across `k` | result is highly fold-partition sensitive |
| Sobel TiO₂/gravity gradients | 0.087 | this one feature construction did not improve the repository-plan point estimate |

The repository-plan full-model rotation-null 95th percentile is 0.226. It was generated for
the fixed, unselected repository-plan statistic. It is **not** a valid significance threshold for the maximum over 60
Optuna trials because the null procedure did not repeat the same 60-trial selection. Thus
0.199 being below 0.226 would not prove absence, and a selected value above 0.226 would not
have established support.

## 1. Optuna

Optuna directly maximizes CV PR-AUC over 60 post-hoc trials. The reported maximum is biased
upward by model selection and lacks a nested outer estimate or selection-calibrated null.
It is best read as a software/tuning diagnostic. It neither strengthens nor weakens the
primary evidence classification.

## 2. Alternate K-Means folds

| Clusters `k` | Full PR-AUC |
|---:|---:|
| 6 | 0.033 |
| 12 | 0.033 |
| 24 | 0.240 |
| 48 | 0.200 |

Calling `k=6` "least leaky" and `k=24` "a leakage artifact" is too strong without a
validated independence model. What the sweep directly establishes is that the estimate moves
more than seven-fold when the map partition changes. Together with the fitted ≈403 km range,
≈910 km primary blocks, and `n_eff ≈ 6.9`, that instability supports an inadequacy diagnosis,
not a robust-negative story.

## 3. Gradient features

Adding Sobel-gradient magnitudes produces PR-AUC 0.087 versus 0.089 in the repository-plan model.
That result describes this particular post-hoc feature construction. It does not show that all
physically plausible boundaries, continuous-field formulations, or spatial scales lack signal.

## Why these paths remain non-confirmatory

- The paths were chosen after seeing the outcome.
- Multiple model/fold/feature searches were not included in a joint null calibration.
- None repairs the mare/highlands validity problem in the TiO₂ predictor.
- None supplies a magnetization-age test of the temporal dynamo mechanism.
- None measures signal-recovery probability through the real spatial support.

## Power and validity follow-up

Full decision-rule power would require repeating the **entire** selection procedure under
zero and known injected effects. That calibration has not been claimed. The completed,
narrower direct-H2-ablation study uses the real mask and spatial structure and reports its
fixed recovery curve and tested-grid floor. It recovers only large encoded effects, has no
physics-justified target effect, and therefore leaves `adequate_power = false`. A separate
USGS mare-domain sensitivity retains 3,928 pixels across **30 mare blocks
(15 contain positives)**, with H1+controls / controls ≈ 0.4766 / 0.4213 (drop ≈ 0.0553). Fold increments
concentrated in two folds and paired *p* = 0.21875. Report binary and continuous estimands
separately. Neither is statistically significant confirmation.

These post-hoc experiments therefore do not overturn the repository-plan criteria failure, but
they also do not convert it into `NOT_SUPPORTED`. The scientifically honest conclusion remains
**`INCONCLUSIVE_LOW_POWER`**.
