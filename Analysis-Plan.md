# Analysis Plan v4 — Spatial Co-location and Evidence-Adequacy Remediation

This is the current working plan for the repository. It reframes the implemented model as
a test of **present-day surface-TiO₂ spatial co-location with thresholded crustal magnetic
anomalies**. It does not recast that proxy as a direct test of the temporal intermittent-
dynamo mechanism.

Sections 1–9 of `Pre-Registration.md` preserve the original plan. Its dated appendix records
the post-result amendment. This document describes both the implemented analysis and the
additional work required before a substantive negative verdict is supportable.

## 1. Scientific question and non-question

**Question tested:** within the selected present-day raster footprint and age mask, can a
family of surface-TiO₂ map features predict the chosen magnetic-anomaly target beyond the
pipeline's spatial nulls and a basin-antipode benchmark?

**Question not tested:** did Ti-rich cumulate melting modulate the lunar dynamo through time?
That mechanism concerns the timing of core heat flow, dynamo episodes, lava cooling, and
remanence acquisition. The current rasters contain no magnetization ages and no direct
measure of deep cumulate composition. A dynamo field is global; it need not make modern
surface TiO₂ co-locate with surviving anomalies.

The code's historical `H1` label therefore means **surface-composition spatial proxy**, not
"the Nichols mechanism." H2 is a **benchmark encoding** of antipode proximity, not assured
ground truth and not the only rival explanation.

## 2. What was repaired in the implementation

The repository contains meaningful engineering corrections: lunar rather than terrestrial
CRSs, real great-circle antipode distances, provenance validation, nodata handling, spatial
rotations instead of element-wise target shuffles, nested tuning, and isolation of synthetic
from real-data outputs. These corrections make the computation auditable and reproducible.

They do not, by themselves, establish independent observations, power, proxy validity, or
causal identification. In particular, 20,556 rows are raster pixels, not 20,556 independent
replicates; the bundled diagnostic estimates approximately one effective observation.

## 3. Implemented data and features

Five layers are aligned to the 1° analysis grid (about 30 km horizontal resolution per degree
at the equator): magnetic field, LROC WAC surface TiO₂, GRAIL Bouguer gravity, GRAIL crustal
thickness, and USGS geologic age. Basin centers/radii are analyst-declared configuration.

| Feature family | Implemented role | Interpretive limit |
|---|---|---|
| `tio2`, `tio2_25/50/100km` | candidate spatial-composition proxy | optical surface regolith; not magnetization age or deep composition |
| `dist_to_antipode_km` | literature-motivated H2 benchmark | six approximate basins; not exact H2 truth |
| `gravity`, `interaction_25/50/100km` | exploratory | absent from the Nichols mechanism; no confirmatory role |
| basin rim, crustal thickness, latitude, nearside | controls | reduce selected confounding; do not exhaust geology |
| geologic unit | age-mask proxy | unit age is not remanence-acquisition age |

The primary joint-valid footprint mask checks numeric range and raster coverage, not terrain-domain validity.
Because the cited retrieval is calibrated for mare regolith, quantitative use in highlands is
out-of-domain unless independently validated. A mare-only analysis requires an external mask
chosen without reference to magnetic outcomes.

## 4. Target and loss of information

The primary target is `|B| >= 5 nT`, producing about 286 clustered positives (~1.4%) in the
primary cell. The 10 nT sensitivity is still rarer. Dichotomization discards field magnitude
and makes PR-AUC highly dependent on a handful of provinces and fold boundaries. The
continuous field is retained in preprocessing. `src/transparent_analysis.py` now provides a
simple blocked ridge comparison of controls versus controls+TiO₂ on `log1p(|B|)`, publishes
per-fold R²/MAE and incremental R², and deliberately emits no row-level p-value. It is a
descriptive complement and has not supplied the binding headline inference. On the real
Imbrian scope, controls-only blocked R² is 0.2590 ± 0.1377 and controls+TiO₂ is
0.2712 ± 0.1366; the fold-mean increment is +0.0121 ± 0.0052 (per-fold +0.0157,
+0.0192, +0.0042, +0.0088, +0.0127). Consistency across these five partitions is useful
description, not independent replication when `n_eff ≈ 1`.

PR-AUC is preferable to accuracy for class imbalance, but that choice does not cure spatial
dependence or low effective sample size.

## 5. Implemented validation and what it currently shows

The pipeline uses grouped spatial folds, nested tuning, two spatial null constructions,
family ablation, a block bootstrap, SHAP summaries, and a block-size sweep. The bundled
diagnostics are:

- fitted target variogram range ≈ 3,752 km;
- primary CV block scale ≈ 910 km;
- `block_exceeds_range = false` and `spatially_adequate = false`;
- `approx_effective_sample_size ≈ 1`;
- full-model fold mean 0.089 with fold SD 0.080;
- block-sweep PR-AUC 0.186, 0.139, 0.089, 0.049, and 0.084 from 15° through 60°;
- alternate K-Means-fold scores from 0.033 to 0.240.

