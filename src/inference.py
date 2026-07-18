"""Fail-closed inference logic for the surface-TiO2 spatial proxy.

The original runtime used an asymmetric rule: spatial adequacy guarded a positive
but a criteria failure was always labelled ``NOT_SUPPORTED``.  That conflated two
different questions.  Leakage can inflate prediction scores, but low effective
sample size and a failed positive control can still make a false negative likely.

The revised rule therefore separates *direction* from *detectability*:

* a would-be positive must survive the largest spatial partition and have enough
  independent regions;
* a negative is ``NOT_SUPPORTED`` only after the real spatial design has shown
  adequate injected-signal power and recovered its literature benchmark;
* otherwise the honest status is ``INCONCLUSIVE_LOW_POWER``.

No heavy dependencies are imported so report generation can defensively re-derive
the status from a metrics file.
"""

from __future__ import annotations

from typing import Dict, Tuple

from . import config


INCONCLUSIVE_LOW_POWER = "INCONCLUSIVE_LOW_POWER"
INCONCLUSIVE_SPATIAL = "INCONCLUSIVE_SPATIAL_AUTOCORRELATION"
MIN_EFFECTIVE_REGIONS = config.MIN_EFFECTIVE_REGIONS
MIN_DETECTION_POWER = config.MIN_DETECTION_POWER


def spatial_adequate(spatial_diagnostics: Dict) -> bool:
    """Whether apparent support survives the largest reported spatial partition.

    This is a partition-sensitivity diagnostic, not proof that leakage changes
    monotonically with block size.  Missing or malformed information fails closed.
    """
    sweep = (spatial_diagnostics or {}).get("block_size_robustness", {})
    cells: Dict[int, Dict] = {}
    for key, value in sweep.items():
        if isinstance(value, dict):
            try:
                cells[int(str(key).lower().replace("deg", ""))] = value
            except ValueError:
                continue
    if not cells:
        return False
    largest = cells[max(cells)]
    return bool(
        largest.get("skipped") is not True
        and largest.get("beats_h2_and_h1_helps") is True
    )


def independent_regions_adequate(
    spatial_diagnostics: Dict, min_effective_regions: float = MIN_EFFECTIVE_REGIONS,
) -> bool:
    """Require both a minimally useful n_eff and blocks at least as large as range."""
    diagnostics = spatial_diagnostics or {}
    try:
        n_eff = float(diagnostics.get("approx_effective_sample_size", 0.0))
    except (TypeError, ValueError):
        return False
    return bool(
        n_eff >= min_effective_regions
        and diagnostics.get("block_exceeds_range") is True
    )


def detection_power_adequate(
    power_diagnostics: Dict | None,
    min_power: float = MIN_DETECTION_POWER,
) -> bool:
    """Require calibrated power *and* recovery of the observed-data benchmark.

    ``adequate_power`` is the canonical machine-readable flag.  A numeric
    ``power_at_target_effect`` is accepted as a defensive fallback.  In either
    case, the benchmark flag must be explicitly true; missing diagnostics never
    license a strong negative claim.
    """
    diagnostics = power_diagnostics or {}
    if "adequate_power" in diagnostics:
        injection_ok = diagnostics.get("adequate_power") is True
    else:
        try:
            injection_ok = float(diagnostics.get("power_at_target_effect", -1.0)) >= min_power
        except (TypeError, ValueError):
            injection_ok = False
    return bool(injection_ok and diagnostics.get("positive_control_recovered") is True)


def negative_evidence_adequate(
    spatial_diagnostics: Dict,
    power_diagnostics: Dict | None,
) -> bool:
    return independent_regions_adequate(spatial_diagnostics) and detection_power_adequate(
        power_diagnostics
    )


def gate_inference(
    criteria_supported: bool,
    spatial_diagnostics: Dict,
    power_diagnostics: Dict | None = None,
) -> Tuple[bool, str]:
    """Return ``(surface_proxy_supported, inference_status)``.

    ``NOT_SUPPORTED`` is deliberately unreachable without affirmative power and
    positive-control evidence.  This prevents absence of sensitivity from being
    reported as evidence of absence.
    """
    if criteria_supported:
        if spatial_adequate(spatial_diagnostics) and independent_regions_adequate(
            spatial_diagnostics
        ):
            return True, "SUPPORTED"
        return False, INCONCLUSIVE_SPATIAL
    if negative_evidence_adequate(spatial_diagnostics, power_diagnostics):
        return False, "NOT_SUPPORTED"
    return False, INCONCLUSIVE_LOW_POWER


def criteria_supported_from_metrics(metrics: Dict) -> bool:
    criteria = metrics.get("Criteria", {})
    return bool(
        criteria.get("criterion_i_beats_null_and_baselines")
        and criteria.get("criterion_ii_h1_tio2_outranks_antipode")
        and criteria.get("criterion_iii_h1_ablation_significant")
    )


def status_from_metrics(metrics: Dict) -> str:
    """Re-derive status rather than trusting a hand-edited ``Inference_Status``."""
    _, status = gate_inference(
        criteria_supported_from_metrics(metrics),
        metrics.get("Spatial_Diagnostics", {}),
        metrics.get("Detection_Power", {}),
    )
    return status


def is_underpowered(
    spatial_diagnostics: Dict,
    prevalence: float,
    power_diagnostics: Dict | None = None,
    min_effective_regions: float = MIN_EFFECTIVE_REGIONS,
    min_prevalence: float = config.MIN_EVENT_PREVALENCE,
) -> bool:
    """Flag low event prevalence, spatial information, or demonstrated sensitivity."""
    return bool(
        prevalence < min_prevalence
        or not independent_regions_adequate(spatial_diagnostics, min_effective_regions)
        or not detection_power_adequate(power_diagnostics)
    )
