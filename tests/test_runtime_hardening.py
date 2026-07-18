"""Focused guards for real/synthetic isolation, provenance, and report claims."""

import json
import os

import numpy as np
import pandas as pd
import pytest

import main as pipeline_main
from src import config, evaluation
from src.report_generator import (
    generate_pdf_report,
    report_inference_status,
)


def test_real_and_synthetic_paths_are_strictly_separated():
    real = config.resolve_pipeline_paths("real")
    synthetic = config.resolve_pipeline_paths("synthetic", "h2_lean")

    assert real.raw_dir == config.RAW_DIR
    assert real.processed_dir == config.PROCESSED_DIR
    assert real.results_dir == config.RESULTS_DIR
    assert synthetic.raw_dir == os.path.join(
        config.PROJECT_ROOT, "data", "synthetic", "h2_lean", "raw"
    )
    assert synthetic.processed_dir == os.path.join(
        config.PROJECT_ROOT, "data", "synthetic", "h2_lean", "processed"
    )
    assert synthetic.results_dir == os.path.join(
        config.PROJECT_ROOT, "results", "synthetic", "h2_lean"
    )
    assert synthetic.raw_dir != real.raw_dir
    assert synthetic.results_dir != real.results_dir

    with pytest.raises(ValueError, match="cannot be used in real data mode"):
        config.resolve_pipeline_paths("real", "h1_lean")
    with pytest.raises(ValueError, match="requires a scenario"):
        config.resolve_pipeline_paths("synthetic", "../../raw")


def test_cli_defaults_to_real_and_rejects_real_mode_synthetic_options(capsys):
    args = pipeline_main.parse_args([])
    assert args.data_mode == "real"
    assert args.scenario is None

    synthetic = pipeline_main.parse_args(["--data-mode", "synthetic"])
    assert synthetic.scenario == "h1_lean"

    with pytest.raises(SystemExit):
        pipeline_main.parse_args(["--scenario", "null"])
    assert "--scenario is only valid with --data-mode synthetic" in capsys.readouterr().err

    with pytest.raises(SystemExit):
        pipeline_main.parse_args(["--regenerate"])
    assert "real data are never generated" in capsys.readouterr().err


def test_cli_rejects_unconfigured_threshold(capsys):
    with pytest.raises(SystemExit):
        pipeline_main.parse_args(["--threshold", "7"])
    error = capsys.readouterr().err
    assert "invalid choice" in error
    assert "5.0" in error and "10.0" in error

    with pytest.raises(ValueError, match="is not configured"):
        evaluation.evaluate_pipeline(cfg=config.PipelineConfig(primary_threshold_nt=7.0))


def test_real_main_requires_provenance_validation_and_never_generates(tmp_path, monkeypatch):
    paths = config.PipelinePaths(
        str(tmp_path / "raw"), str(tmp_path / "processed"),
        str(tmp_path / "results"), str(tmp_path / "results" / "figures"),
    )
    monkeypatch.setattr(config, "resolve_pipeline_paths", lambda mode, scenario: paths)

    calls = {}

    def fake_validate(raw_dir, res_deg, require_real_provenance=False):
        calls["validation"] = (raw_dir, res_deg, require_real_provenance)

    def forbidden_generator(*args, **kwargs):
        pytest.fail("real mode must never invoke the synthetic generator")

    def fake_evaluate(processed_dir, results_dir, cfg, run_metadata=None):
        calls["evaluation"] = (processed_dir, results_dir, run_metadata)
        return {"H1_Supported": False, "Inference_Status": "NOT_SUPPORTED"}

    import src.ingest as ingest
    monkeypatch.setattr(ingest, "validate_raw_grids", fake_validate)
    monkeypatch.setattr(pipeline_main, "generate_synthetic_data", forbidden_generator)
    monkeypatch.setattr(pipeline_main, "preprocess_data", lambda *args: None)
    monkeypatch.setattr(pipeline_main, "evaluate_pipeline", fake_evaluate)
    monkeypatch.setattr(pipeline_main, "generate_pdf_report", lambda *args: calls.setdefault("pdf", args))

    pipeline_main.main(["--data-mode", "real", "--mode", "fast"])

    assert calls["validation"] == (paths.raw_dir, config.GRID_RES_DEG, True)
    run_metadata = calls["evaluation"][2]
    assert run_metadata["data_mode"] == "real"
    assert run_metadata["scenario"] is None
    assert run_metadata["provenance_path"].endswith("real_data_manifest.json")
    assert "python" in run_metadata["runtime"]
    assert "packages" in run_metadata["runtime"]


