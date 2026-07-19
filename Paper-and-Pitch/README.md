# Paper & Pitch Materials

These materials were created around the bundled real-data run. The scientific interpretation
was amended on 2026-07-17 after recognizing that the effective sample size and uncalibrated
target effect do not support a negative verdict. A later matched-null correction establishes
that the encoded H2 benchmark is **not** recovered in v2 (*p* ≈ 0.1724); it does not repair H1 power.

| File | Current status |
|---|---|
| [`Research-Paper.typ`](Research-Paper.typ) | **Authoritative editable source.** Reframed as an underpowered present-day surface-TiO₂ co-location test. |
| [Research-Paper.pdf](Research-Paper.pdf) | Rebuilt from the authoritative `.typ` source and visually verified after the 2026-07-17 amendment. |
| [`metrics.json`](metrics.json) | **Committed snapshot of the full real-data run** backing every number quoted in the paper and README (previously only present locally in the git-ignored `results/`). |
| [`positive_control_power_analysis.json`](positive_control_power_analysis.json) | Completed post-hoc H2 direct-ablation injection curve with replicate-level fold audits. |
| [`impact_antipode_benchmark_calibration.json`](impact_antipode_benchmark_calibration.json) | Matched-statistic fold-matched calibration of the observed H2-only benchmark (86 accepted shifts; *p* ≈ 0.1724; not recovered). |
| [`h1_tio2_power_analysis.json`](h1_tio2_power_analysis.json) | **H1 (TiO₂-driver) injection curve** — the sensitivity calibration for the hypothesis actually under test, with the strength grid extended down into the realistic score regime. |
| [`h2_antipode_low_strength_extension.json`](h2_antipode_low_strength_extension.json) | Downward extension of the H2 curve locating the real benchmark's regime on the strength axis. |
| [Seed-Robustness.md](Seed-Robustness.md) | Demoted random-seed software diagnostic; raw values remain in [`seed_robustness.csv`](seed_robustness.csv). |
| [Exploratory-Robustness.md](Exploratory-Robustness.md) | Post-hoc, uncalibrated implementation diagnostics; not inferential robustness. |
| [Pitch.pptx](Pitch.pptx) · [Pitch.pdf](Pitch.pdf) | Revised 12-slide communication deck synchronized to the amended metrics, scope, and inference status. |

## Current interpretation

The repository-plan success criteria did not pass (`H1_Supported = false`), but the primary CV
blocks are ≈910 km versus a fitted target range of ≈403 km and the approximate effective
sample size is ≈6.9. H2 scores 0.271820. The dedicated H2-only null has mean
0.155877, 95th percentile 0.376621, and empirical *p* = 0.172414, so the encoded observed
H2 benchmark is **not** recovered. The current full-model matched null has mean 0.231862 and
*p* = 0.137931. Both nulls use fold-matched nonidentity shifts (86 accepted from 383
candidates after fold-count matching; pool exhausted below requested 100).
Regenerated v2 power-curve JSONs are committed: structural `adequate_power` is false and
observed H2 is unrecovered. No physics-justified target effect was declared and the
structural effective-region limitation remains. Canonical output therefore has
`positive_control_recovered = false` (observed H2), `power_at_target_effect = null`, and
`adequate_power = false`. The current status remains **`INCONCLUSIVE_LOW_POWER`**.

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
  A post-hoc USGS mare-domain sensitivity leaves 3,928 pixels across **30 mare blocks
  (15 contain positives)**. H1+controls / controls ≈ 0.4766 / 0.4213 (drop ≈ 0.0553); fold increments
  [0.2615, 0.0834, −0.0018, −0.0070, 0.0020] give *p* = 0.21875 — positive in the mean but
  not statistically significant, hence inconclusive rather than confirmatory.
- The binary 10 nT target has about 168 clustered positives (n = 4374; prevalence ≈ 0.0384). PR-AUC, SHAP, ablations, FDR,
  alternate folds, and seed reruns remain descriptive under the adequacy failure.
- The continuous blocked ridge check gives R² 0.2590 for controls and 0.2712 for
  controls+TiO₂ R² 0.3649 / 0.3503 (ΔR² ≈ −0.0146). Report binary and continuous separately. Continuous fold increments are
  descriptive, not independent evidence when effective regions remain limited.
- On the mare proxy, binary scores are as above; continuous estimands remain descriptive. The like-for-like
  full-scope raw-Ti increment is +0.0113, and the common-fold scope difference is +0.0014.
  Mare-only structure remains limited, so this remains inconclusive.
- H2 is an approximate six-basin benchmark, not exact positive-control truth. It is **not**
  recovered against its matched H2-only null (*p* ≈ 0.1724; mean 0.155877; 95th 0.376621);
  the full model's null is used only for the full model.
  This validates sensitivity to the encoding, not an exhaustive impact-magnetization theory.

## Completed H2 injection-recovery result

Standalone Paper-and-Pitch power-curve JSONs are regenerated for the v2 surface product
(prevalence ≈ 0.0384; primary 10 nT). Structural framing from `metrics.json`:
`adequate_power` is false; observed H2 `positive_control_recovered` is false (*p* ≈ 0.1724
against matched null mean 0.155877 / 95th 0.376621). The H2 injection arm does not reach
target power on the tested grid (and collapses at large latent strengths under the v2
mask); the H1 arm first reaches point-estimate 80% power at latent strength **2.0**, but
`adequate_power` stays false without an externally justified target effect. Low-strength
simulation claims are not demonstrated realism. Measured H1 power is **0.467** at strength
1.0 for the illustrative A8 anchor (Wilson 95% CI 0.302–0.639).

This is design-conditional injection sensitivity, not full-decision power. It does not
resimulate tuning, permutation, SHAP, or every conjunctive H1 criterion. With no externally
justified target effect, it cannot support a strong negative verdict. The terrain result
remains a separate descriptive sensitivity (**30 mare blocks; 15 contain positives**).

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
highland terrain. This is an independent, LLM-assisted learning project: repository
development and the reframing used AI coding/writing assistance extensively, because learning
to run — and honestly correct — a rigorous analysis was the project's purpose. Scientific
responsibility remains with the repository author.

The materials in this folder (paper, slides, figures, CSV/JSON) are licensed **CC BY 4.0**
([`../LICENSE-CC-BY-4.0.txt`](../LICENSE-CC-BY-4.0.txt)) — reuse with credit to the author,
and do not present the work as your own. Repository code is MIT ([`../LICENSE`](../LICENSE)).

Underlying LROC/LRO, GRAIL, USGS, and JAXA/Kaguya datasets are not redistributed here and
remain under their institutions' terms. See [`../Data-Sources.md`](../Data-Sources.md) and
[`../References.md`](../References.md).
