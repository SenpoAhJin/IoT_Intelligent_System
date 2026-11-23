"""Tests for feature extraction."""

import pytest
from intelligence.features import extract_features, extract_player_aggregate_features


def test_extract_features_basic():
    """Test basic feature extraction."""
    run_data = {
        "duration_ms": 10000,
        "hits": 3,
        "score": 16000,
        "hit_records": [
            {"duration_ms": 200},
            {"duration_ms": 150},
            {"duration_ms": 180}
        ]
    }
    
    features = extract_features(run_data)
    
    assert features["duration_ms"] == 10000
    assert features["hits"] == 3
    assert features["score"] == 16000
    assert features["avg_hit_duration_ms"] == pytest.approx((200 + 150 + 180) / 3)
    assert features["max_hit_duration_ms"] == 200
    assert features["min_hit_duration_ms"] == 150


def test_extract_features_no_hits():
    """Test feature extraction with no hits."""
    run_data = {
        "duration_ms": 8000,
        "hits": 0,
        "score": 8000,
        "hit_records": []
    }
    
    features = extract_features(run_data)
    
    assert features["hits"] == 0
    assert features["avg_hit_duration_ms"] == 0
    assert features["hits_per_second"] == 0


def test_aggregate_features():
    """Test aggregate feature extraction."""
    runs = [
        {"score": 10000, "hits": 2, "duration_ms": 6000, "status": "finished"},
        {"score": 12000, "hits": 3, "duration_ms": 7000, "status": "finished"},
        {"score": 9000, "hits": 1, "duration_ms": 5000, "status": "finished"},
    ]
    
    agg = extract_player_aggregate_features(runs)
    
    assert agg["avg_score"] == pytest.approx((10000 + 12000 + 9000) / 3)
    assert agg["best_score"] == 9000
    assert agg["avg_hits"] == pytest.approx(2.0)
    assert agg["completion_rate"] == 1.0