def test_synthetic_main_uses_scenario_namespace_and_nonprovenance_validation(
    tmp_path, monkeypatch,
):
    paths = config.PipelinePaths(
        str(tmp_path / "data" / "synthetic" / "null" / "raw"),
        str(tmp_path / "data" / "synthetic" / "null" / "processed"),
        str(tmp_path / "results" / "synthetic" / "null"),
        str(tmp_path / "results" / "synthetic" / "null" / "figures"),
    )
    monkeypatch.setattr(config, "resolve_pipeline_paths", lambda mode, scenario: paths)
    calls = {}

    def fake_generate(raw_dir, res_deg, scenario, seed):
        calls["generation"] = (raw_dir, res_deg, scenario, seed)

    def fake_validate(*args, **kwargs):
        calls["validation"] = (args, kwargs)

    def fake_evaluate(processed_dir, results_dir, cfg, run_metadata=None):
        calls["metadata"] = run_metadata
        return {"H1_Supported": False, "Inference_Status": "NOT_SUPPORTED"}

    import src.ingest as ingest
    monkeypatch.setattr(ingest, "validate_raw_grids", fake_validate)
    monkeypatch.setattr(pipeline_main, "generate_synthetic_data", fake_generate)
    monkeypatch.setattr(pipeline_main, "preprocess_data", lambda *args: None)
    monkeypatch.setattr(pipeline_main, "evaluate_pipeline", fake_evaluate)
    monkeypatch.setattr(pipeline_main, "generate_pdf_report", lambda *args: None)

    pipeline_main.main(["--data-mode", "synthetic", "--scenario", "null", "--mode", "fast"])

    assert calls["generation"][0] == paths.raw_dir
    assert calls["generation"][2] == "null"
    assert calls["validation"] == ((paths.raw_dir, config.GRID_RES_DEG), {})
    assert calls["metadata"]["data_mode"] == "synthetic"
    assert calls["metadata"]["scenario"] == "null"
    assert calls["metadata"]["provenance_path"] is None


def test_synthetic_main_regenerates_stale_cache_missing_terrain(tmp_path, monkeypatch):
    paths = config.PipelinePaths(
        str(tmp_path / "raw"),
        str(tmp_path / "processed"),
        str(tmp_path / "results"),
        str(tmp_path / "results" / "figures"),
    )
    os.makedirs(paths.raw_dir)
    # Model the pre-terrain-schema cache: the old sentinel exists, but the new
    # required mask and other canonical inputs do not.
    (tmp_path / "raw" / config.RAW_FILES["magnetic"]).write_bytes(b"stale")
    monkeypatch.setattr(config, "resolve_pipeline_paths", lambda mode, scenario: paths)
    calls = {"generated": 0}

    def fake_generate(*args, **kwargs):
        calls["generated"] += 1

    import src.ingest as ingest
    monkeypatch.setattr(ingest, "validate_raw_grids", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline_main, "generate_synthetic_data", fake_generate)
    monkeypatch.setattr(pipeline_main, "preprocess_data", lambda *args: None)
    monkeypatch.setattr(
        pipeline_main,
        "evaluate_pipeline",
        lambda *args, **kwargs: {"H1_Supported": False, "Inference_Status": "INCONCLUSIVE_LOW_POWER"},
    )
    monkeypatch.setattr(pipeline_main, "generate_pdf_report", lambda *args: None)

    pipeline_main.main([
        "--data-mode", "synthetic", "--scenario", "h1_lean", "--mode", "fast",
    ])
    assert calls["generated"] == 1


