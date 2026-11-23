"""Feature extraction from run data."""

from typing import Dict, List
import numpy as np


def extract_features(run_data: Dict) -> Dict[str, float]:
    """
    Extract features from a completed run.
    
    Args:
        run_data: Dict with keys: duration_ms, hits, hit_records (list of dicts with duration_ms)
        
    Returns:
        Dict of extracted features
    """
    features = {}
    
    duration_ms = run_data.get("duration_ms", 0)
    hits = run_data.get("hits", 0)
    hit_records = run_data.get("hit_records", [])
    
    features["duration_ms"] = duration_ms
    features["hits"] = hits
    features["score"] = run_data.get("score", duration_ms + hits * 2000)
    
    # Hit timing features
    if hits > 0 and hit_records:
        durations = [h.get("duration_ms", 0) for h in hit_records]
        features["avg_hit_duration_ms"] = np.mean(durations)
        features["max_hit_duration_ms"] = np.max(durations)
        features["min_hit_duration_ms"] = np.min(durations)
        features["std_hit_duration_ms"] = np.std(durations) if len(durations) > 1 else 0
        
        # Hit rate
        if duration_ms > 0:
            features["hits_per_second"] = (hits / duration_ms) * 1000
            features["hits_per_minute"] = (hits / duration_ms) * 60000
        else:
            features["hits_per_second"] = 0
            features["hits_per_minute"] = 0
        
        # Time to first hit
        if hit_records:
            features["time_to_first_hit_ms"] = hit_records[0].get("start_ms", 0)
        else:
            features["time_to_first_hit_ms"] = 0
        
        # Hit clustering - check if hits are clustered in time
        if len(hit_records) > 1:
            start_times = [h.get("start_ms", 0) for h in hit_records]
            gaps = np.diff(sorted(start_times))
            features["avg_gap_between_hits_ms"] = np.mean(gaps)
            features["min_gap_between_hits_ms"] = np.min(gaps)
        else:
            features["avg_gap_between_hits_ms"] = 0
            features["min_gap_between_hits_ms"] = 0
    else:
        features["avg_hit_duration_ms"] = 0
        features["max_hit_duration_ms"] = 0
        features["min_hit_duration_ms"] = 0
        features["std_hit_duration_ms"] = 0
        features["hits_per_second"] = 0
        features["hits_per_minute"] = 0
        features["time_to_first_hit_ms"] = 0
        features["avg_gap_between_hits_ms"] = 0
        features["min_gap_between_hits_ms"] = 0
    
    # Speed metrics
    if duration_ms > 0:
        features["completion_speed"] = 1000 / duration_ms  # completions per second
    else:
        features["completion_speed"] = 0
    
    return features


def extract_player_aggregate_features(runs: List[Dict]) -> Dict[str, float]:
    """
    Extract aggregate features across multiple runs for a player.
    
    Args:
        runs: List of run dicts with features
        
    Returns:
        Dict of aggregate features
    """
    if not runs:
        return {}
    
    agg = {}
    
    # Score statistics
    scores = [r.get("score", 0) for r in runs]
    agg["avg_score"] = np.mean(scores)
    agg["best_score"] = np.min(scores)
    agg["worst_score"] = np.max(scores)
    agg["std_score"] = np.std(scores) if len(scores) > 1 else 0
    
    # Hit statistics
    hits = [r.get("hits", 0) for r in runs]
    agg["avg_hits"] = np.mean(hits)
    agg["total_hits"] = np.sum(hits)
    
    # Duration statistics
    durations = [r.get("duration_ms", 0) for r in runs]
    agg["avg_duration_ms"] = np.mean(durations)
    agg["best_time_ms"] = np.min(durations)
    
    # Consistency
    agg["consistency_score"] = 1.0 / (1.0 + agg["std_score"] / 1000.0) if agg["std_score"] > 0 else 1.0
    
    # Completion rate
    completed = [r for r in runs if r.get("status") == "finished"]
    agg["completion_rate"] = len(completed) / len(runs) if runs else 0
    
    return agg
