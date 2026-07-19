# Pre-Registration — Lunar Intermittent Dynamo ML Test

**Author contact:** https://github.com/lemoon01110

This document fixes the hypotheses, feature definitions, cross-validation scheme,
thresholds, and success/failure criteria **in advance**, so that a null result is
as publishable as a positive one and no analytical degrees of freedom are exploited
after seeing outcomes. The pipeline in `src/` implements exactly what is written here.

---

## 1. Hypotheses

- **H1 (Intermittent Dynamo — Nichols et al., *Nat. Geosci.* 2026).** The paper's driver is
  **deep**: melting of Ti-rich cumulates at the **core–mantle boundary** briefly boosts the
  dynamo *and* produces high-Ti surface volcanism, and its reported correlation is
  **compositional and per-sample** (all strong-field Apollo samples had > ~6 wt.% TiO₂).
  The faithful global prediction is therefore **compositional**: high-TiO₂ units — especially
  Imbrian-age high-Ti mare — record stronger crustal magnetism, while low-Ti terrain does not.
  Crustal gravity plays **no role** in the mechanism (the driver is ~1,400 km deep), so a
  "TiO₂ × subsurface gravity" interaction is **not** H1; it is demoted to an *exploratory*
  control expected to add nothing. See `Fallacy-Audit.md` (F1, F2).
- **H2 (Impact-Basin Antipode).** Anomalies arise from transient plasma amplification
  antipodal to large basin-forming impacts; encoded as great-circle distance to the
  nearest major-basin antipode.

H1 and H2 are modelled **together**; H2 features are genuine competitors, not a strawman.

> **Hypothesis-space caveat (F5).** H1 and H2 are **not** the only explanations (a long-lived
> core dynamo, impact-plasma *amplification* of a weak dynamo, and a basal-magma-ocean dynamo
> are also live). This study discriminates the **H1 compositional signature** from the **H2
> antipodal signature**; it does **not** adjudicate the entire field, and a positive result is
> *not* "evidence that the dynamo exists."

## 2. Data → features (see `src/preprocessing.py`)

All layers are reprojected to a **lunar** cylindrical equal-area CRS (R = 1 737 400 m)
before analysis. Features, computed per equal-area pixel:

| Feature | Role | Definition |
|---|---|---|
| `tio2`, `tio2_25/50/100km` | **H1** | surface TiO₂ wt.% and its neighbourhood means (lateral emplacement of high-Ti flows) |
| `dist_to_antipode_km` | **H2** | great-circle distance to nearest major-basin antipode |
| `gravity`, `interaction_25/50/100km` | *exploratory* | mGal and buffered TiO₂ × positive band-passed gravity — **not** part of H1 (F1); retained to test/refute the invented "subsurface density" add-on |
| `dist_to_basin_rim_km` | control | great-circle distance to nearest basin rim |
| `crustal_thickness` | control | GRAIL-derived |
| `abs_latitude` | control | \|absolute latitude\| |
| `nearside` | control | sub-Earth-point proximity — controls the Procellarum/nearside confound (F8) |

Gravity is band-passed (difference-of-Gaussians proxy for a spherical-harmonic band-pass) to
suppress basin-scale mascons and pixel noise before forming the *exploratory* interaction.

## 3. Target

- Binary "anomaly" at surface-field thresholds **5 nT (primary)** and **10 nT**.
- Continuous field magnitude retained for a secondary regression formulation.

## 4. Cross-validation & statistics (see `src/modeling.py`, `src/evaluation.py`)

- **Spatially-blocked** `GroupKFold` over 30°×30° contiguous blocks (no random k-fold).
- Metric: **PR-AUC** (F1 secondary). Raw accuracy is discarded. `scale_pos_weight` from
  the observed class ratio.
- **Nested** CV: inner spatial `GridSearchCV` tunes hyper-parameters; tuning never sees
  an outer test block.
- **Baselines** (all under the same CV): stratified dummy, prior dummy, logistic
  regression, and an XGBoost trained on H2-only features. *Logistic regression uses the same
  features as the full model, so it is a reported sanity co-baseline, **not** a hard gate:
  a comparable LR score corroborates a real (near-linear) signal rather than refuting H1;
  requiring XGB to beat LR would conflate model choice with hypothesis support.*