def test_inference_gate_requires_spatial_information_and_detection_power():
    """A failed criterion is not a strong negative unless the design could detect
    the target effect; leakage and false-negative power are different axes."""
    adequate = {
        "block_size_robustness": {"60deg": {"beats_h2_and_h1_helps": True}},
        "block_exceeds_range": True,
        "approx_effective_sample_size": 100.0,
    }
    inadequate = {
        "block_size_robustness": {"60deg": {"beats_h2_and_h1_helps": False}},
        "block_exceeds_range": False,
        "approx_effective_sample_size": 1.0,
    }
    calibrated_power = {
        "adequate_power": True,
        "power_at_target_effect": 0.9,
        "positive_control_recovered": True,
    }

    # Positive + adequate -> SUPPORTED; positive + inadequate -> INCONCLUSIVE.
    assert evaluation.spatially_gated_inference(True, adequate) == (True, "SUPPORTED")
    assert evaluation.spatially_gated_inference(True, inadequate) == (
        False, "INCONCLUSIVE_SPATIAL_AUTOCORRELATION"
    )
    # A negative is NOT_SUPPORTED only when both structural and empirical power pass.
    assert evaluation.spatially_gated_inference(False, adequate, calibrated_power) == (
        False, "NOT_SUPPORTED"
    )
    assert evaluation.spatially_gated_inference(False, inadequate, calibrated_power) == (
        False, "INCONCLUSIVE_LOW_POWER"
    )
    assert evaluation.spatially_gated_inference(False, adequate) == (
        False, "INCONCLUSIVE_LOW_POWER"
    )
    # An explicitly false canonical adequacy flag cannot be overridden by a
    # contradictory numeric fallback.
    contradictory_power = {
        "adequate_power": False,
        "power_at_target_effect": 0.99,
        "positive_control_recovered": True,
    }
    assert evaluation.spatially_gated_inference(False, adequate, contradictory_power) == (
        False, "INCONCLUSIVE_LOW_POWER"
    )
    # If the largest requested partition is skipped, a smaller passing cell must
    # not silently become the spatial gate.
    skipped_largest = {
        **adequate,
        "block_size_robustness": {
            "45deg": {"beats_h2_and_h1_helps": True},
            "60deg": {"skipped": True, "reason": "too few blocks"},
        },
    }
    assert evaluation.spatially_gated_inference(True, skipped_largest) == (
        False, "INCONCLUSIVE_SPATIAL_AUTOCORRELATION"
    )

    # Report re-derivation catches a hand-edited SUPPORTED that fails the gate.
    inconsistent = {
        "Inference_Status": "SUPPORTED",
        "Criteria": {
            "criterion_i_beats_null_and_baselines": True,
            "criterion_ii_h1_tio2_outranks_antipode": True,
            "criterion_iii_h1_ablation_significant": True,
        },
        "Spatial_Diagnostics": inadequate,
    }
    assert report_inference_status(inconsistent) == "INCONCLUSIVE_SPATIAL_AUTOCORRELATION"


def test_benchmark_rotation_null_uses_the_same_h2_statistic(monkeypatch):
    """A one-feature H2 score must not be compared with the full-model null."""
    height, width = 2, 30
    rows, cols = np.mgrid[:height, :width]
    frame = pd.DataFrame({
        "row_idx": rows.ravel(),
        "col_idx": cols.ravel(),
        "spatial_block": rows.ravel(),
        "dist_to_antipode_km": np.linspace(0, 1, height * width),
        "mag_binary_5nT": (cols.ravel() % 3 == 0).astype(int),
    })
    seen_features = []

    def fake_cv(factory, X, y, groups, n_folds):
        seen_features.append(list(X.columns))
        return np.array([0.1, 0.2])

    monkeypatch.setattr(evaluation.modeling, "cross_val_pr_auc", fake_cv)
    monkeypatch.setattr(
        evaluation,
        "delayed",
        lambda fn: lambda *args, **kwargs: lambda: fn(*args, **kwargs),
    )
    monkeypatch.setattr(
        evaluation,
        "Parallel",
        lambda **kwargs: lambda jobs: [job() for job in jobs],
    )
    result = evaluation.run_permutation_test(
        frame,
        frame,
        "mag_binary_5nT",
        {"width": width, "height": height},
        config.PipelineConfig(mode="fast"),
        real_full_mean=0.15,
        features=config.H2_FEATURES,
    )
    assert result["features"] == config.H2_FEATURES
    assert result["n_unique_longitude_shifts"] == 20
    assert result["sampled_with_replacement"] is False
    assert result["observed_valid_fold_count"] == 2
    assert result["accepted_rotation_valid_fold_counts"] == [2] * 20
    assert result["Observed_PR_AUC"] == pytest.approx(0.15)
    assert seen_features and all(columns == config.H2_FEATURES for columns in seen_features)


