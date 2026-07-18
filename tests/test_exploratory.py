"""Unit tests for the post-plan exploratory diagnostic helpers.

These cover the data-independent logic (the significance gate and the spherical
K-Means fold construction). The full sweep in `src/exploratory.run` needs the
ingested real grids and is exercised by running the module, not in the unit suite.
"""

import numpy as np
import pandas as pd

from src import exploratory


def test_significance_requires_clearing_the_null_upper_tail():
    p95 = 0.229
    # Clears the null 95th, beats H2, and TiO2 helps -> a genuine win.
    assert exploratory._reaches_significance(0.30, 0.11, 0.02, p95) is True
    # Above the null *mean* (0.11) but below its 95th percentile -> NOT significant.
    assert exploratory._reaches_significance(0.15, 0.11, 0.02, p95) is False
    # Clears the null but loses to the H2 rival -> not a win for H1.
    assert exploratory._reaches_significance(0.30, 0.35, 0.02, p95) is False
    # Clears the null and beats H2 but removing TiO2 does not hurt -> not a win.
    assert exploratory._reaches_significance(0.30, 0.11, -0.01, p95) is False


def test_kmeans_groups_are_spherical_contiguous_and_complete():
    # Two tight clusters of pixels on opposite sides of the Moon.
    rng = np.random.default_rng(0)
    near = pd.DataFrame({
        "lon": rng.uniform(-10, 10, 60), "lat": rng.uniform(-10, 10, 60)})
    far = pd.DataFrame({
        "lon": rng.uniform(160, 179, 60), "lat": rng.uniform(30, 50, 60)})
    df = pd.concat([near, far], ignore_index=True)

    groups = exploratory.kmeans_groups(df, k=2)

    assert groups.shape == (len(df),)
    assert set(np.unique(groups)) == {0, 1}
    # Each geographically tight blob must fall entirely within one cluster
    # (contiguity: nearby pixels are not split across folds).
    assert len(np.unique(groups[:60])) == 1
    assert len(np.unique(groups[60:])) == 1
    assert groups[0] != groups[-1]
