"""Tests for adaptive difficulty."""

import pytest
from intelligence.difficulty import recommend_difficulty, validate_difficulty_config


def test_increase_difficulty_for_clean_runs():
    """Test difficulty increases after multiple clean runs."""
    runs = [
        {"hits": 0, "score": 7000, "duration_ms": 7000},
        {"hits": 1, "score": 8000, "duration_ms": 6000},
        {"hits": 0, "score": 6500, "duration_ms": 6500},
        {"hits": 1, "score": 7500, "duration_ms": 5500},
        {"hits": 0, "score": 6000, "duration_ms": 6000},
    ]
    
    rec = recommend_difficulty(runs, current_penalty=2000)
    
    assert rec is not None
    assert rec["hit_penalty_ms"] > 2000
    assert "clean" in rec["reason"].lower()


def test_decrease_difficulty_for_struggles():
    """Test difficulty decreases after multiple struggles."""
    runs = [
        {"hits": 8, "score": 25000, "duration_ms": 15000},
        {"hits": 10, "score": 28000, "duration_ms": 18000},
        {"hits": 7, "score": 22000, "duration_ms": 14000},
        {"hits": 9, "score": 26000, "duration_ms": 16000},
        {"hits": 11, "score": 30000, "duration_ms": 20000},
    ]
    
    rec = recommend_difficulty(runs, current_penalty=2000)
    
    assert rec is not None
    assert rec["hit_penalty_ms"] < 2000
    assert rec["free_hits"] > 0


def test_validate_difficulty_config():
    """Test config validation and clamping."""
    config = {
        "hit_penalty_ms": 15000,  # Too high
        "free_hits": 20,  # Too high
        "time_limit_ms": 500,  # Too low
        "fast_time_ms": 100000  # Too high
    }
    
    validated = validate_difficulty_config(config)
    
    assert validated["hit_penalty_ms"] == 10000  # Clamped
    assert validated["free_hits"] == 10  # Clamped
    assert validated["time_limit_ms"] == 1000  # Clamped
    assert validated["fast_time_ms"] == 60000  # Clamped
