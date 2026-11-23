"""Adaptive difficulty recommendation."""

from typing import Dict, List, Optional


def recommend_difficulty(recent_runs: List[Dict], current_penalty: int = 2000) -> Optional[Dict]:
    """
    Recommend adaptive difficulty settings based on recent performance.
    
    Args:
        recent_runs: Last 5-10 runs for the player
        current_penalty: Current hit penalty in ms
        
    Returns:
        Dict with recommended settings or None
    """
    if len(recent_runs) < 3:
        return None
    
    # Analyze recent performance
    last_5 = recent_runs[-5:]
    hit_counts = [r.get("hits", 0) for r in last_5]
    scores = [r.get("score", 0) for r in last_5]
    
    avg_hits = sum(hit_counts) / len(hit_counts)
    avg_score = sum(scores) / len(scores)
    
    # Count clean runs (0-1 hits)
    clean_runs = sum(1 for h in hit_counts if h <= 1)
    
    # Count struggles (>5 hits)
    struggles = sum(1 for h in hit_counts if h > 5)
    
    recommendation = {
        "hit_penalty_ms": current_penalty,
        "free_hits": 0,
        "time_limit_ms": None,
        "fast_time_ms": None,
        "reason": ""
    }
    
    # Too easy - multiple clean runs
    if clean_runs >= 3:
        recommendation["hit_penalty_ms"] = min(current_penalty + 500, 5000)
        recommendation["reason"] = "Increasing difficulty: 3+ clean runs detected"
        recommendation["fast_time_ms"] = int(avg_score * 0.8)  # Set a fast time goal
    
    # Too hard - multiple struggles
    elif struggles >= 3:
        recommendation["hit_penalty_ms"] = max(current_penalty - 500, 500)
        recommendation["free_hits"] = 2
        recommendation["reason"] = "Reducing difficulty: 3+ struggles detected"
    
    # In the sweet spot
    elif 1 <= avg_hits <= 3:
        recommendation["reason"] = "Difficulty is well-balanced (1-3 hits per run)"
        return recommendation
    
    # Moderate adjustment needed
    elif avg_hits < 1:
        recommendation["hit_penalty_ms"] = min(current_penalty + 250, 5000)
        recommendation["reason"] = "Slightly increasing difficulty"
    
    elif avg_hits > 4:
        recommendation["hit_penalty_ms"] = max(current_penalty - 250, 500)
        recommendation["free_hits"] = 1
        recommendation["reason"] = "Slightly reducing difficulty"
    
    return recommendation


def validate_difficulty_config(config: Dict) -> Dict:
    """
    Validate and clamp difficulty configuration values.
    
    Args:
        config: Difficulty config dict
        
    Returns:
        Validated config dict
    """
    validated = {}
    
    # Hit penalty: 0-10000ms
    penalty = config.get("hit_penalty_ms", 2000)
    validated["hit_penalty_ms"] = max(0, min(penalty, 10000))
    
    # Free hits: 0-10
    free_hits = config.get("free_hits", 0)
    validated["free_hits"] = max(0, min(free_hits, 10))
    
    # Time limit: 1s-5min or None
    time_limit = config.get("time_limit_ms")
    if time_limit is not None:
        validated["time_limit_ms"] = max(1000, min(time_limit, 300000))
    else:
        validated["time_limit_ms"] = None
    
    # Fast time bonus: 1s-1min or None
    fast_time = config.get("fast_time_ms")
    if fast_time is not None:
        validated["fast_time_ms"] = max(1000, min(fast_time, 60000))
    else:
        validated["fast_time_ms"] = None
    
    return validated


def should_auto_apply(recommendation: Dict, player_history: List[Dict]) -> bool:
    """
    Determine if difficulty should be auto-applied or require approval.
    
    Args:
        recommendation: Recommended difficulty config
        player_history: Player's run history
        
    Returns:
        True if safe to auto-apply
    """
    # Only auto-apply small adjustments
    current_penalty = player_history[-1].get("hit_penalty_ms", 2000) if player_history else 2000
    recommended_penalty = recommendation.get("hit_penalty_ms", 2000)
    
    change = abs(recommended_penalty - current_penalty)
    
    # Auto-apply if change is small (<=500ms) and no free hits being added
    if change <= 500 and recommendation.get("free_hits", 0) == 0:
        return True
    
    return False