The non-monotone sweep and fold-scheme spread show that the measurement is partition-
sensitive. They do not establish a stable negative under spatial blocking. The H2 benchmark
scores 0.110579. The earlier comparison with a 0.110149 null mean was invalid because that
null belonged to the 13-feature full model. Under the dedicated 100-rotation H2-only null
(mean 0.031970; 95th percentile 0.106832), H2 is recovered with empirical *p* = 0.039604.
The rotations are unique nonidentity longitude shifts sampled without replacement and are
accepted only when all five observed folds are evaluable. Of 125 candidates, 12 four-fold
statistics were rejected and the first 100 eligible shifts formed each matched null.
Full-model and H2-only statistics are now compared only with their matched nulls.

Accordingly, the current status is **`INCONCLUSIVE_LOW_POWER`**. `NOT_SUPPORTED` is reserved
for a criteria-failing analysis that has demonstrated adequate power for a declared minimum
effect. `INCONCLUSIVE_SPATIAL_AUTOCORRELATION` is reserved for a would-be positive that fails
the spatial-independence requirement.

## 6. Parameter provenance and forking paths

The original repository registration declared a binding Imbrian/5 nT cell and several
sensitivity paths, but it was not externally time-stamped. The following choices are exposed
because reproducible constants remain researcher degrees of freedom:

| Choice | Value/path | Provenance and status |
|---|---|---|
| Primary threshold | 5 nT; 10 nT sensitivity | analyst-selected in the original repository plan; not justified by an injection-derived detection floor |
| Age mask | Imbrian primary; Imbrian+Nectarian and none | analyst mapping of USGS units; remanence age is unobserved |
| TiO₂ neighborhoods | 25/50/100 km | analyst-selected multiscale features; no claim that any is the unique physical scale |
| Gravity filter | 600→40 km difference of Gaussians | analyst-selected, exploratory, and outside the Nichols mechanism |
| H2 catalogue | six rounded centers/radii | analyst-declared approximation in `src/basins.py`; catalogue uncertainty is not propagated |
| Injected/synthetic H2 scale | 300 km | construction choice used by the synthetic generator and H2 power score; it does not define the observed real-data H2 feature |
| Primary block | 30° with 5 outer folds | original repository choice; fitted range is much larger |
| Block sweep | 15/20/30/45/60° | sensitivity choices in code; exact selection lacks an external physical calibration |
| XGBoost grid | depth 3/4/6, rate 0.05/0.1, 200/400 trees | computationally bounded analyst grid |
| Effective-region adequacy | at least 8 | post-hoc fail-closed heuristic, not externally registered; observed `n_eff ≈ 1` is far below it |
| Detection-power adequacy | 80% at a declared target effect | conventional post-hoc threshold; no scientifically justified target effect was declared |
| Low-prevalence warning | below 2% | post-hoc descriptive warning only; it does not determine inference status |
| Optuna | 60 post-hoc trials | uncalibrated exploratory model selection; not inferential |
| Synthetic scenarios | `h1_lean`, `mixed`, `h2_lean`, `null` | code-path fixtures whose signal construction aligns with the tested features |

CLI switches, sensitivity cells, SHAP feature selection, alternate fold counts, gradient
features, and tuning searches are explicit forking paths. Only the original primary cell was
binding under the original rule; post-hoc paths cannot retroactively become confirmation.

## 7. Post-hoc H2 injection-recovery power analysis (completed direct ablation)

The existing synthetic harness demonstrates that selected code paths can succeed on signals
built to match them. It does **not** measure power on the real mask and spatial structure.

`src/power_analysis.py` implements a pipeline-component-matched direct-ablation analysis. The
completed artifact was generated with:

```bash
python -m src.power_analysis --control h2_antipode --simulations 30 \
  --strengths 0 0.5 1 1.5 2 3 4 --noise-method phase --estimator xgboost \
  --variogram-pairs 60000 \
  --output Paper-and-Pitch/positive_control_power_analysis.json
```

Each strength was applied to 30 independent phase-randomized versions of the `log1p`-
transformed observed continuous magnetic field on the real Imbrian mask, retaining the 5 nT prevalence
and predictor maps. The injected score is the encoded H2 antipode proximity—not a TiO₂
signal. The fixed repository-plan XGBoost is compared with the same model after removing H2.
Primary recovery requires a positive mean PR-AUC drop and paired one-sided *p* < 0.05 under
30° GroupKFold; spatially robust recovery additionally requires a positive drop at 60°.

| Latent coefficient | Robust recoveries | Probability | Wilson 95% CI |
|---:|---:|---:|---:|
| 0 | 3/30 | 0.1000 | 0.0346-0.2562 |
| 0.5 | 18/30 | 0.6000 | 0.4232-0.7541 |
| 1.0 | 27/30 | 0.9000 | 0.7438-0.9654 |
| 1.5 | 28/30 | 0.9333 | 0.7868-0.9815 |
| 2.0 | 29/30 | 0.9667 | 0.8333-0.9941 |
| 3.0, 4.0 | 30/30 each | 1.0000 | 0.8865-1.0000 |

