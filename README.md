# Present-Day Surface TiO₂ and Lunar Crustal Magnetic Anomalies

> [!IMPORTANT]
> **DISCLAIMER: AI-ASSISTED LEARNING PROJECT**
> This repository is an educational project created for learning and experience. The code, documentation, and scientific analysis pipelines were developed with the extensive assistance of Large Language Models (AI). While rigorous testing (including falsifiability guards and spatial validation) has been implemented to ensure mathematical integrity, the text and framing should be read with the understanding that AI tools were used to aid in drafting and architecting this repository.

*An underpowered test of spatial co-location, not a temporal test of the intermittent-dynamo mechanism*


This repository asks a deliberately narrow observational question: **does present-day,
remotely sensed surface TiO₂ spatially co-locate with a thresholded map of lunar crustal
magnetic anomalies under the pipeline's chosen masks, features, and spatial folds?** The
answer from the bundled run is **`INCONCLUSIVE_LOW_POWER`**. The exact metrics snapshot
backing every number quoted below is committed at
[`Paper-and-Pitch/metrics.json`](Paper-and-Pitch/metrics.json).

This is not a planetary-scale test of the temporal/thermal mechanism proposed by Nichols
et al. (2026). A dynamo is a global field source, and that mechanism predicts *when* rocks
were magnetized during short dynamo episodes. This repository has neither magnetization
ages nor source-depth compositions. Its TiO₂ input is a present-day optical surface product,
so a failure to find map co-location cannot refute, confirm, or locate the intermittent
dynamo.

## What this does and doesn't show

> [!NOTE]
> **Two different questions — keep them apart.**
>
> **The mechanism (untouched).** Nichols et al. (2026) propose a *temporal* physics story:
> sinking Ti-rich cumulates perturb the core and drive short dynamo episodes. This project
> has no magnetization ages or paleointensities, so it **cannot test, confirm, or refute
> that mechanism.** It could be entirely correct.
>
> **The mappability (what we actually tested).** A separate, narrower question: can
> present-day *orbital surface* TiO₂ act as a **global map proxy** — predicting *where*
> crustal anomalies sit — at ~30 km (1°) resolution? On the best current global datasets,
> this pipeline **did not detect incremental predictive value**.
>
> **What that failure does *not* establish.** It is **not** a proof that the two are
> physically decoupled, nor that surface TiO₂ can never serve as a proxy. The pipeline's own
> injection test recovers even a *strong* planted TiO₂ signal only ~40% of the time (target
> 80%), and the effective number of independent spatial regions is ≈1. With that little
> power, **failure to detect is not evidence of absence** — which is exactly why the status
> is `INCONCLUSIVE_LOW_POWER`, not "disproven".
>
> **Why a genuine coupling could still be invisible here** (candidate explanations for the
> null — this data cannot adjudicate between them):
> - **Scale / ecological inference** — a micro-scale, grain-level signature can wash out when
>   aggregated into 30 km pixels.
> - **Impact demagnetization** — eons of impacts can shock-erase the magnetic record while
>   leaving the titanium in place.
> - **Downward-continuation / resolution blur** — the surface magnetic field is a
>   reconstructed product near its ~30 km useful-resolution floor, which can smear alignment
>   with sharp compositional boundaries.
>
> **One honest line:** *this does not falsify the Nichols dynamo; it shows that present-day
> orbital surface titanium did not provide a usable global map-proxy in current data, and it
> quantifies that current global data lack the power to settle the question either way.*

The science path uses provenance-validated institutional products. Synthetic data remain
available as an isolated software-validation harness and can never silently satisfy a
real-data run.

## About this project — a learning disclosure

This is an **independent learning project**, not professional or peer-reviewed science. I
built it because the intermittent-dynamo idea in Nichols et al. (2026) struck me as
incredibly interesting, and I wanted to learn — hands-on — what honestly testing such an
idea requires: pre-registration, spatial statistics, power calibration, and the discipline
of correcting one's own overclaims in public.

**Large language models (LLMs) were used extensively throughout** — for code, analysis
design, documentation, and the adversarial reviews that produced the dated amendments in
[`Pre-Registration.md`](Pre-Registration.md). No AI output is treated as scientific
evidence; every scientific choice and claim remains the author's responsibility. The full
decision history — including the mistakes and their corrections — is deliberately preserved
rather than hidden, because learning to correct oneself transparently was the point.
Criticism and corrections are welcome via issues.

## Reproduce the real-data analysis

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # runtime deps + test tools (pytest); use requirements.txt for runtime only