- **Permutation null:** ≥100 **longitudinal rotations** of the target grid (preserving
  spatial autocorrelation), yielding an empirical p-value with +1 smoothing.
- **Ablation:** full vs. **no-H1-TiO₂** (the H1 test) plus no-interaction / no-exploratory /
  H1-only / H2-only, scored per fold; the H1 effect is tested with a **paired one-sided
  Wilcoxon** test on per-fold PR-AUC (no arbitrary effect-size threshold).
- **SHAP:** per-feature mean |SHAP|; the **H1 TiO₂ family** importance is the mean
  |row-summed SHAP| across `tio2` + the three buffers (accounts for collinearity), compared
  against the H2 antipode feature. The exploratory Ti×gravity family importance is reported
  alongside and is expected to be small.
- **Spatial-statistics rigor (`src/spatial_stats.py`, reported in `Spatial_Diagnostics`):**
  (a) an **empirical variogram** gives a large-scale-structure range (reported for context —
  for a rare clustered binary target it is *not* a valid leakage gate; see Fallacy-Audit.md F10);
  (b) a **block-bootstrap 95% CI** on PR-AUC (resampling whole blocks) replaces pixel-count
  precision with honest uncertainty; (c) a stricter **2-D Fourier phase-randomised null**
  (preserves the full power spectrum) supplements the rotation null; (d) a **block-size
  robustness sweep** (15–60°) is the *direct* leakage probe and the basis of the adequacy gate;
  (e) **Benjamini–Hochberg FDR** across the sensitivity grid prevents cherry-picking.
- **Spatial-adequacy gate (asymmetric; `src/inference.py`).** A would-be *positive* is
  certified `SUPPORTED` only if the support **survives the largest CV block** (else
  `INCONCLUSIVE_SPATIAL_AUTOCORRELATION`), because leakage inflates small-block scores. A run
  that fails the criteria is `NOT_SUPPORTED` — leakage cannot cause a false negative (F9). Low
  power (rare prevalence / few independent regions) is reported as a separate caveat.

## 5. Pre-registered success criterion (H1 supported iff ALL hold)

1. **(i)** Full-model spatial-CV PR-AUC exceeds the permutation null (empirical *p* < 0.05)
   **and** exceeds both dummy baselines **and** the H2-only rival model. (Logistic regression
   is reported for transparency but is not a gate — see §4.)
2. **(ii)** The **H1 TiO₂ (compositional) family** outranks the antipodal-distance feature in
   SHAP importance.
3. **(iii)** Ablating the TiO₂ family significantly reduces PR-AUC (paired one-sided
   Wilcoxon *p* < 0.05, positive mean drop).

## 6. Pre-registered failure criterion

If the antipodal feature dominates SHAP, **or** ablating the TiO₂ family does not
significantly degrade performance, **or** the full model fails to beat the null / dummies /
H2-only rival, then the global data **do not support** the intermittent-dynamo compositional
signature. This is reported as a legitimate negative result. A positive result that appears
**only** in a data-driven subset found *after* seeing outcomes is **not** counted as
confirmation (the age masks below are the *only* pre-specified subsets); such a finding is
reported as hypothesis-generating and requiring independent re-test (guards against the
moving-goalposts / no-true-Scotsman fallacy, F6).

## 7. Sensitivity analyses (reported regardless of outcome)

- **Age mask:** Imbrian-only · Imbrian+Nectarian · no mask.
- **Threshold:** 5 nT · 10 nT (+ regression).
- **Buffer radius:** 25 · 50 · 100 km (multi-scale, reported by SHAP).
- **Gravity band-pass cutoffs:** varied around the registered defaults.

## 8. Validation of the test itself

An isolated synthetic generator with **known** ground truth remains available for
machinery validation (`--data-mode synthetic --scenario ...`):
`h1_lean`/`mixed` data should yield **SUPPORTED**; `h2_lean`/`null` data should yield
**NOT SUPPORTED**. A test that cannot fail on H2-driven data would be worthless.

> **This is a test of the *machinery*, not evidence about the Moon (F7).** The synthetic H1
> signature is *built in* by construction, so a synthetic "SUPPORTED" only shows the pipeline
> can detect a signal that is present and reject one that is not. Scientific conclusions
> require running the pipeline on the **real** PDS/USGS/JAXA grids (the default mode; see
> `README.md`).

## 9. Reproducibility

