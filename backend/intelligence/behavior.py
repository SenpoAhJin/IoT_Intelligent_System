"""Behavior pattern analysis."""

from typing import Dict, List


def analyze_behavior(features: Dict[str, float]) -> List[str]:
    """
    Identify behavior patterns from run features.
    
    Args:
        features: Extracted features from a run
        
    Returns:
        List of behavior tags
    """
    tags = []
    
    avg_hit_duration = features.get("avg_hit_duration_ms", 0)
    hits = features.get("hits", 0)
    duration_ms = features.get("duration_ms", 0)
    score = features.get("score", 0)
    
    # Dragging along the wire
    if avg_hit_duration >= 400 and hits > 0:
        tags.append("dragging")
    
    # Overshooting corners
    if avg_hit_duration <= 120 and avg_hit_duration > 0 and hits >= 3:
        tags.append("overshooting")
    
    # Rushing through
    if duration_ms < 8000 and hits >= 5:
        tags.append("rushing")
    
    # Too cautious
    if duration_ms > 20000 and hits == 0:
        tags.append("too_cautious")
    
    # Smooth run
    if hits <= 2 and duration_ms < 15000:
        tags.append("smooth")
    
    # Perfect run
    if hits == 0 and duration_ms < 20000:
        tags.append("perfect")
    
    # Struggling
    if hits >= 8 or score > 25000:
        tags.append("struggling")
    
    # Fast learner - quick completion despite some hits
    if duration_ms < 10000 and 1 <= hits <= 3:
        tags.append("fast_learner")
    
    # Consistent contact
    max_hit = features.get("max_hit_duration_ms", 0)
    min_hit = features.get("min_hit_duration_ms", 0)
    if hits >= 3 and max_hit > 0 and min_hit > 0:
        variation = (max_hit - min_hit) / max_hit if max_hit > 0 else 0
        if variation < 0.3:
            tags.append("consistent_contact")
    
    # Hit clustering - multiple hits in quick succession
    min_gap = features.get("min_gap_between_hits_ms", 0)
    if min_gap > 0 and min_gap < 1000 and hits >= 3:
        tags.append("clustered_hits")
    
    return tags


def get_behavior_advice(tags: List[str]) -> List[str]:
    """
    Generate advice based on behavior tags.
    
    Args:
        tags: List of behavior tags
        
    Returns:
        List of advice strings
    """
    advice = []
    
    advice_map = {
        "dragging": "Try lifting the ring slightly - you're dragging along the wire.",
        "overshooting": "Slow down on corners - you're overshooting and making quick contacts.",
        "rushing": "Take your time - rushing leads to more mistakes.",
        "too_cautious": "You can move faster - zero hits but very slow completion.",
        "smooth": "Great control! Smooth run with minimal contacts.",
        "perfect": "Perfect run! No hits and good time.",
        "struggling": "Take a break and focus on steady hand movement.",
        "fast_learner": "Good balance of speed and control!",
        "consistent_contact": "Your hit durations are very consistent - this suggests a systematic issue.",
        "clustered_hits": "Multiple hits in one area - identify your trouble spots.",
    }
    
    for tag in tags:
        if tag in advice_map:
            advice.append(advice_map[tag])
    
    return advice
