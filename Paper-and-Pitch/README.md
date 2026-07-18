# Paper & Pitch Materials

These materials were created around the bundled real-data run. The scientific interpretation
was amended on 2026-07-17 after recognizing that the effective sample size and uncalibrated
target effect do not support a negative verdict. A later matched-null correction establishes
that the encoded H2 benchmark is recovered; it does not repair H1 power.

| File | Current status |
|---|---|
| [`Research-Paper.typ`](Research-Paper.typ) | **Authoritative editable source.** Reframed as an underpowered present-day surface-TiO₂ co-location test. |
| [Research-Paper.pdf](Research-Paper.pdf) | Rebuilt from the authoritative `.typ` source and visually verified after the 2026-07-17 amendment. |
| [`metrics.json`](metrics.json) | **Committed snapshot of the full real-data run** backing every number quoted in the paper and README (previously only present locally in the git-ignored `results/`). |
| [`positive_control_power_analysis.json`](positive_control_power_analysis.json) | Completed post-hoc H2 direct-ablation injection curve with replicate-level fold audits. |
| [`impact_antipode_benchmark_calibration.json`](impact_antipode_benchmark_calibration.json) | Matched-statistic 100-rotation calibration of the observed H2-only benchmark. |
| [`h1_tio2_power_analysis.json`](h1_tio2_power_analysis.json) | **H1 (TiO₂-driver) injection curve** — the sensitivity calibration for the hypothesis actually under test, with the strength grid extended down into the realistic score regime. |
| [`h2_antipode_low_strength_extension.json`](h2_antipode_low_strength_extension.json) | Downward extension of the H2 curve locating the real benchmark's regime on the strength axis. |
| [Seed-Robustness.md](Seed-Robustness.md) | Demoted random-seed software diagnostic; raw values remain in [`seed_robustness.csv`](seed_robustness.csv). |
| [Exploratory-Robustness.md](Exploratory-Robustness.md) | Post-hoc, uncalibrated implementation diagnostics; not inferential robustness. |
| [Pitch.pptx](Pitch.pptx) · [Pitch.pdf](Pitch.pdf) | Revised 11-slide communication deck synchronized to the amended metrics, scope, and inference status. |

## Current interpretation

The repository-plan success criteria did not pass (`H1_Supported = false`), but the primary CV
blocks are ≈910 km versus a fitted target range of ≈3,752 km and the approximate effective
sample size is ≈1. H2 scores 0.110579. The old comparison with a 0.110149 null mean was
invalid because that null belonged to the full model; the dedicated H2-only null has mean
0.031970, 95th percentile 0.106832, and empirical *p* = 0.039604, so the encoded observed
H2 benchmark is recovered. The current full-model matched null has mean 0.112697 and
*p* = 0.564356. Both nulls use 100 unique nonidentity shifts without replacement and retain
only shifts with the observed five evaluable folds (100 accepted from 125 candidates).
A post-hoc H2 injection curve now recovers sufficiently extreme encoded signals, but no
physics-justified target effect was declared and the structural effective-region limitation
remains. Its canonical output therefore has `positive_control_recovered = true`,
`power_at_target_effect = null`, and `adequate_power = false`. The current status remains
**`INCONCLUSIVE_LOW_POWER`**.

The earlier machine status `NOT_SUPPORTED` came from a post-result asymmetric rule that
allowed failed scientific criteria to bypass the adequacy gate. The dated amendment in
[`../Pre-Registration.md`](../Pre-Registration.md) reports that history and reserves
`NOT_SUPPORTED` for a criteria-failing run with demonstrated adequate injection-recovery
power. `INCONCLUSIVE_SPATIAL_AUTOCORRELATION` is retained for a would-be positive that fails
spatial independence.

## Scope

- The implemented analysis compares **present-day optical surface TiO₂** with a map of
  crustal magnetic anomalies. It does not observe the timing of magnetization or dynamo
  episodes and therefore does not test the temporal mechanism in Nichols et al. (2026).
- The TiO₂ retrieval is mare-calibrated; the primary footprint was not a mare-validity mask.
  A post-hoc USGS mare-domain sensitivity leaves 6,232 pixels, 58 positives, and nine blocks.
  Its mean PR-AUC increment is +0.0676, but the fold increments
  [0.2615, 0.0834, −0.0018, −0.0070, 0.0020] give *p* = 0.21875 — positive in the mean but
  not statistically significant, hence inconclusive rather than confirmatory.