Fixed master seed (`config.RANDOM_SEED`); every stochastic step derives from it. Dataset
versions/DOIs and input/output hashes are recorded in the source, real-data, and run
manifests. After acquisition and ingestion, one command
(`python main.py --data-mode real --mode full`) reproduces every figure and metric from
the canonical grids. Synthetic runs require the explicit isolated mode.

---

# Post-hoc Amendment — 2026-07-17

**Status:** This amendment was written after the real-data outcome was known. It is **not**
part of the original pre-registration and is not presented as such. Sections 1–9 above are
preserved verbatim so that the original commitments, including their broader H1 framing and
asymmetric decision rule, remain auditable.

## A1. Why an amendment is necessary

The original spatial operationalization overreached the cited physical hypothesis. Nichols
et al. propose a temporal/thermal mechanism in which deep Ti-rich cumulate melting changes
core heat flow and dynamo timing. The analysis above instead compares a present-day optical
surface-TiO₂ map with a map of surviving crustal anomalies. It contains no magnetization ages,
eruption ages, paleointensity chronology, or source-depth composition.

The amended scientific question is therefore:

> Under the declared raster, masks, thresholds, features, and folds, does present-day surface
> TiO₂ spatially co-locate with thresholded lunar crustal magnetic anomalies at demonstrated
> detection power?

Any result applies only to that spatial proxy. The temporal intermittent-dynamo mechanism is
untouched and cannot be confirmed or refuted by this experiment.

## A2. Decision-rule history

For transparency, the project has used three interpretations:

1. An early adequacy-aware run returned `INCONCLUSIVE_SPATIAL_AUTOCORRELATION` because the
   primary block scale was smaller than the fitted spatial range.
2. After observing the failed H1 criteria, the rule was changed post hoc to an asymmetric
   gate: failed criteria bypassed adequacy and returned `NOT_SUPPORTED`, on the argument that
   spatial leakage generally inflates scores.
3. This amendment recognizes that leakage and power are distinct. A negative-looking score
   can remain uninformative when effective sample size is too small or signal-recovery
   sensitivity has not been demonstrated.

The amended rule is:

- **`SUPPORTED`:** the surface-proxy criteria pass, spatial adequacy passes, and the claim is
  limited to spatial co-location.
- **`INCONCLUSIVE_SPATIAL_AUTOCORRELATION`:** the scientific criteria would support the
  surface proxy, but the would-be positive fails spatial independence/adequacy.
- **`INCONCLUSIVE_LOW_POWER`:** the scientific criteria fail and adequate detection power for
  a declared minimum effect is not demonstrated, including when effective-region or benchmark
  sensitivity checks fail.
- **`NOT_SUPPORTED`:** the scientific criteria fail *and* a prospective injection-recovery
  analysis demonstrates adequate power for a declared scientifically relevant minimum effect.

The bundled real-data diagnostics have `approx_effective_sample_size ≈ 1`, a fitted
variogram range ≈3,752 km versus a ≈910 km primary block scale,
`block_exceeds_range = false`, rare clustered positives (~1.4%, about 286 pixels), and an H2
benchmark score of 0.110579. Earlier prose compared H2 with the 13-feature full-model null
mean of 0.110149; that was a mismatched statistic. A dedicated 100-rotation H2-only null has
mean 0.031970, 95th percentile 0.106832, and empirical *p* = 0.039604, so the encoded
observed H2 benchmark is recovered. This rerun uses unique nonidentity longitude shifts
without replacement and retains only candidates with the observed five evaluable folds
(100 accepted from 125 evaluated; 12 rejected for four-fold support). The completed post-hoc
direct H2 injection curve also
recovers sufficiently extreme encoded signals, but has no scientifically justified target
effect, leaves `adequate_power = false`, and reproduces the approximate effective-region count
of 1. The amended primary status is therefore **`INCONCLUSIVE_LOW_POWER`**.

The earlier `NOT_SUPPORTED` label remains part of the audit trail but is superseded as the
scientific interpretation. `H1_Supported = false` remains a statement that the registered
success criteria did not pass; it is not evidence that H1 is false.

## A3. H2 is a benchmark, not exact truth

