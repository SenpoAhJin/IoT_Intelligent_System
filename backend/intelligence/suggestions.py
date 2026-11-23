"""Suggestion engine for players and designers."""

from typing import Dict, List
from intelligence.behavior import get_behavior_advice
from intelligence.trends import get_trend_message
from intelligence.anomalies import get_anomaly_summary


def generate_suggestions(
    player_id: str,
    recent_runs: List[Dict],
    behavior_tags: List[str],
    skill_level: str,
    trend: Dict,
    anomalies: List[Dict]
) -> List[Dict]:
    """
    Generate actionable suggestions for a player.
    
    Args:
        player_id: Player identifier
        recent_runs: Recent run data
        behavior_tags: Behavior pattern tags
        skill_level: Current skill level
        trend: Trend analysis result
        anomalies: Detected anomalies
        
    Returns:
        List of suggestion dicts
    """
    suggestions = []
    
    # Behavior-based suggestions
    behavior_advice = get_behavior_advice(behavior_tags)
    for advice in behavior_advice:
        suggestions.append({
            "type": "behavior",
            "message": advice,
            "priority": "normal",
            "data": {"tags": behavior_tags}
        })
    
    # Skill-based suggestions
    if skill_level == "beginner":
        suggestions.append({
            "type": "skill",
            "message": "Take your time and focus on smooth movements. Speed will come with practice.",
            "priority": "high",
            "data": {"skill": skill_level}
        })
    elif skill_level == "expert":
        suggestions.append({
            "type": "skill",
            "message": "Excellent control! Try pushing for even faster times.",
            "priority": "low",
            "data": {"skill": skill_level}
        })
    
    # Trend-based suggestions
    if trend:
        trend_msg = get_trend_message(trend)
        if trend["type"] == "improving":
            suggestions.append({
                "type": "trend",
                "message": f"Great progress! {trend_msg}",
                "priority": "normal",
                "data": trend
            })
        elif trend["type"] == "declining":
            suggestions.append({
                "type": "trend",
                "message": f"Performance slipping. {trend_msg} Consider taking a break.",
                "priority": "high",
                "data": trend
            })
    
    # Anomaly warnings
    for anomaly in anomalies:
        if anomaly["severity"] in ["high", "medium"]:
            suggestions.append({
                "type": "anomaly",
                "message": f"⚠️ {anomaly['message']}",
                "priority": "high" if anomaly["severity"] == "high" else "normal",
                "data": anomaly
            })
    
    # Recent performance insights
    if recent_runs:
        last_run = recent_runs[-1]
        if last_run.get("hits", 0) == 0:
            suggestions.append({
                "type": "achievement",
                "message": "Perfect run! Zero hits - well done!",
                "priority": "normal",
                "data": {"run_uid": last_run.get("run_uid")}
            })
        
        # Personal best
        scores = [r.get("score", 999999) for r in recent_runs]
        if last_run.get("score") == min(scores):
            suggestions.append({
                "type": "achievement",
                "message": "New personal best! 🎉",
                "priority": "high",
                "data": {"score": last_run.get("score")}
            })
    
    return suggestions


def generate_designer_suggestions(all_runs: List[Dict]) -> List[str]:
    """
    Generate suggestions for the maze designer based on aggregate data.
    
    Args:
        all_runs: All completed runs
        
    Returns:
        List of designer suggestion strings
    """
    suggestions = []
    
    if not all_runs:
        return suggestions
    
    # Analyze hit distribution
    hit_counts = [r.get("hits", 0) for r in all_runs]
    avg_hits = sum(hit_counts) / len(hit_counts)
    
    if avg_hits > 8:
        suggestions.append("Average hit count is high (>8). Consider simplifying the maze or adjusting difficulty.")
    
    if avg_hits < 1:
        suggestions.append("Average hit count is very low (<1). Maze might be too easy.")
    
    # Analyze completion times
    durations = [r.get("duration_ms", 0) for r in all_runs]
    avg_duration = sum(durations) / len(durations)
    
    if avg_duration < 5000:
        suggestions.append("Average completion time is very fast (<5s). Maze might be too short.")
    
    if avg_duration > 30000:
        suggestions.append("Average completion time is very slow (>30s). Maze might be too complex.")
    
    # Analyze specific trouble spots (if hit position data available)
    # This would require hit location tracking in hardware
    
    return suggestions
