"""Tests for skill classification."""

import pytest
from intelligence.classifier import classify_skill_rules


def test_expert_classification():
    """Test expert classification."""
    features = {
        "score": 6000,
        "hits": 1,
        "duration_ms": 4000,
        "avg_hit_duration_ms": 100,
        "hits_per_second": 0.25
    }
    
    skill = classify_skill_rules(features)
    assert skill == "expert"


def test_intermediate_classification():
    """Test intermediate classification."""
    features = {
        "score": 12000,
        "hits": 4,
        "duration_ms": 8000,
        "avg_hit_duration_ms": 200,
        "hits_per_second": 0.5
    }
    
    skill = classify_skill_rules(features)
    assert skill == "intermediate"


def test_beginner_classification():
    """Test beginner classification."""
    features = {
        "score": 25000,
        "hits": 10,
        "duration_ms": 15000,
        "avg_hit_duration_ms": 400,
        "hits_per_second": 0.67
    }
    
    skill = classify_skill_rules(features)
    assert skill == "beginner"
