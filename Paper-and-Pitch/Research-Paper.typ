// Present-Day Surface TiO2 and Lunar Crustal Magnetic Anomalies
// Typeset with Typst. Build: typst compile Research-Paper.typ
// Numerical results are from the committed snapshot Paper-and-Pitch/metrics.json
// (full real-data run) and the committed power/calibration JSON artifacts.
// Scientific interpretation follows the dated 2026-07-17 post-hoc amendment.

#let ink    = rgb("#16213e")
#let gold   = rgb("#b5791a")
#let cyan   = rgb("#166b86")
#let amber  = rgb("#b0452c")
#let muted  = rgb("#5a6785")
#let tint   = rgb("#eef1f7")
#let tintg  = rgb("#f7efdd")

#set document(
  title: "Present-Day Surface TiO2 and Lunar Crustal Magnetic Anomalies",
  author: "lemoon01110",
)
#set page(
  paper: "us-letter",
  margin: (x: 1.05in, y: 0.95in),
  footer: context [
    #set text(8.5pt, fill: muted)
    #line(length: 100%, stroke: 0.5pt + rgb("#d7dced"))
    #v(2pt)
    #grid(columns: (1fr, auto), align: (left, right),
      [Lunar Titanium & Magnetism · v1.0.0 · post-hoc reframing dated 2026-07-17],
      [#counter(page).display("1 / 1", both: true)],
    )
  ],
)
#set text(font: "Libertinus Serif", size: 10.5pt, fill: ink, lang: "en")
#set par(justify: true, leading: 0.62em, spacing: 0.9em)
#show heading: set text(font: "Noto Sans")
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => block(above: 1.3em, below: 0.7em)[
  #set text(13pt, fill: ink, weight: "bold")
  #it
]
#show heading.where(level: 2): it => block(above: 1.0em, below: 0.5em)[
  #set text(11pt, fill: cyan, weight: "bold")
  #it
]
#show link: set text(fill: cyan)

// Monte-Carlo quantities are displayed at resolution-honest precision (100
// rotations resolve p only to ~0.01); exact values live in the committed JSON
// artifacts and Paper-and-Pitch/metrics.json.
#let v-full = "0.089"
#let v-h2 = "0.1106"
#let v-null = "0.1127"
#let v-p = "0.56"
#let v-h2-null = "0.0320"
#let v-h2-p = "0.040"
#let v-drop = "−0.0030"
#let v-prev = "1.4%"

#block(width: 100%)[
  #text(9pt, fill: amber, weight: "bold", tracking: 1.5pt)[POST-HOC REFRAMED · ORIGINAL REGISTRATION PRESERVED]
  #v(6pt)
  #text(21pt, fill: ink, weight: "bold")[
    Present-Day Surface TiO#sub[2] and Lunar Crustal Magnetic Anomalies
  ]
  #v(3pt)
  #text(11.5pt, fill: muted, style: "italic")[
    An underpowered test of spatial co-location, not a temporal test of an intermittent dynamo
  ]
  #v(7pt)
  #text(10pt)[*lemoon01110* · #link("https://github.com/lemoon01110/Lunar-Titanium-Magnetism")[github.com/lemoon01110/Lunar-Titanium-Magnetism] · July 2026]
  #v(3pt)
  #text(9pt, fill: muted, style: "italic")[
    An independent, LLM-assisted learning project — not peer-reviewed. See §8 for the
    assistance and responsibility disclosure.
  ]
]

