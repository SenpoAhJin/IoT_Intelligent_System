"""Trend detection for player performance."""

from typing import Dict, List, Optional
import numpy as np


def detect_trend(runs: List[Dict], window: int = 10) -> Optional[Dict]:
    """
    Detect performance trend using linear regression on recent runs.
    
    Args:
        runs: List of run dicts with 'score' and 'finished_at'
        window: Number of recent runs to analyze
        
    Returns:
        Dict with trend info or None if insufficient data
    """
    if len(runs) < 3:
        return None
    
    # Sort by time and take last N runs
    sorted_runs = sorted(runs, key=lambda r: r.get("finished_at", ""))
    recent = sorted_runs[-window:]
    
    if len(recent) < 3:
        return None
    
    # Extract scores
    scores = np.array([r.get("score", 0) for r in recent])
    X = np.arange(len(scores)).reshape(-1, 1)
    
    # Simple linear regression
    X_mean = X.mean()
    y_mean = scores.mean()
    
    numerator = ((X.flatten() - X_mean) * (scores - y_mean)).sum()
    denominator = ((X.flatten() - X_mean) ** 2).sum()
    
    if denominator == 0:
        slope = 0
    else:
        slope = numerator / denominator
    
    intercept = y_mean - slope * X_mean
    
    # Predict first and last
    first_pred = intercept
    last_pred = intercept + slope * (len(scores) - 1)
    
    # Classify trend
    threshold = 500  # ms per run threshold
    
    if slope < -threshold:
        trend_type = "improving"
        confidence = min(abs(slope) / 1000, 1.0)
    elif slope > threshold:
        trend_type = "declining"
        confidence = min(abs(slope) / 1000, 1.0)
    else:
        trend_type = "stable"
        confidence = 0.5
    
    return {
        "type": trend_type,
        "slope": float(slope),
        "confidence": float(confidence),
        "runs_analyzed": len(recent),
        "avg_score": float(y_mean),
        "predicted_change": float(last_pred - first_pred)
    }


def get_trend_message(trend: Optional[Dict]) -> str:
    """
    Generate human-readable trend message.
    
    Args:
        trend: Trend dict from detect_trend
        
    Returns:
        Trend description string
    """
    if not trend:
        return "Not enough data to detect trend (need at least 3 runs)"
    
    trend_type = trend["type"]
    slope = trend["slope"]
    runs = trend["runs_analyzed"]
    
    if trend_type == "improving":
        change = abs(slope)
        return f"Improving! Score dropping by ~{change:.0f}ms per run over last {runs} runs."
    elif trend_type == "declining":
        change = abs(slope)
        return f"Performance declining. Score increasing by ~{change:.0f}ms per run over last {runs} runs."
    else:
        return f"Performance stable over last {runs} runs."


def predict_next_score(runs: List[Dict]) -> Optional[float]:
    """
    Predict the next likely score based on trend.
    
    Args:
        runs: List of run dicts
        
    Returns:
        Predicted score or None
    """
    trend = detect_trend(runs)
    if not trend:
        return None
    
    # Predict next run score
    avg = trend["avg_score"]
    slope = trend["slope"]
    runs_analyzed = trend["runs_analyzed"]
    
    next_score = avg + slope * (runs_analyzed / 2)
    
    # Clamp to reasonable range
    return max(1000, next_score)
