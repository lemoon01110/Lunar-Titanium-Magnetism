import numpy as np
import pandas as pd
import pytest

from src import config
from src.transparent_analysis import continuous_field_analysis


def _frame(signal: bool = True) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n_blocks, rows_per_block = 12, 30
    n = n_blocks * rows_per_block
    tio2 = rng.normal(size=n)
    control = rng.normal(size=n)
    block = np.repeat(np.arange(n_blocks), rows_per_block)
    field = np.exp(1.2 + 0.8 * control + (1.5 * tio2 if signal else 0) + rng.normal(0, .1, n))
    df = pd.DataFrame({
        "mag_anomaly": field,
        "spatial_block": block,
        "control": control,
        "tio2": tio2,
    })
    return df


def test_continuous_analysis_detects_incremental_predictive_information():
    result = continuous_field_analysis(
        _frame(), h1_features=["tio2"], control_features=["control"], n_folds=6,
    )
    assert result["tio2_incremental_r2"]["mean"] > 0.5
    assert len(result["tio2_incremental_r2"]["per_fold"]) == 6
    assert "no_independence_claim" in next(
        key for key in result if key.startswith("descriptive_standardised")
    )


def test_continuous_analysis_does_not_invent_signal():
    result = continuous_field_analysis(
        _frame(signal=False), h1_features=["tio2"], control_features=["control"], n_folds=4,
    )
    assert abs(result["tio2_incremental_r2"]["mean"]) < 0.05


def test_continuous_analysis_fails_closed_on_invalid_inputs():
    frame = _frame().iloc[:5]
    with pytest.raises(ValueError, match="at least ten"):
        continuous_field_analysis(
            frame, h1_features=["tio2"], control_features=["control"],
        )

    bad = _frame()
    bad.loc[0, "mag_anomaly"] = -1
    with pytest.raises(ValueError, match="non-negative"):
        continuous_field_analysis(
            bad, h1_features=["tio2"], control_features=["control"],
        )


def test_continuous_analysis_accepts_inherited_group_safe_folds():
    frame = _frame()
    inherited = (frame["spatial_block"].to_numpy() % 4).astype(int)
    result = continuous_field_analysis(
        frame,
        h1_features=["tio2"],
        control_features=["control"],
        fold_ids=inherited,
    )
    assert result["fold_assignment"] == "caller-supplied inherited spatial folds"
    assert result["n_folds"] == 4
    assert result["fold_ids"] == [0, 1, 2, 3]

    unsafe = inherited.copy()
    unsafe[0] = (unsafe[0] + 1) % 4
    with pytest.raises(ValueError, match="split at least one spatial group"):
        continuous_field_analysis(
            frame,
            h1_features=["tio2"],
            control_features=["control"],
            fold_ids=unsafe,
        )
