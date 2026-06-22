"""
OKR Calculation Utilities
Pure functions for all OKR progress and scoring algorithms
These are unit-testable and framework-agnostic
"""

from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
from enum import Enum


# ============================================================================
# ENUMS
# ============================================================================

class TrendStatus(str, Enum):
    AHEAD = "ahead"
    ON_TRACK = "on_track"
    BEHIND = "behind"
    CRITICAL_DELAY = "critical_delay"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    CRITICAL = "critical"
    BLOCKED = "blocked"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ============================================================================
# KEY RESULT PROGRESS CALCULATION
# ============================================================================

def calculate_kr_progress(
    current_value: float,
    target_value: float,
    is_lower_better: bool,
    start_value: float = 0.0
) -> float:
    """
    Calculate Key Result progress as percentage.
    
    For HIGHER-IS-BETTER metrics:
        progress = min(100, (current_value / target_value) * 100)
    
    For LOWER-IS-BETTER metrics:
        progress = min(100, (target_value / current_value) * 100)
    
    Args:
        current_value: Current metric value
        target_value: Target metric value
        is_lower_better: If True, lower values are better (downtime, defects, etc.)
        start_value: Starting value for context
    
    Returns:
        Progress percentage (0-100)
    
    Examples:
        # Higher is better (e.g., production output)
        >>> calculate_kr_progress(450, 500, False)
        90.0
        
        # Lower is better (e.g., downtime in hours)
        >>> calculate_kr_progress(2, 5, True)
        100.0  # Better than target
        
        # Over target
        >>> calculate_kr_progress(5.5, 5, True)
        90.91  # Still good, capped at 100
    """
    if target_value == 0:
        return 0.0
    
    if current_value == 0 and is_lower_better:
        return 100.0  # Best case for lower-is-better
    
    if is_lower_better:
        # For lower-is-better: fewer is better
        if current_value == 0:
            return 100.0
        progress = (target_value / current_value) * 100
    else:
        # For higher-is-better: more is better
        progress = (current_value / target_value) * 100
    
    # Cap at 100% (can exceed if target is beaten)
    return min(100.0, progress)


def calculate_expected_progress(
    start_date: datetime,
    end_date: datetime,
    current_date: Optional[datetime] = None
) -> float:
    """
    Calculate expected progress based on elapsed time.
    
    expected_progress = (elapsed_days / total_days) * 100
    
    Args:
        start_date: OKR start date
        end_date: OKR end date
        current_date: Current date (defaults to now)
    
    Returns:
        Expected progress percentage (0-100)
    """
    if current_date is None:
        current_date = datetime.utcnow()
    
    total_days = (end_date - start_date).days
    if total_days <= 0:
        return 0.0
    
    elapsed_days = (current_date - start_date).days
    if elapsed_days < 0:
        return 0.0
    
    expected = (elapsed_days / total_days) * 100
    return min(100.0, max(0.0, expected))


# ============================================================================
# OKR SCORING
# ============================================================================

def calculate_okr_progress_from_krs(
    kr_progresses: List[Tuple[float, int]]
) -> float:
    """
    Calculate OKR progress as weighted average of Key Results.
    
    OKR_progress = Σ(KR_progress × KR_weight) / Σ(KR_weights)
    
    Weights remain absolute 1-5 values, NOT normalized percentages.
    
    Args:
        kr_progresses: List of (progress, weight) tuples
    
    Returns:
        Weighted average progress (0-100)
    
    Example:
        >>> kr_data = [(85.0, 3), (90.0, 5), (80.0, 2)]
        >>> calculate_okr_progress_from_krs(kr_data)
        86.5
    """
    if not kr_progresses:
        return 0.0
    
    total_weighted_progress = sum(progress * weight for progress, weight in kr_progresses)
    total_weights = sum(weight for _, weight in kr_progresses)
    
    if total_weights == 0:
        return 0.0
    
    return total_weighted_progress / total_weights


