import pytest
from server.services.progress_normalization_service import (
    calculate_progress,
    NormalizationResult,
    NormalizationError,
)

class MockKR:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_higher_is_better():
    kr = MockKR(kpi_behavior="HIGHER_IS_BETTER", target_value=50.0, allow_overachievement=False)
    
    # Under target
    res = calculate_progress(kr, 10.0)
    assert res.normalized_progress == 20.0
    assert not res.capped
    
    # Exactly on target
    res = calculate_progress(kr, 50.0)
    assert res.normalized_progress == 100.0
    assert not res.capped
    
    # Over target (capped)
    res = calculate_progress(kr, 60.0)
    assert res.normalized_progress == 100.0
    assert res.capped


def test_higher_is_better_overachievement():
    kr = MockKR(kpi_behavior="HIGHER_IS_BETTER", target_value=50.0, allow_overachievement=True)
    res = calculate_progress(kr, 60.0)
    assert res.normalized_progress == 120.0
    assert not res.capped


def test_lower_is_better():
    kr = MockKR(kpi_behavior="LOWER_IS_BETTER", target_value=144.5)
    
    # Beat target
    res = calculate_progress(kr, 120.0)
    assert res.normalized_progress == 100.0
    assert res.capped
    
    # Met target
    res = calculate_progress(kr, 144.5)
    assert res.normalized_progress == 100.0
    assert res.capped
    
    # Missed target
    res = calculate_progress(kr, 150.0)
    assert res.normalized_progress == 96.33
    assert not res.capped


def test_target_match():
    kr = MockKR(kpi_behavior="TARGET_MATCH", target_value=100.0)
    
    # Exact match
    res = calculate_progress(kr, 100.0)
    assert res.normalized_progress == 100.0
    
    # Deviation below
    res = calculate_progress(kr, 98.0)
    assert res.normalized_progress == 98.0
    
    # Deviation above
    res = calculate_progress(kr, 102.0)
    assert res.normalized_progress == 98.0
    
    # Complete miss
    res = calculate_progress(kr, 250.0)
    assert res.normalized_progress == 0.0


def test_boolean():
    kr = MockKR(kpi_behavior="BOOLEAN")
    
    res = calculate_progress(kr, True)
    assert res.normalized_progress == 100.0
    
    res = calculate_progress(kr, False)
    assert res.normalized_progress == 0.0
    
    res = calculate_progress(kr, 1)
    assert res.normalized_progress == 100.0


def test_range():
    kr = MockKR(kpi_behavior="RANGE", target_min=20.0, target_max=25.0, tolerance=20.0)
    # Range span = 5. Tolerance band = 5 * 20% = 1.0
    
    # Inside range
    res = calculate_progress(kr, 22.0)
    assert res.normalized_progress == 100.0
    
    # Outside range but within tolerance
    # Distance = 1.0, which equals tolerance band -> score = 0
    # Wait, distance = 0.5 -> score = 100 - (0.5/1.0)*100 = 50%
    res = calculate_progress(kr, 19.5)
    assert res.normalized_progress == 50.0
    
    res = calculate_progress(kr, 25.5)
    assert res.normalized_progress == 50.0
    
    # Completely outside tolerance
    res = calculate_progress(kr, 19.0)
    assert res.normalized_progress == 0.0
    
    res = calculate_progress(kr, 30.0)
    assert res.normalized_progress == 0.0


def test_milestone():
    kr = MockKR(kpi_behavior="MILESTONE", milestone_total=10)
    
    res = calculate_progress(kr, 5)
    assert res.normalized_progress == 50.0
    
    res = calculate_progress(kr, 10)
    assert res.normalized_progress == 100.0
    
    res = calculate_progress(kr, 0)
    assert res.normalized_progress == 0.0


def test_validation_errors():
    with pytest.raises(NormalizationError):
        kr = MockKR(kpi_behavior="HIGHER_IS_BETTER", target_value=0.0)
        calculate_progress(kr, 10.0)
        
    with pytest.raises(NormalizationError):
        kr = MockKR(kpi_behavior="HIGHER_IS_BETTER", target_value=-50.0)
        calculate_progress(kr, 10.0)

    with pytest.raises(NormalizationError):
        kr = MockKR(kpi_behavior="HIGHER_IS_BETTER", target_value=50.0)
        calculate_progress(kr, -10.0)

    with pytest.raises(NormalizationError):
        kr = MockKR(kpi_behavior="RANGE", target_min=30.0, target_max=20.0)
        calculate_progress(kr, 25.0)

    with pytest.raises(NormalizationError):
        kr = MockKR(kpi_behavior="MILESTONE", milestone_total=0)
        calculate_progress(kr, 5)

    with pytest.raises(NormalizationError):
        kr = MockKR(kpi_behavior="MILESTONE", milestone_total=10)
        calculate_progress(kr, 15)  # Can't complete more than total