The six-basin distance feature is motivated by impact-antipode literature but uses rounded,
analyst-declared basin geometry. It is neither an exhaustive impact catalogue nor an assured
map of all true antipodal magnetization. The earlier near-null characterization was caused by
comparing its one-feature statistic with the full-model null. Against the matched H2-only
rotation null, observed PR-AUC 0.110579 exceeds the 0.106832 null 95th percentile
(*p* = 0.039604). The benchmark encoding is empirically recovered. This does not establish
that every real antipodal association is captured, and it does not calibrate sensitivity to
the distinct H1 surface-TiO₂ family.

## A4. Measurement-domain amendment

The LROC WAC TiO₂ product is an optical surface-regolith retrieval developed for mare
composition. The existing joint-valid mask enforces latitude, nodata, numeric range, and
cross-layer availability but is not a mare/highlands validity mask. Quantitative highland
values are treated as out-of-domain for this inference unless independently validated.

The post-hoc mare-only sensitivity uses the external USGS Unified Geologic Map GIS v2 and the
exact case-sensitive `FIRST_Unit` allowlist `Em`, `Im1`, `Im2`, `Imd`. It fails closed if the
field is unavailable, assigns folds before filtering, and uses raw row-local `tio2` plus
controls; buffered TiO₂ is excluded because center-pixel validity does not establish
buffer-wide support.

Within the legacy Imbrian scope, the mask retains 6,232 pixels, 58 positives, and nine nominal
spatial blocks. TiO₂+controls PR-AUC is 0.1252 versus 0.0576 for controls, for mean increment
+0.0676. Per-fold increments are [0.2615, 0.0834, −0.0018, −0.0070, 0.0020]; the
one-sided paired Wilcoxon *p* is 0.21875. This is a positive-mean but statistically
non-significant, highly unstable descriptive result driven by two folds. It is **inconclusive**, not confirmation, and does not change the
primary `INCONCLUSIVE_LOW_POWER` status.

The same target-free fold assignment is inherited by a continuous raw-TiO₂ ridge comparison.
Full-scope controls/controls+raw-Ti R² are 0.2590/0.2703 (increment +0.0113 ± 0.0049), while
mare-scope values are 0.4257/0.4384 (increment +0.0127 ± 0.0126). Their like-for-like
common-fold incremental-R² difference is +0.0014. The mare-only fitted range is ≈3,289 km,
the 30° block/range ratio is ≈0.277, and the effective-region estimate remains 1. These are
descriptive diagnostics, not independent confirmation; no terrain-specific rotation null or
full-decision power calibration is claimed.

The amended clean TiO₂ ablation removes raw/buffered TiO₂ and all TiO₂×gravity interactions.
Although the interactions remain classified as exploratory rather than H1, retaining them in
the no-Ti model would leave derived Ti information and contaminate the ablation.

The 1:5M USGS mask is itself a generalized terrain proxy: mapped superposed units are
excluded, and boundary rasterization is source- and resolution-dependent. Any future
result-bearing terrain analysis must retain those limits and report its source, version,
transformation, hash, excluded and retained pixels, positive count, prevalence, spatial
diagnostics, folds, nulls, and scores.

## A5. Injection-recovery analysis required before `NOT_SUPPORTED`

The construction-aligned synthetic scenarios validate software pathways but do not quantify
power on the real mask. An ideal result-bearing injection analysis would be specified before
execution and run through the real mask, predictor distribution, spatial clustering, complete
tuning, null, and decision procedure. It would include a zero-effect condition and a fixed
effect-strength grid, repeat independent realizations, and report false-positive rate,
recovery probability, uncertainty, and the minimum detectable effect at a declared power
target. Adequacy must be judged against a scientifically justified minimum effect, not merely
an arbitrarily large injectable signal.

The completed post-hoc implementation in `src/power_analysis.py` is narrower than that ideal.
It injects the standardized H2 antipode-proximity encoding into 30 phase-randomized nuisance
fields derived from `log1p`-transformed observed magnetism per coefficient on the real Imbrian
mask at observed 5 nT prevalence. It compares the
fixed repository-plan XGBoost with the same model after H2 ablation. Primary recovery requires a
positive PR-AUC drop and paired one-sided *p* < 0.05 at 30°; spatially robust recovery also
requires a positive drop at 60°. It does **not** resimulate nested tuning, the permutation
criterion, SHAP ranking, or every conjunctive H1 publication criterion.