# ============================================================================
# TRAJECTORY ENGINE
# ============================================================================

def calculate_trajectory_score(
    current_progress: float,
    expected_progress: float
) -> float:
    """
    Calculate trajectory as ratio of actual to expected progress.
    
    trajectory_score = (current_progress / expected_progress) × 100
    
    When trajectory > 100, OKR is ahead of schedule.
    When trajectory < 100, OKR is behind schedule.
    
    Args:
        current_progress: Current progress percentage
        expected_progress: Expected progress percentage
    
    Returns:
        Trajectory score where 100 = on track
    """
    if expected_progress == 0:
        return 100.0 if current_progress == 0 else 0.0
    
    return (current_progress / expected_progress) * 100


def determine_trend_status(
    trajectory_score: float,
    current_progress: float,
    target_deadline_days: int
) -> TrendStatus:
    """
    Determine trend status based on trajectory and urgency.
    
    Args:
        trajectory_score: Score from calculate_trajectory_score()
        current_progress: Current progress percentage
        target_deadline_days: Days until deadline (can be negative if past due)
    
    Returns:
        TrendStatus enum value
    """
    # Past deadline logic
    if target_deadline_days < 0 and current_progress < 100:
        return TrendStatus.CRITICAL_DELAY
    
    # Trajectory-based assessment
    if trajectory_score >= 110:  # 10% ahead
        return TrendStatus.AHEAD
    elif trajectory_score >= 90:  # Within 10%
        return TrendStatus.ON_TRACK
    elif trajectory_score >= 70:  # 30% behind
        return TrendStatus.BEHIND
    else:
        return TrendStatus.CRITICAL_DELAY


# ============================================================================
# CONFIDENCE ENGINE
# ============================================================================

def calculate_confidence_score(
    update_frequency_days: Optional[int],
    historical_consistency: float,
    kr_count: int,
    completion_velocity: float
) -> float:
    """
    Calculate confidence score based on multiple factors.
    
    Factors considered:
    - Update frequency (fresh data increases confidence)
    - Historical consistency (stable trends increase confidence)
    - KR count (more KRs = better tracking)
    - Completion velocity (sustainable pace)
    
    Args:
        update_frequency_days: Days since last update (lower = better)
        historical_consistency: 0-1 score of consistency
        kr_count: Number of KRs tracking this OKR
        completion_velocity: Progress per day
    
    Returns:
        Confidence score 0-100
    """
    base_score = 50.0
    
    # Update freshness (max +35 points)
    if update_frequency_days is None:
        freshness = 0
    elif update_frequency_days <= 3:
        freshness = 35
    elif update_frequency_days <= 7:
        freshness = 25
    elif update_frequency_days <= 14:
        freshness = 15
    elif update_frequency_days <= 21:
        freshness = 5
    else:
        freshness = 0
    
    # Historical consistency (max +20 points)
    consistency_points = historical_consistency * 20
    
    # KR diversity (max +15 points)
    kr_points = min(15, kr_count * 3)
    
    confidence = base_score + freshness + consistency_points + kr_points
    return min(100.0, max(0.0, confidence))


def calculate_update_freshness_days(last_update: Optional[datetime]) -> Optional[int]:
    """Calculate days since last update"""
    if last_update is None:
        return None
    return (datetime.utcnow() - last_update).days


def calculate_historical_consistency(
    progress_history: List[float]
) -> float:
    """
    Calculate consistency of progress updates over time.
    
    More consistent (less volatile) trends = higher consistency score.
    
    Args:
        progress_history: List of historical progress values
    
    Returns:
        Consistency score 0-1
    """
    if len(progress_history) < 2:
        return 0.5  # Neutral for insufficient data
    
    # Calculate variance of deltas (changes between consecutive values)
    deltas = [progress_history[i] - progress_history[i-1] 
              for i in range(1, len(progress_history))]
    
    if not deltas:
        return 1.0
    
    # Normalize variance to 0-1 scale
    avg_delta = sum(abs(d) for d in deltas) / len(deltas)
    
    # High consistency when deltas are small
    consistency = 1.0 / (1.0 + (avg_delta / 10.0))
    return min(1.0, max(0.0, consistency))


