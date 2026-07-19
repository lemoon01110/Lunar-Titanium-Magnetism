# Random-Seed Software Diagnostic

This file is a software-reproducibility appendix, **not** a scientific robustness result.
The raw ten-seed table remains available in
[`seed_robustness.csv`](seed_robustness.csv) for auditability.

## What the rerun shows

XGBoost uses 0.9 row and column subsampling, and the configured seed is now propagated through
the model and rotation sampler. Across the ten arbitrary seeds, full-model PR-AUC is
0.0916 ± 0.0055, H2-only PR-AUC is 0.1096 ± 0.0011, and the clean Ti-derived ablation drop is
+0.0032 ± 0.0068. The ablation changes sign (−0.0110 to +0.0124), while every row still fails
to beat all baselines and is labelled `NO_INFERENCE`.

The fold-matched rotation-null mean is 0.1164 ± 0.0048 and its empirical *p* is
0.611 ± 0.047. These spreads describe software/RNG and finite-Monte-Carlo sensitivity, not
independent lunar evidence or uncertainty over spatial partitions.

## Why this does not establish robustness

- Raster rows remain spatially dependent regardless of RNG seed.
- The fitted target range under v2 is ≈403 km versus ≈910 km primary blocks, with
  `approx_effective_sample_size ≈ 1`.
- Full-model fold SD is ≈0.080 around a mean of 0.089, and alternate partitions range from
  0.033 to 0.240; partition uncertainty dominates seed variation.
- Rerunning a fixed estimator does not validate the mare-calibrated TiO₂ proxy in highlands.
- Seed variation does not provide an injection-recovery power curve.

The current CSV labels these rows `NO_INFERENCE`, preventing an arbitrary seed sweep from
manufacturing a scientific verdict. Earlier snapshots used `NOT_SUPPORTED` under the
superseded post-result asymmetric rule; that history is documented in
[`../Pre-Registration.md`](../Pre-Registration.md). The current primary interpretation is
**`INCONCLUSIVE_LOW_POWER`** until adequate detection power is demonstrated on the v2
surface product (metrics TBD). Altitude-product seed tables remain software diagnostics only.

No averaging over these seeds changes that status. The subsequently completed direct-H2
injection curve and independently sourced mare-terrain sensitivity are reported in the main
materials. They remain post-hoc and inconclusive: no scientifically justified target effect
was declared, `adequate_power = false`, and the terrain result is concentrated in two folds.
