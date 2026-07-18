"""
Lunar surface-TiO2 spatial-proxy pipeline -- single-command entry point.

    python main.py                      # full run on canonical real data
    python main.py --mode fast          # quick smoke test
    python main.py --data-mode synthetic --scenario h1_lean
    python main.py --data-mode synthetic --scenario h2_lean --regenerate

Reproduces every figure and metric from raw grids with one command.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import platform
import tempfile
from typing import Any, Dict, Sequence

# Headless/workspace-sandbox runs often have a read-only user cache.  Point
# Matplotlib/fontconfig at a task-specific writable cache before importing the
# plotting stack so multiprocessing does not rebuild fonts in every worker.
_RUNTIME_CACHE = os.path.join(tempfile.gettempdir(), "lunar-titanium-magnetism-cache")
os.makedirs(_RUNTIME_CACHE, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", os.path.join(_RUNTIME_CACHE, "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", os.path.join(_RUNTIME_CACHE, "xdg"))

from src import config
from src.data_acquisition import generate_synthetic_data
from src.preprocessing import preprocess_data
from src.evaluation import evaluate_pipeline
from src.report_generator import generate_pdf_report


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Lunar surface-TiO2 spatial-proxy pipeline")
    p.add_argument("--data-mode", choices=config.DATA_MODES, default="real",
                   help="'real' (default) uses only provenance-validated canonical data; "
                        "'synthetic' runs the isolated validation harness")
    p.add_argument("--mode", choices=["fast", "full"], default="full",
                   help="'fast' trims permutations/tuning for a smoke test")
    p.add_argument("--scenario", default=None, choices=config.SYNTHETIC_SCENARIOS,
                   help="synthetic ground-truth regime; valid only with "
                        "--data-mode synthetic (default: h1_lean)")
    p.add_argument("--age-mask", default="imbrian",
                   choices=["imbrian", "imbrian_nectarian", "none"],
                   help="age mask for the primary analysis")
    p.add_argument("--threshold", type=float, choices=config.BINARY_THRESHOLDS_NT,
                   default=config.PRIMARY_THRESHOLD_NT,
                   help="primary binary anomaly threshold (nT); must be one of the "
                        "preconfigured/preprocessed thresholds")
    p.add_argument("--grid-res", type=float, default=config.GRID_RES_DEG,
                   help="synthetic grid resolution (deg/pixel)")
    p.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    p.add_argument("--regenerate", action="store_true",
                   help="regenerate isolated synthetic data; invalid in real mode")
    args = p.parse_args(argv)
    if args.data_mode == "real":
        if args.scenario is not None:
            p.error("--scenario is only valid with --data-mode synthetic")
        if args.regenerate:
            p.error("--regenerate is only valid with --data-mode synthetic; real data are never generated")
    elif args.scenario is None:
        args.scenario = "h1_lean"
    return args


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_path(path: str) -> str:
    """Prefer a portable project-relative path, retaining absolute temp paths."""
    path = os.path.abspath(path)
    relative = os.path.relpath(path, config.PROJECT_ROOT)
    return relative if relative != os.pardir and not relative.startswith(os.pardir + os.sep) else path


def _package_versions() -> Dict[str, str]:
    versions: Dict[str, str] = {}
    for distribution in ("numpy", "pandas", "scikit-learn", "xgboost", "shap", "rasterio", "fpdf2"):
        try:
            versions[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            versions[distribution] = "not-installed"
    return versions


def build_run_metadata(
    paths: config.PipelinePaths, data_mode: str, scenario: str | None,
) -> Dict[str, Any]:
    """Capture enough provenance to identify the exact inputs and runtime."""
    input_paths = [
        os.path.join(paths.raw_dir, filename)
        for filename in (
            *config.RAW_FILES.values(), config.TERRAIN_VALIDITY_FILE,
            config.ANTIPODES_CSV, config.BASINS_CSV,
        )
    ]
    manifest_name = getattr(config, "REAL_DATA_MANIFEST", "real_data_manifest.json")
    provenance_path = os.path.join(paths.raw_dir, manifest_name) if data_mode == "real" else None
    if provenance_path is not None:
        input_paths.append(provenance_path)
        source_manifest = os.path.join(paths.raw_dir, "sources", "source_manifest.json")
        if os.path.isfile(source_manifest):
            input_paths.append(source_manifest)

    hashes = {
        _metadata_path(path): _sha256(path)
        for path in input_paths
        if os.path.isfile(path)
    }
    return {
        "data_mode": data_mode,
        "scenario": scenario,
        "input_directory": _metadata_path(paths.raw_dir),
        "input_hashes_sha256": hashes,
        "provenance_path": _metadata_path(provenance_path) if provenance_path else None,
        "runtime": {
            "python": platform.python_version(),
            "packages": _package_versions(),
        },
    }


def assert_pdf_claim_allowed(metrics: Dict[str, Any], data_mode: str, scenario: str | None) -> None:
    """Fail closed if a negative-control simulation produces a proxy-support claim."""
    claims_support = bool(
        metrics.get("Surface_Proxy_Supported", metrics.get("H1_Supported"))
    ) or metrics.get("Inference_Status") == "SUPPORTED"
    if data_mode == "synthetic" and scenario in {"h2_lean", "null"} and claims_support:
        raise RuntimeError(
            f"False-positive guard: synthetic {scenario!r} data claimed surface-proxy support; "
            "refusing to generate a PDF."
        )


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    print("=== Lunar Surface-TiO2 Spatial-Proxy Pipeline ===")

    paths = config.resolve_pipeline_paths(args.data_mode, args.scenario)
    for d in (paths.raw_dir, paths.processed_dir, paths.results_dir, paths.figures_dir):
        os.makedirs(d, exist_ok=True)

    cfg = config.PipelineConfig(
        random_seed=args.seed,
        grid_res_deg=args.grid_res,
        age_mask=args.age_mask,
        primary_threshold_nt=args.threshold,
        mode=args.mode,
    )

    print("\n--- Step 1: Data Acquisition ---")
    from src.ingest import validate_raw_grids
    if args.data_mode == "real":
        print(f"Validating canonical real data and provenance in {paths.raw_dir}...")
        validate_raw_grids(paths.raw_dir, args.grid_res, require_real_provenance=True)
    else:
        required_synthetic_inputs = (
            *config.RAW_FILES.values(),
            config.TERRAIN_VALIDITY_FILE,
            config.ANTIPODES_CSV,
            config.BASINS_CSV,
        )
        missing_synthetic_inputs = [
            filename for filename in required_synthetic_inputs
            if not os.path.isfile(os.path.join(paths.raw_dir, filename))
        ]
        if args.regenerate or missing_synthetic_inputs:
            if missing_synthetic_inputs and not args.regenerate:
                print(
                    "Synthetic cache is incomplete; regenerating missing canonical "
                    f"schema ({', '.join(missing_synthetic_inputs)})."
                )
            generate_synthetic_data(paths.raw_dir, args.grid_res, args.scenario, args.seed)
        print(f"Validating isolated synthetic {args.scenario!r} data in {paths.raw_dir}...")
        validate_raw_grids(paths.raw_dir, args.grid_res)

    run_metadata = build_run_metadata(paths, args.data_mode, args.scenario)

    print("\n--- Step 2: Preprocessing (equal-area regrid, real distances, buffers) ---")
    preprocess_data(paths.raw_dir, paths.processed_dir, args.grid_res)

    print("\n--- Step 3: Modelling, statistical tests, SHAP ---")
    metrics = evaluate_pipeline(
        paths.processed_dir, paths.results_dir, cfg, run_metadata=run_metadata,
    )

    print("\n--- Step 4: PDF report ---")
    assert_pdf_claim_allowed(metrics, args.data_mode, args.scenario)
    generate_pdf_report(
        os.path.join(paths.results_dir, "metrics.json"),
        paths.figures_dir,
        os.path.join(paths.results_dir, "Research_Paper.pdf"),
    )

    print(f"\n=== Pipeline complete. See {paths.results_dir}/ for metrics and report outputs ===")


if __name__ == "__main__":
    main()