#v(4pt)
#block(fill: tint, inset: 12pt, radius: 6pt, width: 100%)[
  #text(9.5pt, fill: cyan, weight: "bold")[ABSTRACT]
  #v(3pt)
  #set text(9.7pt)
  #set par(justify: true, leading: 0.55em)
  We compare a present-day LROC WAC surface-TiO#sub[2] map with a thresholded map of lunar
  crustal magnetic anomalies using grouped spatial cross-validation. The full model has
  PR-AUC #v-full, below an approximate six-basin antipode benchmark (#v-h2) and near a
  matched full-model spatial-rotation null (#v-null; empirical _p_ = #v-p); removing the
  TiO#sub[2] family does not reduce performance (#v-drop). In contrast, H2 fragilely exceeds
  its own dedicated null (mean #v-h2-null, 95th 0.1068; _p_ = #v-h2-p at 1/101 resolution,
  margin 0.0037). The earlier claim that H2 sat at null was a mismatched-null error. The failed H1 criteria are not a calibrated negative:
  the fitted target range is about 3,752 km versus 910 km blocks and the approximate effective
  sample size is 1. The amended status is
  #raw("INCONCLUSIVE_LOW_POWER"). The experiment tests present-day map co-location only; it
  neither confirms nor refutes the temporal/thermal intermittent-dynamo mechanism of Nichols
  et al. (2026). A post-hoc USGS mare-domain sensitivity is positive in the mean but not
statistically significant and fold-unstable. A
  completed direct H2 injection curve recovers only large encoded effects and leaves
  `adequate_power` false. A companion H1 (TiO#sub[2]-driver) injection curve, with the
  strength grid extended into the realistic score regime, calibrates the sensitivity of the
  hypothesis actually under test: at an illustrative strength-1.0 anchor its power is 0.400
  (Wilson 95% CI 0.246–0.577), so the low-power classification is demonstrated, not asserted.
]

#v(4pt)
#block(fill: tint, inset: 11pt, radius: 6pt, width: 100%, stroke: 0.75pt + cyan)[
  #text(9.5pt, fill: cyan, weight: "bold")[WHAT THIS DOES AND DOES NOT SHOW]
  #v(3pt)
  #set text(9.2pt)
  #set par(justify: true, leading: 0.5em)
  *Mechanism (untouched).* Nichols et al. propose a _temporal_ mechanism — sinking Ti-rich
  cumulates driving short dynamo episodes. With no magnetization ages or paleointensities,
  this study cannot confirm or refute it; the mechanism may be entirely correct.
  *Mappability (tested).* A separate, narrower question — whether present-day orbital surface
  TiO#sub[2] is a usable _global map proxy_ for anomaly location at ~30 km — for which this
  pipeline did not detect incremental predictive value.
  *Not a disproof.* The injection test recovers even a strong planted TiO#sub[2] signal only
  ~40% of the time (target 80%) with effective regions ≈1, so failure to detect is not
  evidence of absence — hence #raw("INCONCLUSIVE_LOW_POWER"), not "decoupled". Scale/ecological
  inference, impact demagnetization, and downward-continuation resolution blur could each hide
  a real coupling in these data.
]

= Scientific scope

Nichols et al. (2026) propose that deep Ti-rich cumulate melting altered core heat flow and
produced short dynamo episodes associated with high-Ti volcanism. That is a claim about
*timing*. A global dynamo can magnetize any rock cooling during an active interval.

This repository has no magnetization ages, eruption-age measurements, source-depth
composition, or paleointensity chronology. It compares two modern maps: optical surface
regolith TiO#sub[2] and surviving crustal field strength. The historical code label "H1"
therefore denotes a *candidate spatial proxy inspired by* Nichols, not the Nichols mechanism
itself.

#grid(columns: (1fr, 1fr), gutter: 10pt,
  block(fill: tintg, inset: 10pt, radius: 5pt, width: 100%)[
    #text(9.5pt, fill: gold, weight: "bold")[Candidate surface proxy]
    #v(2pt) #set text(9.5pt)
    Present-day TiO#sub[2] and 25/50/100 km neighborhood features. A map association would be
    descriptive and would not identify dynamo timing.
  ],
  block(fill: tint, inset: 10pt, radius: 5pt, width: 100%)[
    #text(9.5pt, fill: cyan, weight: "bold")[H2 benchmark]
    #v(2pt) #set text(9.5pt)
    Distance to antipodes derived from six approximate basin centers/radii. This is a
    literature-motivated benchmark, not exact ground truth. It is recovered against its
    matched H2-only rotation null.
  ],
)

= Data and measurement limits