- The binary 5 nT target has about 286 clustered positives. PR-AUC, SHAP, ablations, FDR,
  alternate folds, and seed reruns remain descriptive under the adequacy failure.
- The continuous blocked ridge check gives R² 0.2590 for controls and 0.2712 for
  controls+TiO₂ (increment +0.0121 ± 0.0052). Its five positive fold increments are
  descriptive, not independent evidence when `n_eff ≈ 1`.
- On the mare proxy, the same inherited-fold continuous check with raw TiO₂ gives R² 0.4257
  versus 0.4384 (increment +0.0127 ± 0.0126); one fold is negative. The like-for-like
  full-scope raw-Ti increment is +0.0113, and the common-fold scope difference is +0.0014.
  Mare-only range is ≈3,289 km and `n_eff = 1`, so this remains inconclusive.
- H2 is an approximate six-basin benchmark, not exact positive-control truth. It is recovered
  against its matched H2-only null; the full model's null is used only for the full model.
  This validates sensitivity to the encoding, not an exhaustive impact-magnetization theory.

## Completed H2 injection-recovery result

The power artifact injects the encoded H2 antipode-proximity signal into 30 phase-randomized
versions of the `log1p`-transformed observed continuous magnetic field at each latent coefficient
0, 0.5, 1, 1.5, 2, 3, and 4. It retains the real Imbrian mask, observed 5 nT prevalence,
predictors, and groups. Primary recovery is the paired one-sided direct H2 ablation at 30°;
the robust rule also requires a positive ablation drop at 60°.

| Latent coefficient | Spatially robust recovery | Wilson 95% CI |
|---:|---:|---:|
| 0 | 3/30 (0.1000) | 0.0346-0.2562 |
| 0.5 | 18/30 (0.6000) | 0.4232-0.7541 |
| 1.0 | 27/30 (0.9000) | 0.7438-0.9654 |
| 1.5 | 28/30 (0.9333) | 0.7868-0.9815 |
| 2.0 | 29/30 (0.9667) | 0.8333-0.9941 |
| 3.0, 4.0 | 30/30 (1.0000) each | 0.8865-1.0000 |

The point 80% tested-grid minimum detectable coefficient is 1.0 (bracket 0.5-1.0); the first
coefficient whose Wilson lower bound clears 80% is 2.0. At 1.0 the median top-minus-bottom
signal-quartile risk difference is 0.05565 and the corrected odds ratio is about 606.8, an
extreme injected contrast. The artifact also reproduces a 3,751.7 km fitted range and
`n_eff = 1.0`; 30° (≈909.7 km) and 60° (≈1,819.4 km) blocks remain below the range.

This is direct H2-ablation power, not full-decision power. It does not resimulate tuning,
permutation, SHAP, or every conjunctive H1 criterion, and its latent coefficient is not a
lunar-physics effect size. With no externally justified target effect, it cannot support a
strong negative verdict. The terrain result remains a separate descriptive sensitivity.

## Rebuilding the manuscript

Typst is optional and is not a project dependency. To verify the corrected source without
overwriting the committed PDF, compile to a temporary path; to update the binary deliberately,
run:

```bash
typst compile Research-Paper.typ Research-Paper.pdf
```

The pipeline also emits a separate machine-generated report at
`results/Research_Paper.pdf`. Treat a freshly generated runtime artifact as a record of the
code's metrics/status, and the dated amendment as the authoritative explanation of the rule
change.

## Reproducibility versus inference

Input hashes, fail-closed ingestion, fixed package versions, and seeded reruns are
engineering safeguards. They do not make spatial pixels independent or validate a proxy in
highland terrain. The repository registration was attested only through author-controlled Git
history, without an independent OSF/Zenodo timestamp. This is an independent, LLM-assisted
learning project: repository development and the 2026-07-17 framing amendment used AI
coding/writing assistance extensively, because learning to run — and honestly correct — a
rigorous analysis was the project's purpose. Scientific responsibility remains with the
repository author.

Underlying LROC/LRO, GRAIL, USGS, and JAXA/Kaguya datasets are not redistributed here and
remain under their institutions' terms. See [`../Data-Sources.md`](../Data-Sources.md) and
[`../References.md`](../References.md).
