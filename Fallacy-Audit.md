# Scientific-Framing and Fallacy Audit

**Reference:** Claire I. O. Nichols, Simon Stephenson, et al., *An intermittent dynamo
linked to high-titanium volcanism on the Moon*, *Nature Geoscience* (2026),
doi:10.1038/s41561-026-01929-y.

This audit distinguishes the physical hypothesis in that paper from the spatial proxy
implemented here. It also records the post-result decision-rule history instead of presenting
a later rule as if it had been part of the original registration.

## What Nichols et al. claim, and what this repository observes

Nichols et al. propose a **temporal/thermal mechanism**: melting of deep Ti-rich cumulates
modulates core heat flow and produces short dynamo episodes, while related high-Ti volcanism
reaches the surface. Their empirical relation is per-sample composition versus recorded
paleointensity.

This repository observes present-day optical surface-regolith TiO₂ and a present-day map of
surviving crustal magnetic anomalies. It has no direct eruption ages, remanence-acquisition
ages, source depths, or ancient field chronology. It therefore tests only whether those two
modern maps co-locate under a particular operationalization. The temporal dynamo mechanism is
**untouched** by either a positive or a negative map result.

## F1 — Invented gravity mechanism

**Problem.** TiO₂ × crustal Bouguer gravity was originally treated as a signature of the
deep dynamo driver, although crustal gravity is not the core–mantle process in Nichols et al.

**Disposition.** Gravity and TiO₂ × gravity remain exploratory features only. They cannot
support or refute the Nichols mechanism. A clean TiO₂ ablation now removes every Ti-bearing
term, including these interactions; leaving them in the ablated model would leak the very
signal the comparison claims to remove.

## F2 — Spatial/temporal category error

**Problem.** A dynamo supplies a global field. Rocks acquire remanence when and where they
cool through relevant temperatures; the mechanism need not predict that modern surface TiO₂
will sit atop surviving magnetic anomalies.

**Disposition.** The project is retitled and reframed as a present-day surface spatial
co-location test. It makes no claim to adjudicate dynamo timing.

## F3 — Ecological inference and depth mismatch

**Problem.** A per-rock relation was projected onto aggregated 1° map pixels. UV/Vis TiO₂
samples the optical regolith, while magnetic sources can be older and kilometers deep.
Weathering, burial, impacts, and later mare emplacement can separate surface composition from
the source that carries remanence.

**Disposition.** TiO₂ is an indirect, present-day proxy. Pixel association cannot confirm or
falsify a sample-level law, and a spatial mismatch is not evidence about temporal causation.

## F4 — Wrong carrier / proxy interpretation

**Problem.** Ti-bearing phases are not themselves the required remanence carrier. Treating
TiO₂ as causal overstates a compositional correlation.

**Disposition.** Documents call TiO₂ a candidate proxy, not the magnetic carrier or direct
dynamo driver. SHAP attribution describes model use of that proxy, not physical causation.

## F5 — False dilemma and benchmark overreach

**Problem.** H1 versus H2 was framed as a head-to-head adjudication, although long-lived and
intermittent dynamos, impact remanence, impact-plasma amplification, and other mechanisms can
coexist. The H2 predictor uses six rounded basin centers/radii and a single distance feature.

**Disposition.** H2 is a literature-motivated **benchmark encoding**, not exact ground truth.
Its recovery against the matched H2-only null validates sensitivity to that encoding; it does
not prove impact-related magnetization. Failure to recover it would not have refuted that
mechanism, and outperforming it would not prove an intermittent dynamo.

## F6 — Construct-validity asymmetry

**Problem.** H1 is represented by a noisy surface retrieval used beyond its secure terrain
domain, whereas H2 is represented by clean analytic geometry. This is not a symmetric contest.

**Disposition.** No claim that the design advantages H1 is retained. The primary run is
explicitly limited by unequal proxy quality. A post-hoc USGS mare-only sensitivity is now
reported, but it remains inconclusive.

## F7 — Terrain-domain failure

**Problem.** The LROC WAC TiO₂ retrieval is calibrated for mare regolith, while important
magnetic provinces occur in highlands. Numeric range checks and latitude coverage do not make
highland values scientifically valid.