Five 1° grids (about 30 km horizontal resolution per degree at the equator) are aligned in a
lunar equal-area projection: Kaguya/Lunar Prospector surface magnetic field, LROC WAC TiO#sub[2],
GRAIL gravity and crustal thickness, and USGS geologic units. Provenance manifests and SHA-256
hashes identify the bytes used.

The TiO#sub[2] retrieval is a present-day optical-regolith product calibrated for mare
composition. The primary footprint checks latitude, nodata, numeric range, and cross-layer
coverage but is not a mare/highlands validity mask. Values in highlands are out-of-domain for
this inference unless independently validated. A post-hoc USGS terrain sensitivity is
reported below. The magnetic source can be older and deeper than the observed surface.

The primary target thresholds |B| at 5 nT. It has about 286 positives among 20,556 pixels
(#v-prev), clustered in a few provinces. Thresholding discards the continuous field magnitude;
pixel count is not independent sample size.

= Implemented analysis

Thirteen features enter logistic-regression and XGBoost baselines. The legacy repository-plan estimate uses
five-fold `GroupKFold` over 30° × 30° block labels, nested inner grouped folds for tuning,
PR-AUC, a longitudinal-rotation null, a phase-randomized null, TiO#sub[2] ablation, SHAP, a
block bootstrap, and a block-size sweep.

These are reproducible computations, but the fold construction does not establish independent
regions when the fitted range exceeds the block scale. SHAP describes the fitted model; it is
not evidence of a physical mechanism.

== Continuous-field descriptive check

A standardized ridge comparison retains `log1p(|B|)` rather than thresholding it. Under the
same five blocked folds, controls-only R² is 0.2590 ± 0.1377 and controls+TiO#sub[2] is
0.2712 ± 0.1366. The fold-mean incremental R² is +0.0121 ± 0.0052, with increments
+0.0157, +0.0192, +0.0042, +0.0088, and +0.0127. This consistency is descriptive, not
independent replication: the chosen folds remain inside the fitted dependence range and no
row-level p-value is reported. The small increment does not establish the surface proxy or
the temporal mechanism.

= Observed metrics

#block(fill: tintg, inset: 11pt, radius: 6pt, width: 100%)[
  #grid(columns: (1fr, 1fr, 1fr), gutter: 8pt, align: center,
    [#text(20pt, fill: gold, weight: "bold")[#v-full]\ #text(8.5pt, fill: muted)[full model PR-AUC]],
    [#text(20pt, fill: cyan, weight: "bold")[#v-null]\ #text(8.5pt, fill: muted)[rotation-null mean]],
    [#text(20pt, fill: amber, weight: "bold")[_p_ = #v-p]\ #text(8.5pt, fill: muted)[descriptive null test]],
  )
]

#table(
  columns: (1fr, auto, 1fr),
  inset: (x: 8pt, y: 4.5pt),
  stroke: none,
  fill: (col, row) => if row == 0 { ink } else if calc.odd(row) { tint } else { white },
  align: (left, center, left),
  table.header(
    [#text(fill: white, weight: "bold", size: 9pt)[Diagnostic]],
    [#text(fill: white, weight: "bold", size: 9pt)[Value]],
    [#text(fill: white, weight: "bold", size: 9pt)[Reading]],
  ),
  [Full XGBoost], [#v-full], [fold SD ≈0.080],
  [H2 benchmark], [#v-h2], [matched _p_ = #v-h2-p],
  [Full-model rotation-null mean], [#v-null], [_p_ = #v-p],
  [H2-only null mean / 95th], [#v-h2-null / 0.1068], [100 fold-matched rotations],
  [TiO#sub[2] ablation drop], [#v-drop], [Wilcoxon _p_ = 0.781],
  [Fitted range / block scale], [3752 / 910 km], [block does not exceed range],
  [Approximate effective sample size], [≈1], [underpowered],
)

Both rotation nulls use the same 100 unique nonidentity shifts and the same five evaluable
folds as their observed statistics. Of 125 candidate shifts, 12 with only four evaluable
folds were rejected; the first 100 eligible shifts were retained (13 eligible shifts were
evaluated but unused). Accepted rotated prevalence ranges from 0.00769 to 0.02277 where the
shifted target intersects the fixed Imbrian mask. The full and H2 feature sets are
calibrated separately.

The H2 recovery is *fragile*: with 100 rotations the empirical-_p_ resolution is
1/101 ≈ 0.0099, and the observed score clears the null 95th percentile by only 0.0037. A
different rotation draw could flip nominal significance, so the result should be read as
"the encoded benchmark is detectable", not as a precise probability.

== Partition sensitivity

#table(
  columns: (auto, auto, auto, auto),
  inset: (x: 7pt, y: 4.5pt),
  stroke: none,
  fill: (col, row) => if row == 0 { ink } else if calc.odd(row) { tint } else { white },
  align: (center, center, center, center),
  table.header(
    ..([Block], [Blocks _n_], [Full PR-AUC], [H2 benchmark]).map(c =>
      text(fill: white, weight: "bold", size: 9pt)[#c])
  ),
  [15°], [236], [0.186], [0.068],
  [20°], [151], [0.139], [0.131],
  [30°], [72], [0.089], [0.111],
  [45°], [32], [0.049], [0.085],
  [60°], [18], [0.084], [0.133],
)

The sequence is non-monotone, and post-hoc K-Means folds range from 0.033 to 0.240. It would
be unjustified to recast this instability as a stable negative under spatial blocking. The direct
finding is that the estimate depends strongly on partition choice while the range/block
diagnostic fails.

== Post-hoc USGS mare-domain sensitivity

An external USGS Unified Geologic Map GIS v2 mask uses exact `FIRST_Unit` symbols `Em`,
`Im1`, `Im2`, and `Imd`. Folds are assigned before filtering, and the comparison uses raw
row-local TiO#sub[2] only; buffers are excluded. In the legacy Imbrian scope, 6,232 pixels,
58 positives, and nine nominal blocks remain. TiO#sub[2]+controls PR-AUC is 0.1252 versus
0.0576 for controls, mean increment +0.0676. The five fold increments are 0.2615, 0.0834,
−0.0018, −0.0070, and 0.0020; one-sided paired Wilcoxon _p_ = 0.21875.

Using the same inherited folds and the same raw-Ti model in both scopes, full-scope
controls/controls+TiO#sub[2] R² are 0.2590/0.2703 (increment +0.0113 ± 0.0049), while
mare-scope values are 0.4257/0.4384 (increment +0.0127 ± 0.0126). The descriptive
common-fold increment difference is only +0.0014, and one mare fold is negative. The
mare-scope range is about 3,289 km versus 910 km blocks, with effective-region estimate 1.

The mean increment is positive but not statistically significant (_p_ = 0.219) and is
concentrated in two folds. This post-hoc result is *inconclusive*, not confirmation. The 1:5M mapped-geology mask is also a
generalized proxy with source- and rasterization-dependent boundaries.

== Post-hoc H2 injection-recovery power

Thirty phase-randomized nuisance fields per coefficient approximately preserve the spectrum
of `log1p`-transformed observed magnetism on the real Imbrian mask and 5 nT prevalence. The encoded H2 antipode-proximity
score is added at standardized latent coefficients 0, 0.5, 1, 1.5, 2, 3, and 4. The fixed
XGBoost is compared with the same model after H2 ablation. Primary recovery requires a
positive mean PR-AUC drop and paired one-sided _p_ < 0.05 at 30°; spatially robust recovery
also requires a positive drop at 60°.

#table(
  columns: (auto, auto, auto),
  inset: (x: 7pt, y: 4.5pt),
  stroke: none,
  fill: (col, row) => if row == 0 { ink } else if calc.odd(row) { tint } else { white },
  align: (center, center, center),
  table.header(
    ..([Latent coefficient], [Robust recovery], [Wilson 95% CI]).map(c =>
      text(fill: white, weight: "bold", size: 9pt)[#c])
  ),
  [0], [3/30 (0.1000)], [0.0346-0.2562],
  [0.5], [18/30 (0.6000)], [0.4232-0.7541],
  [1.0], [27/30 (0.9000)], [0.7438-0.9654],
  [1.5], [28/30 (0.9333)], [0.7868-0.9815],
  [2.0], [29/30 (0.9667)], [0.8333-0.9941],
  [3.0, 4.0], [30/30 each], [0.8865-1.0000],
)

The point 80% tested-grid minimum detectable coefficient is 1.0 (bracket 0.5-1.0); requiring
the Wilson lower bound itself to exceed 80% gives 2.0. This is an extreme floor. At
coefficient 1.0, the median positive-rate difference between the top and bottom signal
quartiles is 0.05565 and the corrected odds ratio is about 606.8, with effectively no
bottom-quartile positives.

A downward grid extension (`h2_antipode_low_strength_extension.json`; strengths 0–0.3, 30
simulations each) maps the low-strength behavior on this axis: the design's zero-signal floor
(with-control PR-AUC ≈ 0.135) already exceeds the observed scores (0.089 / 0.111), and across
these strengths (injected scores 0.135–0.251) robust detection is only 0.133–0.267 against
the 0.100 zero-strength rate. Even the H2 arm therefore has no
demonstrated power at realistically-sized effects — its 90%-power operating point
corresponds to injected scores several times anything observed. The mean ablation drop is
+0.030 *at zero strength* (removing the antipode feature hurts under pure clustered noise),
which is the measured mechanism of that arm's anti-conservative false-positive rate, and
the mirror image of the H1 arm's −0.011. The matched-null benchmark recovery reported above
must be read in this light: a fragile rotation-test result in a score regime where the
injection-based criterion fires at most ~27% of the time.

The curve is a direct H2-ablation test, not power for the complete publication rule. It does
not resimulate nested tuning, permutation, SHAP, or every conjunctive H1 criterion. The
coefficient is a simulation unit, not a lunar-physics effect size. The artifact also
reproduces a 3,751.7 km fitted range and effective-region estimate of 1.0; both 30°
(909.7 km) and 60° (1,819.4 km) blocks remain shorter than the range.

== Completed H1 injection curve and illustrative anchor

The same injection design applied to the *hypothesis actually under test*, with the strength
grid extended down into the realistic score regime
(`Paper-and-Pitch/h1_tio2_power_analysis.json`, 30 simulations per strength):

#table(
  columns: (auto, auto, auto, auto, auto),
  inset: (x: 7pt, y: 4.5pt),
  stroke: none,
  fill: (col, row) => if row == 0 { ink } else if calc.odd(row) { tint } else { white },
  align: (center, center, center, center, center),
  table.header(
    ..([Latent strength], [Robust recovery], [Wilson 95% CI], [With-control PR-AUC],
       [Ablation drop]).map(c => text(fill: white, weight: "bold", size: 9pt)[#c])
  ),
  [0], [1/30 (0.033)], [0.006–0.167], [0.135], [−0.0110],
  [0.025–0.2], [0–1/30 each], [≤ 0.167], [0.131–0.145], [−0.003 to −0.012],
  [0.3], [0/30], [0.000–0.114], [0.175], [+0.0127],
  [0.5], [6/30 (0.200)], [0.095–0.373], [0.291], [+0.0772],
  [1.0], [12/30 (0.400)], [0.246–0.577], [0.622], [+0.2795],
)

The tested-grid 80% minimum detectable effect is *not reached at any strength*. The injection
design's zero-signal floor (with-control PR-AUC ≈ 0.135) already exceeds the observed scores
(0.089 / 0.111); across the low-strength grid (0–0.2, injected scores 0.131–0.145) detection
sits at or below the nominal false-positive rate. Mechanistically, the ablation drop is *negative* at weak strengths —
matching the observed real-data drop of −0.0030 — because surface-TiO#sub[2] geography is
spatially collinear with the `nearside`/`abs_latitude` controls: after ablation, the
controls absorb most of a true TiO#sub[2]-driven signal. The registered ablation criterion
is therefore structurally insensitive to H1 in the weak-signal regime, a design property no
seed, fold, or tuning choice repairs.

Zero-strength false-positive rates are *arm-specific*: 0.133 for the H2 arm (the smooth
antipode kernel can align with clustered noise blobs spanning CV blocks) versus 0.033
(nominal) for the H1 arm. Neither arm's operating characteristics may be quoted for the
other — this also resolves the apparent evidential asymmetry between recovering the H2
benchmark and declining to interpret the H1 null: the H2 arm shows *demonstrated sensitivity*
at its operating point, while the H1 arm *did not reach adequate power at any tested strength*
(recovery 0.20 at 0.5, 0.40 at 1.0 — inadequate, not zero).

*Interpretive anchor (Amendment A8).* No physically derived effect size exists — the theory
predicts no surface-map effect — so we use latent strength 1.0 as an _illustrative anchor_:
the strength at which the same pipeline recovers the H2 geometry control with 90% power. The
committed artifact leaves `target_effect_strength` null. Measured H1 power at that anchor is
*0.400 (Wilson 95% CI 0.246–0.577)*, far below the 0.80 requirement, and the classification
does not depend on it (no tested H1 strength reaches 0.80 power). `adequate_power` is
therefore false *on measurement*, not by abstention, and `NOT_SUPPORTED` remains unreachable
on evidence.

= Evidence status and rule history

#block(fill: rgb("#f6e7e1"), inset: 10pt, radius: 5pt, width: 100%, stroke: 0.75pt + amber)[
  #text(10.5pt, weight: "bold")[Status: #text(fill: amber)[INCONCLUSIVE_LOW_POWER] — now
  demonstrated, not asserted.]
  The repository-plan success criteria did not pass, so `H1_Supported` is false. The H1
  injection curve measures power 0.400 (Wilson 95% CI 0.246–0.577) at the declared
  strength-1.0 target — a signal seven times stronger than anything observed — and detection
  at realistic strengths sits at the false-positive rate. Failed H1 criteria are therefore
  quantitatively uninformative about H1's truth. The observed H2 encoding is recovered
  against its matched null, which demonstrates arm-specific sensitivity, not evidence of
  H1's absence.
]

The first adequacy-aware output used `INCONCLUSIVE_SPATIAL_AUTOCORRELATION`. After the result
was observed, an asymmetric rule changed a criteria-failing run to `NOT_SUPPORTED` because
leakage generally inflates scores. That post-hoc rule did not address low power. The dated
amendment now reserves `NOT_SUPPORTED` for a criteria-failing run with demonstrated adequate
injection-recovery power. A would-be positive that fails independence retains
`INCONCLUSIVE_SPATIAL_AUTOCORRELATION`.

= Researcher degrees of freedom

The 5/10 nT thresholds, 25/50/100 km buffers, exploratory 600→40 km gravity filter, six-basin
catalogue, age masks, 30° blocks and block sweep, and model search spaces are reproducible
analyst choices, not uniquely forced physical constants. The 300 km antipode length is used
by the synthetic generator and H2 injection score, not the observed H2 distance feature.
Optuna's post-hoc maximum over 60 trials is uncalibrated for
selection and has no inferential comparison with the repository-plan unselected null.

The configured seed now reaches XGBoost subsampling and rotation sampling. Across ten
arbitrary seeds, full PR-AUC is 0.0916 ± 0.0055 and the clean Ti-derived ablation changes sign
(mean +0.0032 ± 0.0068). This is a software/RNG diagnostic labelled `NO_INFERENCE`, not
independent lunar uncertainty.

= Follow-up analyses

*Injection-recovery power.* Both arms are now complete: the direct H2 ablation curve and the
H1 (TiO#sub[2]-driver) curve with a downward-extended grid. Neither is full pipeline-decision
power (tuning, permutation, SHAP, and the conjunctive H1 rule were not resimulated), and the
latent coefficient is a simulation unit, not a lunar effect scale. At the illustrative
strength-1.0 anchor (Amendment A8; the committed artifact leaves `target_effect_strength`
null), measured H1 power is 0.400 — below the 0.80 adequacy requirement, making the
low-power classification a measurement.

*Terrain validity.* The USGS mare-domain comparison above is now available as a post-hoc
descriptive sensitivity. Its small positive count and fold concentration do not provide an
independent confirmation or repair the structural effective-region limitation.

= Reproducibility is not inferential adequacy

Acquisition hashes, fail-closed ingestion, package records, deterministic seeds, and tests
provide engineering rigor. They do not make pixels independent, validate highland TiO#sub[2],
or increase statistical power. The dated amendments are explicitly post hoc and preserve the
original text.

This is an *independent learning project*: the author is not a professional planetary
scientist and undertook the work because the Nichols et al. (2026) hypothesis was
fascinating. Large language models were used extensively — for code, analysis design,
documentation, and the adversarial reviews behind the amendments. No AI output is treated
as scientific evidence; responsibility for every analysis choice and claim remains with the
author, and the complete decision history, including corrected mistakes, is preserved in
the repository rather than hidden.

= Conclusion

The current global rasters and pipeline do not distinguish the tested present-day surface-
composition proxy from spatial null structure, and the completed H1 injection curve shows the
design has measured, inadequate power (0.400 at the illustrative strength-1.0 anchor; at the
false-positive rate across the low-strength grid) to detect even strong versions of that
proxy. This is not a
discovery of the scale at which titanium "stops" mattering, not a refutation of impact
magnetization, and not a test of the temporal intermittent-dynamo mechanism. What the study
now contributes is a calibrated statement of what this design *could* and *could not* have
seen — the prerequisite any future co-location test must satisfy before its verdict counts.

= References

#set text(7.8pt)
#set par(leading: 0.4em, spacing: 0.35em, hanging-indent: 1em)
Fortezzo, C. M., Spudis, P. D. & Harrel, S. L. (2020). Digital Unified Global Geologic Map of the Moon at 1:5,000,000 scale. _51st LPSC_, Abstract #2760.

Hood, L. L. & Artemieva, N. A. (2008). Antipodal effects of lunar basin-forming impacts. _Icarus_ 193(2), 485–502. #link("https://doi.org/10.1016/j.icarus.2007.08.023")[doi:10.1016/j.icarus.2007.08.023].

Hood, L. L. et al. (2001). Initial mapping and interpretation of lunar crustal magnetic anomalies using Lunar Prospector magnetometer data. _JGR Planets_ 106(E11), 27,825–27,839. #link("https://doi.org/10.1029/2000JE001366")[doi:10.1029/2000JE001366].

Lin, R. P., Anderson, K. A. & Hood, L. L. (1988). Lunar surface magnetic field concentrations antipodal to young large impact basins. _Icarus_ 74(3), 529–541. #link("https://doi.org/10.1016/0019-1035(88)90119-4")[doi:10.1016/0019-1035(88)90119-4].

Nichols, C. I. O., Wade, J. & Stephenson, S. N. (2026). An intermittent dynamo linked to high-titanium volcanism on the Moon. _Nature Geoscience_ 19, 425–431. #link("https://doi.org/10.1038/s41561-026-01929-y")[doi:10.1038/s41561-026-01929-y].

Sato, H. et al. (2017). Lunar mare TiO#sub[2] abundances from UV/Vis reflectance. _Icarus_ 296, 216–238. #link("https://doi.org/10.1016/j.icarus.2017.06.013")[doi:10.1016/j.icarus.2017.06.013].

Tsunakawa, H. et al. (2015). Surface vector mapping of lunar magnetic anomalies. _JGR Planets_ 120, 1160–1185. #link("https://doi.org/10.1002/2014JE004785")[doi:10.1002/2014JE004785].

Wieczorek, M. A. et al. (2013). The crust of the Moon as seen by GRAIL. _Science_ 339. #link("https://doi.org/10.1126/science.1231530")[doi:10.1126/science.1231530].
