"""Tests for anomaly detection."""

import pytest
from intelligence.anomalies import detect_run_anomalies


def test_too_fast_anomaly():
    """Test detection of impossibly fast run."""
    run = {
        "duration_ms": 300,
        "hits": 0,
        "longest_hit_ms": 0,
        "total_contact_ms": 0
    }
    
    anomalies = detect_run_anomalies(run)
    assert any(a["type"] == "too_fast" for a in anomalies)
    assert any(a["severity"] == "high" for a in anomalies)


def test_stuck_contact_anomaly():
    """Test detection of stuck contact."""
    run = {
        "duration_ms": 20000,
        "hits": 1,
        "longest_hit_ms": 15000,
        "total_contact_ms": 15000
    }
    
    anomalies = detect_run_anomalies(run)
    assert any(a["type"] == "stuck_contact" for a in anomalies)


def test_excessive_hits_anomaly():
    """Test detection of excessive hits."""
    run = {
        "duration_ms": 30000,
        "hits": 60,
        "longest_hit_ms": 500,
        "total_contact_ms": 10000
    }
    
    anomalies = detect_run_anomalies(run)
    assert any(a["type"] == "excessive_hits" for a in anomalies)


def test_normal_run_no_anomalies():
    """Test that normal run has no anomalies."""
    run = {
        "duration_ms": 8000,
        "hits": 3,
        "longest_hit_ms": 200,
        "total_contact_ms": 500
    }
    
    anomalies = detect_run_anomalies(run)
    assert len(anomalies) == 0