def test_pipeline_config_rejects_a_mislabeled_primary_block_size():
    with pytest.raises(ValueError, match="must remain 30 degrees"):
        config.PipelineConfig(spatial_block_size_deg=45.0)


def test_final_params_do_not_depend_on_outer_test_scores():
    params = [
        {"max_depth": 3, "learning_rate": 0.1},
        {"max_depth": 4, "learning_rate": 0.1},
        {"max_depth": 3, "learning_rate": 0.1},
    ]
    first = evaluation._pick_best_params(params, np.array([0.1, 0.9, 0.2]))
    second = evaluation._pick_best_params(params, np.array([0.9, 0.1, 0.2]))
    assert first == second == params[0]


def test_core_factories_receive_the_configured_seed(monkeypatch):
    seen = []

    def factory(name):
        def build(*args, seed=None, **kwargs):
            seen.append((name, seed))
            return object()
        return build

    monkeypatch.setattr(evaluation.modeling, "dummy_factory", factory("dummy"))
    monkeypatch.setattr(evaluation.modeling, "logreg_factory", factory("logreg"))
    monkeypatch.setattr(evaluation.modeling, "xgb_factory", factory("xgb"))
    monkeypatch.setattr(
        evaluation.modeling,
        "cross_val_pr_auc",
        lambda model_factory, X, y, groups, n: np.array([0.2, 0.3]),
    )
    frame = pd.DataFrame({feature: [0.0, 1.0, 0.5, 1.5] for feature in config.ALL_FEATURES})
    frame["spatial_block"] = [0, 0, 1, 1]
    frame["mag_binary_5nT"] = [0, 1, 0, 1]
    cfg = config.PipelineConfig(random_seed=17, n_outer_folds=2, mode="fast")
    evaluation.run_baselines_and_full(frame, "mag_binary_5nT", cfg)
    evaluation.run_ablation(frame, "mag_binary_5nT", cfg)
    assert seen and all(seed == 17 for _, seed in seen)


@pytest.mark.parametrize("scenario", ["h2_lean", "null"])
def test_pdf_refuses_negative_control_false_positive(tmp_path, scenario):
    with pytest.raises(RuntimeError, match="False-positive guard"):
        pipeline_main.assert_pdf_claim_allowed(
            {"H1_Supported": True, "Inference_Status": "SUPPORTED"},
            "synthetic", scenario,
        )

    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(json.dumps({
        "Run_Metadata": {"data_mode": "synthetic", "scenario": scenario},
        "Inference_Status": "SUPPORTED",
        "H1_Supported": True,
    }))
    output = tmp_path / "should_not_exist.pdf"

    with pytest.raises(RuntimeError, match="False-positive guard"):
        generate_pdf_report(str(metrics_path), str(tmp_path), str(output))
    assert not output.exists()