# ============================================================================
# HEALTH ENGINE
# ============================================================================

def calculate_health_status(
    progress: float,
    days_since_update: Optional[int],
    trajectory_score: float,
    confidence_score: float,
    days_until_deadline: int
) -> HealthStatus:
    """
    Determine OKR health status based on multiple factors.
    
    HEALTHY (green):
        - Progress >= 60% OR
        - On track with fresh updates (< 7 days) AND trajectory > 90%
    
    NEEDS_ATTENTION (yellow):
        - Progress < 60% AND trajectory > 70% OR
        - Stale data (14+ days) despite progress
    
    CRITICAL (red):
        - Progress < 40% AND no recent update (> 21 days) OR
        - Trajectory < 50% for 7+ days without update
    
    BLOCKED (dark red):
        - No progress for 30+ days OR
        - Confidence < 20%
    
    Args:
        progress: Current OKR progress 0-100
        days_since_update: Days since last progress update
        trajectory_score: Trajectory score (100 = on track)
        confidence_score: Confidence score 0-100
        days_until_deadline: Days remaining (negative = overdue)
    
    Returns:
        HealthStatus enum
    """
    # Blocked conditions
    if confidence_score < 20:
        return HealthStatus.BLOCKED
    
    if days_since_update and days_since_update >= 30:
        return HealthStatus.BLOCKED
    
    # Critical conditions
    if progress < 40 and days_since_update and days_since_update > 21:
        return HealthStatus.CRITICAL
    
    if trajectory_score < 50 and days_since_update and days_since_update >= 7:
        return HealthStatus.CRITICAL
    
    if days_until_deadline < 7 and progress < 80:
        return HealthStatus.CRITICAL
    
    # Needs attention conditions
    if days_since_update and days_since_update >= 14:
        return HealthStatus.NEEDS_ATTENTION
    
    if progress < 60 and trajectory_score < 80:
        return HealthStatus.NEEDS_ATTENTION
    
    if trajectory_score < 70:
        return HealthStatus.NEEDS_ATTENTION
    
    # Healthy
    if progress >= 60 and trajectory_score >= 90:
        return HealthStatus.HEALTHY
    
    if progress >= 75:
        return HealthStatus.HEALTHY
    
    return HealthStatus.NEEDS_ATTENTION


# ============================================================================
# RISK ENGINE
# ============================================================================

def calculate_risk_level(
    health_status: HealthStatus,
    confidence_score: float,
    trajectory_score: float,
    progress: float,
    days_until_deadline: int
) -> RiskLevel:
    """
    Assess OKR risk level.
    
    Args:
        health_status: Current health status
        confidence_score: Confidence in tracking (0-100)
        trajectory_score: Trajectory score (100 = on track)
        progress: Current progress (0-100)
        days_until_deadline: Days remaining
    
    Returns:
        RiskLevel enum
    """
    # Blocked = highest risk
    if health_status == HealthStatus.BLOCKED:
        return RiskLevel.CRITICAL
    
    # Critical health + low confidence
    if health_status == HealthStatus.CRITICAL:
        if confidence_score < 40:
            return RiskLevel.CRITICAL
        return RiskLevel.HIGH
    
    # Needs attention assessment
    if health_status == HealthStatus.NEEDS_ATTENTION:
        if trajectory_score < 50 or confidence_score < 50:
            return RiskLevel.HIGH
        return RiskLevel.MEDIUM
    
    # Healthy but check trajectory
    if trajectory_score < 80:
        return RiskLevel.MEDIUM
    
    if days_until_deadline < 14 and progress < 75:
        return RiskLevel.MEDIUM
    
    return RiskLevel.LOW


