"""Tests for behavior analysis."""

import pytest
from intelligence.behavior import analyze_behavior, get_behavior_advice


def test_dragging_behavior():
    """Test detection of dragging pattern."""
    features = {
        "avg_hit_duration_ms": 500,
        "hits": 5,
        "duration_ms": 15000,
        "score": 25000
    }
    
    tags = analyze_behavior(features)
    assert "dragging" in tags


def test_overshooting_behavior():
    """Test detection of overshooting pattern."""
    features = {
        "avg_hit_duration_ms": 100,
        "hits": 4,
        "duration_ms": 8000,
        "score": 16000
    }
    
    tags = analyze_behavior(features)
    assert "overshooting" in tags


def test_perfect_run():
    """Test detection of perfect run."""
    features = {
        "avg_hit_duration_ms": 0,
        "hits": 0,
        "duration_ms": 6000,
        "score": 6000
    }
    
    tags = analyze_behavior(features)
    assert "perfect" in tags


def test_behavior_advice():
    """Test advice generation."""
    tags = ["dragging", "rushing"]
    advice = get_behavior_advice(tags)
    
    assert len(advice) == 2
    assert any("lifting" in a.lower() for a in advice)
    assert any("time" in a.lower() for a in advice)