def test_evaluate_pipeline_preserves_optional_run_metadata(tmp_path, monkeypatch):
    processed = tmp_path / "processed"
    results = tmp_path / "results"
    processed.mkdir()
    rows = 3
    df = pd.DataFrame({feature: np.zeros(rows) for feature in config.ALL_FEATURES})
    df["age_class"] = config.AGE_IMBRIAN
    df["spatial_block"] = np.arange(rows)
    df["mag_binary_5nT"] = [0, 1, 0]
    df["lon"] = [-1.0, 0.0, 1.0]
    df["lat"] = [-1.0, 0.0, 1.0]
    df["row_idx"] = [0, 0, 0]
    df["col_idx"] = [0, 1, 2]
    df["mag_anomaly"] = [1.0, 2.0, 1.5]
    df["tio2_terrain_valid"] = [1, 1, 1]
    df.to_csv(processed / "modeling_dataset.csv", index=False)
    (processed / "grid_meta.json").write_text(json.dumps({"width": 3, "height": 1}))

    summary = {"mean": 0.7, "std": 0.0, "per_fold": [0.7]}
    monkeypatch.setattr(evaluation, "core_analysis", lambda *args: {
        "baselines": {
            "positive_prevalence": 1 / 3, "n_pixels": rows, "n_blocks": rows,
            "Dummy_Stratified_PR_AUC": summary, "Dummy_Prior_PR_AUC": summary,
            "LogReg_PR_AUC": summary, "H2_Only_PR_AUC": summary,
            "XGB_Full_PR_AUC": summary,
        },
        "ablation": {}, "beats_all_baselines": True,
        "full_ge_logreg": True, "ablation_significant": True,
    })
    monkeypatch.setattr(
        evaluation.modeling, "nested_cv_pr_auc", lambda *args: (np.array([0.7]), [{}])
    )
    monkeypatch.setattr(evaluation, "run_permutation_test", lambda *args, **kwargs: {
        "Empirical_p_value": 0.01, "n_permutations": 1,
        "Null_95th_PR_AUC": 0.1,
    })
    monkeypatch.setattr(evaluation, "run_detection_power", lambda *args, **kwargs: (
        {"analysis": "test fixture", "minimum_detectable_effect": {}},
        {
            "adequate_power": False,
            "power_at_target_effect": None,
            "positive_control_recovered": True,
        },
    ))
    monkeypatch.setattr(evaluation.modeling, "fit_final_model", lambda *args: object())
    monkeypatch.setattr(evaluation.interpretability, "compute_shap", lambda model, X, seed: (
        np.zeros((len(X), len(config.ALL_FEATURES))), X.copy(), {}
    ))
    monkeypatch.setattr(evaluation.interpretability, "h1_vs_h2_ranking", lambda *args: {
        "h1_outranks_antipode": True,
    })
    monkeypatch.setattr(
        evaluation.interpretability, "make_figures", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(evaluation, "run_spatial_diagnostics", lambda *args: {
        "block_exceeds_range": True,
        "approx_effective_sample_size": 100.0,
        "spatially_adequate": True,
        "block_size_robustness": {"60deg": {"beats_h2_and_h1_helps": True}},
    })
    monkeypatch.setattr(evaluation, "_run_sensitivity", lambda *args: {})
    monkeypatch.setattr(
        evaluation.transparent_analysis,
        "continuous_field_analysis",
        lambda *args, **kwargs: {
            "estimand": "test fixture",
            "fold_ids": [0, 1, 2],
            "tio2_incremental_r2": {"per_fold": [0.0, 0.0, 0.0]},
        },
    )
    monkeypatch.setattr(
        evaluation.terrain_sensitivity,
        "evaluate_full_vs_mare",
        lambda *args, **kwargs: {"analysis": "test fixture"},
    )

    supplied = {
        "data_mode": "real",
        "scenario": None,
        "input_hashes_sha256": {"data/raw/example.tif": "abc123"},
        "provenance_path": "data/raw/real_data_manifest.json",
        "runtime": {"python": "test", "packages": {}},
    }
    metrics = evaluation.evaluate_pipeline(
        str(processed), str(results), config.PipelineConfig(mode="fast"),
        run_metadata=supplied,
    )

    assert metrics["Run_Metadata"] == supplied
    assert metrics["Inference_Status"] == "SUPPORTED"
    assert metrics["H1_Supported"] is True
    on_disk = json.loads((results / "metrics.json").read_text())
    assert on_disk["Run_Metadata"] == supplied

    unknown = evaluation.evaluate_pipeline(
        str(processed), str(results), config.PipelineConfig(mode="fast"),
        run_metadata=None,
    )
    terrain = unknown["Terrain_Validity_Sensitivity"]
    assert terrain["status"] == "skipped_unknown_input_provenance"
    assert "USGS" not in json.dumps(terrain)