**Disposition.** Highlands are treated as out-of-domain for quantitative TiO₂ inference until
validated. The primary joint-valid footprint is not a mare-validity mask. The implemented
USGS GIS v2 mask uses `FIRST_Unit` values `Em`, `Im1`, `Im2`, and `Imd`, raw TiO₂ only, and
folds assigned before filtering. Within the legacy Imbrian scope it leaves 6,232 pixels,
58 positives, and nine blocks. TiO₂+controls scores 0.1252 versus 0.0576 for controls, but
fold increments [0.2615, 0.0834, −0.0018, −0.0070, 0.0020] give one-sided paired
Wilcoxon *p* = 0.21875. The positive mean is not statistically significant, is driven by
two folds, and is inconclusive.

## F8 — Effective sample size and pseudoreplication

**Problem.** The raster contains 20,556 rows but the target is spatially clustered. The fitted
range is ≈3,752 km, the primary block scale is ≈910 km, `block_exceeds_range` is false, and
the shipped approximation gives `n_eff ≈ 1`. Treating pixels or even 72 nominal blocks as
independent precision is pseudoreplication.

**Disposition.** The primary evidence status is `INCONCLUSIVE_LOW_POWER`. Pixel-level scores,
Wilcoxon results, FDR cells, SHAP rankings, and bootstrap intervals are descriptive under this
adequacy failure; none rescues an inferential sample size of approximately one. The completed
H2 injection artifact reproduces the same ≈3,751.7 km range and `n_eff = 1.0`; both its 30°
(≈909.7 km) and 60° (≈1,819.4 km) holdouts remain shorter than the fitted range.

## F9 — Post-result decision-rule change

**Problem.** The first adequacy-aware label was `INCONCLUSIVE_SPATIAL_AUTOCORRELATION`. After
the outcome was observed, the rule was changed so failed H1 criteria bypassed adequacy and
reported `NOT_SUPPORTED`, justified by the claim that leakage can only inflate a score. That
answered leakage bias but not the separate question of detection power.

**Disposition.** The history is reported explicitly. The 2026-07-17 post-hoc amendment uses:

- `SUPPORTED` only for a criteria-positive, spatially adequate surface-proxy result;
- `INCONCLUSIVE_SPATIAL_AUTOCORRELATION` for a would-be positive that fails independence;
- `INCONCLUSIVE_LOW_POWER` for a criteria-negative run whose adequate detection power has not
  been demonstrated; and
- `NOT_SUPPORTED` only when a criteria-negative run has demonstrated adequate power for a
  prospectively declared minimum effect.

This amendment is not described as preregistered and does not rewrite the original text.

## F10 — Leakage and power were conflated

**Problem.** Even if local train/test leakage tends to inflate performance, low power can
still prevent detection. The block sweep is not monotone: full PR-AUC is 0.186, 0.139, 0.089,
0.049, and 0.084 from 15° through 60°. Alternate folds span 0.033–0.240. A clean
"less leakage makes the result more negative" story cannot be inferred from that jagged curve.

**Disposition.** Claims of a stable negative under spatial blocking are removed. The range/block mismatch and
partition sensitivity are evidence of inadequacy, not a basis for a stronger negative.

## F11 — Mismatched H2 null and corrected positive control

**Problem.** The earlier claim that H2 scored 0.111 "against a null of 0.110" compared a
one-feature H2 statistic with the rotation-null distribution of the 13-feature full model.
Those statistics have different flexibility and null behavior; the comparison could not
establish H2 benchmark failure.

**Disposition.** A dedicated H2-only test using 100 unique nonidentity rotations gives
observed PR-AUC 0.110579, null mean 0.031970, null 95th percentile 0.106832, and
+1-smoothed empirical *p* = 0.039604. The encoded observed H2 benchmark is therefore
recovered. The matched full-model null instead has mean 0.112697 and *p* = 0.564356. Each
accepted rotation has the same five evaluable folds as the observed statistic; 12 of 125
candidate shifts were rejected for having only four. The earlier 0.110149 comparison used
the full-model statistic and repeated sampled shifts, so it could not calibrate H2. H2 remains
an approximate six-basin encoding rather than exact ground truth, but the former benchmark-
failure claim is withdrawn.

The completed post-hoc injection analysis independently supplies synthetic H2 truth on the real mask and
predictor maps. Across 30 phase surrogates per coefficient, spatially robust direct-ablation
recovery is 3/30 at zero (0.1000; Wilson 95% CI 0.0346-0.2562), 18/30 at 0.5,
27/30 at 1.0, 28/30 at 1.5, 29/30 at 2.0, and 30/30 at 3.0 and 4.0. The point 80%
tested-grid minimum is coefficient 1.0 (bracket 0.5-1.0); the conservative
lower-confidence-bound minimum is 2.0.

