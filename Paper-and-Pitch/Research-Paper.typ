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
      [Lunar Titanium & Magnetism · v2.0.0 · post-hoc reframing dated 2026-07-17],
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

// Monte-Carlo quantities are displayed at resolution-honest precision (v2 fold-matched
// pool: 86 rotations → 1/87 resolution); exact values live in the committed JSON
// artifacts and Paper-and-Pitch/metrics.json.
#let v-full = "0.395"
#let v-h2 = "0.2718"
#let v-null = "0.2319"
#let v-p = "0.138"
#let v-h2-null = "0.155877"
#let v-h2-p = "0.172"
#let v-drop = "+0.0424"
#let v-prev = "3.8%"

#block(width: 100%)[
  #text(9pt, fill: amber, weight: "bold", tracking: 1.5pt)[POST-HOC REFRAMED · AUTHOR-DECLARED PLAN]
  #v(6pt)
  #text(21pt, fill: ink, weight: "bold")[
    Present-Day Surface TiO#sub[2] and Lunar Crustal Magnetic Anomalies
  ]
  #v(3pt)
  #text(11.5pt, fill: muted, style: "italic")[
    An underpowered test of spatial co-location, not a temporal test of an intermittent dynamo
  ]
  #v(7pt)
  #text(10pt)[*Jack Wu (lemoon01110)* · ORCID #link("https://orcid.org/0009-0004-1710-9018")[0009-0004-1710-9018] · #link("https://github.com/lemoon01110/Lunar-Titanium-Magnetism")[github.com/lemoon01110/Lunar-Titanium-Magnetism] · July 2026]
  #v(3pt)
  #text(9pt, fill: muted, style: "italic")[
    Independent work, openly assisted — an LLM-assisted learning project, not peer-reviewed.
    See §8 for the assistance and responsibility disclosure.
  ]
]

