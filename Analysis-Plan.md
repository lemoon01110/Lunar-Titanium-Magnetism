# Analysis Plan v4 — Spatial Co-location and Evidence-Adequacy Remediation

Binding scores use **default-config XGBoost**; nested tuning is **diagnostic only**.

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
causal identification. In particular, 4,374 quantitative Imbrian rows are raster pixels, not 4,374 independent
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

The primary target is surface `|B| >= 10 nT` on Imbrian ∩ `tio2_quantitative`, producing
about 168 clustered positives (~3.8%; n = 4374) in the primary cell. The 25 nT sensitivity
is still rarer. Dichotomization discards field magnitude
and makes PR-AUC highly dependent on a handful of provinces and fold boundaries. The
continuous field is retained in preprocessing. `src/transparent_analysis.py` now provides a
simple blocked ridge comparison of controls versus controls+TiO₂ on `log1p(|B|)`, publishes
per-fold R²/MAE and incremental R², and deliberately emits no row-level p-value. It is a
descriptive complement and has not supplied the binding headline inference. On the real
Imbrian scope, controls-only blocked R² is 0.2590 ± 0.1377 and controls+TiO₂ is
0.3503; the fold-mean increment is **−0.0146** (TiO₂ does not help continuously).
Report binary and continuous estimands separately. Consistency across partitions is useful
description, not independent replication when effective regions remain limited (`n_eff ≈ 6.9`).

PR-AUC is preferable to accuracy for class imbalance, but that choice does not cure spatial
dependence or low effective sample size.

## 5. Implemented validation and what it currently shows

The pipeline uses grouped spatial folds, nested tuning, two spatial null constructions,
family ablation, a block bootstrap, SHAP summaries, and a block-size sweep. The bundled
diagnostics are:

- fitted target variogram range ≈ 403 km;
- primary CV block scale ≈ 910 km;
- `block_exceeds_range = false` and `spatially_adequate = false`;
- `approx_effective_sample_size ≈ 1`;
- full-model fold mean 0.089 with fold SD 0.080;
- block-sweep PR-AUC 0.186, 0.139, 0.089, 0.049, and 0.084 from 15° through 60°;
- alternate K-Means-fold scores from 0.033 to 0.240.

The non-monotone sweep and fold-scheme spread show that the measurement is partition-
sensitive. They do not establish a stable negative under spatial blocking. The H2 benchmark
scores 0.271820. Under the dedicated fold-matched H2-only null (86 accepted shifts; mean
0.155877; 95th percentile 0.376621), H2 is **not** recovered (empirical *p* = 0.172414;
`recovered_above_matched_spatial_null = false`). This is more restrained than v1.
The rotations are unique nonidentity longitude shifts sampled without replacement and are
accepted only when all five observed folds are evaluable. Of 125 candidates, 12 four-fold
statistics were rejected and the first 100 eligible shifts formed each matched null.
Full-model and H2-only statistics are now compared only with their matched nulls.

Accordingly, the current status is **`INCONCLUSIVE_LOW_POWER`**. `NOT_SUPPORTED` is reserved
for a criteria-failing analysis that has demonstrated adequate power for a declared minimum
effect. `INCONCLUSIVE_SPATIAL_AUTOCORRELATION` is reserved for a would-be positive that fails
the spatial-independence requirement.

## 6. Parameter provenance and forking paths

The original repository registration declared a binding Imbrian cell (now 10 nT primary / 25 nT
sensitivity under v2 surface product) and several
sensitivity paths, but it was not externally time-stamped. The following choices are exposed
because reproducible constants remain researcher degrees of freedom:

| Choice | Value/path | Provenance and status |
|---|---|---|
| Primary threshold | 10 nT; 25 nT sensitivity | analyst-selected in the repository plan for the surface Tsunakawa/Wieczorek product; not justified by an injection-derived detection floor |
| Age mask | Imbrian primary; Imbrian+Nectarian and none | analyst mapping of USGS units; remanence age is unobserved |
| TiO₂ neighborhoods | 25/50/100 km | analyst-selected multiscale features; no claim that any is the unique physical scale |
| Gravity filter | 600→40 km difference of Gaussians | analyst-selected, exploratory, and outside the Nichols mechanism |
| H2 catalogue | six rounded centers/radii | analyst-declared approximation in `src/basins.py`; catalogue uncertainty is not propagated |
| Injected/synthetic H2 scale | 300 km | construction choice used by the synthetic generator and H2 power score; it does not define the observed real-data H2 feature |
| Primary block | 30° with 5 outer folds | original repository choice; fitted range is much larger |
| Block sweep | 15/20/30/45/60° | sensitivity choices in code; exact selection lacks an external physical calibration |
| XGBoost grid | depth 3/4/6, rate 0.05/0.1, 200/400 trees | computationally bounded analyst grid |
| Effective-region adequacy | at least 8 | post-hoc fail-closed heuristic, not externally registered; observed `n_eff ≈ 6.9` is still below it |
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
transformed observed continuous magnetic field on the real Imbrian mask, retaining the 10 nT prevalence
and predictor maps. The injected score is the encoded H2 antipode proximity—not a TiO₂
signal. The fixed repository-plan XGBoost is compared with the same model after removing H2.
Primary recovery requires a positive mean PR-AUC drop and paired one-sided *p* < 0.05 under
30° GroupKFold; spatially robust recovery additionally requires a positive drop at 60°.