That recovery does not establish adequate scientific power. Coefficient 1.0 already produces
a median top-minus-bottom signal-quartile risk difference of 0.05565 and a corrected odds
ratio of about 606.8—an extreme injected contrast with effectively no bottom-quartile
positives. The coefficient is a latent simulation unit, not a physics-calibrated H2 effect,
and no scientifically justified target effect was declared. `positive_control_recovered` is
therefore true while `power_at_target_effect` remains null and `adequate_power` remains false.
The direct H2 ablation also does not resimulate tuning, permutation, SHAP, or every conjunctive
H1 criterion; it cannot be represented as full-decision power for H1.

## F12 — Dichotomization and clustered rarity

**Problem.** Thresholding |B| at 5 nT discards magnitude and leaves about 286 clustered
positives (~1.4%); 10 nT is rarer. PR-AUC then moves sharply with how the provinces are split.

**Disposition.** Threshold results are not presented as stable planetary measurements.
The implemented blocked ridge comparison preserves `log1p(|B|)`: controls-only R² is
0.2590 and controls+TiO₂ is 0.2712, with fold-mean increment +0.0121 ± 0.0052. All five
chosen-fold increments are positive, but they are descriptive rather than inferential because
the partitions do not create independent regions (`n_eff ≈ 1`) and no row-level p-value is
reported. This small increment cannot rescue the headline or establish the temporal mechanism.

## F13 — Researcher degrees of freedom

**Problem.** Thresholds, 25/50/100 km smoothing, the 600→40 km gravity filter, age masks,
basin catalogue, blocks, and tuning spaces all admit alternate choices. A fixed value in code
is reproducible but not physically inevitable.

**Disposition.** `Analysis-Plan.md` lists the choices, provenance, primary/sensitivity paths,
and post-hoc forks. The 300 km antipode scale is identified as a synthetic-generator and H2
injection-score choice, not a parameter of the observed real-data H2 feature. Sensitivities
are not promoted to confirmation.

## F14 — Optuna selection against an unselected null

**Problem.** The maximum over 60 Optuna trials was compared descriptively with a null
quantile calibrated for the repository-plan, unselected statistic. That comparison is invalid for
inference in either direction because the selection step is missing from the null procedure.

**Disposition.** Optuna is labelled uncalibrated, post-hoc, and non-inferential. Its 0.199
score neither strengthens nor weakens the primary status.

## F15 — Random seeds presented as scientific robustness

**Problem.** Earlier identical scores were partly an implementation error: the configured
seed did not reach every model factory. Even correctly varied RNG seeds do not sample new
lunar regions or quantify partition/model uncertainty.

**Disposition.** The seed is now propagated through XGBoost and rotation sampling. Across ten
arbitrary seeds, full PR-AUC is 0.0916 ± 0.0055, H2 PR-AUC is 0.1096 ± 0.0011, and the clean
Ti-derived ablation drop is +0.0032 ± 0.0068 and changes sign. The table is a software
sensitivity diagnostic labelled `NO_INFERENCE`; fold/region uncertainty and power remain the
relevant issues.

## F16 — Engineering rigor marketed as inference rigor

**Problem.** Tests, SHA-256 hashes, fail-closed ingestion, package pins, XGBoost, and SHAP can
make a pipeline reproducible without making its observations independent or its proxy valid.

**Disposition.** Documentation separates byte-level and software assurances from scientific
adequacy. ML complexity does not increase `n_eff`; logistic regression, XGBoost, SHAP, and a
large test suite cannot substitute for independent regions or calibrated recovery.

## F17 — Registration verifiability and assistance disclosure

**Problem.** The registration is attested only by a mutable, author-controlled Git history.
It has no OSF/Zenodo registration, third-party timestamp, independent custodian, or co-author
attestation.

**Disposition.** That limitation is stated plainly. The amendment is dated and labelled post
hoc. Future result-bearing plans should be externally archived before execution. Repository
development and the 2026-07-17 remediation used AI coding/writing assistance; scientific
responsibility remains with the repository author.

## Net claim

The bundled run does not distinguish the tested surface-TiO₂ spatial proxy from spatial null
structure at demonstrated power. The observed H2 encoding is recovered against its matched
H2-only null, and a direct H2 injection is recovered once the encoded signal is extreme. But
no physics-justified target effect has adequate demonstrated power and the effective-region
estimate remains one. The correct status is **`INCONCLUSIVE_LOW_POWER`**. The study does not
show where a sample-scale relation "stops," does not establish H2 as the unique explanation,
and does not adjudicate the temporal intermittent-dynamo mechanism.