#v(4pt)
#block(fill: tint, inset: 12pt, radius: 6pt, width: 100%)[
  #text(9.5pt, fill: cyan, weight: "bold")[ABSTRACT]
  #v(3pt)
  #set text(9.7pt)
  #set par(justify: true, leading: 0.55em)
  We compare a present-day LROC WAC surface-TiO#sub[2] map (`tio2_quantitative`, ≥2 wt%) with
  the surface-evaluated Tsunakawa/Wieczorek |B| product (primary 10 nT; 25 nT sensitivity)
  using grouped spatial cross-validation. Binding scores use default-config XGBoost; nested
  tuning is diagnostic only. The full model has PR-AUC #v-full against a matched full-model
  spatial-rotation null (#v-null; empirical _p_ = #v-p; 86 fold-matched shifts). The H2
  antipode benchmark (#v-h2) is *not* recovered against its matched null (mean #v-h2-null,
  95th 0.376621; _p_ = #v-h2-p at 1/87 = 86+1 resolution). Ablation drop is #v-drop; Wilcoxon
  _p_ is unavailable for a significance claim. Continuous ridge ΔR² ≈ −0.0146 (report binary
  and continuous separately). Prevalence ≈ #v-prev is the expected no-skill PR-AUC. Fitted
  range ≈ 403 km; $n_"eff"$ ≈ 6.9. Status: #raw("INCONCLUSIVE_LOW_POWER"); `H1_Supported` is
  false; `adequate_power` is false. A post-hoc USGS mare-domain sensitivity uses 30 mare
  blocks (15 with positives; n = 3928). Regenerated H1 power at strength 1.0 is 0.467
  (Wilson 95% CI 0.302–0.639); `adequate_power` remains false.
]

#v(4pt)
#block(fill: tint, inset: 11pt, radius: 6pt, width: 100%, stroke: 0.75pt + cyan)[
  #text(9.5pt, fill: cyan, weight: "bold")[WHAT THIS DOES AND DOES NOT SHOW]
  #v(3pt)
  #set text(9.2pt)
  #set par(justify: true, leading: 0.5em)
  *Mechanism (untouched).* Nichols et al. propose a _temporal_ mechanism — radiogenic melting
  of ilmenite-bearing cumulates at the core–mantle boundary after overturn, increasing core
  heat flux (not simply continued sinking). With no magnetization ages or paleointensities,
  this study cannot confirm or refute it; the mechanism may be entirely correct.
  *Mappability (tested).* A separate, narrower question — whether present-day orbital surface
  TiO#sub[2] is a usable _global map proxy_ for anomaly location at ~30 km — for which this
  pipeline did not detect incremental predictive value.
  *Not a disproof.* The injection test recovers a strong planted TiO#sub[2] signal only
  ~47% of the time at the illustrative strength-1.0 anchor (target 80%) with limited
  effective regions, so failure to detect is not evidence of absence — hence
  #raw("INCONCLUSIVE_LOW_POWER"), not "decoupled". Scale/ecological
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
    literature-motivated benchmark, not exact ground truth. It is *not* recovered against its
    matched H2-only rotation null (_p_ ≈ 0.1724; mean 0.155877; 95th 0.376621).
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

The primary target thresholds surface |B| at 10 nT (25 nT sensitivity). It has about 168 positives among 4,374 quantitative Imbrian pixels
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
0.3503. The fold-mean incremental R² is −0.0146. Report binary and continuous estimands
separately. This continuous result is descriptive, not
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
  [H2-only null mean / 95th], [#v-h2-null / 0.376621], [86 fold-matched rotations (pool exhausted)],
  [TiO#sub[2] ablation drop], [#v-drop], [Wilcoxon _p_ unavailable],
  [Fitted range / block scale], [403 / 910 km], [block exceeds range; n_eff ≈ 6.9],
  [Approximate effective sample size], [≈1], [underpowered],
)

Both rotation nulls use fold-matched nonidentity shifts (86 accepted; pool exhausted below
requested 100) and the same four evaluable
folds as their observed statistics. Of 125 candidate shifts, 12 with only four evaluable
folds were rejected; the first 100 eligible shifts were retained (13 eligible shifts were
evaluated but unused). Accepted rotated prevalence ranges from 0.00769 to 0.02277 where the
shifted target intersects the fixed Imbrian mask. The full and H2 feature sets are
calibrated separately.

The H2 *non-recovery* is *fragile* in resolution: with 86 rotations the empirical-_p_ resolution is
1/87 ≈ 0.0099, and the observed score clears the null 95th percentile by only 0.0037. A
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
row-local TiO#sub[2] only; buffers are excluded. In the Imbrian ∩ quantitative scope,
_n_ = 3,928 across *30 mare blocks (15 contain positives)*. TiO#sub[2]+controls PR-AUC is
≈0.4766 versus controls-only ≈0.4213 (drop ≈0.0553); Wilcoxon _p_ unavailable for significance.

Continuous estimands remain descriptive and are reported separately from the binary scores.
Mare structure remains limited relative to CV blocks. This post-hoc result is *inconclusive*,
not confirmation. The 1:5M mapped-geology mask is also a generalized proxy with source- and
rasterization-dependent boundaries.

== Post-hoc H2 injection-recovery power

Standalone Paper-and-Pitch power-curve JSONs are regenerated for the v2 surface product;
structural `adequate_power` is false. Thirty phase-randomized nuisance fields per coefficient
approximately preserve the spectrum of `log1p`-transformed observed magnetism on the real
Imbrian mask and 10 nT prevalence. The encoded H2 antipode-proximity score is added at
standardized latent coefficients 0, 0.5, 1, 1.5, 2, 3, and 4. The fixed XGBoost is compared
with the same model after H2 ablation. Primary recovery requires a positive mean PR-AUC drop
and paired one-sided _p_ < 0.05 at 30°; spatially robust recovery also requires a positive
drop at 60°.

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
  [0], [5/30 (0.1667)], [0.0734-0.3356],
  [0.5], [11/30 (0.3667)], [0.2187-0.5449],
  [1.0], [9/30 (0.3000)], [0.1666-0.4788],
  [1.5], [1/30 (0.0333)], [0.0059-0.1667],
  [2.0], [0/30 (0.0000)], [0.0000-0.1135],
  [3.0, 4.0], [0/30 each], [0.0000-0.1135],
)

Under the v2 surface product the H2 arm does *not* reach 80% recovery on the tested grid —
robust detection peaks near coefficient 0.5 (~0.37) and collapses at larger latent strengths
(structurally limited; `adequate_power` remains false). Treat the grid as a design-sensitivity
probe, not demonstrated realism. Fitted range ≈ 403 km and $n_"eff"$ ≈ 6.9; both 30°
(~910 km) and 60° (~1,819 km) blocks exceed the fitted range.

A downward grid extension (`h2_antipode_low_strength_extension.json`; strengths 0–0.3, 30
simulations each) maps the low-strength behavior on this axis: across these strengths
robust detection is only 0.100–0.367 against the 0.167 zero-strength rate, with with-control
PR-AUC ≈ 0.126–0.240. Even the H2 arm therefore has no demonstrated power at
realistically-sized effects. The mean ablation drop is +0.023 *at zero strength* (removing
the antipode feature hurts under pure clustered noise), which is the measured mechanism of
that arm's anti-conservative false-positive rate. The matched-null benchmark non-recovery
reported above must be read in this light: a fragile rotation-test result in a score regime
where the injection-based criterion fires well below target power.

The curve is a direct H2-ablation test, not power for the complete publication rule. It does
not resimulate nested tuning, permutation, SHAP, or every conjunctive H1 criterion. The
coefficient is a simulation unit, not a lunar-physics effect size. The artifact also
leaves `target_effect_strength` null and `adequate_power` false.

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
  [0], [0/30 (0.000)], [0.000–0.114], [0.126], [−0.0019],
  [0.05–0.2], [0–1/30 each], [≤ 0.167], [0.122–0.135], [−0.004 to +0.004],
  [0.4], [7/30 (0.233)], [0.118–0.409], [0.183], [+0.0354],
  [0.6], [12/30 (0.400)], [0.246–0.577], [0.269], [+0.0881],
  [1.0], [14/30 (0.467)], [0.302–0.639], [0.437], [+0.2142],
  [2.0], [24/30 (0.800)], [0.627–0.905], [0.697], [+0.4261],
)

