"""Random-number diagnostic for the legacy threshold classifier.

The repository-plan run fixes a single master seed (``config.RANDOM_SEED = 42``).
This diagnostic deliberately varies that seed through XGBoost subsampling and the
rotation sampler. Repetition across arbitrary RNG seeds is still not evidence of
scientific robustness; it only exposes software/RNG sensitivity.

Per seed it recomputes the legacy pipeline's threshold-classifier diagnostics:
the baseline/ablation cross-validation scores and the spatial-rotation permutation
null. It deliberately skips components outside this software/RNG check (nested
tuning, SHAP figures, block-size sweep, sensitivity grid, PDF) so
the sweep is cheap. It emits ``NO_INFERENCE`` for every row: changing a random seed
cannot repair an effective sample size near one or establish detection power.

Run:  ``python -m src.seed_robustness``  (optionally ``--seeds 42 1 2 3``)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
from typing import Dict, List

import pandas as pd

from . import config
from . import evaluation

# Registered seed first, then nine arbitrary additional seeds.
DEFAULT_SEEDS: List[int] = [42, 1, 7, 13, 23, 71, 101, 202, 303, 777]

DEFAULT_OUT = os.path.join(config.PROJECT_ROOT, "Paper-and-Pitch", "seed_robustness.csv")

FIELDS = [
    "seed", "full_pr_auc", "full_std", "h2_only_pr_auc",
    "null_mean", "null_std", "perm_p", "tio2_drop",
    "beats_all_baselines", "verdict",
]


def evaluate_seed(seed: int, df_all: pd.DataFrame, grid_meta: Dict) -> Dict:
    """Recompute legacy repository-plan scores for one RNG seed; emit no verdict."""
    cfg = config.PipelineConfig(random_seed=seed)  # mode=full, primary threshold, imbrian
    target = f"mag_binary_{int(cfg.primary_threshold_nt)}nT"
    df_primary = evaluation.subset_by_age(df_all, cfg.age_mask)

    core = evaluation.core_analysis(df_primary, target, cfg)
    baselines = core["baselines"]
    full_mean = baselines["XGB_Full_PR_AUC"]["mean"]
    perm = evaluation.run_permutation_test(df_primary, df_all, target, grid_meta, cfg, full_mean)

    return {
        "seed": seed,
        "full_pr_auc": round(full_mean, 6),
        "full_std": round(baselines["XGB_Full_PR_AUC"]["std"], 6),
        "h2_only_pr_auc": round(baselines["H2_Only_PR_AUC"]["mean"], 6),
        "null_mean": round(perm["Null_Mean_PR_AUC"], 6),
        "null_std": round(perm["Null_Std_PR_AUC"], 6),
        "perm_p": round(perm["Empirical_p_value"], 6),
        "tio2_drop": round(core["ablation"]["H1_tio2_drop_mean"], 6),
        "beats_all_baselines": core["beats_all_baselines"],
        "verdict": "NO_INFERENCE",
    }


def run(seeds: List[int], out_path: str) -> Dict:
    df_all = pd.read_csv(os.path.join(config.PROCESSED_DIR, "modeling_dataset.csv"))
    with open(os.path.join(config.PROCESSED_DIR, "grid_meta.json")) as fh:
        grid_meta = json.load(fh)

    rows = []
    for i, seed in enumerate(seeds, 1):
        row = evaluate_seed(seed, df_all, grid_meta)
        rows.append(row)
        print(f"[{i}/{len(seeds)}] seed={seed:<4} full={row['full_pr_auc']:.4f} "
              f"h2={row['h2_only_pr_auc']:.4f} null={row['null_mean']:.4f} "
              f"p={row['perm_p']:.3f} drop={row['tio2_drop']:+.4f} {row['verdict']}",
              flush=True)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    def agg(key):
        xs = [r[key] for r in rows]
        return statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0)

    print("\n=== across seeds (mean +/- std) ===")
    for key in ("full_pr_auc", "h2_only_pr_auc", "null_mean", "perm_p", "tio2_drop"):
        mean, std = agg(key)
        print(f"  {key:16s} {mean:+.4f} +/- {std:.4f}")
    n_no_inference = sum(row["verdict"] == "NO_INFERENCE" for row in rows)
    print("  Scientific inference: none (seed repetition does not measure power)")
    print(f"\nWrote {out_path}")
    return {"rows": rows, "n_no_inference": n_no_inference}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Software/RNG diagnostic for legacy threshold-classifier metrics."
    )
    ap.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    run(args.seeds, args.out)


if __name__ == "__main__":
    main()
