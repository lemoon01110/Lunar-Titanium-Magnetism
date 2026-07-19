# Present-Day Surface TiO₂ and Lunar Crustal Magnetic Anomalies

> [!NOTE]
> **Educational & AI-Assisted Project**
> This repository is a personal project created for learning and hands-on experience. Artificial Intelligence (Large Language Models) was used extensively throughout its development to help me **write the code, understand the geophysical concepts, and rigorously catch statistical and logical errors**. It is a demonstration of using AI as a research and learning assistant, and the results should be read in that educational context.

*An underpowered test of spatial co-location, not a temporal test of the intermittent-dynamo mechanism*


This repository asks a deliberately narrow observational question: **does present-day,
remotely sensed surface TiO₂ spatially co-locate with a thresholded map of lunar crustal
magnetic anomalies under the pipeline's chosen masks, features, and spatial folds?** The
answer from the bundled run is **`INCONCLUSIVE_LOW_POWER`**. The exact metrics snapshot
backing every number quoted below is committed at
[`Paper-and-Pitch/metrics.json`](Paper-and-Pitch/metrics.json).

**Release v2.0.0** uses the surface-evaluated Tsunakawa/Wieczorek magnetic product
(Wieczorek `T2015_449`; |B| at lunar mean radius), primary threshold **10 nT** (25 nT
sensitivity), and the LROC WAC TiO₂ **tio2_quantitative** mask (≥2 wt%; cells below the
detection limit are non-quantitative). Binding scores, spatial nulls, ablation, and decision
criteria use **default-config XGBoost**; nested/tuned XGBoost is **diagnostic only** (and
here the tuned PR-AUC is *lower* than default). **v1.0.0 is superseded** and must not be
cited or deposited — it used JAXA `MA_GDOP_001` (a 30 km *altitude* grid wrongly treated as
a surface map) with 5/10 nT cutoffs. Author: Jack Wu
([ORCID 0009-0004-1710-9018](https://orcid.org/0009-0004-1710-9018)). The analysis plan is
an **author-declared** prospective plan whose timing **cannot be independently verified**.

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
> radiogenic melting of ilmenite-bearing cumulates at the core–mantle boundary after overturn,
> increasing core heat flux during short dynamo episodes (not simply continued sinking of
> Ti-rich material). This project has no magnetization ages or paleointensities, so it
> **cannot test, confirm, or refute that mechanism.** It could be entirely correct.
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

Primary scope: Imbrian ∩ `tio2_quantitative` (≥2 wt%), surface |B| ≥ **10 nT**
(`n_pixels` = 4374; prevalence ≈ 0.0384 ≈ 3.8%). Prevalence is the **expected no-skill /
random PR-AUC** for a constant-prior classifier here. Report **binary and continuous**
estimands separately. The repository-plan H1 criteria all failed on the canonical run, and the experiment
also fails its adequacy checks:

| Diagnostic | Result |
|---|---:|
| Full spatial-CV PR-AUC (binding default-config XGB) | 0.3949 ± 0.210 across folds |
| Nested/tuned XGB PR-AUC (diagnostic only) | 0.3141 (lower than default) |
| H2 benchmark PR-AUC | 0.2718 |
| Dummy-prior / LogReg PR-AUC | 0.0480 / 0.2565 |
| Full-model fold-matched rotation-null mean / 95th / empirical *p* | 0.2319 / 0.4910 / 0.1379 |
| Matched H2-only null mean / 95th / empirical *p* | 0.155877 / 0.376621 / 0.1724 |
| Continuous controls / controls+TiO₂ blocked R² | 0.3649 / 0.3503 |
| Descriptive continuous incremental R² (ΔR²) | -0.0146 |
| Ablation H1 TiO₂ drop mean / Wilcoxon *p* | +0.0424 / unavailable (not used for significance) |
| Mare-valid sensitivity (n / blocks / +blocks) | 3928 / 30 / 15 |
| Mare H1+controls / controls-only / drop | 0.4766 / 0.4213 / 0.0553 |
| Fitted target variogram range | ≈ 403 km |
| Primary CV block scale | ≈ 910 km |
| `block_exceeds_range` | `true` |
| Approximate effective sample size | ≈ 6.9 |
| **H1 injection power at declared target (strength 1.0)** | **0.467** (from regenerated `h1_tio2_power_analysis.json` on the v2 surface product) |

`H1_Supported` is `false`. The appropriate evidence classification is
**`INCONCLUSIVE_LOW_POWER`**, not evidence of absence. Report the **binary** classifier
estimands and the **continuous** ridge estimands separately — they answer different
questions; the continuous ΔR² ≈ -0.0146 shows the TiO₂ family does **not** help
continuously. There are 168 positive pixels (~3.8%), clustered across provinces; pixel count
is therefore not an independent sample size. The bundled guard already records
`negative_result_may_be_underpowered = true`; the amendment makes that limitation binding
rather than a footnote to a negative verdict. The block sweep is also non-monotone (0.537,
0.377, 0.395, 0.250, 0.377 at 15°, 20°, 30°, 45°, and 60°), so it does not support a clean
"less leakage strengthens the negative" narrative.

The H2 distance feature is a **literature-motivated benchmark**, not exact ground truth. It
uses six approximate basin centers/radii and scores 0.271820. A dedicated matched H2-only
null using fold-matched nonidentity rotations has mean 0.155877, 95th percentile 0.376621,
and +1-smoothed empirical *p* = 0.172414: the observed encoded H2 benchmark is **not
recovered** against its matched spatial null (`recovered_above_matched_spatial_null =
false`). This is more restrained than v1 (which reported recovery). The full model remains
compared only with its own matched null (mean 0.231862, 95th 0.490983, *p* = 0.137931). Both
nulls retain only rotations with the observed four evaluable folds: 383 unique candidates
were evaluated, 297 were rejected for fold-count mismatch, and the fold-matched pool
exhausted at **86** accepted shifts (below the requested 100). Rotated prevalence ranges
widely where the shifted target intersects the fixed Imbrian mask. Failure to recover H2
prevents strong negative inference about the surface-TiO₂ proxy; it does not establish H1
power.

The non-recovery reading is also **fragile** in resolution: with 86 rotations the
empirical-*p* resolution is 1/87 ≈ 0.0115 (disclose **86+1**), so a different eligible-shift
draw could move the *p*-value. Read it as "the encoded benchmark did not clear its matched
null in this draw", not as a precise probability. `positive_control_recovered` is **false**
for the observed H2 benchmark (and remains false for the H1 arm).

### Which "chance" level applies where

Four different reference levels now appear in this repository. They are not
interchangeable; quoting a score against the wrong one is the mismatched-null error
corrected in earlier amendments.

| Reference level | Value | Statistic it calibrates |
|---|---:|---|
| Expected no-skill / prevalence PR-AUC | 0.0384 | random/constant-prior baseline for this rare target |
| Matched H2-only rotation null (mean) | 0.155877 | the one-feature H2 benchmark (obs. 0.2718) |
| Full-model rotation null (mean) | 0.231862 | the 13-feature full model (obs. 0.3949) |
| Injection design (standalone JSONs) | regenerated for v2 | see Adequacy follow-up; `adequate_power` is false |

Note the full model scores *above* its own null mean but does **not** clear *p* < 0.05
(*p* ≈ 0.1379), and the H2 benchmark (0.2718) sits below its matched null 95th (0.3766).

A completed post-hoc injection study separately calibrates direct control ablation under the
real mask, prevalence, predictors, and 30°/60° folds. It does not calibrate tuning, the
permutation criterion, SHAP ranking, or every conjunctive H1 decision criterion, so neither
H2 result can turn H1's inconclusive score into a substantive negative conclusion.

### Old rule and post-hoc amendment

The pre-amendment metrics snapshot and earlier prose used the machine label **`NOT_SUPPORTED`** under a
post-result asymmetric rule: failed H1 criteria bypassed the spatial-adequacy gate on the
argument that leakage inflates scores. That rule addressed only one possible bias and did
not address low power. The dated amendment appended to
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
- The LROC WAC TiO₂ algorithm is a mare-regolith retrieval with a **2 wt% detection limit**;
  below-detection cells are non-quantitative (`tio2_quantitative`). The primary legacy run
  used the joint-valid / quantitative footprint, not a mare-validity mask. A post-hoc USGS
  mare-domain sensitivity is reported below (**30 mare blocks; 15 contain positives**).
- Surface UV/Vis TiO₂ samples the optical regolith, whereas magnetic anomalies can arise from
  older and deeper sources. Present-day spatial mismatch is not temporal evidence.
- Thresholding surface |B| at **10 nT** (25 nT sensitivity) discards field magnitude and
  yields a rare, clustered target. `src/transparent_analysis.py` implements a descriptive
  blocked ridge comparison on `log1p(|B|)`: controls-only blocked R² is 0.3649 and
  controls+TiO₂ is 0.3503, for fold-mean incremental R² **-0.0146**. Report binary and
  continuous estimands separately; the continuous result remains descriptive because those
  folds do not establish independent regions; the analysis emits no row-level p-value and
  does not replace the binding headline.
- H2 geometry is an approximate operationalization and cannot serve as assured exact truth;
  in v2 it is **not** recovered against its matched null.

## Adequacy follow-up

The follow-ups now have different statuses under the v2.0.0 surface product:

1. **H2 injection-recovery power analysis — completed; `adequate_power` is false.**
   The committed `metrics.json` records `Detection_Power.adequate_power` is false and
   `observed_h2_benchmark_recovered` / `positive_control_recovered` is false. Regenerated
   [`Paper-and-Pitch/positive_control_power_analysis.json`](Paper-and-Pitch/positive_control_power_analysis.json)
   shows the H2 injection arm remains structurally limited (`n_eff` ≈ 6.9) and does not reach
   target power on the tested grid. Treat the strength grid as a **low-strength simulation /
   design-sensitivity** probe, not demonstrated realism of lunar physics. See also
   [`h2_antipode_low_strength_extension.json`](Paper-and-Pitch/h2_antipode_low_strength_extension.json).
2. **H1 (TiO₂-driver) injection curve — regenerated; measured power 0.467 at strength 1.0**
   ([`Paper-and-Pitch/h1_tio2_power_analysis.json`](Paper-and-Pitch/h1_tio2_power_analysis.json)).
   On the v2 surface product the tested-grid 80% point estimate first appears at latent
   strength **2.0**, but `Detection_Power.adequate_power` remains **false** because no
   externally justified target effect anchors the curve and the design stays structurally
   limited. Low-strength points (≤0.2) stay near zero detection probability — far from a
   demonstrated-realism claim.
3. **Externally sourced mare-terrain mask — descriptive result available.** A post-hoc mask
   derived from USGS Unified Geologic Map GIS v2 `FIRST_Unit` symbols `Em`, `Im1`, `Im2`, and
   `Imd` leaves **3,928** pixels, **30 mare blocks**, and **15** blocks containing positives
   in the Imbrian ∩ quantitative scope. Using raw row-local TiO₂ only (buffers excluded),
   TiO₂+controls scores ≈0.4766 versus ≈0.4213 for controls, a mean drop/increment ≈0.0553.
   Wilcoxon *p* is unavailable for a significance claim here; the result is **inconclusive**
   — it is not confirmation and is not presented as evidence.

With the regenerated H1 curve, we still anchor interpretation to an **illustrative** effect
(Amendment A8 in [`Pre-Registration.md`](Pre-Registration.md)): latent strength 1.0. It is
**not** a physically derived effect size — the Nichols theory does **not** provide a registered
present-day spatial effect size — and the committed artifact leaves `target_effect_strength`
null. Measured H1 power at that anchor is **0.467**, far below the 0.80 requirement.
`INCONCLUSIVE_LOW_POWER` is therefore **demonstrated rather than asserted**: the registered
criteria could not reliably fire even for a strong planted TiO₂-driven signal at the
declared illustrative anchor. Observed-H2 `positive_control_recovered` is false; the H1
injection arm reaches point-estimate 80% only at strength 2.0 and remains at 0.467 at the
illustrative strength-1.0 anchor, so `adequate_power` is false on *measurement* rather than
by abstention, and `NOT_SUPPORTED` stays unreachable on evidence. The structural facts
under v2 include fitted range ≈403 km; 30°/60° blocks ≈910/1,819 km; effective sample size
≈6.9; and fold-matched null pools exhausted at 86 permutations. The strongest supported
headline is therefore: **jointly available numerical coverage within the registered scope
does not distinguish the tested surface-composition proxy from spatial null structure at the
registered criteria, and the design has measured, inadequate power (`adequate_power` is false)
to settle the question.**

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
| `--threshold` | `10.0` | binary anomaly threshold in nT (`10.0` or `25.0`) |
| `--grid-res` | `1.0` | synthetic grid resolution in degrees per pixel |
| `--regenerate` | off | rebuild isolated synthetic inputs; invalid for real data |

The primary cell is Imbrian/10 nT (25 nT sensitivity). Thresholds, 25/50/100 km buffers, the 600→40 km
exploratory gravity filter, the basin catalogue, block sizes, and model search spaces are
analyst choices. Their selection history and forking paths are disclosed in
`Analysis-Plan.md`; registration does not make them physically unique.

## Method summary

- Binding estimator: **default-config XGBoost**. Nested tuning is **diagnostic only** and is
  not used for criteria (tuned PR-AUC can be lower than default, as in this run).
- Cross-validation holds out groups of 30° × 30° spatial blocks, with nested inner spatial
  folds for tuning. Even when blocks exceed the fitted range, few effective independent
  regions remain; this design does not establish strong independent folds for the present target.
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
  attribution: *"Jack Wu (lemoon01110), Surface TiO2 and Lunar Crustal Magnetism: An
  Underpowered Spatial Co-location Analysis (v2.0.0, 2026),
  https://github.com/lemoon01110/Lunar-Titanium-Magnetism, CC BY 4.0."*
  **v1.0.0 is superseded** and must not be cited or deposited. Third-party lunar
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
