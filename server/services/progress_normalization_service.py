"""
Progress Normalization Service
==============================

Intelligent progress calculation engine that supports 6 KPI behaviors:
- HIGHER_IS_BETTER: Production, Sales, Revenue, Units Manufactured
- LOWER_IS_BETTER: Production Cost, Machine Downtime, Defect Rate
- TARGET_MATCH: Inventory, Required Workforce, Machine Availability
- BOOLEAN: ISO Audit Completed, Training Completed
- RANGE: Temperature, Humidity, Pressure, Quality Metrics
- MILESTONE: ERP Migration, Machine Installation, Plant Commissioning

All calculation functions are pure (no DB dependency) for easy unit testing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Result Container ─────────────────────────────────────────────────────────

@dataclass
class NormalizationResult:
    """Result of a progress normalization calculation."""
    actual_value: float
    normalized_progress: float  # 0–100 (or higher if overachievement)
    formula_used: str           # Human-readable formula description
    metric_type: str            # KPIBehavior value
    capped: bool = False        # Whether result was capped at 100


# ── Validation Errors ────────────────────────────────────────────────────────

class NormalizationError(ValueError):
    """Raised when a normalization input is invalid."""
    pass


# ── Pure Calculation Functions ───────────────────────────────────────────────

def calculate_higher_is_better(
    actual: float,
    target: float,
    allow_overachievement: bool = False,
) -> NormalizationResult:
    """
    Higher actual values mean better performance.
    Examples: Production Volume, Sales Revenue, Units Manufactured.

    Formula: completion = (actual / target) × 100
    """
    if target <= 0:
        raise NormalizationError("Target must be positive for HIGHER_IS_BETTER")
    if actual < 0:
        raise NormalizationError("Actual value cannot be negative for HIGHER_IS_BETTER")

    raw = (actual / target) * 100.0
    capped = False

    if not allow_overachievement and raw > 100.0:
        raw = 100.0
        capped = True

    progress = round(max(0.0, raw), 2)

    return NormalizationResult(
        actual_value=actual,
        normalized_progress=progress,
        formula_used=f"HIGHER_IS_BETTER: ({actual} / {target}) × 100 = {progress}%",
        metric_type="HIGHER_IS_BETTER",
        capped=capped,
    )


def calculate_lower_is_better(
    actual: float,
    target: float,
) -> NormalizationResult:
    """
    Lower actual values mean better performance.
    Examples: Production Cost, Machine Downtime, Defect Rate.

    If actual <= target: completion = 100% (beat or met target)
    If actual > target:  completion = (target / actual) × 100
    Always capped at 100%.
    """
    if target <= 0:
        raise NormalizationError("Target must be positive for LOWER_IS_BETTER")
    if actual < 0:
        raise NormalizationError("Actual value cannot be negative for LOWER_IS_BETTER")

    if actual <= target:
        progress = 100.0
        formula = f"LOWER_IS_BETTER: actual ({actual}) ≤ target ({target}) → 100%"
    else:
        raw = (target / actual) * 100.0
        progress = round(max(0.0, raw), 2)
        formula = f"LOWER_IS_BETTER: ({target} / {actual}) × 100 = {progress}%"

    return NormalizationResult(
        actual_value=actual,
        normalized_progress=progress,
        formula_used=formula,
        metric_type="LOWER_IS_BETTER",
        capped=(actual <= target),
    )


def calculate_target_match(
    actual: float,
    target: float,
) -> NormalizationResult:
    """
    Matching the target exactly is ideal; any deviation reduces completion.
    Examples: Inventory Level, Required Workforce, Budget, Ideal Temperature.

    Formula: completion = (1 - |actual - target| / target) × 100
    Never below zero.
    """
    if target <= 0:
        raise NormalizationError("Target must be positive for TARGET_MATCH")

    deviation = abs(actual - target)
    raw = (1.0 - deviation / target) * 100.0
    progress = round(max(0.0, min(100.0, raw)), 2)

    return NormalizationResult(
        actual_value=actual,
        normalized_progress=progress,
        formula_used=f"TARGET_MATCH: (1 - |{actual} - {target}| / {target}) × 100 = {progress}%",
        metric_type="TARGET_MATCH",
        capped=False,
    )


def calculate_range(
    actual: float,
    target_min: float,
    target_max: float,
    tolerance: float = 20.0,
) -> NormalizationResult:
    """
    Value within range is 100%. Values outside range degrade based on tolerance.
    Examples: Temperature, Humidity, Pressure, Quality Metrics.

    Inside [min, max]: 100%
    Outside: score = max(0, 100 - (distance / tolerance_band) × 100)
    where tolerance_band = (max - min) × tolerance / 100

    Args:
        actual: Actual measured value
        target_min: Lower bound of acceptable range
        target_max: Upper bound of acceptable range
        tolerance: How far outside the range before score hits 0 (as % of range span)
    """
    if target_min >= target_max:
        raise NormalizationError(
            f"Range min ({target_min}) must be less than max ({target_max})"
        )
    if tolerance < 0:
        raise NormalizationError("Tolerance cannot be negative")

    range_span = target_max - target_min

    if target_min <= actual <= target_max:
        progress = 100.0
        formula = f"RANGE: {actual} is within [{target_min}, {target_max}] → 100%"
    else:
        if actual < target_min:
            distance = target_min - actual
        else:
            distance = actual - target_max

        tolerance_band = range_span * tolerance / 100.0
        if tolerance_band <= 0:
            progress = 0.0
        else:
            raw = 100.0 - (distance / tolerance_band) * 100.0
            progress = round(max(0.0, raw), 2)

        formula = (
            f"RANGE: {actual} outside [{target_min}, {target_max}], "
            f"distance={round(distance, 2)}, tolerance_band={round(tolerance_band, 2)} → {progress}%"
        )

    return NormalizationResult(
        actual_value=actual,
        normalized_progress=progress,
        formula_used=formula,
        metric_type="RANGE",
        capped=False,
    )


def calculate_boolean(
    completed: bool,
) -> NormalizationResult:
    """
    Binary completion: done or not done.
    Examples: ISO Audit Completed, Training Completed, Certification Completed.
    """
    progress = 100.0 if completed else 0.0

    return NormalizationResult(
        actual_value=1.0 if completed else 0.0,
        normalized_progress=progress,
        formula_used=f"BOOLEAN: {'Completed' if completed else 'Not Completed'} → {progress}%",
        metric_type="BOOLEAN",
        capped=False,
    )


def calculate_milestone(
    completed: int,
    total: int,
) -> NormalizationResult:
    """
    Progress = completed milestones / total milestones × 100.
    Examples: ERP Migration, Machine Installation, Plant Commissioning.
    """
    if total <= 0:
        raise NormalizationError("Total milestones must be positive")
    if completed < 0:
        raise NormalizationError("Completed milestones cannot be negative")
    if completed > total:
        raise NormalizationError(
            f"Completed milestones ({completed}) cannot exceed total ({total})"
        )

    progress = round((completed / total) * 100.0, 2)

    return NormalizationResult(
        actual_value=float(completed),
        normalized_progress=progress,
        formula_used=f"MILESTONE: {completed} / {total} × 100 = {progress}%",
        metric_type="MILESTONE",
        capped=False,
    )


# ── Master Dispatcher ────────────────────────────────────────────────────────

def calculate_progress(kr, actual_value: float) -> NormalizationResult:
    """
    Master function: determine KPI behavior from the KeyResult and dispatch
    to the appropriate calculation strategy.

    Args:
        kr: KeyResult model instance (or any object with kpi_behavior, target_value, etc.)
        actual_value: The raw business value submitted by the user

    Returns:
        NormalizationResult with the computed completion percentage
    """
    behavior = getattr(kr, "kpi_behavior", None) or "HIGHER_IS_BETTER"
    target = getattr(kr, "target_value", None) or 0.0
    allow_over = getattr(kr, "allow_overachievement", False)

    if behavior == "HIGHER_IS_BETTER":
        return calculate_higher_is_better(actual_value, target, allow_over)

    elif behavior == "LOWER_IS_BETTER":
        return calculate_lower_is_better(actual_value, target)

    elif behavior == "TARGET_MATCH":
        return calculate_target_match(actual_value, target)

    elif behavior == "BOOLEAN":
        completed = bool(actual_value) if actual_value is not None else False
        return calculate_boolean(completed)

    elif behavior == "RANGE":
        target_min = getattr(kr, "target_min", None)
        target_max = getattr(kr, "target_max", None)
        tolerance = getattr(kr, "tolerance", None) or 20.0

        if target_min is None or target_max is None:
            raise NormalizationError(
                "RANGE KPIs require target_min and target_max to be set"
            )
        return calculate_range(actual_value, target_min, target_max, tolerance)

    elif behavior == "MILESTONE":
        milestone_total = getattr(kr, "milestone_total", None)
        if milestone_total is None or milestone_total <= 0:
            raise NormalizationError(
                "MILESTONE KPIs require milestone_total to be set (> 0)"
            )
        return calculate_milestone(int(actual_value), milestone_total)

    else:
        logger.warning(
            "Unknown kpi_behavior '%s' for KR, falling back to HIGHER_IS_BETTER",
            behavior,
        )
        return calculate_higher_is_better(actual_value, target, allow_over)
"""
    Wrapper for dashboard/cascade compatibility.
    Given a KeyResult, compute normalized progress using its current_value.
"""


def normalize_kr_progress(kr) -> float:
    """
    Drop-in replacement for the old calculate_kr_progress.
    Returns 0-100 float.
    """
    try:
        current = getattr(kr, "current_value", 0.0) or 0.0
        result = calculate_progress(kr, current)
        return result.normalized_progress
    except NormalizationError:
        # Fallback for malformed KRs: simple ratio
        target = getattr(kr, "target_value", 0.0) or 0.0
        current = getattr(kr, "current_value", 0.0) or 0.0
        if target <= 0:
            return 0.0
        return round(min(100.0, max(0.0, (current / target) * 100.0)), 1)