| Latent coefficient | Robust recoveries | Probability | Wilson 95% CI |
|---:|---:|---:|---:|
| 0 | 5/30 | 0.1667 | 0.0734-0.3356 |
| 0.5 | 11/30 | 0.3667 | 0.2187-0.5449 |
| 1.0 | 9/30 | 0.3000 | 0.1666-0.4788 |
| 1.5 | 1/30 | 0.0333 | 0.0059-0.1667 |
| 2.0 | 0/30 | 0.0000 | 0.0000-0.1135 |
| 3.0, 4.0 | 0/30 each | 0.0000 | 0.0000-0.1135 |

Under the regenerated v2 surface product, **no** tested coefficient attains 80%
point-estimate power; robust detection peaks near 0.5 and collapses at larger latent
strengths. Treat the grid as a design-sensitivity probe, not demonstrated realism.

This completed curve is narrower than a power analysis of the full publication decision. It
does **not** rerun nested tuning, the permutation criterion, SHAP ranking, or every conjunctive
H1 criterion. It does **not** demonstrate high-strength recovery of the encoded H2 feature
under v2. Together with the matched observed-target H2 test (*p* = 0.172414; not recovered),
it does **not** establish recovery of this encoded benchmark—not the truth of all
impact-magnetization claims.

The structural limitation also remains binding. Under v2 the artifact reports fitted range
≈403 km and `approx_effective_independent_regions ≈ 6.9`; 30°/60° blocks ≈910/1,819 km both
exceed the fitted range. The latent grid is a post-hoc simulation choice, not an odds ratio
or a lunar physics parameter, and no scientifically justified `target_effect_strength` was
declared. Accordingly, `positive_control_recovered = false` for the observed H2 benchmark
and for the H2 injection arm on the tested grid; `power_at_target_effect = null` and
`adequate_power = false`. The criteria-negative real-data result remains
`INCONCLUSIVE_LOW_POWER`.

## 8. Terrain-validity analysis (post-hoc descriptive result)

The implemented mask uses the external USGS Unified Geologic Map GIS v2 and the exact
case-sensitive `FIRST_Unit` allowlist `Em`, `Im1`, `Im2`, `Imd`. It fails closed if the unit
field is unavailable, assigns folds on the full scope before filtering, and compares raw
row-local `tio2` plus controls with the same controls. Buffered TiO₂ is excluded because a
center-pixel mask does not establish buffer-wide terrain support.

Within the Imbrian ∩ `tio2_quantitative` scope, the mare-valid mask leaves **3,928** pixels
across **30 mare blocks (15 contain positives)**. The clean TiO₂+controls model has PR-AUC
≈0.4766 versus ≈0.4213 for controls (drop ≈0.0553). Wilcoxon *p* is unavailable for a
significance claim, so the result is **inconclusive** and cannot confirm the proxy or the
dynamo mechanism.

The inherited-fold continuous check uses the same controls and raw row-local TiO₂; report
binary and continuous estimands separately. Continuous increments remain descriptive under
limited effective spatial information.

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
- The approximate H2 benchmark is **not** recovered against its matched H2-only rotation null
  (*p* ≈ 0.1724; null mean 0.155877; 95th 0.376621; 86+1 resolution). This restrains negative
  inference about H1; it is not validation of H1, an exhaustive H2
  catalogue, or the temporal Nichols mechanism.

## 10. Reproducibility limits

Source hashes, manifests, package versions, tests, and propagated seeds are valuable
engineering controls. A random-seed sweep probes software/RNG sensitivity, not independent
replication. SHAP describes the fitted model, not physical causation.

The dated appendix in `Pre-Registration.md` records the post-hoc amendments to the original
plan; the amended verdict rule is explicitly not presented as fixed in advance. The analysis
code and parameter file are version-controlled separately from the generated results.