The first tested coefficient attaining 80% point-estimate power is 1.0, bounded by the tested
grid to (0.5, 1.0]; the conservative coefficient whose Wilson lower bound clears 80% is 2.0.
This floor is very large in achieved-risk terms: at coefficient 1.0, the median positive-rate
difference between the top and bottom signal quartiles is 0.05565 and the Haldane-Anscombe
corrected odds ratio is about 606.8, with effectively no positives in the bottom quartile.

This completed curve is narrower than a power analysis of the full publication decision. It
does **not** rerun nested tuning, the permutation criterion, SHAP ranking, or every conjunctive
H1 criterion. It demonstrates recovery of a sufficiently strong encoded H2 feature in a
direct ablation, not power for surface TiO₂ or the Nichols temporal mechanism. Together with
the matched observed-target H2 test (*p* = 0.039604), it establishes recovery of this encoded
benchmark—not the truth of all impact-magnetization claims.

The structural limitation also remains binding. The same artifact reproduces a 3,751.7 km
variogram range and `approx_effective_independent_regions = 1.0`; 30° blocks are ≈909.7 km
(range ratio 0.2425) and 60° blocks are ≈1,819.4 km (ratio 0.4850), so neither reaches the
fitted range. The latent grid is a post-hoc simulation choice, not an odds ratio or a lunar
physics parameter, and no scientifically justified `target_effect_strength` was declared.
Accordingly, `positive_control_recovered = true` only means that some tested injected signal
was recoverable; `power_at_target_effect = null` and `adequate_power = false`. The criteria-
negative real-data result remains `INCONCLUSIVE_LOW_POWER`.

## 8. Terrain-validity analysis (post-hoc descriptive result)

The implemented mask uses the external USGS Unified Geologic Map GIS v2 and the exact
case-sensitive `FIRST_Unit` allowlist `Em`, `Im1`, `Im2`, `Imd`. It fails closed if the unit
field is unavailable, assigns folds on the full scope before filtering, and compares raw
row-local `tio2` plus controls with the same controls. Buffered TiO₂ is excluded because a
center-pixel mask does not establish buffer-wide terrain support.

Within the legacy Imbrian scope, the mask leaves 6,232 pixels, 58 positives, and nine nominal
spatial blocks. The clean TiO₂+controls model has PR-AUC 0.1252 versus 0.0576 for controls,
for mean increment +0.0676. Per-fold increments are [0.2615, 0.0834, −0.0018, −0.0070,
0.0020]; the one-sided paired Wilcoxon *p* is 0.21875. The average is positive but not
statistically significant, is driven by two folds, and does not pass the paired test, so it
is **inconclusive** and cannot confirm the proxy or the dynamo mechanism.

The inherited-fold continuous check uses the same controls and raw row-local TiO₂ in both
scopes. Full-scope controls/controls+raw-Ti R² are 0.2590/0.2703 (increment +0.0113 ±
0.0049); mare-scope values are 0.4257/0.4384 (increment +0.0127 ± 0.0126), for a descriptive
common-fold scope difference of +0.0014. The mare fold increments include one negative value.
Its fitted range is ≈3,289 km, the 30° block/range ratio is ≈0.277, and `n_eff = 1`, so this
continuous check remains structurally inconclusive.

The analysis also follows these reporting rules:

1. label the global TiO₂ analyses out-of-domain/descriptive and run separate binary and
   continuous checks in the mapped mare proxy domain;
2. report excluded/retained pixels and positive targets, rather than silently dropping them;
3. recompute prevalence, inherited-fold scores, variogram, and effective sample size within
   the mare scope; the present post-hoc sensitivity does not claim a terrain-specific rotation
   null or full-decision power calibration;
4. treat highlands as out-of-domain rather than as low-Ti measurements; and
5. label the result mare-domain, not global.

A future confirmatory mare-domain study would also need its entire null and injection-power
procedures defined prospectively and rerun inside that terrain scope.

The mask remains an approximate 1:5M geology proxy: mapped superposed units are excluded and
boundary rasterization is source- and resolution-dependent. A future independently replicated
mare-domain analysis must not reuse this post-hoc result as confirmation.

## 9. Interpretation policy

- A criteria-positive result with inadequate spatial independence is
  `INCONCLUSIVE_SPATIAL_AUTOCORRELATION`.
- A criteria-negative result with failed or unmeasured detection power is
  `INCONCLUSIVE_LOW_POWER`.
- `NOT_SUPPORTED` requires demonstrated adequate power for a prospectively declared minimum
  effect as well as failure of the scientific criteria.
- `SUPPORTED` applies only to the surface co-location proxy and still cannot establish the
  temporal dynamo mechanism.
- The approximate H2 benchmark is recovered against its matched H2-only rotation null. This
  is positive-control evidence for that encoding, not validation of H1, an exhaustive H2
  catalogue, or the temporal Nichols mechanism.

## 10. Reproducibility limits

Source hashes, manifests, package versions, tests, and propagated seeds are valuable
engineering controls. A random-seed sweep probes software/RNG sensitivity, not independent
replication. SHAP describes the fitted model, not physical causation.

The dated appendix in `Pre-Registration.md` records the post-hoc amendments to the original
plan; the amended verdict rule is explicitly not presented as fixed in advance. The analysis
code and parameter file are version-controlled separately from the generated results.