The tested-grid 80% point estimate first appears at latent strength *2.0*, but
`adequate_power` remains false because no externally justified target effect anchors the
curve and the design stays structurally limited ($n_"eff"$ ≈ 6.9). Across the low-strength
grid (0–0.2) detection sits at or below the nominal false-positive rate. Mechanistically,
the ablation drop is near zero or *negative* at weak strengths because surface-TiO#sub[2]
geography is spatially collinear with the `nearside`/`abs_latitude` controls: after ablation,
the controls absorb most of a true TiO#sub[2]-driven signal. The registered ablation criterion
is therefore structurally insensitive to H1 in the weak-signal regime, a design property no
seed, fold, or tuning choice repairs.

Zero-strength false-positive rates are *arm-specific*: ≈0.167 for the H2 arm (the smooth
antipode kernel can align with clustered noise blobs spanning CV blocks) versus 0.000
(nominal) for the H1 arm under this draw. Neither arm's operating characteristics may be
quoted for the other. Under v2 the H2 arm *does not* demonstrate high-strength recovery
(curve collapses above ~0.5), while the H1 arm reaches point-estimate 80% only at strength
2.0 and remains at 0.467 at the illustrative strength-1.0 anchor.

*Interpretive anchor (Amendment A8).* No physically derived effect size exists — the theory
predicts no surface-map effect — so we use latent strength 1.0 as an _illustrative anchor_.
The committed artifact leaves `target_effect_strength` null. Measured H1 power at that anchor
is *0.467 (Wilson 95% CI 0.302–0.639)*, far below the 0.80 requirement. `adequate_power` is
therefore false *on measurement*, not by abstention, and `NOT_SUPPORTED` remains unreachable
on evidence.

= Evidence status and rule history

#block(fill: rgb("#f6e7e1"), inset: 10pt, radius: 5pt, width: 100%, stroke: 0.75pt + amber)[
  #text(10.5pt, weight: "bold")[Status: #text(fill: amber)[INCONCLUSIVE_LOW_POWER] — now
  demonstrated, not asserted.]
  The repository-plan success criteria did not pass, so `H1_Supported` is false. The H1
  injection curve measures power 0.467 (Wilson 95% CI 0.302–0.639) at the declared
  strength-1.0 target — a strong planted signal far above the observed score regime — and detection
  at realistic strengths sits at the false-positive rate. Failed H1 criteria are therefore
  quantitatively uninformative about H1's truth. The observed H2 encoding is *not* recovered
  against its matched null.
]

The first adequacy-aware output used `INCONCLUSIVE_SPATIAL_AUTOCORRELATION`. After the result
was observed, an asymmetric rule changed a criteria-failing run to `NOT_SUPPORTED` because
leakage generally inflates scores. That post-hoc rule did not address low power. The dated
amendment now reserves `NOT_SUPPORTED` for a criteria-failing run with demonstrated adequate
injection-recovery power. A would-be positive that fails independence retains
`INCONCLUSIVE_SPATIAL_AUTOCORRELATION`.

= Researcher degrees of freedom

The 10/25 nT thresholds, 25/50/100 km buffers, exploratory 600→40 km gravity filter, six-basin
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
null), measured H1 power is 0.467 — below the 0.80 adequacy requirement, making the
low-power classification a measurement.

*Terrain validity.* The USGS mare-domain comparison above is now available as a post-hoc
descriptive sensitivity. Its small positive count and fold concentration do not provide an
independent confirmation or repair the structural effective-region limitation.

= Reproducibility is not inferential adequacy

Acquisition hashes, fail-closed ingestion, package records, deterministic seeds, and tests
provide engineering rigor. They do not make pixels independent, validate highland TiO#sub[2],
or increase statistical power. The dated amendments are explicitly post hoc and preserve the
original text.

This is an *independent learning project*, not peer-reviewed planetary science. Language
models (LLMs) assisted with code, drafting, documentation, and adversarial review. No AI
output is treated as scientific evidence; responsibility for every analysis choice and claim
remains with the author. The complete decision history, including corrected mistakes, is
preserved in the repository rather than hidden.

= Conclusion

The current global rasters and pipeline do not distinguish the tested present-day surface-
composition proxy from spatial null structure, and the completed H1 injection curve shows the
design has measured, inadequate power (0.467 at the illustrative strength-1.0 anchor; near
the false-positive rate across the low-strength grid) to detect even strong versions of that
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