The standardized latent-field coefficients are 0, 0.5, 1, 1.5, 2, 3, and 4. Spatially robust
recovery is 3/30 at zero (0.1000; Wilson 95% CI 0.0346-0.2562), 18/30 at 0.5
(0.6000), 27/30 at 1.0 (0.9000), 28/30 at 1.5, 29/30 at 2.0, and 30/30 at 3.0
and 4.0. The point-estimate 80% tested-grid minimum detectable coefficient is 1.0, bracketed by 0.5 and
1.0; the first coefficient whose Wilson lower bound itself exceeds 80% is 2.0.

The minimum is extreme in achieved-effect terms. At coefficient 1.0 the median positive-rate
difference between the top and bottom signal quartiles is 0.05565 and the corrected odds ratio
is about 606.8, with effectively no positives in the bottom quartile. These coefficients are
simulation-design choices, not odds ratios or externally justified lunar effects. The fitted
range is 3,751.7 km, compared with ≈909.7 km at 30° and ≈1,819.4 km at 60°; the approximate
effective-region count remains 1.0.

The scientifically relevant `target_effect_strength` therefore remains unset. In the
canonical `Detection_Power` output, `positive_control_recovered = true` means only that some
tested synthetic H2 signals were recovered, while `power_at_target_effect = null` and
`adequate_power = false`. The machine-readable result is
`Paper-and-Pitch/positive_control_power_analysis.json`. It does not justify `NOT_SUPPORTED` or
alter `INCONCLUSIVE_LOW_POWER`, and injecting H2 truth does not make the observed H2 map exact
truth.

## A6. Researcher degrees of freedom

The following constants were fixed in the repository but are not claimed to be uniquely
dictated by physics: 5/10 nT thresholds; 25/50/100 km TiO₂ buffers; a 600→40 km exploratory
gravity band-pass; the six-basin catalogue; 30° primary blocks and 15/20/30/45/60° sweep;
age masks; XGBoost search space; and post-hoc Optuna/fold/gradient analyses. The 300 km
antipode length is a synthetic-generator and H2 injection-score choice, not part of the
observed real-data H2 predictor.

The original binding cell was Imbrian/5 nT. Other cells and post-hoc variants remain
sensitivity or hypothesis-generating paths. A maximum over 60 Optuna trials is uncalibrated
for selection and may not be compared inferentially with a null quantile computed for the
unselected registered statistic.

## A7. Reproducibility and assistance disclosure

Hashes, manifests, propagated random seeds, package versions, and tests establish important
engineering properties. They do not establish independent observations, construct validity,
or statistical power. Repeating arbitrary RNG seeds probes software sensitivity; it does not
sample new lunar regions or reduce spatial uncertainty.

Repository development and the amendments used AI coding/writing assistance. No AI output is
treated as scientific evidence; the repository author remains responsible for the analysis
choices, verification, and claims.

---

# Second Amendment — 2026-07-17 (later same day)

**Status:** Written after the first amendment and after all numbers below were known.
Sections 1–9 and A1–A7 are preserved verbatim above.

## A8. Completed H1 injection curve and a declared target effect

The first amendment left two acknowledged gaps: the injection-recovery calibration existed
only for the H2 geometry control, and no minimum scientifically relevant effect was declared,
which made `NOT_SUPPORTED` unreachable *by abstention* rather than by evidence. Both gaps are
now closed with committed artifacts.

**H1 (TiO₂-driver) injection curve** (`Paper-and-Pitch/h1_tio2_power_analysis.json`;
30 simulations per strength; grid extended downward into the realistic score regime):

| Latent strength | Robust recovery | Wilson 95% CI | Mean with-control PR-AUC | Mean ablation drop |
|---:|---:|---:|---:|---:|
| 0 | 1/30 (0.033) | 0.006–0.167 | 0.135 | −0.0110 |
| 0.025–0.2 | 0–1/30 each | ≤ 0.167 | 0.131–0.145 | −0.0033 to −0.0120 |
| 0.3 | 0/30 | 0.000–0.114 | 0.175 | +0.0127 |
| 0.5 | 6/30 (0.200) | 0.095–0.373 | 0.291 | +0.0772 |
| 1.0 | 12/30 (0.400) | 0.246–0.577 | 0.622 | +0.2795 |