# ============================================================================
# ALIGNMENT CONTRIBUTION
# ============================================================================

def calculate_alignment_contribution(
    aligned_child_progresses: List[Tuple[float, int]],
    alignment_type_weights: Dict[str, float] = None
) -> float:
    """
    Calculate parent OKR contribution from aligned children.
    
    Uses weighted average of child OKRs' progress values.
    Different alignment types can have different weights.
    
    Args:
        aligned_child_progresses: List of (child_progress, contribution_weight)
        alignment_type_weights: Optional type-specific weights
    
    Returns:
        Alignment contribution score 0-100
    """
    if not aligned_child_progresses:
        return 0.0
    
    total_weighted = sum(progress * weight 
                        for progress, weight in aligned_child_progresses)
    total_weights = sum(weight for _, weight in aligned_child_progresses)
    
    if total_weights == 0:
        return 0.0
    
    return total_weighted / total_weights


def calculate_parent_okr_score(
    own_kr_score: float,
    own_weight_factor: float,
    alignment_contribution: float,
    alignment_weight_factor: float
) -> float:
    """
    Calculate parent OKR final score combining own KRs and alignment.
    
    final_score = (own_kr_score × own_weight_factor) 
                + (alignment_contribution × alignment_weight_factor)
    
    Where own_weight_factor + alignment_weight_factor = 1.0
    
    Args:
        own_kr_score: OKR's own Key Result weighted score
        own_weight_factor: Weight for own KRs (0-1)
        alignment_contribution: Contribution from aligned children
        alignment_weight_factor: Weight for alignment (0-1)
    
    Returns:
        Final OKR score (0-100)
    
    Example (Organization level: 80% own, 20% alignment):
        >>> calculate_parent_okr_score(85, 0.8, 72, 0.2)
        81.4
    """
    final = (own_kr_score * own_weight_factor) + \
            (alignment_contribution * alignment_weight_factor)
    return min(100.0, max(0.0, final))


# ============================================================================
# LEVEL-SPECIFIC WEIGHT FACTORS
# ============================================================================

LEVEL_WEIGHT_FACTORS = {
    "organization": {"own": 0.80, "alignment": 0.20},
    "region": {"own": 0.75, "alignment": 0.25},
    "plant": {"own": 0.70, "alignment": 0.30},
    "department": {"own": 0.80, "alignment": 0.20},
    "team": {"own": 0.85, "alignment": 0.15},
    "employee": {"own": 1.00, "alignment": 0.00},
}


def get_level_weight_factors(level_type: str) -> Tuple[float, float]:
    """
    Get own_weight and alignment_weight for a hierarchy level.
    
    Returns:
        (own_weight_factor, alignment_weight_factor)
    """
    if level_type not in LEVEL_WEIGHT_FACTORS:
        return (1.0, 0.0)  # Default: 100% own
    
    factors = LEVEL_WEIGHT_FACTORS[level_type]
    return (factors["own"], factors["alignment"])


# ============================================================================
# CIRCULAR DEPENDENCY DETECTION
# ============================================================================

def detect_circular_alignment(
    parent_id: str,
    child_id: str,
    existing_alignments: Dict[str, List[str]]
) -> bool:
    """
    Detect if creating an alignment would form a circular dependency.
    
    Uses DFS to check if child has any path back to parent.
    
    Args:
        parent_id: Parent OKR ID
        child_id: Child OKR ID
        existing_alignments: Dict mapping OKR id -> list of its children
    
    Returns:
        True if circular dependency would be created
    """
    visited = set()
    
    def has_path_to_target(current_id: str, target_id: str) -> bool:
        if current_id == target_id:
            return True
        if current_id in visited:
            return False
        
        visited.add(current_id)
        
        for child in existing_alignments.get(current_id, []):
            if has_path_to_target(child, target_id):
                return True
        
        return False
    
    # Check if child has any path to parent (which would create cycle)
    return has_path_to_target(child_id, parent_id)
