"""
Central configuration for the lunar surface-TiO2 spatial-proxy analysis.

Every tunable constant, path, random seed, feature list, threshold, and
cross-validation parameter lives here so that a single file fully determines a
run.  Centralisation makes a run reproducible, but it does not make the choices
independent, inferentially adequate, or externally pre-registered.  The explicit
``PARAMETER_PROVENANCE`` table below records that distinction.

Nothing in this module imports heavy scientific libraries, so it is safe to
import from anywhere (including tests) without side effects.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Reproducibility
# --------------------------------------------------------------------------- #
# A single master seed. All stochastic components derive their seeds from this
# so that the whole pipeline is deterministic given RANDOM_SEED.
RANDOM_SEED: int = 42

# --------------------------------------------------------------------------- #
# Physical constants (the Moon, not the Earth)
# --------------------------------------------------------------------------- #
# The original code reprojected lunar data with EPSG:6933 (an *Earth* equal-area
# CRS). That silently rescales every distance by the ratio of Earth to lunar
# radius. We define proper lunar CRSs using the IAU mean radius.
LUNAR_RADIUS_M: float = 1_737_400.0
LUNAR_RADIUS_KM: float = LUNAR_RADIUS_M / 1000.0

# Lunar geographic (plate carree, degrees) CRS.
LUNAR_GEO_CRS: str = f"+proj=longlat +R={LUNAR_RADIUS_M:.1f} +no_defs"
# Lunar cylindrical equal-area CRS (equal-area is required so polar pixels are
# not over-weighted and area-based statistics are unbiased).
LUNAR_CEA_CRS: str = (
    f"+proj=cea +lat_ts=0 +lon_0=0 +R={LUNAR_RADIUS_M:.1f} +units=m +no_defs"
)

# Sentinel used for out-of-projection (nodata) pixels after reprojection.
NODATA: float = -9_999.0

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR: str = os.path.join(PROJECT_ROOT, "data", "raw")
PROCESSED_DIR: str = os.path.join(PROJECT_ROOT, "data", "processed")
RESULTS_DIR: str = os.path.join(PROJECT_ROOT, "results")
FIGURES_DIR: str = os.path.join(RESULTS_DIR, "figures")
REAL_DATA_MANIFEST: str = "real_data_manifest.json"
TERRAIN_VALIDITY_FILE: str = "tio2_mare_validity.tif"

# Synthetic validation runs are deliberately isolated from the canonical real
# inputs and publishable results.  Keeping the scenario in the path also
# prevents one synthetic ground-truth regime from silently reusing another's
# processed table or metrics.
DATA_MODES: Tuple[str, ...] = ("real", "synthetic")
SYNTHETIC_SCENARIOS: Tuple[str, ...] = ("h1_lean", "mixed", "h2_lean", "null")
SYNTHETIC_DATA_DIR: str = os.path.join(PROJECT_ROOT, "data", "synthetic")
SYNTHETIC_RESULTS_DIR: str = os.path.join(RESULTS_DIR, "synthetic")

RAW_FILES: Dict[str, str] = {
    "magnetic": "magnetic_anomaly.tif",
    "tio2": "tio2_abundance.tif",
    "gravity": "bouguer_gravity.tif",
    "age": "geologic_age.tif",
    "thickness": "crustal_thickness.tif",
}
# Sato et al. (2017) designed and calibrated the WAC UV/Vis TiO2 product for
# lunar mare deposits.  The USGS geologic units below are the explicit terrain
# mask used by the mare-only sensitivity analysis; highlands are not silently
# treated as valid zero/low-Ti measurements.
MARE_UNIT_SYMBOLS: Tuple[str, ...] = ("Em", "Im1", "Im2", "Imd")
ANTIPODES_CSV: str = "antipodes.csv"
BASINS_CSV: str = "basins.csv"


@dataclass(frozen=True)
class PipelinePaths:
    """Resolved input, intermediate, and output directories for one run."""

    raw_dir: str
    processed_dir: str
    results_dir: str
    figures_dir: str


def resolve_pipeline_paths(data_mode: str, scenario: str | None = None) -> PipelinePaths:
    """Return paths that cannot mix real and synthetic pipeline artifacts.

    Real analysis retains the project's canonical ``data/raw``,
    ``data/processed``, and ``results`` locations.  Synthetic validation is
    namespaced by its declared ground-truth scenario.
    """
    if data_mode not in DATA_MODES:
        raise ValueError(f"Unknown data_mode {data_mode!r}; choose from {DATA_MODES}")
    if data_mode == "real":
        if scenario is not None:
            raise ValueError("A synthetic scenario cannot be used in real data mode")
        return PipelinePaths(RAW_DIR, PROCESSED_DIR, RESULTS_DIR, FIGURES_DIR)

    if scenario not in SYNTHETIC_SCENARIOS:
        raise ValueError(
            f"Synthetic data mode requires a scenario from {SYNTHETIC_SCENARIOS}; "
            f"got {scenario!r}"
        )
    scenario_data_dir = os.path.join(SYNTHETIC_DATA_DIR, scenario)
    scenario_results_dir = os.path.join(SYNTHETIC_RESULTS_DIR, scenario)
    return PipelinePaths(
        raw_dir=os.path.join(scenario_data_dir, "raw"),
        processed_dir=os.path.join(scenario_data_dir, "processed"),
        results_dir=scenario_results_dir,
        figures_dir=os.path.join(scenario_results_dir, "figures"),
    )

# --------------------------------------------------------------------------- #
# Grid / synthetic-data parameters
# --------------------------------------------------------------------------- #
GRID_RES_DEG: float = 1.0  # degrees/pixel of the source grids

# Age-unit encoding used in geologic_age.tif (spatially contiguous provinces).
AGE_OTHER: int = 0
AGE_NECTARIAN: int = 1
AGE_IMBRIAN: int = 2

# Buffer radii (km) for the lateral-migration neighborhood features.
BUFFER_RADII_KM: Tuple[float, ...] = (25.0, 50.0, 100.0)

# Characteristic length (km) of the antipodal signal in the synthetic generator.
# Kept fairly tight so the antipodal effect is a LOCALISED patch near each antipode
# (as real antipodal magnetisation is), not a smooth global gradient -- the latter
# would give the synthetic target an unrealistically long autocorrelation range.
ANTIPODE_LENGTH_SCALE_KM: float = 300.0

# Band-pass (difference-of-Gaussians) cutoffs used as a spatial proxy for the
# spherical-harmonic band-pass that isolates mid-wavelength gravity structure.
# Low cutoff removes basin-scale mascons; high cutoff removes pixel noise.
GRAVITY_BANDPASS_LOW_KM: float = 600.0   # remove structure larger than this
GRAVITY_BANDPASS_HIGH_KM: float = 40.0   # remove structure smaller than this

# --------------------------------------------------------------------------- #
# Target definition
# --------------------------------------------------------------------------- #
# Surface-field thresholds (nT) at which a pixel is called a "magnetic anomaly".
# Reporting several removes the "results depend on one arbitrary cutoff" critique.
BINARY_THRESHOLDS_NT: Tuple[float, ...] = (5.0, 10.0)
PRIMARY_THRESHOLD_NT: float = 5.0
# Target positive-class prevalence the synthetic generator calibrates toward
# (~10% anomalous, matching the "~90% non-anomalous" premise of the proposal).
TARGET_PREVALENCE: float = 0.10

# --------------------------------------------------------------------------- #
# Feature groups (single source of truth for every model / ablation)
# --------------------------------------------------------------------------- #
# Spatial proxy under study.  Nichols et al. (2026) analyse dated basalt samples
# and a time-dependent core-mantle mechanism; they do not propose that today's
# regolith TiO2 map must co-locate with crustal anomalies.  These variables encode
# only that narrower, postulated surface-composition proxy.  They cannot adjudicate
# the temporal intermittent-dynamo mechanism.  Gravity is excluded because it is
# not part of even this operational proxy.  See Fallacy-Audit.md (F1--F4).
TIO2_BUFFER_FEATURES: List[str] = [f"tio2_{int(r)}km" for r in BUFFER_RADII_KM]
H1_FEATURES: List[str] = ["tio2"] + TIO2_BUFFER_FEATURES

# EXPLORATORY block: gravity and the Ti x gravity interaction are NOT part of the
# Nichols hypothesis. They are retained only to test/refute the invented
# "subsurface density" add-on; the model is expected to find them unimportant.
INTERACTION_FEATURES: List[str] = [f"interaction_{int(r)}km" for r in BUFFER_RADII_KM]
EXPLORATORY_FEATURES: List[str] = ["gravity"] + INTERACTION_FEATURES
# Every feature that contains TiO2 information.  H1's clean ablation must remove
# this entire set: leaving TiO2 x gravity interactions behind would leak the
# signal being ablated even though those terms are classified as exploratory.
TIO2_DERIVED_FEATURES: List[str] = H1_FEATURES + INTERACTION_FEATURES

# Literature-motivated impact-antipode benchmark + geophysical controls.  It is a
# diagnostic benchmark, not an exhaustive rival and not guaranteed to be recovered
# by a one-feature global model.
H2_FEATURES: List[str] = ["dist_to_antipode_km"]
CONTROL_FEATURES: List[str] = [
    "dist_to_antipode_km",   # H2 primary
    "dist_to_basin_rim_km",  # basin-proximity confounder
    "crustal_thickness",     # general geophysical control
    "abs_latitude",          # latitude control
    "nearside",              # nearside/Procellarum (high-Ti + anomaly) confounder (F8)
]

ALL_FEATURES: List[str] = H1_FEATURES + EXPLORATORY_FEATURES + CONTROL_FEATURES

# Terms that must NEVER appear in the H1 signal, because they are absent from the
# Nichols mechanism (crustal gravity senses the wrong depth; antipode is the rival).
FORBIDDEN_IN_H1: List[str] = ["gravity", "interaction", "dist_to_antipode"]


def validate_feature_groups() -> None:
    """Structural guard against reintroducing the F1 non-sequitur (see Fallacy-Audit.md).

    Runs at import, so any future edit that slips gravity / the Ti x gravity
    interaction / the antipode feature back into the H1 signal fails loudly instead
    of silently resurrecting the fallacy.
    """
    for feat in H1_FEATURES:
        assert not any(bad in feat for bad in FORBIDDEN_IN_H1), (
            f"H1 feature {feat!r} looks like gravity/interaction/antipode; H1 must be "
            f"PURELY compositional TiO2 (Fallacy-Audit.md F1)."
        )
    assert set(H1_FEATURES).isdisjoint(EXPLORATORY_FEATURES), "H1 and exploratory overlap"
    assert set(H1_FEATURES).isdisjoint(H2_FEATURES), "H1 and H2 overlap"
    assert set(TIO2_DERIVED_FEATURES) == set(H1_FEATURES) | set(INTERACTION_FEATURES)
    # Every modelled feature must belong to exactly one declared group.
    declared = set(H1_FEATURES) | set(EXPLORATORY_FEATURES) | set(CONTROL_FEATURES)
    assert set(ALL_FEATURES) == declared, "ALL_FEATURES not partitioned by the groups"


validate_feature_groups()

# --------------------------------------------------------------------------- #
# Cross-validation / model parameters
# --------------------------------------------------------------------------- #
SPATIAL_BLOCK_SIZE_DEG: float = 30.0  # 30 deg x 30 deg contiguous CV blocks
N_OUTER_FOLDS: int = 5
N_INNER_FOLDS: int = 3
N_PERMUTATIONS: int = 100  # spatial-rotation null distribution size
MIN_EFFECTIVE_REGIONS: float = 8.0
MIN_DETECTION_POWER: float = 0.80
MIN_EVENT_PREVALENCE: float = 0.02

# Prospective injection/recovery grid for the H2 diagnostic control.  Strength is
# defined in src.power_analysis as a standardised latent-field coefficient, not a
# lunar-physics parameter.  No member is silently designated as the scientific
# target effect: the grid identifies a conditional detection floor only.
POWER_STRENGTHS: Tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0)
N_POWER_SIMULATIONS: int = 30
POWER_ADEQUACY_BLOCK_DEG: float = 60.0
CONTINUOUS_RIDGE_ALPHA: float = 1.0

# --------------------------------------------------------------------------- #
# Researcher-decision provenance (reproducibility is not pre-registration)
# --------------------------------------------------------------------------- #
# These choices were visible in the repository-local analysis plan, but the plan
# has no independent timestamp.  They are therefore reported as researcher choices
# and subjected to sensitivity analyses; none is presented as uniquely compelled by
# physics.  Keep this table machine-readable so metrics.json carries the disclosure.
PARAMETER_PROVENANCE: Dict[str, Dict[str, str]] = {
    "grid_resolution_1deg": {
        "role": "harmonised analysis grid (~30 km per degree at the equator)",
        "selection": "computational/harmonisation choice; not optimised against the target",
        "sensitivity": "native-resolution inference is not claimed",
    },
    "binary_thresholds_5_10nT": {
        "role": "legacy rare-event classifier thresholds",
        "selection": "researcher-chosen in the repository-local plan; not externally registered",
        "sensitivity": "both thresholds reported; continuous-field analysis is now mandatory",
    },
    "tio2_buffers_25_50_100km": {
        "role": "neighbourhood means for a postulated lateral surface proxy",
        "selection": "researcher-chosen scales; no claim that Nichols et al. specified them",
        "sensitivity": "family is ablated together; individual-scale interpretation is exploratory",
    },
    "gravity_bandpass_600_40km": {
        "role": "exploratory control feature only",
        "selection": "researcher-chosen difference-of-Gaussians cutoffs",
        "sensitivity": "excluded from the TiO2 proxy and never used to define support",
    },
    "antipode_length_300km": {
        "role": "synthetic-generator and H2 injection-control localisation",
        "selection": "researcher-chosen validation/power-simulation scale, not an inferred lunar length",
        "sensitivity": "does not enter the observed real-data antipode-distance feature",
    },
    "cv_blocks_30deg": {
        "role": "legacy primary spatial partition",
        "selection": "researcher-chosen in the repository-local plan",
        "sensitivity": "15/20/30/45/60-degree results are reported as non-monotone partition sensitivity",
    },
    "primary_age_mask_imbrian": {
        "role": "legacy primary surface-age subset",
        "selection": "researcher-chosen temporal proxy; not source-rock dating",
        "sensitivity": "Imbrian+Nectarian and unmasked cells are also reported",
    },
    "injection_power_grid": {
        "role": "conditional sensitivity curve for the impact-antipode diagnostic control",
        "selection": "standardised latent coefficients 0--4; no coefficient is asserted to be a physical target effect",
        "sensitivity": "30 Monte Carlo fields per strength, 30-degree primary folds, and a 60-degree robustness check",
    },
    "continuous_ridge_alpha": {
        "role": "regularization for the transparent continuous-field descriptive model",
        "selection": "fixed analyst choice of 1.0; not tuned against held-out outcomes",
        "sensitivity": "coefficients and blocked score increments are descriptive, not an inferential endpoint",
    },
    "minimum_effective_regions_8": {
        "role": "post-hoc fail-closed adequacy threshold for strong positive or negative labels",
        "selection": "analyst-chosen heuristic; not established by lunar physics or external registration",
        "sensitivity": "the observed estimate is approximately 1, so reasonable alternatives do not change the current status",
    },
    "minimum_detection_power_0_80": {
        "role": "post-hoc minimum power for an adequacy claim at a declared target effect",
        "selection": "conventional analyst choice; the target effect remains undeclared",
        "sensitivity": "reported separately from point-estimate and Wilson-lower-bound power",
    },
    "low_event_prevalence_0_02": {
        "role": "descriptive underpowered-warning threshold only; it does not determine inference status",
        "selection": "analyst-chosen post-hoc diagnostic threshold",
        "sensitivity": "the exact prevalence and positive count are always reported",
    },
}


@dataclass(frozen=True)
class PipelineConfig:
    """Bundles run-level knobs; instantiate once and thread it through."""

    random_seed: int = RANDOM_SEED
    grid_res_deg: float = GRID_RES_DEG
    n_outer_folds: int = N_OUTER_FOLDS
    n_inner_folds: int = N_INNER_FOLDS
    n_permutations: int = N_PERMUTATIONS
    n_power_simulations: int = N_POWER_SIMULATIONS
    spatial_block_size_deg: float = SPATIAL_BLOCK_SIZE_DEG
    primary_threshold_nt: float = PRIMARY_THRESHOLD_NT
    # Which age mask to use for the *primary* analysis; sensitivity runs vary it.
    age_mask: str = "imbrian"  # one of {"imbrian", "imbrian_nectarian", "none"}
    # "fast" trims permutations/tuning for smoke tests; "full" honours the plan.
    mode: str = "full"

    # Hyper-parameter search space for the nested spatial GridSearchCV.
    # Kept modest (12 combos) so nested CV stays tractable; reg_lambda is fixed
    # in DEFAULT_PARAMS to bound the search size.
    param_grid: Dict[str, List] = field(
        default_factory=lambda: {
            "max_depth": [3, 4, 6],
            "learning_rate": [0.05, 0.1],
            "n_estimators": [200, 400],
        }
    )

    def __post_init__(self) -> None:
        # The processed ``spatial_block`` column is the fixed 30-degree
        # repository-plan partition. Reject a contradictory label rather than
        # scoring 30-degree groups while reporting another size.
        if float(self.spatial_block_size_deg) != float(SPATIAL_BLOCK_SIZE_DEG):
            raise ValueError(
                "PipelineConfig.spatial_block_size_deg must remain 30 degrees; "
                "use the explicit block-size sensitivity analysis for alternatives"
            )

    def scaled_permutations(self) -> int:
        return 20 if self.mode == "fast" else self.n_permutations

    def scaled_power_simulations(self) -> int:
        """Small smoke curve in fast mode; full mode estimates the published curve."""
        return 2 if self.mode == "fast" else self.n_power_simulations

    def resolved_power_strengths(self) -> Tuple[float, ...]:
        """Use the complete declared grid except in explicitly non-publishable fast mode."""
        return (0.0, 2.0, 4.0) if self.mode == "fast" else POWER_STRENGTHS

    def resolved_param_grid(self) -> Dict[str, List]:
        """A tiny grid in fast mode, the full grid otherwise."""
        if self.mode == "fast":
            return {"max_depth": [3, 4], "learning_rate": [0.1], "n_estimators": [200]}
        return self.param_grid