The tested-grid 80% minimum detectable effect is **not reached at any strength**, including
1.0 — a strength at which the injected signal produces a with-control score of 0.62, roughly
seven times the observed full-model score (0.089). The injection design's zero-signal floor
(with-control PR-AUC ≈ 0.135) already exceeds the observed scores (0.089 / 0.111); across the
low-strength grid (0–0.2, injected scores 0.131–0.145) detection is at or below the nominal
false-positive rate. `positive_control_recovered` is `false` for the H1 arm.

**Mechanism.** The ablation drop is *negative* at weak strengths (−0.003 to −0.012),
matching the observed real-data drop (−0.0030): surface-TiO₂ geography is spatially
collinear with the `nearside`/`abs_latitude` controls, so the ablated model recovers most of
a true TiO₂-driven signal through the controls. The registered ablation criterion is
therefore structurally insensitive to H1 in the weak-signal regime — a design property, now
measured, that no seed, fold, or tuning choice repairs.

**Arm-specific false-positive rates.** At zero strength the H2 arm's primary detection rate
is 0.133 (anti-conservative: the smooth antipode kernel can align with clustered noise blobs
that span CV blocks), while the H1 arm's is 0.033 (nominal). The two arms of this design have
*measured, different* operating characteristics; neither may be quoted for the other.

**Low-strength H2 extension** (`Paper-and-Pitch/h2_antipode_low_strength_extension.json`).
Extending the H2 grid downward (strengths 0–0.3, 30 simulations each) maps the low-strength
behavior on that axis too: the zero-signal floor (with-control PR-AUC ≈ 0.135) already
exceeds the observed scores (0.089 / 0.111), and robust detection across those strengths is
only 0.133–0.267 against a 0.100 zero-strength rate. The mean ablation drop is **+0.030 at zero strength** — removing the
antipode feature hurts under pure clustered noise — which is the measured mechanism of that
arm's anti-conservatism (the H1 arm's zero-strength drop is −0.011, the mirror image).
Neither arm has demonstrated power at realistically-sized effects; the design detects only
signals whose injected scores (≈0.5 and above) are several times anything observed. This
also tempers the matched-null H2 recovery: it is a fragile rotation-test result in a score
regime where the injection-based criterion would fire at most ~27% of the time.

**Illustrative anchor (not a physically derived effect size).** The theory predicts no
surface-map effect, so no scientifically justified target strength exists; the committed
artifact leaves `target_effect_strength` null. As an *illustrative anchor* we use
**latent strength 1.0** — the strength at which the *same* pipeline recovers the H2 geometry control
with 90% power. At that anchor, H1 power is **0.400 (Wilson 95% CI 0.246–0.577)** — far below
the 0.80 requirement. For the H1 arm — the hypothesis under test — the classification is
also insensitive to this anchor choice: no tested H1 strength reaches 0.80 power, so any
alternative anchor on the tested grid yields the same `INCONCLUSIVE_LOW_POWER`. `INCONCLUSIVE_LOW_POWER` for the surface-TiO₂ proxy is therefore now a
**demonstrated** classification, not an asserted one, and `NOT_SUPPORTED` remains unreachable
on *evidence* (measured inadequate power), not by abstention. This declaration is post hoc
and is binding for interpretation of the present data; future runs must pass
`--target-effect-strength 1.0`.

**Resolution of the apparent H2/H1 asymmetry.** Recovering the encoded H2 benchmark
(matched-null empirical *p* ≈ 0.0396, fragile as disclosed) while declining to interpret the
H1 null is not an inconsistent evidential standard: the H2 arm has demonstrated sensitivity
at its operating point and the H1 arm has demonstrated *in*sensitivity at every tested
strength. The two claims are now both backed by measurement.

## A9. Wording and citation-integrity fixes

Applied in this release: statistically non-significant post-hoc means (e.g., the mare-domain
*p* = 0.219) are no longer described with promissory language anywhere in the repository, and
a guard test enforces this; the fragility of the H2 matched-null recovery (resolution 1/101,
margin 0.0037 over the null 95th percentile) is disclosed wherever the *p*-value is quoted;
and the full real-data metrics snapshot backing the paper is committed at
`Paper-and-Pitch/metrics.json`. The released version is **v1.0.0** — the current,
power-calibrated interpretation, treated as the project's first complete release, improved
forward from there (1.1.0, 1.2.0, …).