python -m src.acquire all
python -m src.ingest all
python -m src.ingest validate
python main.py --data-mode real --mode full
pytest -q
```

`python -m src.acquire all` downloads about 2 GB including safely extracted archives.
It is resumable, enforces code-pinned SHA-256 values for all 23 institutional payloads,
verifies every LROC IMG against its PDS4 label, and binds all 327 extracted GRAIL/USGS
members byte-for-byte to their pinned ZIPs in `data/raw/sources/source_manifest.json`.
Ingestion re-hashes every source and extracted member, converts all five layers in a
staging directory, applies lunar schema/range/coverage checks, and only then promotes the
canonical outputs and `data/raw/real_data_manifest.json`.

These checks establish **engineering reproducibility and input identity**. They do not
establish statistical power, independence, construct validity, or causal identification.

Outputs are written to:

- `results/metrics.json` — scores, diagnostics, run mode, input hashes, and package versions
- `results/Research_Paper.pdf` — machine-generated report
- `results/figures/*.png` — model-description figures
- `data/processed/modeling_dataset.csv` — aligned equal-area modeling table

See `Data-Sources.md` for products, transformations, units, coverage, and scientific
validity limits.

## Current real-data evidence

The repository-plan H1 criteria all failed on the canonical run, but the experiment also fails
its adequacy checks:

| Diagnostic | Result |
|---|---:|
| Full spatial-CV PR-AUC | 0.0890 ± 0.080 across folds |
| H2 benchmark PR-AUC | 0.1106 |
| Full-model fold-matched rotation-null mean / empirical *p* | 0.1127 / 0.5644 |
| Matched H2-only null mean / 95th / empirical *p* | 0.0320 / 0.1068 / 0.0396 |
| Continuous controls / controls+TiO₂ blocked R² | 0.2590 / 0.2712 |
| Descriptive continuous incremental R² | +0.0121 ± 0.0052 |
| Clean TiO₂-derived ablation drop / Wilcoxon *p* | −0.0030 / 0.7813 |
| Mare-only continuous controls / controls+raw-TiO₂ R² | 0.4257 / 0.4384 |
| Mare-only continuous raw-TiO₂ increment | +0.0127 ± 0.0126 |
| Fitted target variogram range | ≈ 3,752 km |
| Primary CV block scale | ≈ 910 km |
| `block_exceeds_range` | `false` |
| Approximate effective sample size | ≈ 1 |
| **H1 injection power at declared target (strength 1.0)** | **0.400 (Wilson 95% CI 0.246–0.577)** |

`H1_Supported` is `false`. The appropriate evidence classification is
**`INCONCLUSIVE_LOW_POWER`**, not evidence of absence. There are about 286 positive pixels
(~1.4%), but they are clustered into very few magnetic provinces; pixel count is therefore
not an independent sample size. The bundled guard already records
`negative_result_may_be_underpowered = true`; the amendment makes that limitation binding
rather than a footnote to a negative verdict. The block sweep is also non-monotone (0.186,
0.139, 0.089,
0.049, 0.084 at 15°, 20°, 30°, 45°, and 60°), so it does not support a clean
"less leakage strengthens the negative" narrative.

The H2 distance feature is a **literature-motivated benchmark**, not exact ground truth. It
uses six approximate basin centers/radii and scores 0.110579. Earlier prose incorrectly
compared that one-feature H2 statistic with the full-model rotation-null mean of 0.110149.
That null was mismatched. A dedicated H2-only null using 100 unique nonidentity rotations has
mean 0.031970, 95th percentile 0.106832, and +1-smoothed empirical *p* = 0.039604: the
observed encoded H2 benchmark **is recovered**. The full model remains compared only with its
own matched null (mean 0.112697, *p* = 0.564356). Both nulls retain only rotations with the
observed five evaluable folds: 125 unique candidates were evaluated, 12 four-fold candidates
were rejected, and the first 100 eligible shifts were used. Rotated prevalence ranges from
0.00769 to 0.02277 where the shifted target intersects the fixed Imbrian mask. This correction
supports sensitivity to the encoded H2 feature, but does not make the six-basin encoding
exact truth or establish power for H1.

The recovery is also **fragile**: with 100 rotations the empirical-*p* resolution is
1/101 ≈ 0.0099, and the observed score (0.110579) clears the null 95th percentile
(0.106832) by only 0.0037 — a different rotation draw could flip nominal significance.
Read it as "the encoded benchmark is detectable", not as a precise probability.

### Which "chance" level applies where

Four different reference levels now appear in this repository. They are not
interchangeable; quoting a score against the wrong one is the mismatched-null error
corrected above.

| Reference level | Value | Statistic it calibrates |
|---|---:|---|
| Positive-prevalence floor | 0.0139 | absolute lower bound for any PR-AUC here |
| Matched H2-only rotation null (mean) | 0.0320 | the one-feature H2 benchmark (obs. 0.1106) |
| Full-model rotation null (mean) | 0.1127 | the 13-feature full model (obs. 0.0890) |
| Injection zero-strength mean | ≈ 0.135 | with-control PR-AUC inside the injection design |

Note the full model scores *below* its own null mean, and the celebrated H2 benchmark
(0.1106) sits below the injection design's zero-signal level (0.135) — different
constructions, different chance lines.

A completed post-hoc injection study separately calibrates the *direct H2 ablation* under the
real mask, prevalence, predictors, and 30°/60° folds. It does not calibrate tuning, the
permutation criterion, SHAP ranking, or every conjunctive H1 decision criterion, so neither
H2 result can turn H1's null-looking score into a substantive negative conclusion.

### Old rule and post-hoc amendment

The pre-amendment metrics snapshot and earlier prose used the machine label **`NOT_SUPPORTED`** under a
post-result asymmetric rule: failed H1 criteria bypassed the spatial-adequacy gate on the
argument that leakage inflates scores. That rule addressed only one possible bias and did
not address low power; the earlier claimed benchmark failure was also based on the mismatched
null corrected above. The dated amendment appended to
`Pre-Registration.md` now reserves `NOT_SUPPORTED` for a criteria-failing run with
demonstrated adequate detection power. A would-be positive that fails spatial independence
remains `INCONCLUSIVE_SPATIAL_AUTOCORRELATION`; the present criteria-failing but
underpowered run is `INCONCLUSIVE_LOW_POWER`.

This change is explicitly **post hoc**. It does not rewrite the original commitments and is
reported so readers can see the full decision-rule history.

Repository development and the amendments used AI coding/writing assistance; the repository
author is responsible for all scientific choices and claims.

## Measurement and scope limits

- Nichols et al. report a time/composition relation in returned rock samples. This analysis
  compares aggregated map pixels and therefore tests a new spatial proxy, not that mechanism.
- The LROC WAC TiO₂ algorithm is a mare-regolith retrieval. The primary legacy run used the
  joint-valid footprint, not a mare-validity mask. A post-hoc USGS mare-domain sensitivity is
  reported below.
- Surface UV/Vis TiO₂ samples the optical regolith, whereas magnetic anomalies can arise from
  older and deeper sources. Present-day spatial mismatch is not temporal evidence.
- Thresholding |B| at 5 nT discards field magnitude and yields a rare, clustered target.
  `src/transparent_analysis.py` implements a descriptive blocked ridge comparison on
  `log1p(|B|)`: controls-only blocked R² is 0.2590 and controls+TiO₂ is 0.2712, for
  fold-mean incremental R² +0.0121 ± 0.0052. The increment is consistently positive across
  the five chosen folds, but remains descriptive because those folds do not establish
  independent regions; the analysis emits no row-level p-value and does not replace the
  binding headline.
- H2 geometry is an approximate operationalization and cannot serve as assured exact truth.

## Adequacy follow-up

The two required follow-ups now have different statuses:

1. **H2 injection-recovery power analysis — direct-ablation result available.** Thirty
   phase-randomized nuisance fields per strength approximately preserve the two-dimensional
   spectrum of `log1p`-transformed observed magnetism;
   each receives the encoded antipode-proximity signal at standardized latent coefficients
   0, 0.5, 1, 1.5, 2, 3, and 4. Recovery requires the repository-plan paired one-sided ablation at
   30° plus a positive ablation drop at 60°. Spatially robust recovery is 3/30 at zero
   (0.1000; Wilson 95% CI 0.0346-0.2562), 18/30 at 0.5 (0.6000), 27/30 at 1.0
   (0.9000), 28/30 at 1.5, 29/30 at 2.0, and 30/30 at 3.0 and 4.0. The point-estimate
   80% tested-grid minimum detectable coefficient is 1.0 (bracket 0.5–1.0); requiring the
   Wilson lower bound itself to exceed
   80% gives 2.0. At coefficient 1.0 the median top-minus-bottom signal-quartile risk
   difference is 0.05565 and the corrected odds ratio is about 606.8—an extreme effect with
   effectively no bottom-quartile positives. See
   [`Paper-and-Pitch/positive_control_power_analysis.json`](Paper-and-Pitch/positive_control_power_analysis.json).
   A downward grid extension
   ([`h2_antipode_low_strength_extension.json`](Paper-and-Pitch/h2_antipode_low_strength_extension.json))
   maps the low-strength behavior: the design's zero-signal floor (with-control PR-AUC ≈ 0.135)
   already exceeds the observed scores (0.089 / 0.111), and across strengths 0.025–0.3 (injected
   scores 0.135–0.251) robust detection is only 0.133–0.267 against a
   0.100 zero-strength rate — so even the H2 arm has no demonstrated power at
   realistically-sized effects, and its mean ablation drop is **+0.030 at zero strength**
   (removing the antipode feature hurts under pure clustered noise), the measured mechanism
   of that arm's 0.133 anti-conservative false-positive rate. This also tempers the
   matched-null recovery above: it is a fragile rotation-test result in a score regime where
   the injection-based criterion fires at most ~27% of the time.
2. **H1 (TiO₂-driver) injection curve — the previously missing arm, now complete.** The same
   injection design applied to the hypothesis actually under test, with the strength grid
   extended down into the realistic score regime
   ([`Paper-and-Pitch/h1_tio2_power_analysis.json`](Paper-and-Pitch/h1_tio2_power_analysis.json)).
   Robust recovery is 1/30 at strength 0, 0–1/30 across 0.025–0.2 (injected scores 0.131–0.145,
   already above the observed 0.089), 0/30 at 0.3, 6/30 (0.200) at 0.5, and only
   12/30 (**0.400**, Wilson 95% CI 0.246–0.577) at 1.0 — a strength whose injected
   with-control score (0.62) is roughly seven times the observed. The tested-grid 80% minimum
   detectable effect is **not reached at any strength**. Mechanistically, the ablation drop is
   *negative* at weak strengths (−0.003 to −0.012, matching the observed −0.0030) because
   TiO₂ geography is collinear with the `nearside`/`abs_latitude` controls, which absorb the
   signal after ablation. Zero-strength false-positive rates are arm-specific: 0.133 for the
   H2 arm (the smooth antipode kernel can align with clustered noise) versus 0.033 (nominal)
   for the H1 arm — so neither arm's operating characteristics may be quoted for the other.
3. **Externally sourced mare-terrain mask — descriptive result available.** A post-hoc mask
   derived from USGS Unified Geologic Map GIS v2 `FIRST_Unit` symbols `Em`, `Im1`, `Im2`, and
   `Imd` leaves 6,232 pixels, 58 positives, and nine nominal spatial blocks in the legacy
   Imbrian scope. Using raw row-local TiO₂ only (buffers excluded), TiO₂+controls scores
   0.1252 versus 0.0576 for controls, a mean increment of +0.0676. Fold increments are
   [0.2615, 0.0834, −0.0018, −0.0070, 0.0020] and the paired one-sided Wilcoxon
   *p* is 0.21875. The mean increment is positive but **not statistically significant**
   (*p* = 0.219); given its concentration in two folds and the small positive count, the
   result is **inconclusive** — it is not confirmation and is not presented as evidence. The
   same inherited folds give mare-only continuous R² 0.4257 for controls and 0.4384 after
   adding raw TiO₂, an increment of +0.0127 ± 0.0126 with one negative fold. The like-for-like
   full-scope raw-Ti increment is +0.0113, so the descriptive common-fold scope difference is
   only +0.0014. Mare-only range is ≈3,289 km versus ≈910 km blocks and `n_eff = 1`, so the
   continuous result is also structurally inconclusive.

With the H1 curve complete, we anchor interpretation to an **illustrative** effect
(Amendment A8 in [`Pre-Registration.md`](Pre-Registration.md)): latent strength 1.0 — the
strength at which the same pipeline recovers the H2 geometry control with 90% power. It is
**not** a physically derived effect size (the theory predicts none for a surface map), and
the committed artifact leaves `target_effect_strength` null. Measured H1 power at that anchor
is **0.400 (Wilson 95% CI 0.246–0.577)**, far below the 0.80 requirement — and the
classification is insensitive to the anchor choice, since no tested H1 strength reaches 0.80
power.
`INCONCLUSIVE_LOW_POWER` is therefore **demonstrated rather than asserted**: the registered
criteria could not reliably fire even for a TiO₂-driven signal seven times stronger than
anything observed. `positive_control_recovered` is true only for the H2 arm (false for the
H1 arm), `adequate_power` is false on *measurement* rather than by abstention, and
`NOT_SUPPORTED` stays unreachable on evidence. The structural facts are unchanged (fitted
range ≈3,752 km; 30°/60° blocks ≈910/1,819 km, both below the range; effective sample size
≈1). The strongest supported headline is therefore: **the current global datasets and
pipeline do not distinguish the tested surface-composition proxy from spatial null structure,
and the design has measured, inadequate power to detect even strong versions of that proxy.**

## Synthetic validation harness

Synthetic runs require an explicit mode and live under `data/synthetic/`; they never write
to `data/raw`, `data/processed`, or the real result directory.

```bash
python main.py --data-mode synthetic --scenario h1_lean --regenerate
python main.py --data-mode synthetic --scenario h2_lean --regenerate
python main.py --data-mode synthetic --scenario null --mode fast --regenerate
```

Supported scenarios are `h1_lean`, `mixed`, `h2_lean`, and `null`. Passing construction-
aligned synthetic scenarios validates code paths only. It is not a calibrated positive
control for the effect sizes, spatial support, or measurement error in the real data.

## CLI and analyst choices

| Flag | Default | Meaning |
|---|---|---|
| `--data-mode` | `real` | verified real inputs or isolated synthetic harness |
| `--mode` | `full` | `fast` trims permutations and tuning for a smoke test |
| `--scenario` | unset | synthetic regime only |
| `--age-mask` | `imbrian` | `imbrian`, `imbrian_nectarian`, or `none` |
| `--threshold` | `5.0` | binary anomaly threshold in nT (`5.0` or `10.0`) |
| `--grid-res` | `1.0` | synthetic grid resolution in degrees per pixel |
| `--regenerate` | off | rebuild isolated synthetic inputs; invalid for real data |

The primary cell was Imbrian/5 nT. Thresholds, 25/50/100 km buffers, the 600→40 km
exploratory gravity filter, the basin catalogue, block sizes, and model search spaces are
analyst choices. Their selection history and forking paths are disclosed in
`Analysis-Plan.md`; registration does not make them physically unique.

## Method summary

- Cross-validation holds out groups of 30° × 30° spatial blocks, with nested inner spatial
  folds for tuning. Because the fitted correlation range exceeds those blocks, this design
  does not establish independent folds for the present target.
- Longitudinal-rotation and 2-D phase-randomized nulls preserve selected spatial structure.
  The completed H2 injection study reuses the phase spectrum for a direct ablation power
  curve, but does not resimulate tuning, permutation, SHAP, or the full conjunctive H1 rule.
- H1 in the original code label means the surface-TiO₂ feature family. It should be read as
  the repository's spatial operationalization, not the Nichols temporal mechanism itself.
- Gravity and TiO₂ × gravity are exploratory controls. Optuna, alternate folds, gradients,
  SHAP, and seed reruns are descriptive/post-hoc and do not alter the inference status.
- Run metadata records data mode, input hashes, provenance manifests, Python version, and
  key package versions for reproducibility.

## Citing this work and its data sources

Please cite both this repository and the underlying products and papers. This project
distributes no third-party data.

- **This repository:** use GitHub's *Cite this repository* button (`CITATION.cff`), while
  noting that the corrected scope is the spatial co-location question above.
- **Bibliography:** [`References.md`](References.md).
- **Data provenance:** [`Data-Sources.md`](Data-Sources.md).
- **License:** code is [MIT](LICENSE); the paper, slides, figures, and data artifacts
  (CSV/JSON) are [CC BY 4.0](LICENSE-CC-BY-4.0.txt) — reuse and adaptation are welcome **with
  credit to the author**, and the work may not be presented as someone else's. Suggested
  attribution: *"Lemon (lemoon01110), Surface TiO2 and Lunar Crustal Magnetism: An
  Underpowered Spatial Co-location Analysis (v1.0.0, 2026),
  https://github.com/lemoon01110/Lunar-Titanium-Magnetism, CC BY 4.0."* Third-party lunar
  datasets are not redistributed and remain under their institutions' terms.

## Repository layout

```text
src/acquire.py           source acquisition and manifest
src/basins.py            approximate H2 benchmark configuration
src/ingest.py            conversion, validation, and provenance manifest
src/data_acquisition.py  isolated synthetic software-validation harness
src/preprocessing.py     common-grid alignment, distances, masks, and targets
src/modeling.py          spatial GroupKFold, baselines, and nested tuning
src/evaluation.py        nulls, ablations, criteria, sensitivity, and metadata
src/spatial_stats.py     variogram, bootstrap, phase null, and block sweep
src/interpretability.py  descriptive SHAP comparisons and maps
src/power_analysis.py    real-structure injection/recovery power analysis
src/terrain_sensitivity.py  full-versus-USGS-mare domain comparison
src/transparent_analysis.py continuous-field descriptive ridge comparison
src/report_generator.py  machine-generated PDF report
tests/                   engineering, regression, and scientific-claim guards
main.py                  explicit-mode pipeline entry point
```
